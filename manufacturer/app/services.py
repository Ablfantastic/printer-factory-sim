import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.provider_client import ProviderClient

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


class ManufacturerService:
    def __init__(self, db: Session):
        self.db = db
        self._ensure_sim_state()

    # ------------------------------------------------------------------
    # Sim state
    # ------------------------------------------------------------------

    def _ensure_sim_state(self) -> None:
        if self.db.get(models.SimState, "current_day") is None:
            self.db.add(models.SimState(key="current_day", value="1"))
            self.db.commit()

    def current_day(self) -> int:
        return int(self.db.get(models.SimState, "current_day").value)

    def set_current_day(self, day: int) -> None:
        self.db.get(models.SimState, "current_day").value = str(day)
        self.db.commit()

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

    def load_config(self) -> dict[str, Any]:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Raw-parts inventory
    # ------------------------------------------------------------------

    def get_inventory(self) -> list[dict[str, Any]]:
        rows = self.db.query(models.Inventory).order_by(models.Inventory.product_name).all()
        return [
            {"product_id": r.product_id, "product_name": r.product_name, "quantity": r.quantity}
            for r in rows
        ]

    def _inventory_qty(self, product_name: str) -> int:
        row = self.db.query(models.Inventory).filter_by(product_name=product_name).first()
        return row.quantity if row else 0

    def _adjust_inventory(self, product_name: str, delta: int) -> None:
        row = self.db.query(models.Inventory).filter_by(product_name=product_name).first()
        if row is None:
            product = self.db.query(models.Product).filter_by(name=product_name).first()
            if product is None:
                product = models.Product(name=product_name, type="raw")
                self.db.add(product)
                self.db.commit()
                self.db.refresh(product)
            row = models.Inventory(product_id=product.id, product_name=product_name, quantity=0)
            self.db.add(row)
            self.db.commit()
        row.quantity = max(0, row.quantity + delta)
        self.db.commit()

    # ------------------------------------------------------------------
    # Finished-printer stock
    # ------------------------------------------------------------------

    def get_finished_stock(self) -> list[dict[str, Any]]:
        rows = self.db.query(models.FinishedStock).order_by(models.FinishedStock.model).all()
        return [{"model": r.model, "quantity": r.quantity} for r in rows]

    def _finished_qty(self, model: str) -> int:
        row = self.db.query(models.FinishedStock).filter_by(model=model).first()
        return row.quantity if row else 0

    def _adjust_finished_stock(self, model: str, delta: int) -> None:
        row = self.db.query(models.FinishedStock).filter_by(model=model).first()
        if row is None:
            row = models.FinishedStock(model=model, quantity=0)
            self.db.add(row)
            self.db.commit()
        row.quantity = max(0, row.quantity + delta)
        self.db.commit()

    # ------------------------------------------------------------------
    # Printer catalog & prices
    # ------------------------------------------------------------------

    def list_printer_models(self) -> list[dict[str, Any]]:
        rows = self.db.query(models.PrinterModel).order_by(models.PrinterModel.name).all()
        return [self._serialize_printer_model(r) for r in rows]

    def _serialize_printer_model(self, pm: models.PrinterModel) -> dict[str, Any]:
        bom = json.loads(pm.bom) if pm.bom else {}
        return {
            "id": pm.id,
            "name": pm.name,
            "wholesale_price": pm.wholesale_price,
            "production_days": pm.production_days,
            "daily_capacity": pm.daily_capacity,
            "bom": bom,
        }

    def set_wholesale_price(self, model: str, price: float) -> dict[str, Any]:
        if price <= 0:
            raise ValueError("Price must be positive")
        pm = self.db.query(models.PrinterModel).filter_by(name=model).first()
        if pm is None:
            raise ValueError(f"Model '{model}' not found")
        pm.wholesale_price = price
        self.db.commit()
        self.log_event("price_set", entity_type="printer_model", entity_id=pm.id,
                       detail={"model": model, "price": price})
        return self._serialize_printer_model(pm)

    # ------------------------------------------------------------------
    # Capacity
    # ------------------------------------------------------------------

    def get_capacity(self) -> dict[str, Any]:
        day = self.current_day()
        total_capacity = sum(
            pm.daily_capacity
            for pm in self.db.query(models.PrinterModel).all()
        )
        in_progress = (
            self.db.query(models.SalesOrder)
            .filter_by(status="in_progress")
            .all()
        )
        units_in_progress = sum(o.quantity for o in in_progress)
        pending_released = (
            self.db.query(models.SalesOrder)
            .filter(models.SalesOrder.status.in_(["pending", "released"]))
            .all()
        )
        units_pending = sum(o.quantity for o in pending_released)
        return {
            "current_day": day,
            "daily_capacity_total": total_capacity,
            "units_in_progress": units_in_progress,
            "units_pending_or_released": units_pending,
            "utilisation_pct": round(units_in_progress / total_capacity * 100, 1) if total_capacity else 0,
            "per_model": [
                {"model": pm.name, "daily_capacity": pm.daily_capacity, "production_days": pm.production_days}
                for pm in self.db.query(models.PrinterModel).all()
            ],
        }

    # ------------------------------------------------------------------
    # Sales orders (inbound from retailers)
    # ------------------------------------------------------------------

    def create_sales_order(self, retailer: str, model: str, quantity: int) -> dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        pm = self.db.query(models.PrinterModel).filter_by(name=model).first()
        if pm is None:
            raise ValueError(f"Model '{model}' not in catalog")
        day = self.current_day()
        unit_price = pm.wholesale_price
        order = models.SalesOrder(
            retailer=retailer,
            model=model,
            quantity=quantity,
            unit_price=unit_price,
            total_price=unit_price * quantity,
            placed_day=day,
            expected_delivery_day=day + pm.production_days + 1,
            status="pending",
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        self.log_event("sales_order_received", entity_type="sales_order", entity_id=order.id,
                       detail={"retailer": retailer, "model": model, "qty": quantity,
                               "unit_price": unit_price})
        return self._serialize_sales_order(order)

    def list_sales_orders(self, status: str | None = None) -> list[dict[str, Any]]:
        q = self.db.query(models.SalesOrder)
        if status:
            q = q.filter_by(status=status)
        return [self._serialize_sales_order(o) for o in q.order_by(models.SalesOrder.id).all()]

    def get_sales_order(self, order_id: int) -> dict[str, Any] | None:
        o = self.db.query(models.SalesOrder).filter_by(id=order_id).first()
        return self._serialize_sales_order(o) if o else None

    def _serialize_sales_order(self, o: models.SalesOrder) -> dict[str, Any]:
        return {
            "id": o.id,
            "retailer": o.retailer,
            "model": o.model,
            "quantity": o.quantity,
            "unit_price": o.unit_price,
            "total_price": o.total_price,
            "placed_day": o.placed_day,
            "released_day": o.released_day,
            "production_start_day": o.production_start_day,
            "expected_delivery_day": o.expected_delivery_day,
            "shipped_day": o.shipped_day,
            "delivered_day": o.delivered_day,
            "status": o.status,
        }

    def release_order(self, order_id: int) -> dict[str, Any]:
        order = self.db.query(models.SalesOrder).filter_by(id=order_id).first()
        if order is None:
            raise ValueError(f"Sales order {order_id} not found")
        if order.status != "pending":
            raise ValueError(f"Order {order_id} is '{order.status}', must be 'pending' to release")
        order.status = "released"
        order.released_day = self.current_day()
        self.db.commit()
        self.log_event("order_released", entity_type="sales_order", entity_id=order.id,
                       detail={"model": order.model, "qty": order.quantity})
        return self._serialize_sales_order(order)

    def get_production_status(self) -> list[dict[str, Any]]:
        orders = (
            self.db.query(models.SalesOrder)
            .filter(models.SalesOrder.status.in_(["released", "in_progress"]))
            .order_by(models.SalesOrder.id)
            .all()
        )
        return [self._serialize_sales_order(o) for o in orders]

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def list_providers(self) -> list[dict[str, Any]]:
        providers = self.load_config()["manufacturer"]["providers"]
        result = []
        for provider in providers:
            client = ProviderClient(provider["url"])
            status = "unreachable"
            current_day = None
            try:
                if client.health():
                    status = "ok"
                    current_day = client.get_current_day()
            except Exception:
                pass
            result.append({"name": provider["name"], "url": provider["url"],
                            "status": status, "current_day": current_day})
        return result

    def get_provider(self, supplier_name: str) -> dict[str, Any]:
        providers = self.load_config()["manufacturer"]["providers"]
        provider = next((p for p in providers if p["name"] == supplier_name), None)
        if provider is None:
            raise ValueError(f"Unknown provider '{supplier_name}'.")
        return provider

    def supplier_catalog(self, supplier_name: str) -> list[dict[str, Any]]:
        return ProviderClient(self.get_provider(supplier_name)["url"]).get_catalog()

    # ------------------------------------------------------------------
    # Purchase orders (outbound to providers)
    # ------------------------------------------------------------------

    def create_purchase_order(self, supplier_name: str, product_name: str, quantity: int) -> dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        provider = self.get_provider(supplier_name)
        client = ProviderClient(provider["url"])
        catalog = client.get_catalog()
        product = next((i for i in catalog if i["name"] == product_name), None)
        if product is None:
            raise ValueError(f"Product '{product_name}' not found in provider catalog.")
        remote_order = client.create_order("manufacturer", product["id"], quantity)
        purchase = models.PurchaseOrder(
            supplier_name=supplier_name,
            supplier_url=provider["url"],
            provider_order_id=remote_order["id"],
            provider_product_id=remote_order["product_id"],
            product_name=remote_order["product_name"],
            quantity=remote_order["quantity"],
            unit_price=remote_order["unit_price"],
            total_price=remote_order["total_price"],
            placed_day=self.current_day(),
            expected_delivery_day=remote_order["expected_delivery_day"],
            status=remote_order["status"],
        )
        self.db.add(purchase)
        self.db.commit()
        self.db.refresh(purchase)
        self.log_event("purchase_order_placed", entity_type="purchase_order", entity_id=purchase.id,
                       detail={"supplier": supplier_name, "provider_order_id": purchase.provider_order_id,
                               "product": product_name, "quantity": quantity})
        return self.serialize_purchase_order(purchase)

    def serialize_purchase_order(self, order: models.PurchaseOrder) -> dict[str, Any]:
        return {
            "id": order.id,
            "supplier_name": order.supplier_name,
            "supplier_url": order.supplier_url,
            "provider_order_id": order.provider_order_id,
            "provider_product_id": order.provider_product_id,
            "product_name": order.product_name,
            "quantity": order.quantity,
            "unit_price": order.unit_price,
            "total_price": order.total_price,
            "placed_day": order.placed_day,
            "expected_delivery_day": order.expected_delivery_day,
            "delivered_day": order.delivered_day,
            "status": order.status,
        }

    def list_purchase_orders(self) -> list[dict[str, Any]]:
        rows = self.db.query(models.PurchaseOrder).order_by(models.PurchaseOrder.id).all()
        return [self.serialize_purchase_order(r) for r in rows]

    # ------------------------------------------------------------------
    # Day advance — production pipeline
    # ------------------------------------------------------------------

    def advance_day(self) -> dict[str, Any]:
        day = self.current_day()

        # Step 1: released orders → check BOM, consume parts, move to in_progress
        released = (
            self.db.query(models.SalesOrder).filter_by(status="released").all()
        )
        for order in released:
            pm = self.db.query(models.PrinterModel).filter_by(name=order.model).first()
            if pm is None:
                continue
            bom = json.loads(pm.bom) if pm.bom else {}
            # Check all parts are available
            can_produce = all(
                self._inventory_qty(part) >= qty * order.quantity
                for part, qty in bom.items()
            )
            if can_produce:
                for part, qty in bom.items():
                    self._adjust_inventory(part, -(qty * order.quantity))
                order.status = "in_progress"
                order.production_start_day = day
                self.db.commit()
                self.log_event("production_started", entity_type="sales_order", entity_id=order.id,
                               detail={"model": order.model, "qty": order.quantity,
                                       "bom_consumed": {p: q * order.quantity for p, q in bom.items()}})
            else:
                missing = {
                    p: q * order.quantity - self._inventory_qty(p)
                    for p, q in bom.items()
                    if self._inventory_qty(p) < q * order.quantity
                }
                self.log_event("production_blocked", entity_type="sales_order", entity_id=order.id,
                               detail={"model": order.model, "qty": order.quantity, "missing_parts": missing})

        # Step 2: in_progress orders that have completed production → add to finished stock
        in_progress = (
            self.db.query(models.SalesOrder).filter_by(status="in_progress").all()
        )
        for order in in_progress:
            pm = self.db.query(models.PrinterModel).filter_by(name=order.model).first()
            production_days = pm.production_days if pm else 1
            if order.production_start_day is not None and day >= order.production_start_day + production_days:
                order.status = "completed"
                self.db.commit()
                self._adjust_finished_stock(order.model, order.quantity)
                self.log_event("production_completed", entity_type="sales_order", entity_id=order.id,
                               detail={"model": order.model, "qty": order.quantity})

        # Step 3: completed sales orders with finished stock → ship them
        completed = (
            self.db.query(models.SalesOrder).filter_by(status="completed").all()
        )
        for order in completed:
            available = self._finished_qty(order.model)
            if available >= order.quantity:
                self._adjust_finished_stock(order.model, -order.quantity)
                order.status = "shipped"
                order.shipped_day = day
                self.db.commit()
                self.log_event("order_shipped", entity_type="sales_order", entity_id=order.id,
                               detail={"model": order.model, "qty": order.quantity,
                                       "retailer": order.retailer})

        # Step 4: shipped orders → delivered (1 day after shipping)
        shipped = (
            self.db.query(models.SalesOrder).filter_by(status="shipped").all()
        )
        for order in shipped:
            if order.shipped_day is not None and day >= order.shipped_day + 1:
                order.status = "delivered"
                order.delivered_day = day
                self.db.commit()
                self.log_event("order_delivered", entity_type="sales_order", entity_id=order.id,
                               detail={"model": order.model, "qty": order.quantity,
                                       "retailer": order.retailer})

        # Step 5: poll provider purchase orders
        purchases = self.db.query(models.PurchaseOrder).filter(
            models.PurchaseOrder.status != "delivered"
        ).all()
        for purchase in purchases:
            try:
                client = ProviderClient(purchase.supplier_url)
                remote = client.get_order(purchase.provider_order_id)
                purchase.status = remote["status"]
                if remote["status"] == "delivered" and purchase.delivered_day is None:
                    purchase.delivered_day = day
                    self.db.commit()
                    self._adjust_inventory(purchase.product_name, purchase.quantity)
                    self.log_event("purchase_order_delivered", entity_type="purchase_order",
                                   entity_id=purchase.id,
                                   detail={"product": purchase.product_name, "qty": purchase.quantity})
                else:
                    self.db.commit()
            except Exception:
                pass

        self.log_event("day_advanced", detail={"completed_day": day})
        self.set_current_day(day + 1)
        return {"current_day": day + 1}

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def export_state(self) -> dict[str, Any]:
        return {
            "current_day": self.current_day(),
            "inventory": self.get_inventory(),
            "finished_stock": self.get_finished_stock(),
            "printer_models": self.list_printer_models(),
            "sales_orders": self.list_sales_orders(),
            "purchase_orders": self.list_purchase_orders(),
            "events": [
                {
                    "sim_day": e.sim_day, "event_type": e.event_type,
                    "entity_type": e.entity_type, "entity_id": e.entity_id,
                    "detail": e.detail, "created_at": e.created_at,
                }
                for e in self.db.query(models.Event).order_by(models.Event.id).all()
            ],
        }

    def import_state(self, data: dict[str, Any]) -> None:
        for tbl in [models.Event, models.SalesOrder, models.PurchaseOrder,
                    models.FinishedStock, models.PrinterModel,
                    models.Inventory, models.Product, models.SimState]:
            self.db.query(tbl).delete()
        self.db.commit()

        for item in data.get("inventory", []):
            product = models.Product(name=item["product_name"], type="raw")
            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)
            self.db.add(models.Inventory(product_id=product.id,
                                         product_name=item["product_name"],
                                         quantity=item["quantity"]))
            self.db.commit()

        for item in data.get("printer_models", []):
            self.db.add(models.PrinterModel(
                name=item["name"], wholesale_price=item["wholesale_price"],
                production_days=item["production_days"], daily_capacity=item["daily_capacity"],
                bom=json.dumps(item.get("bom", {})),
            ))
        self.db.commit()

        for item in data.get("finished_stock", []):
            self.db.add(models.FinishedStock(model=item["model"], quantity=item["quantity"]))
        self.db.commit()

        for item in data.get("sales_orders", []):
            self.db.add(models.SalesOrder(**{k: v for k, v in item.items() if k != "id"}))
        self.db.commit()

        self.db.add(models.SimState(key="current_day", value=str(data.get("current_day", 1))))
        self.db.commit()


# ------------------------------------------------------------------
# Seed helper
# ------------------------------------------------------------------

def load_seed(db: Session, seed_path: Path) -> None:
    if db.query(models.Product).first():
        return

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    products: dict[str, models.Product] = {}

    for pd in payload.get("products", []):
        product = models.Product(name=pd["name"], type=pd["type"])
        db.add(product)
        db.commit()
        db.refresh(product)
        products[product.name] = product

    for inv in payload.get("inventory", []):
        product = products[inv["product"]]
        db.add(models.Inventory(product_id=product.id, product_name=product.name,
                                quantity=inv["quantity"]))
    db.commit()

    for pm_data in payload.get("printer_models", []):
        db.add(models.PrinterModel(
            name=pm_data["name"],
            wholesale_price=pm_data["wholesale_price"],
            production_days=pm_data["production_days"],
            daily_capacity=pm_data["daily_capacity"],
            bom=json.dumps(pm_data.get("bom", {})),
        ))
    db.commit()

    for fs in payload.get("finished_stock", []):
        db.add(models.FinishedStock(model=fs["model"], quantity=fs["quantity"]))
    db.commit()

    svc = ManufacturerService(db)
    svc.log_event("seed_loaded", detail={"product_count": len(payload.get("products", []))})
