import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app import models


class ProviderService:
    def __init__(self, db: Session):
        self.db = db
        self._ensure_sim_state()

    def _ensure_sim_state(self) -> None:
        current = self.db.get(models.SimState, "current_day")
        if current is None:
            self.db.add(models.SimState(key="current_day", value="1"))
            self.db.commit()

    def current_day(self) -> int:
        return int(self.db.get(models.SimState, "current_day").value)

    def set_current_day(self, day: int) -> None:
        state = self.db.get(models.SimState, "current_day")
        state.value = str(day)
        self.db.commit()

    def get_state_value(self, key: str, default: str) -> str:
        state = self.db.get(models.SimState, key)
        return state.value if state is not None else default

    def set_state_value(self, key: str, value: str) -> None:
        state = self.db.get(models.SimState, key)
        if state is None:
            self.db.add(models.SimState(key=key, value=value))
        else:
            state.value = value
        self.db.commit()

    def market_signal(self) -> dict[str, Any]:
        return {
            "supply_modifier": float(self.get_state_value("supply_modifier", "1.0")),
            "lead_time_modifier": float(self.get_state_value("lead_time_modifier", "1.0")),
            "label": self.get_state_value("market_label", ""),
        }

    def set_market_signal(
        self,
        *,
        supply_modifier: float = 1.0,
        lead_time_modifier: float = 1.0,
        label: str | None = None,
    ) -> dict[str, Any]:
        supply_modifier = max(0.1, float(supply_modifier))
        lead_time_modifier = max(0.1, float(lead_time_modifier))
        self.set_state_value("supply_modifier", f"{supply_modifier:.4f}")
        self.set_state_value("lead_time_modifier", f"{lead_time_modifier:.4f}")
        self.set_state_value("market_label", label or "")
        self.log_event(
            "market_signal_set",
            detail={
                "supply_modifier": supply_modifier,
                "lead_time_modifier": lead_time_modifier,
                "label": label or "",
            },
        )
        return self.market_signal()

    def log_event(
        self,
        event_type: str,
        *,
        entity_type: str | None = None,
        entity_id: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            models.Event(
                sim_day=self.current_day(),
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=json.dumps(detail or {}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
        self.db.commit()

    def get_catalog(self) -> list[dict[str, Any]]:
        products = (
            self.db.query(models.Product)
            .options(joinedload(models.Product.pricing_tiers), joinedload(models.Product.stock))
            .order_by(models.Product.name)
            .all()
        )
        return [
            {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "lead_time_days": product.lead_time_days,
                "stock_quantity": product.stock.quantity if product.stock else 0,
                "pricing_tiers": [
                    {
                        "min_quantity": tier.min_quantity,
                        "unit_price": tier.unit_price,
                    }
                    for tier in sorted(product.pricing_tiers, key=lambda item: item.min_quantity)
                ],
            }
            for product in products
        ]

    def get_stock(self) -> list[dict[str, Any]]:
        rows = (
            self.db.query(models.Stock, models.Product.name)
            .join(models.Product, models.Product.id == models.Stock.product_id)
            .order_by(models.Product.name)
            .all()
        )
        return [
            {
                "product_id": stock.product_id,
                "product_name": name,
                "quantity": stock.quantity,
            }
            for stock, name in rows
        ]

    def _select_price(self, product: models.Product, quantity: int) -> float:
        tiers = sorted(product.pricing_tiers, key=lambda item: item.min_quantity)
        chosen = None
        for tier in tiers:
            if quantity >= tier.min_quantity:
                chosen = tier
        if chosen is None:
            raise ValueError(f"No pricing tier defined for product '{product.name}' and quantity {quantity}.")
        return chosen.unit_price

    def create_order(self, buyer: str, product_id: int, quantity: int) -> dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        product = (
            self.db.query(models.Product)
            .options(joinedload(models.Product.pricing_tiers), joinedload(models.Product.stock))
            .filter(models.Product.id == product_id)
            .first()
        )
        if product is None:
            raise ValueError("Product not found.")

        available_stock = product.stock.quantity if product.stock else 0
        if available_stock < quantity:
            raise ValueError(
                f"Insufficient stock for {product.name}. Available={available_stock}, requested={quantity}."
            )

        unit_price = self._select_price(product, quantity)
        day = self.current_day()
        signal = self.market_signal()
        lead_time_modifier = float(signal["lead_time_modifier"])
        effective_lead_time = max(1, math.ceil(product.lead_time_days * lead_time_modifier))
        expected_delivery_day = day + effective_lead_time

        product.stock.quantity -= quantity

        order = models.Order(
            buyer=buyer,
            product_id=product.id,
            quantity=quantity,
            unit_price=unit_price,
            total_price=unit_price * quantity,
            placed_day=day,
            expected_delivery_day=expected_delivery_day,
            status="pending",
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        self.log_event(
            "order_placed",
            entity_type="order",
            entity_id=order.id,
            detail={
                "buyer": buyer,
                "product": product.name,
                "quantity": quantity,
                "expected_delivery_day": expected_delivery_day,
                "base_lead_time_days": product.lead_time_days,
                "lead_time_modifier": lead_time_modifier,
                "effective_lead_time_days": effective_lead_time,
            },
        )
        self.log_event(
            "stock_updated",
            entity_type="product",
            entity_id=product.id,
            detail={"product": product.name, "new_quantity": product.stock.quantity},
        )
        return self.serialize_order(order)

    def serialize_order(self, order: models.Order) -> dict[str, Any]:
        product = order.product or self.db.get(models.Product, order.product_id)
        return {
            "id": order.id,
            "buyer": order.buyer,
            "product_id": order.product_id,
            "product_name": product.name if product else "",
            "quantity": order.quantity,
            "unit_price": order.unit_price,
            "total_price": order.total_price,
            "placed_day": order.placed_day,
            "expected_delivery_day": order.expected_delivery_day,
            "shipped_day": order.shipped_day,
            "delivered_day": order.delivered_day,
            "status": order.status,
        }

    def list_orders(self, status: str | None = None) -> list[dict[str, Any]]:
        query = self.db.query(models.Order).options(joinedload(models.Order.product)).order_by(models.Order.id)
        if status:
            query = query.filter(models.Order.status == status)
        return [self.serialize_order(order) for order in query.all()]

    def get_order(self, order_id: int) -> dict[str, Any]:
        order = (
            self.db.query(models.Order)
            .options(joinedload(models.Order.product))
            .filter(models.Order.id == order_id)
            .first()
        )
        if order is None:
            raise ValueError("Order not found.")
        return self.serialize_order(order)

    def restock(self, product_name: str, quantity: int) -> dict[str, Any]:
        product = self.db.query(models.Product).filter(models.Product.name == product_name).first()
        if product is None:
            raise ValueError("Product not found.")
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if product.stock is None:
            product.stock = models.Stock(product_id=product.id, quantity=0)

        signal = self.market_signal()
        supply_modifier = float(signal["supply_modifier"])
        received_quantity = quantity
        if supply_modifier < 1.0:
            received_quantity = max(1, math.floor(quantity * supply_modifier))

        product.stock.quantity += received_quantity
        self.db.commit()

        self.log_event(
            "stock_updated",
            entity_type="product",
            entity_id=product.id,
            detail={
                "product": product.name,
                "requested_quantity": quantity,
                "received_quantity": received_quantity,
                "supply_modifier": supply_modifier,
                "new_quantity": product.stock.quantity,
            },
        )
        return {
            "product": product.name,
            "requested_quantity": quantity,
            "received_quantity": received_quantity,
            "quantity": product.stock.quantity,
        }

    def raise_all_prices(self, percent: float) -> list[dict[str, Any]]:
        """Raise the tier-1 (min_quantity=1) price of every product by `percent`%."""
        products = (
            self.db.query(models.Product)
            .options(joinedload(models.Product.pricing_tiers))
            .all()
        )
        results = []
        for product in products:
            tier = next((t for t in product.pricing_tiers if t.min_quantity == 1), None)
            if tier is None:
                continue
            new_price = round(tier.unit_price * (1 + percent / 100), 2)
            tier.unit_price = new_price
            self.log_event("price_changed", entity_type="product", entity_id=product.id,
                           detail={"product": product.name, "min_quantity": 1,
                                   "unit_price": new_price, "change_pct": percent})
            results.append({"product": product.name, "min_quantity": 1, "unit_price": new_price})
        self.db.commit()
        return results

    def set_price(self, product_name: str, min_quantity: int, price: float) -> dict[str, Any]:
        product = (
            self.db.query(models.Product)
            .options(joinedload(models.Product.pricing_tiers))
            .filter(models.Product.name == product_name)
            .first()
        )
        if product is None:
            raise ValueError("Product not found.")

        tier = next((item for item in product.pricing_tiers if item.min_quantity == min_quantity), None)
        if tier is None:
            tier = models.PricingTier(product_id=product.id, min_quantity=min_quantity, unit_price=price)
            self.db.add(tier)
        else:
            tier.unit_price = price
        self.db.commit()

        self.log_event(
            "price_changed",
            entity_type="product",
            entity_id=product.id,
            detail={"product": product.name, "min_quantity": min_quantity, "unit_price": price},
        )
        return {"product": product.name, "min_quantity": min_quantity, "unit_price": price}

    def advance_day(self) -> dict[str, Any]:
        day = self.current_day()
        orders = self.db.query(models.Order).order_by(models.Order.id).all()

        for order in orders:
            if order.status == "pending":
                order.status = "confirmed"
                self.db.commit()
                self.log_event("order_confirmed", entity_type="order", entity_id=order.id, detail={"status": "confirmed"})
            if order.status == "confirmed":
                order.status = "in_progress"
                self.db.commit()
                self.log_event("order_in_progress", entity_type="order", entity_id=order.id, detail={"status": "in_progress"})
            if order.status == "in_progress":
                order.status = "shipped"
                order.shipped_day = day
                self.db.commit()
                self.log_event("order_shipped", entity_type="order", entity_id=order.id, detail={"shipped_day": day})
            if order.status == "shipped" and order.expected_delivery_day <= day:
                order.status = "delivered"
                order.delivered_day = day
                self.db.commit()
                self.log_event(
                    "order_delivered",
                    entity_type="order",
                    entity_id=order.id,
                    detail={"delivered_day": day},
                )

        self.log_event("day_advanced", detail={"completed_day": day})
        self.set_current_day(day + 1)
        return {"current_day": day + 1}

    def export_state(self) -> dict[str, Any]:
        return {
            "current_day": self.current_day(),
            "market_signal": self.market_signal(),
            "catalog": self.get_catalog(),
            "orders": self.list_orders(),
            "events": [
                {
                    "sim_day": event.sim_day,
                    "event_type": event.event_type,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "detail": event.detail,
                    "created_at": event.created_at,
                }
                for event in self.db.query(models.Event).order_by(models.Event.id).all()
            ],
        }

    def import_state(self, data: dict[str, Any]) -> None:
        self.db.query(models.Event).delete()
        self.db.query(models.Order).delete()
        self.db.query(models.Stock).delete()
        self.db.query(models.PricingTier).delete()
        self.db.query(models.Product).delete()
        self.db.query(models.SimState).delete()
        self.db.commit()

        for product_data in data.get("catalog", []):
            product = models.Product(
                name=product_data["name"],
                description=product_data.get("description"),
                lead_time_days=product_data["lead_time_days"],
            )
            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)

            self.db.add(models.Stock(product_id=product.id, quantity=product_data.get("stock_quantity", 0)))
            for tier in product_data.get("pricing_tiers", []):
                self.db.add(
                    models.PricingTier(
                        product_id=product.id,
                        min_quantity=tier["min_quantity"],
                        unit_price=tier["unit_price"],
                    )
                )
            self.db.commit()

        self.db.add(models.SimState(key="current_day", value=str(data.get("current_day", 1))))
        market_signal = data.get("market_signal", {})
        self.db.add(models.SimState(key="supply_modifier", value=str(market_signal.get("supply_modifier", 1.0))))
        self.db.add(models.SimState(key="lead_time_modifier", value=str(market_signal.get("lead_time_modifier", 1.0))))
        self.db.add(models.SimState(key="market_label", value=str(market_signal.get("label", ""))))
        self.db.commit()


def load_seed(db: Session, seed_path: Path) -> None:
    if db.query(models.Product).first():
        return

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    for product_data in payload.get("products", []):
        product = models.Product(
            name=product_data["name"],
            description=product_data.get("description"),
            lead_time_days=product_data["lead_time_days"],
        )
        db.add(product)
        db.commit()
        db.refresh(product)

        db.add(models.Stock(product_id=product.id, quantity=product_data.get("initial_stock", 0)))
        for tier in product_data.get("pricing", []):
            db.add(
                models.PricingTier(
                    product_id=product.id,
                    min_quantity=tier["min_qty"],
                    unit_price=tier["price"],
                )
            )
        db.commit()

    service = ProviderService(db)
    service.log_event("seed_loaded", detail={"product_count": len(payload.get("products", []))})
