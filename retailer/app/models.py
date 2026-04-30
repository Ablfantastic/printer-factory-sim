from sqlalchemy import Column, Float, Integer, String, Text

from app.database import Base


class CatalogItem(Base):
    __tablename__ = "catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String, unique=True, nullable=False)
    retail_price = Column(Float, nullable=False)
    wholesale_price = Column(Float, nullable=True)


class Stock(Base):
    __tablename__ = "stock"

    model = Column(String, primary_key=True)
    quantity = Column(Integer, nullable=False, default=0)


class CustomerOrder(Base):
    __tablename__ = "customer_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer = Column(String, nullable=False)
    model = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    placed_day = Column(Integer, nullable=False)
    fulfilled_day = Column(Integer, nullable=True)
    status = Column(String, nullable=False)  # pending / fulfilled / backordered / cancelled


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    manufacturer_order_id = Column(Integer, nullable=True)
    model = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=True)
    total_price = Column(Float, nullable=True)
    placed_day = Column(Integer, nullable=False)
    expected_delivery_day = Column(Integer, nullable=True)
    delivered_day = Column(Integer, nullable=True)
    status = Column(String, nullable=False)  # pending / confirmed / in_progress / shipped / delivered


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sim_day = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    entity_type = Column(String, nullable=True)
    entity_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(String, nullable=False)


class SimState(Base):
    __tablename__ = "sim_state"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
