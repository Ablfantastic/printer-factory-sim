"""Pydantic schemas for API request/response validation."""
from datetime import date
from typing import Optional, List
from pydantic import BaseModel


# Product schemas
class ProductBase(BaseModel):
    name: str
    type: str  # 'raw' or 'finished'


class ProductCreate(ProductBase):
    pass


class ProductResponse(ProductBase):
    id: int

    class Config:
        from_attributes = True


# Supplier schemas
class SupplierBase(BaseModel):
    name: str
    product_id: int
    unit_cost: float = 0.0
    lead_time_days: int = 0


class SupplierCreate(SupplierBase):
    pass


class SupplierResponse(SupplierBase):
    id: int

    class Config:
        from_attributes = True


# Inventory schemas
class InventoryItem(BaseModel):
    product_id: int
    product_name: str
    quantity: int

    class Config:
        from_attributes = True


# BOM schemas
class BOMItem(BaseModel):
    finished_product_id: int
    material_id: int
    material_name: str
    quantity: int

    class Config:
        from_attributes = True


# Purchase Order schemas
class PurchaseOrderBase(BaseModel):
    supplier_id: int
    product_id: int
    quantity: int


class PurchaseOrderCreate(PurchaseOrderBase):
    pass


class PurchaseOrderResponse(PurchaseOrderBase):
    id: int
    issue_date: date
    expected_delivery: date
    status: str

    class Config:
        from_attributes = True


# Manufacturing Order schemas
class ManufacturingOrderBase(BaseModel):
    product_id: int
    quantity: int


class ManufacturingOrderCreate(ManufacturingOrderBase):
    pass


class ManufacturingOrderResponse(ManufacturingOrderBase):
    id: int
    created_date: date
    status: str

    class Config:
        from_attributes = True


# Event schemas
class EventResponse(BaseModel):
    id: int
    type: str
    sim_date: date
    detail: Optional[str]

    class Config:
        from_attributes = True


# Day advance response
class DayAdvanceResponse(BaseModel):
    current_day: int
    simulated_date: date
    events_generated: int
    summary: dict
