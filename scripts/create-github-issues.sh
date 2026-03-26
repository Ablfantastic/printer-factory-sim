#!/bin/bash
# Script to create GitHub Issues for all milestones/checkpoints
# Run this after authenticating with: gh auth login

set -e

echo "Creating GitHub Issues for 3D Printer Production Simulator milestones..."

# First, create necessary labels if they don't exist
echo ""
echo "Setting up labels..."

gh label create "milestone" --color "4682B4" --description "Major milestone/checkpoint" --force 2>/dev/null || true
gh label create "enhancement" --color "a2eeef" --description "New feature or enhancement" --force 2>/dev/null || true
gh label create "high-priority" --color "d73a4a" --description "High priority item" --force 2>/dev/null || true
gh label create "testing" --color "0e8a16" --description "Testing related" --force 2>/dev/null || true
gh label create "documentation" --color "0075ca" --description "Documentation improvements" --force 2>/dev/null || true
gh label create "future-work" --color "cfd3d7" --description "Future enhancements" --force 2>/dev/null || true

echo "Labels ready!"
echo ""

# Milestone 1: Project Setup & Architecture
gh issue create --title "Milestone 1: Project Setup & Architecture" --body "$(cat <<'EOF'
## Overview
Set up the foundational project structure, configuration, and architecture for the 3D Printer Production Simulator.

## Tasks
- [ ] Initialize Python project structure with proper package layout
- [ ] Set up virtual environment and dependency management (requirements.txt or pyproject.toml)
- [ ] Configure SQLite database connection and initialization scripts
- [ ] Set up FastAPI application skeleton with basic routing
- [ ] Create configuration management for initial production plan (BOM, suppliers, capacity)
- [ ] Add logging infrastructure for simulation events
- [ ] Set up basic CI/CD workflow (GitHub Actions)
- [ ] Document architecture decisions in `/docs`

## Acceptance Criteria
- Project builds and runs without errors
- Database schema initializes correctly
- Basic API endpoint returns health check
- Configuration files are properly loaded

## Related Requirements
- R0 (Initial configuration)

---
*Created from project specification*
EOF
)" --label "milestone,enhancement,high-priority"

# Milestone 2: Data Model & Persistence
gh issue create --title "Milestone 2: Data Model & Database Implementation" --body "$(cat <<'EOF'
## Overview
Implement the complete data model with SQLite persistence for all entities defined in the specification.

## Tasks
- [ ] Create Product table (id, name, type: raw/finished)
- [ ] Create Supplier table (id, name, product_id FK, unit_cost, lead_time_days)
- [ ] Create Inventory table (product_id FK, quantity)
- [ ] Create BOM table (finished_product_id FK, material_id FK, quantity)
- [ ] Create PurchaseOrder table (id, supplier_id FK, product_id FK, quantity, issue_date, expected_delivery, status)
- [ ] Create ManufacturingOrder table (id, created_date, product_id FK, quantity, status)
- [ ] Create Event table (id, type, sim_date, detail)
- [ ] Implement database initialization and migration scripts
- [ ] Create Pydantic models matching the database schema
- [ ] Implement CRUD operations for all entities

## Acceptance Criteria
- All tables created with correct relationships and constraints
- Pydantic models validate data correctly
- Seed data script loads example production plan

## Related Requirements
- Section 6 (Data model)
- R7 (JSON import/export baseline)

---
*Created from project specification*
EOF
)" --label "milestone,enhancement,high-priority"

# Milestone 3: Core Simulation Engine
gh issue create --title "Milestone 3: Core Simulation Engine" --body "$(cat <<'EOF'
## Overview
Build the discrete-event simulation engine that handles day-by-day production cycle simulation.

## Tasks
- [ ] Implement SimPy-based or turn-based day loop simulation engine
- [ ] Create demand generation module (R1): random order generation with configurable mean/variance
- [ ] Implement purchase order processing with lead time delivery (R4)
- [ ] Implement manufacturing order processing with capacity limits (R4)
- [ ] Create BOM consumption logic for production
- [ ] Implement daily capacity enforcement (capacity_per_day limit)
- [ ] Build event logging system (R6): log all significant events with sim_date and detail
- [ ] Create `run_day()` function orchestrating the 24-hour simulation cycle
- [ ] Implement warehouse capacity checks

## Daily Flow Implementation (Section 9)
- [ ] Step 1: Generate new manufacturing orders (demand)
- [ ] Step 2: Process pending deliveries (PO arrivals)
- [ ] Step 3: Process production (consume BOM, respect capacity)
- [ ] Step 4: Log all events
- [ ] Step 5: Advance simulated calendar

## Acceptance Criteria
- Simulation runs day-by-day correctly
- Demand generation produces configurable random orders
- PO deliveries arrive on expected delivery date
- Production respects capacity limits and stock availability
- All events are logged with correct dates

## Related Requirements
- R1 (Demand generation)
- R4 (Event simulation)
- R5 (Calendar advance)
- R6 (Event log)

---
*Created from project specification*
EOF
)" --label "milestone,enhancement,high-priority"

# Milestone 4: REST API
gh issue create --title "Milestone 4: REST API Development" --body "$(cat <<'EOF'
## Overview
Implement comprehensive REST API endpoints following FastAPI best practices with OpenAPI documentation.

## Core Endpoints (Section 7.2)
- [ ] `POST /api/day/advance` - Run single day simulation cycle
- [ ] `POST /api/orders/{order_id}/release` - Release manufacturing order to production
- [ ] `POST /api/purchases` - Create purchase order

## Additional Endpoints (Section 7.3)
- [ ] `GET /api/calendar` - Get current simulated day/date
- [ ] `GET /api/orders/pending` - Get pending manufacturing orders with BOM expansion
- [ ] `GET /api/inventory` - Get stock levels with optional shortage flags
- [ ] `GET /api/suppliers` - Get supplier catalog
- [ ] `GET /api/products` - Get products (raw and finished)
- [ ] `GET /api/bom` - Get bill of materials configuration
- [ ] `GET /api/events` - Get event history (with date/type filters)
- [ ] `GET /api/capacity` - Get production capacity settings

## JSON Import/Export (R7)
- [ ] `POST /api/import` - Import inventory and/or full snapshot from JSON
- [ ] `GET /api/export/inventory` - Export current inventory state as JSON
- [ ] `GET /api/export/events` - Export event history as JSON
- [ ] `GET /api/export/full` - Export complete simulation state (recommended)

## API Features
- [ ] Implement Pydantic request/response models for all endpoints
- [ ] Add proper error handling with meaningful HTTP status codes
- [ ] Ensure UI/API parity (R8): every UI action has corresponding endpoint
- [ ] Verify OpenAPI/Swagger docs auto-generate correctly

## Acceptance Criteria
- All endpoints return correct data and handle errors gracefully
- OpenAPI docs accessible at `/docs`
- API validation catches invalid inputs
- Import/export works with minimum required data (inventory, events)

## Related Requirements
- R7 (JSON import/export)
- R8 (REST API)

---
*Created from project specification*
EOF
)" --label "milestone,enhancement,high-priority"

# Milestone 5: Dashboard UI
gh issue create --title "Milestone 5: Streamlit Dashboard UI" --body "$(cat <<'EOF'
## Overview
Build the Streamlit-based control dashboard for the production planner user role.

## Layout Areas (Section 8)
- [ ] **Header**: Display current simulated day + "Advance Day" button
- [ ] **Orders Panel**: Table of pending manufacturing orders with automatic BOM calculation
- [ ] **Inventory Panel**: Stock levels with highlighted shortages
- [ ] **Purchasing Panel**: Supplier dropdown, quantity input, "Issue Order" action
- [ ] **Production Panel**: Daily capacity display, releasable orders queue, in-progress orders
- [ ] **Charts Section**: Stock levels and completed orders over time

## Interactive Features
- [ ] Release selected manufacturing orders (multi-select support)
- [ ] Issue purchase orders with product/supplier selection
- [ ] Real-time update after each action
- [ ] Visual indicators for low stock/shortages

## Charts (matplotlib integration)
- [ ] Inventory levels over time chart
- [ ] Completed orders throughput chart
- [ ] Optional: Pending vs released orders trend

## Acceptance Criteria
- Dashboard loads and displays all panels correctly
- "Advance Day" triggers simulation and refreshes UI
- Order release updates inventory and order status
- Purchase orders created with correct lead time delivery
- Charts render historical data properly

## Related Requirements
- R2 (Control dashboard)
- R3 (User decisions)
- R6 (Event log for charts)

---
*Created from project specification*
EOF
)" --label "milestone,enhancement"

# Milestone 6: Integration & Testing
gh issue create --title "Milestone 6: Integration, Testing & Documentation" --body "$(cat <<'EOF'
## Overview
Complete integration testing, edge case handling, and final documentation.

## Testing
- [ ] Unit tests for simulation engine components
- [ ] Integration tests for API endpoints
- [ ] E2E test: Complete scenario from Section 11 walkthrough
- [ ] Test demand generation randomness and configuration
- [ ] Test capacity limits enforcement
- [ ] Test PO lead time delivery timing
- [ ] Test BOM consumption accuracy
- [ ] Test import/export round-trip

## Edge Cases
- [ ] Handle insufficient stock when releasing orders
- [ ] Handle warehouse capacity limits on PO delivery
- [ ] Handle zero/negative demand generation edge cases
- [ ] Validate BOM references resolve to valid Products

## Documentation
- [ ] Update README with setup instructions
- [ ] Document API endpoints with examples
- [ ] Create user guide for production planner role
- [ ] Add code comments explaining complex logic
- [ ] Document order of operations within a day (Section 13 #2)

## Performance
- [ ] Verify simulation can run many days efficiently
- [ ] Check database query performance on large event logs
- [ ] Optimize chart rendering for long histories

## Acceptance Criteria
- All tests pass (>80% coverage recommended)
- Example scenario from Section 11 executes correctly
- Documentation is complete and clear
- No critical bugs in core simulation logic

## Traceability
- Verify R0-R8 requirements are met (Section 14)

---
*Created from project specification*
EOF
)" --label "milestone,testing,documentation"

# Technical Debt / Future Work
gh issue create --title "Future Enhancements (Not in Scope)" --body "$(cat <<'EOF'
## Out of Scope Items (from Specification Section 1.2)
These items are explicitly out of scope but could be considered for future iterations:

### Accounting
- Full accounting system beyond simple cost display
- Profit/loss tracking
- Cash flow management
- Multi-currency support

### Advanced Logistics
- Multi-factory logistics coordination
- Regional distribution centers
- Shipping and transportation modeling

### Detailed Shop-Floor Scheduling
- Machine-level scheduling
- Worker shift management
- Maintenance windows
- Bottleneck analysis

### Hardware Integration
- Real hardware sensor integration
- IoT device connectivity
- Physical inventory tracking

### Schema Extensions (Section 13 Notes)
- [ ] Supplier price tiers (current model uses single unit_cost)
- [ ] Multi-SKU suppliers per row normalization
- [ ] Extended warehouse capacity policies (reject vs cap overflow)

## Nice-to-Have Features
- [ ] Scenario saving/loading
- [ ] Multiple production plans comparison
- [ ] What-if analysis tools
- [ ] Alert notifications for low stock
- [ ] Export reports to CSV/PDF

---
*Created from project specification Section 1.2 and 13*
EOF
)" --label "enhancement,future-work"

echo ""
echo "=========================================="
echo "All milestone issues have been created!"
echo "=========================================="
