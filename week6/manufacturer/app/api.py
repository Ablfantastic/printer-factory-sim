from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app import models
from app.schemas import PurchaseOrderCreateRequest
from app.services import ManufacturerService


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Manufacturer App", version="1.0.0")


def get_service(db: Session = Depends(get_db)) -> ManufacturerService:
    return ManufacturerService(db)


@app.get("/api/day/current")
def current_day(service: ManufacturerService = Depends(get_service)):
    return {"current_day": service.current_day()}


@app.get("/api/calendar")
def calendar(service: ManufacturerService = Depends(get_service)):
    return {"current_day": service.current_day()}


@app.post("/api/day/advance")
def advance_day(service: ManufacturerService = Depends(get_service)):
    return service.advance_day()


@app.get("/api/stock")
def stock(service: ManufacturerService = Depends(get_service)):
    return service.get_inventory()


@app.get("/api/inventory")
def inventory(service: ManufacturerService = Depends(get_service)):
    return service.get_inventory()


@app.get("/api/providers")
def providers(service: ManufacturerService = Depends(get_service)):
    return service.list_providers()


@app.get("/api/providers/{supplier_name}/catalog")
def provider_catalog(supplier_name: str, service: ManufacturerService = Depends(get_service)):
    try:
        return service.supplier_catalog(supplier_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/purchases")
def create_purchase(request: PurchaseOrderCreateRequest, service: ManufacturerService = Depends(get_service)):
    try:
        return service.create_purchase_order(request.supplier_name, request.product_name, request.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/purchases")
def purchases(service: ManufacturerService = Depends(get_service)):
    return service.list_purchase_orders()


@app.get("/api/events")
def events(service: ManufacturerService = Depends(get_service)):
    return [
        {
            "id": event.id,
            "sim_day": event.sim_day,
            "event_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "detail": event.detail,
            "created_at": event.created_at,
        }
        for event in service.db.query(models.Event).order_by(models.Event.id).all()
    ]


@app.get("/health")
def health():
    return {"status": "ok", "service": "manufacturer"}


@app.get("/")
def root():
    return {"name": "manufacturer", "docs": "/docs"}
