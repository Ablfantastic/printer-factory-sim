"""Core simulation engine for day-by-day production cycle."""
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import random

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import (
    Product, ProductType, Inventory, BOM,
    PurchaseOrder, PurchaseOrderStatus,
    ManufacturingOrder, OrderStatus, Event
)


class SimulationEngine:
    """Handles the discrete-event simulation of the production factory."""

    def __init__(self, db: Session):
        self.db = db
        self.current_day = 1
        self._load_or_init_state()

    def _load_or_init_state(self):
        """Load current state from database or initialize if empty."""
        day_state = self.db.query(Event).filter(
            Event.type == "simulation_started"
        ).first()
        
        if day_state:
            # Parse starting day from event detail
            try:
                import json
                detail = json.loads(day_state.detail) if day_state.detail else {}
                self.current_day = detail.get("start_day", 1)
            except:
                pass

    def advance_day(self) -> Dict[str, Any]:
        """
        Run a single day simulation cycle.
        
        Daily flow (Section 9):
        1. Generate new manufacturing orders (demand)
        2. Process pending deliveries (PO arrivals)
        3. Process production (consume BOM, respect capacity)
        4. Log all events
        5. Advance simulated calendar
        """
        events_generated = []
        simulated_date = date(2026, 1, 1) + timedelta(days=self.current_day - 1)

        # Step 1: Generate demand (new manufacturing orders)
        new_orders = self._generate_demand(simulated_date)
        events_generated.extend(new_orders)

        # Step 2: Process pending deliveries (PO arrivals)
        delivery_events = self._process_deliveries(simulated_date)
        events_generated.extend(delivery_events)

        # Step 3: Process production
        production_events = self._process_production(simulated_date)
        events_generated.extend(production_events)

        # Step 4: All events are logged during each step

        # Step 5: Advance calendar
        self.current_day += 1

        return {
            "current_day": self.current_day - 1,
            "simulated_date": simulated_date.isoformat(),
            "events_generated": len(events_generated),
            "summary": {
                "demand_orders": len([e for e in events_generated if "demand" in e["type"]]),
                "deliveries": len([e for e in events_generated if "delivery" in e["type"]]),
                "production": len([e for e in events_generated if "production" in e["type"]])
            }
        }

    def _generate_demand(self, sim_date: date) -> List[Dict[str, Any]]:
        """Generate random manufacturing orders based on configured mean/variance."""
        events = []
        
        # Configurable parameters (default values)
        mean_demand = 5
        variance = 4
        
        # Generate random demand using normal distribution
        demand_quantity = max(0, int(random.gauss(mean_demand, variance**0.5)))
        
        if demand_quantity > 0:
            # Create manufacturing order for default printer model
            mo = ManufacturingOrder(
                created_date=sim_date,
                product_id=1,  # Default to first finished product
                quantity=demand_quantity,
                status=OrderStatus.PENDING.value
            )
            self.db.add(mo)
            self.db.commit()
            
            event = {
                "type": "demand_generated",
                "sim_date": sim_date.isoformat(),
                "detail": f"New manufacturing order #{mo.id} for {demand_quantity} units"
            }
            self._log_event(event)
            events.append(event)

        return events

    def _process_deliveries(self, sim_date: date) -> List[Dict[str, Any]]:
        """Process purchase orders that arrive today."""
        events = []
        
        # Find POs due today
        due_pos = self.db.query(PurchaseOrder).filter(
            and_(
                PurchaseOrder.expected_delivery == sim_date,
                PurchaseOrder.status != PurchaseOrderStatus.DELIVERED.value
            )
        ).all()

        for po in due_pos:
            # Update PO status
            po.status = PurchaseOrderStatus.SHIPPED.value
            
            # Add materials to inventory
            inv = self.db.query(Inventory).filter(
                Inventory.product_id == po.product_id
            ).first()
            
            if inv:
                inv.quantity += po.quantity
            else:
                inv = Inventory(product_id=po.product_id, quantity=po.quantity)
                self.db.add(inv)
            
            self.db.commit()
            
            event = {
                "type": "shipment_delivered",
                "sim_date": sim_date.isoformat(),
                "detail": f"Purchase order #{po.id}: {po.quantity} units delivered"
            }
            self._log_event(event)
            events.append(event)

        return events

    def _process_production(self, sim_date: date) -> List[Dict[str, Any]]:
        """Process manufacturing orders within daily capacity limits."""
        events = []
        
        # Get capacity from config (default)
        capacity_per_day = 10
        
        # Get pending orders
        pending_orders = self.db.query(ManufacturingOrder).filter(
            ManufacturingOrder.status == OrderStatus.PENDING.value
        ).all()

        produced_today = 0
        
        for mo in pending_orders:
            if produced_today >= capacity_per_day:
                break
            
            # Check if we have enough materials (simplified check)
            if self._check_bom_availability(mo.product_id, min(mo.quantity, capacity_per_day - produced_today)):
                # Consume materials and complete production
                consume_qty = min(mo.quantity, capacity_per_day - produced_today)
                self._consume_bom(mo.product_id, consume_qty)
                
                produced_today += consume_qty
                
                if consume_qty >= mo.quantity:
                    mo.status = OrderStatus.COMPLETED.value
                    event_type = "production_completed"
                else:
                    mo.status = OrderStatus.IN_PROGRESS.value
                    event_type = "production_started"
                
                self.db.commit()
                
                event = {
                    "type": event_type,
                    "sim_date": sim_date.isoformat(),
                    "detail": f"Manufacturing order #{mo.id}: {consume_qty} units processed"
                }
                self._log_event(event)
                events.append(event)

        return events

    def _check_bom_availability(self, product_id: int, quantity: int) -> bool:
        """Check if BOM materials are available for production."""
        bom_items = self.db.query(BOM).filter(
            BOM.finished_product_id == product_id
        ).all()
        
        for item in bom_items:
            inv = self.db.query(Inventory).filter(
                Inventory.product_id == item.material_id
            ).first()
            
            required = item.quantity * quantity
            available = inv.quantity if inv else 0
            
            if available < required:
                return False
        
        return True

    def _consume_bom(self, product_id: int, quantity: int):
        """Consume BOM materials for production."""
        bom_items = self.db.query(BOM).filter(
            BOM.finished_product_id == product_id
        ).all()
        
        for item in bom_items:
            inv = self.db.query(Inventory).filter(
                Inventory.product_id == item.material_id
            ).first()
            
            if inv:
                inv.quantity -= item.quantity * quantity

    def _log_event(self, event: Dict[str, Any]):
        """Log an event to the database."""
        db_event = Event(
            type=event["type"],
            sim_date=date.fromisoformat(event["sim_date"]),
            detail=event.get("detail")
        )
        self.db.add(db_event)
        self.db.commit()

    def release_order(self, order_id: int) -> Dict[str, Any]:
        """Release a manufacturing order to production."""
        mo = self.db.query(ManufacturingOrder).filter(
            ManufacturingOrder.id == order_id
        ).first()
        
        if not mo:
            return {"success": False, "error": "Order not found"}
        
        if mo.status != OrderStatus.PENDING.value:
            return {"success": False, "error": "Order not in pending status"}
        
        # Check BOM availability
        if not self._check_bom_availability(mo.product_id, mo.quantity):
            return {"success": False, "error": "Insufficient materials"}
        
        # Mark as in progress
        mo.status = OrderStatus.IN_PROGRESS.value
        self.db.commit()
        
        return {"success": True, "order_id": order_id, "status": "in_progress"}

    def create_purchase_order(
        self, 
        supplier_id: int, 
        product_id: int, 
        quantity: int
    ) -> Dict[str, Any]:
        """Create a new purchase order."""
        supplier = self.db.query(Supplier).filter(
            Supplier.id == supplier_id
        ).first()
        
        if not supplier:
            return {"success": False, "error": "Supplier not found"}
        
        issue_date = date(2026, 1, 1) + timedelta(days=self.current_day - 1)
        expected_delivery = issue_date + timedelta(days=supplier.lead_time_days)
        
        po = PurchaseOrder(
            supplier_id=supplier_id,
            product_id=product_id,
            quantity=quantity,
            issue_date=issue_date,
            expected_delivery=expected_delivery,
            status=PurchaseOrderStatus.PENDING.value
        )
        self.db.add(po)
        self.db.commit()
        
        return {
            "success": True,
            "purchase_order_id": po.id,
            "expected_delivery": expected_delivery.isoformat()
        }

    def get_inventory(self) -> List[Dict[str, Any]]:
        """Get current inventory levels."""
        items = []
        # Query inventory joined with product names
        results = self.db.query(
            Inventory.product_id,
            Product.name.label('product_name'),
            Inventory.quantity
        ).join(Product, Inventory.product_id == Product.id).all()

        for product_id, product_name, quantity in results:
            items.append({
                "product_id": product_id,
                "product_name": product_name,
                "quantity": quantity
            })

        return items

    def get_pending_orders(self) -> List[Dict[str, Any]]:
        """Get all pending manufacturing orders with BOM details."""
        orders = []
        mos = self.db.query(ManufacturingOrder).filter(
            ManufacturingOrder.status == OrderStatus.PENDING.value
        ).all()
        
        for mo in mos:
            bom_items = self.db.query(BOM).filter(
                BOM.finished_product_id == mo.product_id
            ).all()
            
            orders.append({
                "id": mo.id,
                "product_id": mo.product_id,
                "quantity": mo.quantity,
                "created_date": mo.created_date.isoformat(),
                "bom": [
                    {
                        "material_id": b.material_id,
                        "quantity": b.quantity * mo.quantity
                    }
                    for b in bom_items
                ]
            })
        
        return orders
