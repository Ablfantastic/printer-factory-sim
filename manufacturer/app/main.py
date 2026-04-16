"""FastAPI application for 3D Printer Production Simulator."""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import List

from app.database import engine, Base, get_db, run_sqlite_migrations
from app import models, schemas
from app.simulation import SimulationEngine

# Create database tables
Base.metadata.create_all(bind=engine)
run_sqlite_migrations()

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


@app.post("/api/simulation/reset")
def reset_simulation():
    """
    Reset the simulation to a fresh seeded state (day 1, default inventory, no open orders).
    """
    from app.seed import reset_simulation_data

    reset_simulation_data()
    return {"success": True, "message": "Simulation reset to initial state."}


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


@app.get("/api/purchasing/eta", response_model=schemas.PurchasingEtaResponse)
def get_purchasing_eta(db: Session = Depends(get_db)):
    """
    Lead time per supplier–material (if you place a PO today) and ETA for open POs.
    Arrival dates match PO logic: issue_date (simulated today) + lead_time_days.
    """
    sim = get_simulation(db)
    today = date(2026, 1, 1) + timedelta(days=sim.current_day - 1)

    product_names = {p.id: p.name for p in db.query(models.Product).all()}

    catalog: List[schemas.SupplierMaterialLeadTime] = []
    for s in db.query(models.Supplier).order_by(models.Supplier.id).all():
        lead = s.lead_time_days or 0
        arrival = today + timedelta(days=lead)
        catalog.append(
            schemas.SupplierMaterialLeadTime(
                supplier_id=s.id,
                supplier_name=s.name,
                product_id=s.product_id,
                material_name=product_names.get(s.product_id, "?"),
                lead_time_days=lead,
                arrival_date_if_ordered_today=arrival,
                days_to_arrival_if_ordered_today=lead,
            )
        )

    open_pos: List[schemas.OpenPurchaseOrderEta] = []
    for po in (
        db.query(models.PurchaseOrder)
        .filter(models.PurchaseOrder.status != models.PurchaseOrderStatus.DELIVERED.value)
        .order_by(models.PurchaseOrder.expected_delivery, models.PurchaseOrder.id)
        .all()
    ):
        sup = db.query(models.Supplier).filter(models.Supplier.id == po.supplier_id).first()
        days_left = (po.expected_delivery - today).days
        open_pos.append(
            schemas.OpenPurchaseOrderEta(
                id=po.id,
                supplier_name=sup.name if sup else "?",
                material_name=product_names.get(po.product_id, "?"),
                quantity=po.quantity,
                issue_date=po.issue_date,
                expected_delivery=po.expected_delivery,
                status=po.status,
                days_until_delivery=max(0, days_left),
            )
        )

    return schemas.PurchasingEtaResponse(
        simulated_date=today,
        catalog=catalog,
        open_purchase_orders=open_pos,
    )


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
    po = sim.db.query(models.PurchaseOrder).filter(
        models.PurchaseOrder.id == result["purchase_order_id"]
    ).first()
    
    return schemas.PurchaseOrderResponse.model_validate(po)


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
    return [schemas.EventResponse.model_validate(e) for e in events]


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
