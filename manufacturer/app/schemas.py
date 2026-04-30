from typing import Optional

from pydantic import BaseModel


class InventoryItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: int


class ProviderInfoResponse(BaseModel):
    name: str
    url: str
    current_day: Optional[int] = None
    status: str


class ProviderCatalogItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    lead_time_days: int
    stock_quantity: int
    pricing_tiers: list[dict]


class PurchaseOrderCreateRequest(BaseModel):
    supplier_name: str
    product_name: str
    quantity: int


class PurchaseOrderResponse(BaseModel):
    id: int
    supplier_name: str
    supplier_url: str
    provider_order_id: int
    provider_product_id: int
    product_name: str
    quantity: int
    unit_price: float
    total_price: float
    placed_day: int
    expected_delivery_day: int
    delivered_day: Optional[int] = None
    status: str


class DayResponse(BaseModel):
    current_day: int


class EventResponse(BaseModel):
    id: int
    sim_day: int
    event_type: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    detail: Optional[str] = None
    created_at: str
