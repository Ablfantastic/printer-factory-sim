"""Core simulation engine for day-by-day production cycle."""
import json
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import random

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import (
    Product, ProductType, Inventory, BOM,
    PurchaseOrder, PurchaseOrderStatus,
    ManufacturingOrder, OrderStatus, Event,
    Supplier,
)

SIMULATION_STATE_EVENT = "simulation_started"


class SimulationEngine:
    """Handles the discrete-event simulation of the production factory."""

    def __init__(self, db: Session):
        self.db = db
        self.current_day = 1
        self._load_or_init_state()

    def _load_or_init_state(self):
        """Load current simulated calendar day from DB (persists across HTTP requests)."""
        day_state = self.db.query(Event).filter(
            Event.type == SIMULATION_STATE_EVENT
        ).first()

        if not day_state:
            day_state = Event(
                type=SIMULATION_STATE_EVENT,
                sim_date=date(2026, 1, 1),
                detail=json.dumps({"current_day": 1}),
            )
            self.db.add(day_state)
            self.db.commit()
            self.current_day = 1
            return

        try:
            detail = json.loads(day_state.detail) if day_state.detail else {}
            self.current_day = int(
                detail.get("current_day", detail.get("start_day", 1))
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            self.current_day = 1

    def _persist_current_day(self) -> None:
        """Persist calendar so the next API request sees the same simulated day."""
        day_state = self.db.query(Event).filter(
            Event.type == SIMULATION_STATE_EVENT
        ).first()
        if not day_state:
            self._load_or_init_state()
            return
        detail = {}
        try:
            detail = json.loads(day_state.detail) if day_state.detail else {}
        except json.JSONDecodeError:
            pass
        detail["current_day"] = self.current_day
        day_state.detail = json.dumps(detail)
        self.db.commit()

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

        # Step 5: Advance calendar (persisted so PO issue dates and deliveries stay consistent)
        self.current_day += 1
        self._persist_current_day()

        return {
            "current_day": self.current_day,
            "simulated_date": simulated_date.isoformat(),
            "events_generated": len(events_generated),
            "summary": {
                "demand_orders": len([e for e in events_generated if "demand" in e["type"]]),
                "deliveries": len([e for e in events_generated if "delivery" in e["type"]]),
                "production": len([e for e in events_generated if "production" in e["type"]])
            }
        }

    def _finished_product_ids(self) -> List[int]:
        rows = self.db.query(Product.id).filter(
            Product.type == ProductType.FINISHED.value
        ).all()
        return [r[0] for r in rows]

    def _generate_demand(self, sim_date: date) -> List[Dict[str, Any]]:
        """Generate random manufacturing orders based on configured mean/variance."""
        events = []

        finished_ids = self._finished_product_ids()
        if not finished_ids:
            return events

        # Configurable parameters (default values)
        mean_demand = 5
        variance = 4
        capacity_per_day = 10

        # Generate random demand using normal distribution (cap so orders can clear in reasonable time)
        demand_quantity = max(0, int(random.gauss(mean_demand, variance**0.5)))
        demand_quantity = min(demand_quantity, capacity_per_day * 3)

        if demand_quantity > 0:
            product_id = random.choice(finished_ids)
            mo = ManufacturingOrder(
                created_date=sim_date,
                product_id=product_id,
                quantity=demand_quantity,
                units_produced=0,
                status=OrderStatus.PENDING.value,
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
            po.status = PurchaseOrderStatus.DELIVERED.value

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
        """Run production for released (in-progress) orders within daily capacity."""
        events = []

        capacity_per_day = 10

        in_progress = self.db.query(ManufacturingOrder).filter(
            ManufacturingOrder.status == OrderStatus.IN_PROGRESS.value
        ).order_by(ManufacturingOrder.id).all()

        produced_today = 0

        for mo in in_progress:
            if produced_today >= capacity_per_day:
                break

            prior = mo.units_produced or 0
            remaining = mo.quantity - prior
            if remaining <= 0:
                mo.status = OrderStatus.COMPLETED.value
                self.db.commit()
                continue

            batch = min(remaining, capacity_per_day - produced_today)
            # Raw materials were consumed in full when the order was released
            self._add_product_inventory(mo.product_id, batch)
            mo.units_produced = prior + batch
            produced_today += batch

            if mo.units_produced >= mo.quantity:
                mo.status = OrderStatus.COMPLETED.value
                event_type = "production_completed"
            else:
                event_type = "production_in_progress"

            self.db.commit()

            event = {
                "type": event_type,
                "sim_date": sim_date.isoformat(),
                "detail": f"Manufacturing order #{mo.id}: {batch} units produced "
                f"({mo.units_produced}/{mo.quantity})",
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

    def _add_product_inventory(self, product_id: int, quantity: int) -> None:
        """Increase on-hand stock for a product (e.g. finished goods from production)."""
        inv = self.db.query(Inventory).filter(Inventory.product_id == product_id).first()
        if inv:
            inv.quantity += quantity
        else:
            self.db.add(Inventory(product_id=product_id, quantity=quantity))

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
        
        if not self._check_bom_availability(mo.product_id, mo.quantity):
            return {"success": False, "error": "Insufficient materials"}

        # Issue full BOM to the order now so inventory reflects committed production
        self._consume_bom(mo.product_id, mo.quantity)

        mo.units_produced = 0
        mo.status = OrderStatus.IN_PROGRESS.value
        self.db.commit()

        issue_date = date(2026, 1, 1) + timedelta(days=self.current_day - 1)
        self._log_event(
            {
                "type": "order_released",
                "sim_date": issue_date.isoformat(),
                "detail": f"Manufacturing order #{order_id}: materials issued for {mo.quantity} units",
            }
        )

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

        self._log_event(
            {
                "type": "purchase_issued",
                "sim_date": issue_date.isoformat(),
                "detail": json.dumps(
                    {
                        "purchase_order_id": po.id,
                        "supplier_id": supplier_id,
                        "product_id": product_id,
                        "quantity": quantity,
                        "expected_delivery": expected_delivery.isoformat(),
                    }
                ),
            }
        )

        return {
            "success": True,
            "purchase_order_id": po.id,
            "expected_delivery": expected_delivery.isoformat(),
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
            bom_rows = []
            for b in bom_items:
                mat = self.db.query(Product).filter(Product.id == b.material_id).first()
                bom_rows.append(
                    {
                        "material_id": b.material_id,
                        "material_name": mat.name if mat else "?",
                        "quantity": b.quantity * mo.quantity,
                    }
                )

            orders.append(
                {
                    "id": mo.id,
                    "product_id": mo.product_id,
                    "quantity": mo.quantity,
                    "created_date": mo.created_date,
                    "status": mo.status,
                    "bom": bom_rows,
                }
            )
        
        return orders
