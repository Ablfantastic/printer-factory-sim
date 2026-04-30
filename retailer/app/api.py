import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import services
from app.database import SessionLocal, get_db, init_db
from app.schemas import (
    CatalogItemOut,
    CustomerOrderCreate,
    CustomerOrderOut,
    DayInfo,
    EventOut,
    PriceSetRequest,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    StockItemOut,
)

# Config is injected at startup via APP_CONFIG env var (path to config JSON)
_config: dict = {}


def _manufacturer_url() -> str:
    return _config.get("retailer", {}).get("manufacturer", {}).get("url", "http://localhost:8002")


def _retailer_name() -> str:
    return _config.get("retailer", {}).get("name", "Retailer")


def _markup_pct() -> float:
    return float(_config.get("retailer", {}).get("markup_pct", 30))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config
    config_path = os.environ.get("APP_CONFIG", "config.json")
    try:
        _config = json.loads(Path(config_path).read_text())
    except Exception:
        _config = {}
    init_db()
    yield


app = FastAPI(title="Retailer API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"service": "retailer", "name": _retailer_name()}


@app.get("/health")
def health():
    return {"status": "ok", "service": "retailer", "name": _retailer_name()}


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@app.get("/api/catalog", response_model=List[CatalogItemOut])
def catalog(db: Session = Depends(get_db)):
    return services.get_catalog(db)


@app.post("/api/catalog/price")
def set_price(model: str, req: PriceSetRequest, db: Session = Depends(get_db)):
    try:
        item = services.set_price(db, model, req.price, _markup_pct())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return item


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

@app.get("/api/stock", response_model=List[StockItemOut])
def stock(db: Session = Depends(get_db)):
    return services.get_stock(db)


# ---------------------------------------------------------------------------
# Customer orders
# ---------------------------------------------------------------------------

@app.post("/api/orders", response_model=CustomerOrderOut, status_code=201)
def create_order(payload: CustomerOrderCreate, db: Session = Depends(get_db)):
    try:
        order = services.create_customer_order(
            db, payload.customer, payload.model, payload.quantity
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return order


@app.get("/api/orders", response_model=List[CustomerOrderOut])
def list_orders(status: Optional[str] = None, db: Session = Depends(get_db)):
    return services.list_customer_orders(db, status)


@app.get("/api/orders/{order_id}", response_model=CustomerOrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = services.get_customer_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/api/orders/{order_id}/fulfill", response_model=CustomerOrderOut)
def fulfill_order(order_id: int, db: Session = Depends(get_db)):
    try:
        return services.fulfill_order(db, order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/orders/{order_id}/backorder", response_model=CustomerOrderOut)
def backorder_order(order_id: int, db: Session = Depends(get_db)):
    try:
        return services.backorder_order(db, order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------

@app.post("/api/purchases", response_model=PurchaseOrderOut, status_code=201)
def create_purchase(payload: PurchaseOrderCreate, db: Session = Depends(get_db)):
    po = services.create_purchase_order(
        db, payload.model, payload.quantity, _manufacturer_url(), _retailer_name()
    )
    return po


@app.get("/api/purchases", response_model=List[PurchaseOrderOut])
def list_purchases(db: Session = Depends(get_db)):
    return services.list_purchase_orders(db)


# ---------------------------------------------------------------------------
# Day
# ---------------------------------------------------------------------------

@app.get("/api/day/current", response_model=DayInfo)
def current_day(db: Session = Depends(get_db)):
    return DayInfo(current_day=services._current_day(db))


@app.post("/api/day/advance", response_model=DayInfo)
def advance_day(db: Session = Depends(get_db)):
    new_day = services.advance_day(db, _manufacturer_url())
    return DayInfo(current_day=new_day)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.get("/api/events", response_model=List[EventOut])
def events(db: Session = Depends(get_db)):
    from app.models import Event
    return db.query(Event).order_by(Event.id).all()


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

@app.get("/api/export")
def export(db: Session = Depends(get_db)):
    return services.export_state(db)


@app.post("/api/import")
def import_data(data: dict, db: Session = Depends(get_db)):
    services.import_state(db, data)
    return {"status": "imported"}
