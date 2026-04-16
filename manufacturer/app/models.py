"""SQLAlchemy models for the simulation database."""
from datetime import date
from enum import Enum as PyEnum
from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.database import Base


class ProductType(PyEnum):
    RAW = "raw"
    FINISHED = "finished"


class OrderStatus(PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class PurchaseOrderStatus(PyEnum):
    PENDING = "pending"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)  # 'raw' or 'finished'

    suppliers = relationship("Supplier", back_populates="product")
    inventory = relationship("Inventory", back_populates="product", uselist=False)
    bom_as_finished = relationship("BOM", foreign_keys="BOM.finished_product_id", back_populates="finished_product")
    bom_as_material = relationship("BOM", foreign_keys="BOM.material_id", back_populates="material")
    purchase_orders = relationship("PurchaseOrder", back_populates="product")
    manufacturing_orders = relationship("ManufacturingOrder", back_populates="product")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_cost = Column(Float, default=0.0)
    lead_time_days = Column(Integer, default=0)

    product = relationship("Product", back_populates="suppliers")
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier")


class Inventory(Base):
    __tablename__ = "inventory"

    product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    quantity = Column(Integer, default=0)

    product = relationship("Product", back_populates="inventory")


class BOM(Base):
    __tablename__ = "bom"

    finished_product_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    material_id = Column(Integer, ForeignKey("products.id"), primary_key=True)
    quantity = Column(Integer, nullable=False, default=1)

    finished_product = relationship("Product", foreign_keys=[finished_product_id], back_populates="bom_as_finished")
    material = relationship("Product", foreign_keys=[material_id], back_populates="bom_as_material")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    issue_date = Column(Date, nullable=False)
    expected_delivery = Column(Date, nullable=False)
    status = Column(String, default="pending")

    supplier = relationship("Supplier", back_populates="purchase_orders")
    product = relationship("Product", back_populates="purchase_orders")


class ManufacturingOrder(Base):
    __tablename__ = "manufacturing_orders"

    id = Column(Integer, primary_key=True, index=True)
    created_date = Column(Date, nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String, default="pending")

    product = relationship("Product", back_populates="manufacturing_orders")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False)
    sim_date = Column(Date, nullable=False)
    detail = Column(String)  # JSON string for structured data
