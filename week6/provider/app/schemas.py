from typing import Optional

from pydantic import BaseModel


class PricingTierResponse(BaseModel):
    min_quantity: int
    unit_price: float


class CatalogProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    lead_time_days: int
    stock_quantity: int
    pricing_tiers: list[PricingTierResponse]


class StockItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: int


class OrderCreateRequest(BaseModel):
    buyer: str
    product_id: int
    quantity: int


class OrderResponse(BaseModel):
    id: int
    buyer: str
    product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    placed_day: int
    expected_delivery_day: int
    shipped_day: Optional[int] = None
    delivered_day: Optional[int] = None
    status: str


class DayResponse(BaseModel):
    current_day: int


class MessageResponse(BaseModel):
    message: str
