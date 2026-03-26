#!/usr/bin/env python3
"""
Create GitHub Issues for the 3D Printer Production Simulator project.

Usage:
    # Dry run - preview issues only:
    python scripts/create_github_issues.py --dry-run
    
    # Via GitHub CLI (requires authentication):
    python scripts/create_github_issues.py --with-cli
"""

import sys


# ============================================================================
# MILESTONE DEFINITIONS
# ============================================================================

MILESTONES = [
    "Phase 1: Foundation",
    "Phase 2: Core Simulation", 
    "Phase 3: Production Logic",
    "Phase 4: UI Integration",
    "Phase 5: Polish & Export"
]

ISSUES = [
    # ================================================================
    # PHASE 1: Foundation
    # ================================================================
    {
        "title": "🏗️ Set up project structure and dependencies",
        "milestone": "Phase 1: Foundation",
        "labels": ["setup", "infrastructure", "good first issue"],
        "body": """## Description
Initialize the repository with proper directory structure, configuration files, and all required dependencies.

## Tasks
- [ ] Create directory structure (`src/`, `docs/`, `config/`, `data/`)
- [ ] Create `requirements.txt` with all dependencies
- [ ] Create `.env.example` for environment variables
- [ ] Add `.gitignore` for Python projects
- [ ] Initialize Git repository (if not already done)
- [ ] Create initial README.md with project overview

## Acceptance Criteria
- [ ] Project clones and runs without errors
- [ ] `pip install -r requirements.txt` completes successfully
- [ ] Directory structure matches specification in `claude.md`"""
    },
    {
        "title": "🗄️ Design and implement database schema",
        "milestone": "Phase 1: Foundation",
        "labels": ["database", "backend", "priority-high"],
        "body": """## Description
Set up SQLite database with all core tables as defined in the PRD.

## Tasks
- [ ] Create `src/database.py` with SQLAlchemy engine and SessionLocal
- [ ] Implement SQLModel entities for all 8 tables:
  - `products`
  - `suppliers`
  - `inventory`
  - `bom` (Bill of Materials)
  - `purchase_orders`
  - `manufacturing_orders`
  - `events`
  - `configuration`
- [ ] Create database initialization script `initialize_db.py`
- [ ] Add table creation with proper foreign key constraints

## Acceptance Criteria
- [ ] All 8 tables created with correct columns and constraints
- [ ] Foreign key relationships working properly
- [ ] Database file created at `data/simulation.db`"""
    },
    {
        "title": "📦 Implement Product model and CRUD operations",
        "milestone": "Phase 1: Foundation",
        "labels": ["backend", "api", "model"],
        "body": """## Description
Create the Product entity and REST API endpoints for basic CRUD operations.

## Tasks
- [ ] Define SQLModel for `Product` table
- [ ] Create Pydantic schemas: `ProductBase`, `ProductCreate`, `ProductUpdate`, `ProductResponse`
- [ ] Implement FastAPI router at `/api/v1/products`
- [ ] Endpoints: GET list, GET single, POST create, PUT update, DELETE

## Product Fields
- id: int (PK, auto-increment)
- name: str (unique, not null)
- type: str ('raw' | 'finished')
- assembly_time_hours: float (optional)

## Acceptance Criteria
- [ ] All endpoints return correct status codes
- [ ] Validation prevents invalid product types
- [ ] OpenAPI docs show endpoints correctly at `/docs`"""
    },
    {
        "title": "🏭 Implement Supplier model and CRUD operations",
        "milestone": "Phase 1: Foundation",
        "labels": ["backend", "api", "model"],
        "body": """## Description
Create the Supplier entity and REST API endpoints.

## Tasks
- [ ] Define SQLModel for `Supplier` table
- [ ] Create Pydantic schemas for Supplier
- [ ] Implement FastAPI router at `/api/v1/suppliers`
- [ ] Support filtering by product_id

## Supplier Fields
- id, name, product_id (FK), lead_time_days
- base_unit_cost, pricing_unit, units_per_pricing_unit

## Acceptance Criteria
- [ ] Supplier references valid product
- [ ] Filtering by product_id works correctly"""
    },
    {
        "title": "📊 Implement Inventory management",
        "milestone": "Phase 1: Foundation",
        "labels": ["backend", "api", "inventory"],
        "body": """## Description
Create Inventory tracking system with automatic initialization when products are added.

## Tasks
- [ ] Define SQLModel for `Inventory` table (one row per product)
- [ ] Create Pydantic schemas: `InventoryResponse`, `InventoryAdjust`
- [ ] Implement FastAPI router at `/api/v1/inventory`
- [ ] Auto-initialize inventory when product is created

## Acceptance Criteria
- [ ] Inventory rows auto-created for new products
- [ ] Adjustment endpoint validates non-negative final quantity"""
    },
    {
        "title": "🔗 Implement Bill of Materials (BOM) service",
        "milestone": "Phase 1: Foundation",
        "labels": ["backend", "api", "bom"],
        "body": """## Description
Create BOM management allowing definition of material requirements for finished products.

## Tasks
- [ ] Define SQLModel for `BOM` table (composite PK)
- [ ] Create FastAPI router at `/api/v1/bom`
- [ ] Create `BOMService` with method `expand_bom(finished_product_id)`
- [ ] Handle pcb_ref type references as additional line items

## Acceptance Criteria
- [ ] Cannot add BOM where finished type != 'finished'
- [ ] Cannot add BOM where material type != 'raw'
- [ ] Expansion returns {material_name: quantity} dict"""
    },
    {
        "title": "⚙️ Implement Configuration service",
        "milestone": "Phase 1: Foundation",
        "labels": ["backend", "api", "configuration"],
        "body": """## Description
Create global configuration storage for simulation parameters.

## Tasks
- [ ] Define SQLModel for `Configuration` table
- [ ] Implement endpoints: GET all, GET single, PUT update
- [ ] Predefined keys: capacity_per_day, warehouse_capacity, demand_mean, demand_variance
- [ ] Create `load_config_from_json(filepath)` function

## Acceptance Criteria
- [ ] All predefined keys exist after initialization
- [ ] Config values persist across requests"""
    },
    {
        "title": "🔄 Implement Event logging service",
        "milestone": "Phase 1: Foundation",
        "labels": ["backend", "api", "events"],
        "body": """## Description
Centralized event logging for all state changes in the simulation.

## Tasks
- [ ] Define SQLModel for `Event` table
- [ ] Implement endpoints: GET events (filterable), GET types, GET timeline
- [ ] Create `EventLogger.log(event_type, sim_date, entity_type, entity_id, detail)`

## Event Types
DEMAND_GENERATED, MO_RELEASED, PRODUCTION_STARTED/COMPLETED, PO_ISSUED/SHIPPED/DELIVERED, INVENTORY_ADJUSTMENT, CAPACITY_HIT_LIMIT, STOCKOUT_WARNING, WAREHOUSE_FULL, DAY_ADVANCED

## Acceptance Criteria
- [ ] Events include both simulated date and real timestamp
- [ ] Timeline endpoint aggregates events by day/type"""
    },
    {
        "title": "📜 Create database seed script with sample scenario",
        "milestone": "Phase 1: Foundation",
        "labels": ["backend", "data", "documentation"],
        "body": """## Description
Create initialization script to populate database with default scenario data.

## Tasks
- [ ] Enhance `initialize_db.py` to load JSON configuration
- [ ] Create `config/default.json` with example scenario
- [ ] Add --reset and --scenario command-line arguments
- [ ] Include 2-3 printer models, 5-10 raw materials, complete BOMs

## Acceptance Criteria
- [ ] Running `python initialize_db.py` creates fully populated database
- [ ] Seed script idempotent (can run multiple times safely)"""
    },
    
    # ================================================================
    # PHASE 2: Core Simulation
    # ================================================================
    {
        "title": "🎭 Set up SimPy simulation environment",
        "milestone": "Phase 2: Core Simulation",
        "labels": ["simulation", "backend", "simpy"],
        "body": """## Description
Initialize SimPy-based discrete-event simulation engine.

## Tasks
- [ ] Create `src/simulation/environment.py`:
  - SimPy Environment setup
  - Date/time management wrapper around env.now
  - SimulationEngine class with current_date property
- [ ] Create `src/simulation/clock.py` for date conversions
- [ ] Wire up POST /api/v1/simulation/day/advance
- [ ] Create POST /api/v1/simulation/reset

## Acceptance Criteria
- [ ] run_day() increments simulation date by 1
- [ ] Reset restores initial state
- [ ] API endpoint responds within reasonable time"""
    },
    {
        "title": "📈 Implement Demand Generation Service",
        "milestone": "Phase 2: Core Simulation",
        "labels": ["simulation", "backend", "demand"],
        "body": """## Description
Random manufacturing order generation based on configured mean/variance.

## Tasks
- [ ] Create `src/services/demand_service.py`:
  - generate_orders(sim_date) -> list[ManufacturingOrder]
  - Sample from normal distribution using numpy
  - Distribute demand across models with configurable weights
- [ ] Store generated orders with status='pending'
- [ ] Log DEMAND_GENERATED event for each order

## Parameters from config
- demand_mean: Average daily demand
- demand_variance: Variance for randomization

## Acceptance Criteria
- [ ] Zero or more orders generated per day
- [ ] Orders have created_date matching current sim date"""
    },
    {
        "title": "📋 Implement Manufacturing Order lifecycle",
        "milestone": "Phase 2: Core Simulation",
        "labels": ["backend", "api", "manufacturing-orders"],
        "body": """## Description
Full CRUD and lifecycle management for Manufacturing Orders.

## Tasks
- [ ] Define SQLModel for ManufacturingOrder table
- [ ] Implement FastAPI router at `/api/v1/manufacturing-orders`
- [ ] Endpoints: GET list/filter, GET single, POST release, GET /{id}/bom, DELETE
- [ ] Status transitions: pending -> in_progress -> completed

## Release Logic
1. Verify product exists and type='finished'
2. Change status to 'in_progress', set released_date
3. Log MO_RELEASED event

## Acceptance Criteria
- [ ] Pending MOs display with expanded BOM summary
- [ ] Can only release pending orders"""
    },
    {
        "title": "🛒 Implement Purchase Order service",
        "milestone": "Phase 2: Core Simulation",
        "labels": ["backend", "api", "purchasing"],
        "body": """## Description
Create purchase orders with automatic delivery scheduling.

## Tasks
- [ ] Define SQLModel for PurchaseOrder table
- [ ] Implement FastAPI router at `/api/v1/purchase-orders`
- [ ] Endpoints: GET list/filter, GET single, POST create, DELETE cancel
- [ ] Add cost preview endpoint with tiered pricing

## PO Creation Logic
- expected_delivery = issue_date + supplier.lead_time_days
- total_cost = calculate_tiered_cost(supplier, quantity)

## Acceptance Criteria
- [ ] Expected delivery calculated from supplier lead time
- [ ] Cost reflects tiered pricing structure"""
    },
    {
        "title": "📦 Implement Inventory Service (consumption & checks)",
        "milestone": "Phase 2: Core Simulation",
        "labels": ["backend", "services", "inventory"],
        "body": """## Description
Core inventory management: availability checks, consumption, receiving.

## Tasks
- [ ] Create src/services/inventory_service.py:
  - get_stock(product_id)
  - check_availability(material_requirements)
  - consume(material_id, quantity)
  - receive_purchase(product_id, quantity)
  - can_fit_in_warehouse(additional_units)

## Warehouse Capacity Enforcement (Strict)
Per spec decision #2, deliveries exceeding capacity must be REJECTED.

## Acceptance Criteria
- [ ] Shortage detection identifies exact missing materials
- [ ] Warehouse enforcement rejects oversize deliveries"""
    },
    {
        "title": "🔄 Process PO deliveries in daily simulation",
        "milestone": "Phase 2: Core Simulation",
        "labels": ["simulation", "backend", "deliveries"],
        "body": """## Description
Integrate purchase order delivery processing into the daily cycle.

## Tasks
- [ ] In simulation_engine.run_day(), add delivery processing step:
  1. Query POs where expected_delivery == current_date AND status='pending'
  2. For each PO: check warehouse capacity, update inventory, log event
  
## Daily Loop Order (Option A)
1. Generate Demand
2. Process Deliveries
3. Process Production
4. Log completion
5. Advance calendar

## Acceptance Criteria
- [ ] POs deliver automatically on expected date
- [ ] Over-capacity deliveries rejected (not capped)"""
    },
    
    # ================================================================
    # PHASE 3: Production Logic
    # ================================================================
    {
        "title": "🏭 Implement Production Service",
        "milestone": "Phase 3: Production Logic",
        "labels": ["backend", "services", "production"],
        "body": """## Description
Process manufacturing orders within daily capacity constraints.

## Tasks
- [ ] Create src/services/production_service.py:
  - get_active_orders() -> list[MO with status='in_progress']
  - process_order(mo, remaining_capacity) -> units_produced
  - complete_mo(mo)
- [ ] Process orders FIFO by released_date
- [ ] Track remaining_capacity and stop when exhausted

## Processing Logic
1. Get BOM requirements
2. Check material availability
3. If shortage: log STOCKOUT_WARNING, skip MO
4. If no shortage: consume BOM, update MO progress

## Acceptance Criteria
- [ ] Capacity strictly enforced (never exceed limit)
- [ ] Shortages cause MO to be skipped"""
    },
    {
        "title": "🔗 Integrate full daily simulation loop",
        "milestone": "Phase 3: Production Logic",
        "labels": ["simulation", "backend", "integration"],
        "body": """## Description
Wire all services together into complete day advancement cycle.

## Tasks
- [ ] Finalize simulation_engine.run_day() implementation
- [ ] Return DayResult object with:
  - Orders generated, POs delivered, units produced, events logged
- [ ] Single API call runs entire day cycle

## Acceptance Criteria
- [ ] Response includes summary for UI display
- [ ] Events table has complete audit trail
- [ ] Tests verify each step executes in order"""
    },
    {
        "title": "🧪 Implement BOM expansion with reference resolution",
        "milestone": "Phase 3: Production Logic",
        "labels": ["backend", "services", "bom"],
        "body": """## Description
Fully resolve BOM entries including pcb_ref style references.

## Tasks
- [ ] In BOMService.expand_for_product():
  - Load raw BOM entries from database
  - Resolve string references like pcb_ref: CTRL-V2
  - Add as separate BOM line item
- [ ] In calculate_requirements(): multiply by order quantity

## Acceptance Criteria
- [ ] String references resolved to actual products
- [ ] Both generic and specific references treated as additional items"""
    },
    {
        "title": "🚨 Implement shortage detection and alerts",
        "milestone": "Phase 3: Production Logic",
        "labels": ["backend", "alerts", "inventory"],
        "body": """## Description
Detect and report material shortages against pending/released orders.

## Tasks
- [ ] Create InventoryService.check_shortages():
  - Compare available stock against total pending demand
  - Calculate net available = current_stock - committed_to_released_orders
- [ ] Add shortage info to BOM response (required, available, shortage, status)
- [ ] Log STOCKOUT_WARNING event during production

## Acceptance Criteria
- [ ] Shortages visible before attempting to release order
- [ ] UI-ready format includes actionable information"""
    },
    
    # ================================================================
    # PHASE 4: UI Integration
    # ================================================================
    {
        "title": "🎨 Build Streamlit dashboard skeleton",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "streamlit", "ui"],
        "body": """## Description
Create main Streamlit application with layout framework.

## Tasks
- [ ] Create app.py with Streamlit app entry point
- [ ] Set up page config: title, wide layout
- [ ] Create header: simulated date, Advance Day button, Reset button
- [ ] Create tabbed content: Orders, Inventory, Production, Purchasing
- [ ] Create sidebar stats panel
- [ ] Create right panel for charts (toggleable)

## Acceptance Criteria
- [ ] App launches with streamlit run app.py
- [ ] Tabs switch correctly
- [ ] Header displays placeholder date"""
    },
    {
        "title": "📡 Create API client utilities",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "api-client", "integration"],
        "body": """## Description
Build helper functions for Streamlit to communicate with FastAPI.

## Tasks
- [ ] Create src/api_client.py:
  - APIClient class with base_url configuration
  - Methods wrapping all needed endpoints
- [ ] Use httpx or requests for HTTP calls
- [ ] Add error handling with user-friendly messages

## Acceptance Criteria
- [ ] All API endpoints have wrapper methods
- [ ] Connection errors handled gracefully"""
    },
    {
        "title": "📦 Build Orders panel component",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "streamlit", "orders"],
        "body": """## Description
Display pending manufacturing orders with release functionality.

## Tasks
- [ ] Fetch and display pending MOs in a table
- [ ] Add checkbox selection for bulk actions
- [ ] Add accordion/detail view per order with BOM breakdown
- [ ] Highlight shortages in red
- [ ] Connect to API endpoints for MOs and BOM

## Acceptance Criteria
- [ ] Pending orders display correctly
- [ ] BOM expansion shows material details
- [ ] Release updates UI without refresh"""
    },
    {
        "title": "📊 Build Inventory panel component",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "streamlit", "inventory"],
        "body": """## Description
Display stock levels with shortage highlighting.

## Tasks
- [ ] Table showing all products with stock
- [ ] Color coding: Red (critical), Yellow (low), Green (adequate)
- [ ] Sort by urgency (lowest stock first)
- [ ] Visual indicator for warehouse capacity utilization

## Acceptance Criteria
- [ ] Stock levels update after day advance
- [ ] Color coding applied consistently"""
    },
    {
        "title": "🛍️ Build Purchasing panel component",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "streamlit", "purchasing"],
        "body": """## Description
Create PO creation form and active POs display.

## Tasks
- [ ] Create PO form: supplier dropdown, product selector, quantity input
- [ ] Preview: expected cost, expected delivery date
- [ ] Active POs table sorted by delivery date
- [ ] Connect to API for suppliers, PO CRUD, cost calculation

## Acceptance Criteria
- [ ] Supplier/product linkage enforced
- [ ] Cost preview accurate
- [ ] PO creation adds to active list immediately"""
    },
    {
        "title": "⚙️ Build Production panel component",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "streamlit", "production"],
        "body": """## Description
Display capacity usage and in-progress orders.

## Tasks
- [ ] Capacity widget: \"X/Y printers used today\" with progress bar
- [ ] In-Progress Orders table with progress bars
- [ ] Released Queue (orders waiting for capacity)
- [ ] Connect to API for MOs and configuration

## Acceptance Criteria
- [ ] Capacity accurately reflects daily usage
- [ ] Progress bars update after day advance"""
    },
    {
        "title": "📈 Build Charts panel",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "streamlit", "charts"],
        "body": """## Description
Visualizations for inventory trends and throughput.

## Tasks
- [ ] Chart 1: Stock Levels Over Time (multi-line, toggleable series)
- [ ] Chart 2: Production Throughput (bar chart by week)
- [ ] Use matplotlib with st.pyplot()
- [ ] Cache chart generation to avoid redundant computation

## Acceptance Criteria
- [ ] Charts render within acceptable time (< 2 seconds)
- [ ] Line chart allows toggling series"""
    },
    {
        "title": "🔄 Add event log viewer",
        "milestone": "Phase 4: UI Integration",
        "labels": ["frontend", "streamlit", "events"],
        "body": """## Description
Scrollable feed of recent events for audit/debugging.

## Tasks
- [ ] Chronological list of events with expandable details
- [ ] Filter by event type dropdown
- [ ] Limit to last N events with \"Load More\"
- [ ] Connect to API for events listing

## Acceptance Criteria
- [ ] Recent events visible immediately
- [ ] Type filter works correctly"""
    },
    
    # ================================================================
    # PHASE 5: Polish & Export
    # ================================================================
    {
        "title": "💾 Implement Export service",
        "milestone": "Phase 5: Polish & Export",
        "labels": ["backend", "export", "backup"],
        "body": """## Description
State export for backup and sharing.

## Tasks
- [ ] Create ImportExportService with export_full_state(), export_inventory(), export_events()
- [ ] Implement endpoints: POST /export/state, /export/inventory, /export/events
- [ ] Full snapshot includes: config, products, suppliers, inventory, bom, orders, events

## Acceptance Criteria
- [ ] Export files are valid JSON
- [ ] Full export round-trips (can be re-imported)
- [ ] Streamlit offers download button for exports"""
    },
    {
        "title": "📥 Implement Import service",
        "milestone": "Phase 5: Polish & Export",
        "labels": ["backend", "import", "data"],
        "body": """## Description
State import for restoration and scenario loading.

## Tasks
- [ ] Add import_full_state() and import_config_only() to ImportExportService
- [ ] Implement endpoints: POST /import/state, /import/config
- [ ] Validate JSON structure and referential integrity
- [ ] Version check for compatibility

## Acceptance Criteria
- [ ] Exported state can be re-imported
- [ ] Failed import leaves database unchanged (transactional)"""
    },
    {
        "title": "🎯 Implement edge case handling",
        "milestone": "Phase 5: Polish & Export",
        "labels": ["backend", "edge-cases", "quality"],
        "body": """## Description
Handle unusual but possible scenarios gracefully.

## Edge Cases to Handle
1. Zero demand day (normal distribution produces <=0)
2. Empty inventory during production
3. All warehouses full
4. Negative adjustments blocked
5. Invalid configuration values

## Acceptance Criteria
- [ ] No unhandled exceptions in normal operation
- [ ] User sees informative message (not cryptic error)"""
    },
    {
        "title": "📝 Write comprehensive README.md",
        "milestone": "Phase 5: Polish & Export",
        "labels": ["documentation", "readme"],
        "body": """## Description
User-facing documentation for installation and usage.

## Contents Required
1. Project title and tagline
2. Features list
3. Tech stack
4. Prerequisites (Python 3.11+)
5. Installation steps
6. Running instructions (API + Dashboard)
7. Usage examples
8. Project structure
9. Links to PRD.md and claude.md

## Acceptance Criteria
- [ ] New user can set up in under 15 minutes
- [ ] Commands copy-paste cleanly"""
    },
    {
        "title": "✅ Create sample scenario library",
        "milestone": "Phase 5: Polish & Export",
        "labels": ["scenarios", "testing", "data"],
        "body": """## Description
Pre-configured scenarios for testing and demonstration.

## Scenarios to Create
1. quick_start.json - Simple setup for learning
2. challenging.json - Stress test with tight constraints
3. balanced.json - Realistic middle ground

## Usage
python initialize_db.py --scenario config/scenarios/challenging.json

## Acceptance Criteria
- [ ] All scenarios load successfully
- [ ] Each demonstrates different dynamics"""
    },
    {
        "title": "🔍 Final requirements review and gap analysis",
        "milestone": "Phase 5: Polish & Export",
        "labels": ["review", "qa", "documentation"],
        "body": """## Description
Verify all specification requirements are implemented.

## Tasks
- [ ] Create checklist from specification R0-R8 requirements
- [ ] Test end-to-end scenario (advance days, release orders, issue POs, export)
- [ ] OpenAPI documentation review at /docs
- [ ] Documentation completeness check

## Acceptance Criteria
- [ ] All R0-R8 requirements marked satisfied
- [ ] No known critical bugs
- [ ] Documentation reflects actual implementation"""
    },
]


def print_dry_run():
    """Print all issues for review."""
    print("="*70)
    print("GITHUB ISSUES PREVIEW - 3D Printer Production Simulator")
    print("="*70)
    print(f"\nTotal issues to create: {len(ISSUES)}")
    print(f"Milestones: {len(MILESTONES)}")
    
    for milestone in MILESTONES:
        count = len([i for i in ISSUES if i["milestone"] == milestone])
        print(f"  - {milestone}: {count} issues")
    
    print("\n" + "="*70)
    print("ISSUE DETAILS")
    print("="*70)
    
    for issue in ISSUES:
        print(f"\n{'─'*70}")
        print(f"[{issue['milestone']}]")
        print(f"TITLE: {issue['title']}")
        print(f"LABELS: {', '.join(issue['labels'])}")
        body_preview = issue["body"][:300].replace('\n', ' ')
        print(f"BODY PREVIEW: {body_preview}...")


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == '--dry-run':
        print_dry_run()
        return
    
    print("Usage:")
    print("  python scripts/create_github_issues.py --dry-run  # Preview issues")
    print("")
    print(f"Total issues ready: {len(ISSUES)}")
    print(f"Milestones: {' | '.join(MILESTONES)}")
    print_dry_run()


if __name__ == '__main__':
    main()
