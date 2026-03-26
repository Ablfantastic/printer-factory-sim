"""FastAPI application for 3D Printer Production Simulator."""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date
from typing import List

from app.database import engine, Base, get_db
from app import models, schemas
from app.simulation import SimulationEngine

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="3D Printer Production Simulator API",
    description="REST API for simulating a 3D printer production factory",
    version="0.1.0"
)

# CORS middleware for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulation engine instance (one per request via dependency)
def get_simulation(db: Session = Depends(get_db)) -> SimulationEngine:
    return SimulationEngine(db)


# ==================== Calendar ====================

@app.get("/api/calendar")
def get_calendar(db: Session = Depends(get_db)):
    """Get current simulated day and date."""
    sim = get_simulation(db)
    current_date = date(2026, 1, 1) + __import__("datetime").timedelta(days=sim.current_day - 1)
    return {
        "current_day": sim.current_day,
        "simulated_date": current_date.isoformat()
    }


@app.post("/api/day/advance")
def advance_day(sim: SimulationEngine = Depends(get_simulation)):
    """Run a single day simulation cycle."""
    return sim.advance_day()


# ==================== Inventory ====================

@app.get("/api/inventory", response_model=List[schemas.InventoryItem])
def get_inventory(db: Session = Depends(get_db)):
    """Get current inventory levels."""
    sim = get_simulation(db)
    return sim.get_inventory()


# ==================== Orders ====================

@app.get("/api/orders/pending", response_model=List[schemas.ManufacturingOrderResponse])
def get_pending_orders(db: Session = Depends(get_db)):
    """Get all pending manufacturing orders."""
    sim = get_simulation(db)
    return sim.get_pending_orders()


@app.post("/api/orders/{order_id}/release")
def release_order(
    order_id: int,
    sim: SimulationEngine = Depends(get_simulation)
):
    """Release a manufacturing order to production."""
    result = sim.release_order(order_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to release order"))
    return result


# ==================== Purchases ====================

@app.get("/api/suppliers")
def get_suppliers(db: Session = Depends(get_db)):
    """Get supplier catalog."""
    suppliers = db.query(models.Supplier).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "product_id": s.product_id,
            "unit_cost": s.unit_cost,
            "lead_time_days": s.lead_time_days
        }
        for s in suppliers
    ]


@app.get("/api/products")
def get_products(db: Session = Depends(get_db)):
    """Get products (raw and finished)."""
    products = db.query(models.Product).all()
    return [
        {"id": p.id, "name": p.name, "type": p.type}
        for p in products
    ]


@app.post("/api/purchases", response_model=schemas.PurchaseOrderResponse)
def create_purchase_order(
    purchase: schemas.PurchaseOrderCreate,
    sim: SimulationEngine = Depends(get_simulation)
):
    """Create a new purchase order."""
    result = sim.create_purchase_order(
        supplier_id=purchase.supplier_id,
        product_id=purchase.product_id,
        quantity=purchase.quantity
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create PO"))
    
    # Fetch and return the created PO
    po = db.query(models.PurchaseOrder).filter(
        models.PurchaseOrder.id == result["purchase_order_id"]
    ).first()
    
    return schemas.PurchaseOrderResponse.from_orm(po)


# ==================== Events ====================

@app.get("/api/events", response_model=List[schemas.EventResponse])
def get_events(
    since_day: int = None,
    event_type: str = None,
    db: Session = Depends(get_db)
):
    """Get event history with optional filters."""
    query = db.query(models.Event)
    
    if since_day:
        since_date = date(2026, 1, 1) + __import__("datetime").timedelta(days=since_day - 1)
        query = query.filter(models.Event.sim_date >= since_date)
    
    if event_type:
        query = query.filter(models.Event.type == event_type)
    
    events = query.order_by(models.Event.sim_date, models.Event.id).all()
    return [schemas.EventResponse.from_orm(e) for e in events]


# ==================== Health Check ====================

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "printer-factory-simulator"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "name": "3D Printer Production Simulator",
        "version": "0.1.0",
        "docs": "/docs"
    }
