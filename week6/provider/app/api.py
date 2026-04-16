from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.schemas import DayResponse, OrderCreateRequest
from app.services import ProviderService


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Provider App", version="1.0.0")


def get_service(db: Session = Depends(get_db)) -> ProviderService:
    return ProviderService(db)


@app.get("/api/catalog")
def get_catalog(service: ProviderService = Depends(get_service)):
    return service.get_catalog()


@app.get("/api/stock")
def get_stock(service: ProviderService = Depends(get_service)):
    return service.get_stock()


@app.post("/api/orders")
def create_order(request: OrderCreateRequest, service: ProviderService = Depends(get_service)):
    try:
        return service.create_order(request.buyer, request.product_id, request.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/orders")
def list_orders(status: str | None = Query(default=None), service: ProviderService = Depends(get_service)):
    return service.list_orders(status=status)


@app.get("/api/orders/{order_id}")
def get_order(order_id: int, service: ProviderService = Depends(get_service)):
    try:
        return service.get_order(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/day/advance", response_model=DayResponse)
def advance_day(service: ProviderService = Depends(get_service)):
    return service.advance_day()


@app.get("/api/day/current", response_model=DayResponse)
def current_day(service: ProviderService = Depends(get_service)):
    return {"current_day": service.current_day()}


@app.get("/health")
def health():
    return {"status": "ok", "service": "provider"}


@app.get("/")
def root():
    return {"name": "provider", "docs": "/docs"}
