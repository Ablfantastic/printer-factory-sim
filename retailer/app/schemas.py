from typing import List, Optional

from pydantic import BaseModel


class CatalogItemOut(BaseModel):
    id: int
    model: str
    retail_price: float
    wholesale_price: Optional[float] = None

    model_config = {"from_attributes": True}


class StockItemOut(BaseModel):
    model: str
    quantity: int

    model_config = {"from_attributes": True}


class CustomerOrderCreate(BaseModel):
    customer: str
    model: str
    quantity: int = 1


class CustomerOrderOut(BaseModel):
    id: int
    customer: str
    model: str
    quantity: int
    placed_day: int
    fulfilled_day: Optional[int] = None
    status: str

    model_config = {"from_attributes": True}


class PurchaseOrderCreate(BaseModel):
    model: str
    quantity: int


class PurchaseOrderOut(BaseModel):
    id: int
    manufacturer_order_id: Optional[int] = None
    model: str
    quantity: int
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    placed_day: int
    expected_delivery_day: Optional[int] = None
    delivered_day: Optional[int] = None
    status: str

    model_config = {"from_attributes": True}


class PriceSetRequest(BaseModel):
    price: float


class DayInfo(BaseModel):
    current_day: int


class EventOut(BaseModel):
    id: int
    sim_day: int
    event_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    detail: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}
