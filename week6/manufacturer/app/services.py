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

    def get_inventory(self) -> list[dict[str, Any]]:
        rows = self.db.query(models.Inventory).order_by(models.Inventory.product_name).all()
        return [
            {
                "product_id": row.product_id,
                "product_name": row.product_name,
                "quantity": row.quantity,
            }
            for row in rows
        ]

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
                status = "unreachable"
            result.append(
                {
                    "name": provider["name"],
                    "url": provider["url"],
                    "status": status,
                    "current_day": current_day,
                }
            )
        return result

    def get_provider(self, supplier_name: str) -> dict[str, Any]:
        providers = self.load_config()["manufacturer"]["providers"]
        provider = next((item for item in providers if item["name"] == supplier_name), None)
        if provider is None:
            raise ValueError(f"Unknown provider '{supplier_name}'.")
        return provider

    def supplier_catalog(self, supplier_name: str) -> list[dict[str, Any]]:
        provider = self.get_provider(supplier_name)
        client = ProviderClient(provider["url"])
        return client.get_catalog()

    def create_purchase_order(self, supplier_name: str, product_name: str, quantity: int) -> dict[str, Any]:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        provider = self.get_provider(supplier_name)
        client = ProviderClient(provider["url"])
        catalog = client.get_catalog()
        product = next((item for item in catalog if item["name"] == product_name), None)
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

        self.log_event(
            "purchase_order_placed",
            entity_type="purchase_order",
            entity_id=purchase.id,
            detail={
                "supplier": supplier_name,
                "provider_order_id": purchase.provider_order_id,
                "product": product_name,
                "quantity": quantity,
            },
        )
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
        return [self.serialize_purchase_order(row) for row in rows]

    def _ensure_inventory_item(self, product_name: str, quantity_delta: int) -> None:
        inventory = self.db.query(models.Inventory).filter(models.Inventory.product_name == product_name).first()
        if inventory is None:
            product = self.db.query(models.Product).filter(models.Product.name == product_name).first()
            if product is None:
                product = models.Product(name=product_name, type="raw")
                self.db.add(product)
                self.db.commit()
                self.db.refresh(product)
            inventory = models.Inventory(product_id=product.id, product_name=product_name, quantity=0)
            self.db.add(inventory)
            self.db.commit()

        inventory.quantity += quantity_delta
        self.db.commit()
        self.log_event(
            "stock_updated",
            entity_type="inventory",
            entity_id=inventory.product_id,
            detail={"product": product_name, "new_quantity": inventory.quantity},
        )

    def advance_day(self) -> dict[str, Any]:
        day = self.current_day()
        purchases = self.db.query(models.PurchaseOrder).filter(models.PurchaseOrder.status != "delivered").all()

        for purchase in purchases:
            client = ProviderClient(purchase.supplier_url)
            remote_order = client.get_order(purchase.provider_order_id)
            purchase.status = remote_order["status"]

            if remote_order["status"] == "delivered" and purchase.delivered_day is None:
                purchase.delivered_day = day
                self.db.commit()
                self._ensure_inventory_item(purchase.product_name, purchase.quantity)
                self.log_event(
                    "purchase_order_delivered",
                    entity_type="purchase_order",
                    entity_id=purchase.id,
                    detail={
                        "provider_order_id": purchase.provider_order_id,
                        "product": purchase.product_name,
                        "quantity": purchase.quantity,
                    },
                )
            else:
                self.db.commit()

        self.log_event("day_advanced", detail={"completed_day": day})
        self.set_current_day(day + 1)
        return {"current_day": day + 1}

    def export_state(self) -> dict[str, Any]:
        return {
            "current_day": self.current_day(),
            "inventory": self.get_inventory(),
            "purchase_orders": self.list_purchase_orders(),
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
        self.db.query(models.PurchaseOrder).delete()
        self.db.query(models.Inventory).delete()
        self.db.query(models.Product).delete()
        self.db.query(models.SimState).delete()
        self.db.commit()

        for item in data.get("inventory", []):
            product = models.Product(name=item["product_name"], type="raw")
            self.db.add(product)
            self.db.commit()
            self.db.refresh(product)
            self.db.add(
                models.Inventory(
                    product_id=product.id,
                    product_name=item["product_name"],
                    quantity=item["quantity"],
                )
            )
            self.db.commit()

        self.db.add(models.SimState(key="current_day", value=str(data.get("current_day", 1))))
        self.db.commit()


def load_seed(db: Session, seed_path: Path) -> None:
    if db.query(models.Product).first():
        return

    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    products: dict[str, models.Product] = {}

    for product_data in payload.get("products", []):
        product = models.Product(name=product_data["name"], type=product_data["type"])
        db.add(product)
        db.commit()
        db.refresh(product)
        products[product.name] = product

    for inventory_data in payload.get("inventory", []):
        product = products[inventory_data["product"]]
        db.add(
            models.Inventory(
                product_id=product.id,
                product_name=product.name,
                quantity=inventory_data["quantity"],
            )
        )
        db.commit()

    service = ManufacturerService(db)
    service.log_event("seed_loaded", detail={"product_count": len(payload.get("products", []))})
