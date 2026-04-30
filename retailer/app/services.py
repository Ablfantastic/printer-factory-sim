import json
from datetime import datetime
from typing import Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.models import CatalogItem, CustomerOrder, Event, PurchaseOrder, SimState, Stock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.utcnow().isoformat()


def _current_day(db: Session) -> int:
    row = db.query(SimState).filter_by(key="current_day").first()
    return int(row.value) if row else 1


def _log_event(db: Session, event_type: str, entity_type: str, entity_id: int, detail: dict):
    day = _current_day(db)
    ev = Event(
        sim_day=day,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=json.dumps(detail),
        created_at=_now(),
    )
    db.add(ev)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def get_catalog(db: Session) -> List[CatalogItem]:
    return db.query(CatalogItem).all()


def set_price(db: Session, model: str, price: float, markup_pct: float = 30.0) -> CatalogItem:
    item = db.query(CatalogItem).filter_by(model=model).first()
    if not item:
        raise ValueError(f"Model '{model}' not in catalog")
    min_price = (item.wholesale_price or 0) * (1 + markup_pct / 100)
    if item.wholesale_price and price < min_price:
        raise ValueError(
            f"Price {price} is below minimum {min_price:.2f} "
            f"({markup_pct}% markup on wholesale {item.wholesale_price})"
        )
    item.retail_price = price
    db.commit()
    db.refresh(item)
    _log_event(db, "price_set", "catalog", item.id, {"model": model, "price": price})
    db.commit()
    return item


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

def get_stock(db: Session) -> List[Stock]:
    return db.query(Stock).all()


def _stock_for(db: Session, model: str) -> int:
    row = db.query(Stock).filter_by(model=model).first()
    return row.quantity if row else 0


def _adjust_stock(db: Session, model: str, delta: int):
    row = db.query(Stock).filter_by(model=model).first()
    if row is None:
        row = Stock(model=model, quantity=0)
        db.add(row)
    row.quantity = max(0, row.quantity + delta)
    db.commit()


# ---------------------------------------------------------------------------
# Customer orders
# ---------------------------------------------------------------------------

def create_customer_order(db: Session, customer: str, model: str, quantity: int) -> CustomerOrder:
    if not db.query(CatalogItem).filter_by(model=model).first():
        raise ValueError(f"Model '{model}' not in catalog")

    day = _current_day(db)
    order = CustomerOrder(
        customer=customer,
        model=model,
        quantity=quantity,
        placed_day=day,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    available = _stock_for(db, model)
    if available >= quantity:
        _fulfill_order(db, order)
    else:
        order.status = "backordered"
        db.commit()
        _log_event(db, "order_backordered", "customer_order", order.id,
                   {"model": model, "qty": quantity, "available": available})
        db.commit()

    return order


def list_customer_orders(db: Session, status: Optional[str] = None) -> List[CustomerOrder]:
    q = db.query(CustomerOrder)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(CustomerOrder.id).all()


def get_customer_order(db: Session, order_id: int) -> Optional[CustomerOrder]:
    return db.query(CustomerOrder).filter_by(id=order_id).first()


def fulfill_order(db: Session, order_id: int) -> CustomerOrder:
    order = db.query(CustomerOrder).filter_by(id=order_id).first()
    if not order:
        raise ValueError(f"Order {order_id} not found")
    if order.status == "fulfilled":
        raise ValueError(f"Order {order_id} already fulfilled")
    _fulfill_order(db, order)
    return order


def _fulfill_order(db: Session, order: CustomerOrder):
    available = _stock_for(db, order.model)
    if available < order.quantity:
        raise ValueError(
            f"Not enough stock for {order.model}: need {order.quantity}, have {available}"
        )
    _adjust_stock(db, order.model, -order.quantity)
    order.status = "fulfilled"
    order.fulfilled_day = _current_day(db)
    db.commit()
    _log_event(db, "order_fulfilled", "customer_order", order.id,
               {"model": order.model, "qty": order.quantity, "customer": order.customer})
    db.commit()


def backorder_order(db: Session, order_id: int) -> CustomerOrder:
    order = db.query(CustomerOrder).filter_by(id=order_id).first()
    if not order:
        raise ValueError(f"Order {order_id} not found")
    if order.status not in ("pending",):
        raise ValueError(f"Cannot backorder order with status '{order.status}'")
    order.status = "backordered"
    db.commit()
    _log_event(db, "order_backordered", "customer_order", order.id,
               {"model": order.model, "qty": order.quantity})
    db.commit()
    return order


# ---------------------------------------------------------------------------
# Purchase orders (retailer → manufacturer)
# ---------------------------------------------------------------------------

def list_purchase_orders(db: Session) -> List[PurchaseOrder]:
    return db.query(PurchaseOrder).order_by(PurchaseOrder.id).all()


def create_purchase_order(
    db: Session, model: str, quantity: int, manufacturer_url: str, retailer_name: str
) -> PurchaseOrder:
    day = _current_day(db)
    po = PurchaseOrder(
        model=model,
        quantity=quantity,
        placed_day=day,
        status="pending",
    )
    db.add(po)
    db.commit()
    db.refresh(po)

    try:
        resp = httpx.post(
            f"{manufacturer_url}/api/orders",
            json={"retailer": retailer_name, "model": model, "quantity": quantity},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        po.manufacturer_order_id = data.get("id")
        po.unit_price = data.get("unit_price")
        po.total_price = data.get("total_price")
        po.expected_delivery_day = data.get("expected_delivery_day")
        po.status = data.get("status", "confirmed")
        db.commit()
        _log_event(db, "purchase_order_placed", "purchase_order", po.id,
                   {"model": model, "qty": quantity, "manufacturer_order_id": po.manufacturer_order_id})
        db.commit()
    except Exception as exc:
        _log_event(db, "purchase_order_failed", "purchase_order", po.id,
                   {"model": model, "qty": quantity, "error": str(exc)})
        db.commit()

    return po


def _poll_purchase_orders(db: Session, manufacturer_url: str):
    """Fetch current status of open purchase orders from manufacturer."""
    open_pos = (
        db.query(PurchaseOrder)
        .filter(PurchaseOrder.status.notin_(["delivered", "cancelled"]))
        .filter(PurchaseOrder.manufacturer_order_id.isnot(None))
        .all()
    )
    for po in open_pos:
        try:
            resp = httpx.get(
                f"{manufacturer_url}/api/orders/{po.manufacturer_order_id}",
                timeout=10.0,
            )
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            data = resp.json()
            new_status = data.get("status", po.status)
            if new_status != po.status:
                old_status = po.status
                po.status = new_status
                if po.expected_delivery_day is None:
                    po.expected_delivery_day = data.get("expected_delivery_day")
                if new_status == "delivered":
                    po.delivered_day = _current_day(db)
                    _adjust_stock(db, po.model, po.quantity)
                    _log_event(db, "stock_received", "purchase_order", po.id,
                               {"model": po.model, "qty": po.quantity,
                                "manufacturer_order_id": po.manufacturer_order_id})
                    db.commit()
                    _auto_fulfill_backorders(db, po.model)
                else:
                    _log_event(db, "purchase_order_status_changed", "purchase_order", po.id,
                               {"old": old_status, "new": new_status})
                db.commit()
        except Exception:
            pass


def _auto_fulfill_backorders(db: Session, model: str):
    """After receiving stock, try to fulfill backordered orders for this model."""
    backorders = (
        db.query(CustomerOrder)
        .filter_by(model=model, status="backordered")
        .order_by(CustomerOrder.id)
        .all()
    )
    for order in backorders:
        available = _stock_for(db, model)
        if available >= order.quantity:
            _fulfill_order(db, order)
        else:
            break


# ---------------------------------------------------------------------------
# Day advance
# ---------------------------------------------------------------------------

def advance_day(db: Session, manufacturer_url: str):
    _poll_purchase_orders(db, manufacturer_url)

    row = db.query(SimState).filter_by(key="current_day").first()
    if row is None:
        row = SimState(key="current_day", value="1")
        db.add(row)
    new_day = int(row.value) + 1
    row.value = str(new_day)
    db.commit()

    _log_event(db, "day_advanced", "sim", 0, {"new_day": new_day})
    db.commit()
    return new_day


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

def export_state(db: Session) -> dict:
    catalog = [
        {"model": i.model, "retail_price": i.retail_price, "wholesale_price": i.wholesale_price}
        for i in db.query(CatalogItem).all()
    ]
    stock = [{"model": s.model, "quantity": s.quantity} for s in db.query(Stock).all()]
    customer_orders = [
        {
            "id": o.id, "customer": o.customer, "model": o.model,
            "quantity": o.quantity, "placed_day": o.placed_day,
            "fulfilled_day": o.fulfilled_day, "status": o.status,
        }
        for o in db.query(CustomerOrder).all()
    ]
    purchase_orders = [
        {
            "id": p.id, "manufacturer_order_id": p.manufacturer_order_id,
            "model": p.model, "quantity": p.quantity,
            "unit_price": p.unit_price, "total_price": p.total_price,
            "placed_day": p.placed_day, "expected_delivery_day": p.expected_delivery_day,
            "delivered_day": p.delivered_day, "status": p.status,
        }
        for p in db.query(PurchaseOrder).all()
    ]
    events = [
        {
            "id": e.id, "sim_day": e.sim_day, "event_type": e.event_type,
            "entity_type": e.entity_type, "entity_id": e.entity_id,
            "detail": e.detail, "created_at": e.created_at,
        }
        for e in db.query(Event).all()
    ]
    state = {row.key: row.value for row in db.query(SimState).all()}
    return {
        "catalog": catalog,
        "stock": stock,
        "customer_orders": customer_orders,
        "purchase_orders": purchase_orders,
        "events": events,
        "sim_state": state,
    }


def import_state(db: Session, data: dict):
    for tbl in [CatalogItem, Stock, CustomerOrder, PurchaseOrder, Event, SimState]:
        db.query(tbl).delete()
    db.commit()

    for item in data.get("catalog", []):
        db.add(CatalogItem(**item))
    for item in data.get("stock", []):
        db.add(Stock(**item))
    for item in data.get("customer_orders", []):
        db.add(CustomerOrder(**item))
    for item in data.get("purchase_orders", []):
        db.add(PurchaseOrder(**item))
    for item in data.get("events", []):
        db.add(Event(**item))
    for k, v in data.get("sim_state", {}).items():
        db.add(SimState(key=k, value=v))
    db.commit()
