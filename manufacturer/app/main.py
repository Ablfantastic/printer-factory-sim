"""FastAPI application: manufacturer — production, sales orders, and provider purchasing."""
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app import models
from app.schemas import PurchaseOrderCreateRequest
from app.services import ManufacturerService

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Manufacturer App",
    description="Factory: production, sales orders, and provider purchasing",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_service(db: Session = Depends(get_db)) -> ManufacturerService:
    return ManufacturerService(db)


# ------------------------------------------------------------------
# Health / root
# ------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "manufacturer"}


@app.get("/")
def root():
    return {"name": "manufacturer", "docs": "/docs"}


# ------------------------------------------------------------------
# Day
# ------------------------------------------------------------------

@app.get("/api/day/current")
def current_day(service: ManufacturerService = Depends(get_service)):
    return {"current_day": service.current_day()}


@app.get("/api/calendar")
def calendar(service: ManufacturerService = Depends(get_service)):
    return {"current_day": service.current_day()}


@app.post("/api/day/advance")
def advance_day(service: ManufacturerService = Depends(get_service)):
    return service.advance_day()


# ------------------------------------------------------------------
# Raw-parts inventory
# ------------------------------------------------------------------

@app.get("/api/stock")
def stock(service: ManufacturerService = Depends(get_service)):
    return service.get_inventory()


@app.get("/api/inventory")
def inventory(service: ManufacturerService = Depends(get_service)):
    return service.get_inventory()


# ------------------------------------------------------------------
# Finished-printer stock
# ------------------------------------------------------------------

@app.get("/api/finished-stock")
def finished_stock(service: ManufacturerService = Depends(get_service)):
    return service.get_finished_stock()


# ------------------------------------------------------------------
# Printer catalog & prices
# ------------------------------------------------------------------

@app.get("/api/price")
def price_list(service: ManufacturerService = Depends(get_service)):
    return service.list_printer_models()


class PriceSetRequest(BaseModel):
    price: float


@app.post("/api/price/{model}")
def price_set(model: str, req: PriceSetRequest, service: ManufacturerService = Depends(get_service)):
    try:
        return service.set_wholesale_price(model, req.price)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ------------------------------------------------------------------
# Capacity
# ------------------------------------------------------------------

@app.get("/api/capacity")
def capacity(service: ManufacturerService = Depends(get_service)):
    return service.get_capacity()


# ------------------------------------------------------------------
# Sales orders (inbound from retailers)
# ------------------------------------------------------------------

class SalesOrderCreateRequest(BaseModel):
    retailer: str
    model: str
    quantity: int


@app.post("/api/orders", status_code=201)
def create_sales_order(req: SalesOrderCreateRequest, service: ManufacturerService = Depends(get_service)):
    try:
        return service.create_sales_order(req.retailer, req.model, req.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/orders")
def list_sales_orders(status: Optional[str] = None, service: ManufacturerService = Depends(get_service)):
    return service.list_sales_orders(status)


@app.get("/api/orders/{order_id}")
def get_sales_order(order_id: int, service: ManufacturerService = Depends(get_service)):
    order = service.get_sales_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return order


@app.post("/api/orders/{order_id}/release")
def release_order(order_id: int, service: ManufacturerService = Depends(get_service)):
    try:
        return service.release_order(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/production/status")
def production_status(service: ManufacturerService = Depends(get_service)):
    return service.get_production_status()


# ------------------------------------------------------------------
# Provider purchases
# ------------------------------------------------------------------

@app.get("/api/providers")
def providers(service: ManufacturerService = Depends(get_service)):
    return service.list_providers()


@app.get("/api/providers/{supplier_name}/catalog")
def provider_catalog(supplier_name: str, service: ManufacturerService = Depends(get_service)):
    try:
        return service.supplier_catalog(supplier_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/api/purchases")
def create_purchase(request: PurchaseOrderCreateRequest, service: ManufacturerService = Depends(get_service)):
    try:
        return service.create_purchase_order(request.supplier_name, request.product_name, request.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/api/purchases")
def purchases(service: ManufacturerService = Depends(get_service)):
    return service.list_purchase_orders()


# ------------------------------------------------------------------
# Events
# ------------------------------------------------------------------

@app.get("/api/events")
def events(service: ManufacturerService = Depends(get_service)):
    return [
        {
            "id": e.id, "sim_day": e.sim_day, "event_type": e.event_type,
            "entity_type": e.entity_type, "entity_id": e.entity_id,
            "detail": e.detail, "created_at": e.created_at,
        }
        for e in service.db.query(models.Event).order_by(models.Event.id).all()
    ]


# ------------------------------------------------------------------
# Export / Import
# ------------------------------------------------------------------

@app.get("/api/export")
def export(service: ManufacturerService = Depends(get_service)):
    return service.export_state()


@app.post("/api/import")
def import_data(data: dict, service: ManufacturerService = Depends(get_service)):
    service.import_state(data)
    return {"status": "imported"}
