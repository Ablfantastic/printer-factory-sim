from sqlalchemy import Column, Float, Integer, String, Text

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)


class Inventory(Base):
    __tablename__ = "inventory"

    product_id = Column(Integer, primary_key=True)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=0)


class PrinterModel(Base):
    """Finished printer models produced by the manufacturer."""
    __tablename__ = "printer_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    wholesale_price = Column(Float, nullable=False)
    production_days = Column(Integer, nullable=False, default=1)
    daily_capacity = Column(Integer, nullable=False, default=5)
    bom = Column(Text, nullable=True)  # JSON: {"part_name": qty, ...}


class FinishedStock(Base):
    """Finished-printer inventory ready to ship."""
    __tablename__ = "finished_stock"

    model = Column(String, primary_key=True)
    quantity = Column(Integer, nullable=False, default=0)


class SalesOrder(Base):
    """Inbound orders received from retailers."""
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    retailer = Column(String, nullable=False)
    model = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=True)
    total_price = Column(Float, nullable=True)
    placed_day = Column(Integer, nullable=False)
    released_day = Column(Integer, nullable=True)
    production_start_day = Column(Integer, nullable=True)
    expected_delivery_day = Column(Integer, nullable=True)
    shipped_day = Column(Integer, nullable=True)
    delivered_day = Column(Integer, nullable=True)
    status = Column(String, nullable=False)  # pending/released/in_progress/completed/shipped/delivered


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_name = Column(String, nullable=False)
    supplier_url = Column(String, nullable=False)
    provider_order_id = Column(Integer, nullable=False)
    provider_product_id = Column(Integer, nullable=False)
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    placed_day = Column(Integer, nullable=False)
    expected_delivery_day = Column(Integer, nullable=False)
    delivered_day = Column(Integer)
    status = Column(String, nullable=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sim_day = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    entity_type = Column(String)
    entity_id = Column(Integer)
    detail = Column(Text)
    created_at = Column(String, nullable=False)


class SimState(Base):
    __tablename__ = "sim_state"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
