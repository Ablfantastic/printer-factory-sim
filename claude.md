# 3D Printer Production Simulator — AI Agent Guide

**Version:** 1.0  
**Last updated:** 2026-03-26  
**Purpose:** Guidance for AI agents, developers, and reviewers implementing this system.

---

## Quick Reference

```bash
# Start the API server
python run_api.py

# Launch the Streamlit dashboard
streamlit run app.py

# Initialize/reset the database
python initialize_db.py

# Load a scenario
python initialize_db.py --scenario config/scenarios/quick_start.json
```

### Port Usage
| Service | Default Port | URL |
| :--- | :--- | :--- |
| FastAPI Server | `8000` | `http://localhost:8000` |
| FastAPI Docs | `8000` | `http://localhost:8000/docs` |
| Streamlit Dashboard | `8501` | `http://localhost:8501` |

### Key Files
| File | Purpose |
| :--- | :--- |
| `src/main.py` | FastAPI application factory |
| `app.py` | Streamlit entry point |
| `src/database.py` | SQLAlchemy engine and session management |
| `src/models/*.py` | SQLModel entity definitions |
| `src/schemas/*.py` | Pydantic DTOs for request/response |
| `src/services/*.py` | Business logic services |
| `src/simulation/*.py` | SimPy environment and processes |
| `docs/PRD.md` | Full Product Requirements Document |
| `config/default.json` | Default configuration |

---

## 1. Architecture Overview

### System Flow

```
┌──────────────┐     HTTP      ┌──────────────┐
│   Streamlit  │ ◄────────────► │   FastAPI    │
│   Dashboard  │   JSON/RPC     │   REST API   │
└──────────────┘                └──────┬───────┘
                                       │
                               ┌───────▼───────┐
                               │ SimPy Engine  │
                               │ + Services    │
                               └───────┬───────┘
                                       │
                               ┌───────▼───────┐
                               │  SQLite DB    │
                               └───────────────┘
```

### Component Responsibilities

| Component | Role | Dependencies |
| :--- | :--- | :--- |
| **Streamlit** | Thin UI client; no business logic | FastAPI via HTTP |
| **FastAPI** | Request routing, validation, orchestration | Pydantic, all services |
| **SimPy Environment** | Time progression, day cycle execution | None (pure simulation) |
| **Services** | Domain logic (BOM, Inventory, Purchasing, Production) | Models, EventLogger |
| **Models (SQLModel)** | Database entities | SQLAlchemy |
| **Schemas (Pydantic)** | API serialization | None |

### Daily Simulation Loop

When "Advance Day" is called:

1. **Generate Demand** → Create random manufacturing orders based on configured mean/variance
2. **Process Deliveries** → Deliver POs whose `expected_delivery == current_date`; update inventory
3. **Process Production** → For each in-progress MO: consume BOM, respect daily capacity
4. **Log Events** → Record all state changes in `events` table
5. **Advance Calendar** → `current_date += 1 day`

**Order of operations matters:** See §7.1 of PRD.md for detailed pseudocode.

---

## 2. Data Model

### Core Tables (SQLite)

#### products
| Column | Type | Constraints |
| :--- | :--- | :--- |
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL, UNIQUE |
| type | TEXT | CHECK(type IN ('raw', 'finished')) |
| assembly_time_hours | REAL | DEFAULT NULL |

#### suppliers
| Column | Type | Constraints |
| :--- | :--- | :--- |
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| name | TEXT | NOT NULL |
| product_id | INTEGER | FK → products.id |
| lead_time_days | INTEGER | NOT NULL |
| base_unit_cost | REAL | NOT NULL |
| pricing_unit | TEXT | DEFAULT 'unit' |
| units_per_pricing_unit | INTEGER | DEFAULT 1 |

#### inventory
| Column | Type | Constraints |
| :--- | :--- | :--- |
| product_id | INTEGER | PK, FK → products.id |
| quantity | INTEGER | DEFAULT 0 |

#### bom
| Column | Type | Constraints |
| :--- | :--- | :--- |
| finished_product_id | INTEGER | PK, FK → products.id |
| material_id | INTEGER | PK, FK → products.id |
| quantity | INTEGER | NOT NULL |

#### purchase_orders
| Column | Type | Constraints |
| :--- | :--- | :--- |
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| supplier_id | INTEGER | FK → suppliers.id |
| product_id | INTEGER | FK → products.id |
| quantity | INTEGER | NOT NULL |
| issue_date | DATE | NOT NULL |
| expected_delivery | DATE | NOT NULL |
| actual_delivery | DATE | NULLABLE |
| status | TEXT | pending \| shipped \| delivered \| cancelled |
| total_cost | REAL | NULLABLE |

#### manufacturing_orders
| Column | Type | Constraints |
| :--- | :--- | :--- |
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| created_date | DATE | NOT NULL |
| product_id | INTEGER | FK → products.id |
| quantity | INTEGER | NOT NULL |
| released_date | DATE | NULLABLE |
| completed_date | DATE | NULLABLE |
| status | TEXT | pending \| in_progress \| completed \| cancelled |
| materials_consumed | JSON | NULLABLE |

#### events
| Column | Type | Constraints |
| :--- | :--- | :--- |
| id | INTEGER | PRIMARY KEY AUTOINCREMENT |
| event_type | TEXT | NOT NULL |
| sim_date | DATE | NOT NULL |
| timestamp | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP |
| entity_type | TEXT | NULLABLE |
| entity_id | INTEGER | NULLABLE |
| detail | TEXT | JSON payload |

#### configuration
| Column | Type | Constraints |
| :--- | :--- | :--- |
| key | TEXT | PRIMARY KEY |
| value | TEXT | JSON-encoded |
| description | TEXT | NULLABLE |

---

## 3. Tech Stack

| Layer | Technology | Version | Notes |
| :--- | :--- | :--- | :--- |
| Language | Python | 3.11+ | Type hints required |
| Simulation | SimPy | 4.x | Discrete-event engine |
| API | FastAPI | 0.109+ | Auto OpenAPI docs |
| ORM | SQLModel | 0.0.x | SQLAlchemy + Pydantic |
| Validation | Pydantic | 2.x | v2 syntax |
| UI | Streamlit | 1.30+ | Dashboard framework |
| Charts | matplotlib | 3.8+ | Integration with Streamlit |
| Runtime | uvicorn | 0.27+ | ASGI server |

### Key Design Decisions

1. **SimPy over custom loop**: Provides natural time progression and makes modeling staggered deliveries easier.

2. **Strict warehouse enforcement**: If a delivery would exceed capacity, it is rejected (not capped).

3. **MO status flow**: pending → in_progress (on release) → completed (materials consumed during daily processing)

4. **Capacity = count limit**: Not hours-based; configurable printers/day.

5. **Tiered pricing**: Implemented at application layer using `pricing_unit` and `units_per_pricing_unit`.

6. **BOM references treated as additional items**: `pcb_ref: CTRL-V2` adds a separate line item, not replacement.

---

## 4. API Endpoints

All endpoints under `/api/v1`. Base URL: `http://localhost:8000`

### Simulation Control

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/simulation/status` | Current date, day count |
| POST | `/api/v1/simulation/day/advance` | Run one day cycle |
| POST | `/api/v1/simulation/reset` | Reset to initial state |
| GET | `/api/v1/simulation/configuration` | All config values |
| PUT | `/api/v1/simulation/configuration/{key}` | Update single setting |

### Products

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/products` | List all products |
| POST | `/api/v1/products` | Create product |
| GET | `/api/v1/products/{id}` | Single product |
| PUT | `/api/v1/products/{id}` | Update product |
| DELETE | `/api/v1/products/{id}` | Delete (if no deps) |

### Suppliers

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/suppliers` | List suppliers |
| GET | `/api/v1/suppliers?product_id=X` | Filter by product |
| POST | `/api/v1/suppliers` | Create supplier |
| PUT | `/api/v1/suppliers/{id}` | Update supplier |

### Inventory

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/inventory` | All stock levels |
| GET | `/api/v1/inventory/{product_id}` | Single product |
| GET | `/api/v1/inventory/shortages` | Items below demand |
| POST | `/api/v1/inventory/adjust` | Manual adjustment |

### Bill of Materials

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/bom` | All BOM entries |
| GET | `/api/v1/bom/{finished_id}` | BOM for product |
| POST | `/api/v1/bom` | Add BOM entry |
| PUT | `/api/v1/bom/{finished}/{material}` | Update quantity |
| DELETE | `/api/v1/bom/{finished}/{material}` | Remove entry |

### Manufacturing Orders

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/manufacturing-orders` | All MOs |
| GET | `/api/v1/manufacturing-orders?status=pending` | Filter |
| POST | `/api/v1/manufacturing-orders/{id}/release` | Release to production |
| GET | `/api/v1/manufacturing-orders/{id}/bom` | Expand BOM |
| DELETE | `/api/v1/manufacturing-orders/{id}` | Cancel order |

### Purchase Orders

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/purchase-orders` | All POs |
| POST | `/api/v1/purchase-orders` | Create PO |
| GET | `/api/v1/purchase-orders/{id}` | Single PO |
| DELETE | `/api/v1/purchase-orders/{id}` | Cancel PO |
| GET | `/api/v1/purchase-orders/calculate-cost` | Preview tiered pricing |

### Events & Export

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/v1/events` | Event history |
| GET | `/api/v1/events/timeline` | Aggregated for charts |
| POST | `/api/v1/export/state` | Full snapshot |
| POST | `/api/v1/export/inventory` | Inventory only |
| POST | `/api/v1/import/state` | Restore from JSON |

---

## 5. Event Types

Every significant action generates an event:

| Event Type | Triggered When |
| :--- | :--- |
| `DEMAND_GENERATED` | New MO created by random demand |
| `MO_RELEASED` | Planner releases MO to production |
| `PRODUCTION_STARTED` | First unit of MO processed |
| `PRODUCTION_COMPLETED` | MO fully manufactured |
| `PO_ISSUED` | Purchase order created |
| `PO_SHIPPED` | Supplier ships order |
| `PO_DELIVERED` | Goods arrive at warehouse |
| `INVENTORY_ADJUSTMENT` | Any stock change |
| `CAPACITY_HIT_LIMIT` | Daily capacity exhausted |
| `STOCKOUT_WARNING` | Material shortage detected |
| `WAREHOUSE_FULL` | Delivery exceeds capacity |
| `DAY_ADVANCED` | Simulation cycle complete |

---

## 6. Configuration Schema

Loadable via `config/default.json`:

```json
{
  "global": {
    "capacity_per_day": 10,
    "warehouse_capacity": 500,
    "demand_mean": 2.0,
    "demand_variance": 1.5
  },
  "products": [
    {"id": 1, "name": "P3D-Classic", "type": "finished"},
    {"id": 10, "name": "kit_piezas", "type": "raw"}
  ],
  "bom": [
    {
      "finished_product_id": 1,
      "entries": {
        "kit_piezas": 1,
        "CTRL-V2": 1
      }
    }
  ],
  "suppliers": [
    {
      "name": "Acme Components",
      "product_name": "kit_piezas",
      "unit_cost": 50.0,
      "lead_time_days": 5,
      "pricing_unit": "box",
      "units_per_pricing_unit": 100
    }
  ],
  "initial_inventory": {
    "kit_piezas": 30
  }
}
```

---

## 7. Implementation Guidelines

### Code Style

- **Type hints required** for all function signatures
- **Docstrings** for public functions (Google or NumPy style)
- **No `print()` in production code** — use `logging` module
- **Business logic in services**, not in API handlers
- **One class/function per concern** — avoid god objects

### Example: Creating a Purchase Order

```python
from fastapi import APIRouter, Depends, HTTPException
from src.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderResponse
from src.services.purchasing_service import create_purchase_order

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])

@router.post("", response_model=PurcahseOrderResponse)
async def create_po(po_data: PurchaseOrderCreate):
    try:
        po = await create_purchase_order(po_data)
        return po
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Example: Daily Simulation Step

```python
import simpy
from datetime import timedelta
from src.services import demand, purchasing, production, events

def run_day(env: simpy.Environment, current_date: date):
    # Step 1: Generate demand
    new_orders = demand.generate_orders(current_date)
    
    # Step 2: Process deliveries
    arriving_pos = purchasing.get_due_deliveries(current_date)
    for po in arriving_pos:
        inventory.receive_purchase(po)
        events.log('PO_DELIVERED', current_date, po_id=po.id)
    
    # Step 3: Production
    remaining = config.capacity_per_day
    for mo in production.get_active_orders():
        if remaining <= 0:
            break
        if inventory.has_materials(mo):
            produced = min(mo.remaining, remaining)
            inventory.consume_bom(mo.product_id, produced)
            remaining -= produced
    
    # Step 4: Advance calendar
    env.current_date += timedelta(days=1)
```

### Directory Structure Refresher

```
printer-factory-sim/
├── src/
│   ├── api/              # FastAPI routers
│   ├── models/           # SQLModel entities
│   ├── schemas/          # Pydantic DTOs
│   ├── services/         # Business logic
│   └── simulation/       # SimPy processes
├── config/               # JSON configs
├── data/                 # SQLite database
├── docs/                 # Documentation
├── app.py                # Streamlit entry
└── run_api.py            # FastAPI standalone
```

---

## 8. Development Workflow

### Phase Checklist

- [ ] **Phase 1: Foundation** — DB schema, CRUD APIs, config loader
- [ ] **Phase 2: Core Simulation** — SimPy setup, demand generation, event logging
- [ ] **Phase 3: Production Logic** — Capacity, BOM consumption, warehouse enforcement
- [ ] **Phase 4: UI Integration** — Streamlit dashboard, charts
- [ ] **Phase 5: Polish** — Import/export, edge cases, documentation

### Before Making Changes

1. Review `docs/PRD.md` for requirements context
2. Check existing tests (when added) don't break
3. Verify API endpoint parity with UI updates
4. Update this `claude.md` if behavior changes

### Testing Commands (Future)

```bash
# When tests are added
pytest tests/
pytest tests/test_simulation.py -v
```

---

## 9. Common Pitfalls

| Issue | Why It Happens | How to Avoid |
| :--- | :--- | :--- |
| Incorrect BOM expansion | Not resolving `pcb_ref` strings to product IDs | Always query products table when expanding |
| Warehouse over-capacity | Failing to check before receiving PO | Call `can_fit_in_warehouse()` before any receive |
| Double-consuming materials | Consuming on release vs. during production | Only consume during daily production step |
| Wrong event timestamps | Using real-time instead of simulated date | Always pass `sim_date` from env |
| Tiered pricing errors | Not dividing remainder proportionally | Use formula in §7.3 of PRD.md |
| Capacity not respected | Processing all MOs regardless of limit | Track `remaining_capacity` and break when exhausted |

---

## 10. Troubleshooting

### "Database locked" Error

**Cause:** Multiple processes accessing SQLite simultaneously  
**Fix:** Ensure only one process runs at a time, or enable WAL mode in connection settings

### "Module not found: simpy"

**Cause:** Virtual environment not activated or dependencies not installed  
**Fix:** 
```bash
pip install -r requirements.txt
```

### API Returns 500 on Day Advance

**Cause:** Missing configuration or invalid BOM reference  
**Fix:** Check `configuration` table has all required keys; verify product names in BOM exist

### Demand Always Zero

**Cause:** Normal distribution with low mean/high variance can produce negative values  
**Fix:** Ensure `max(0, int(random_value))` in demand service

---

## 11. Glossary

| Term | Meaning |
| :--- | :--- |
| **MO** | Manufacturing Order — produce finished goods |
| **PO** | Purchase Order — buy raw materials |
| **BOM** | Bill of Materials — recipe for a product |
| **Sim Day** | One iteration of the simulation loop |
| **Lead Time** | Days from PO issuance to delivery |

---

## 12. References

- [PRD.md](docs/PRD.md) — Full requirements document
- [SPEC.md](docs/SPEC.md) — Original specification (if available)
- [SQLite Docs](https://www.sqlite.org/docs.html)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SimPy Docs](https://simpy.readthedocs.io/)
- [Streamlit Docs](https://docs.streamlit.io/)

---

*Keep this document synced with implementation changes.*
