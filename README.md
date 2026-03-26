# 3D Printer Production Simulator

A discrete-event simulation system for modeling a factory that manufactures 3D printers.

## Quick Start

### 1. Start the Backend API

```bash
./start_api.sh
```

The API will be available at `http://localhost:8000` with Swagger docs at `/docs`.

### 2. Start the Frontend Dashboard (in a new terminal)

```bash
./start_ui.sh
```

The dashboard will be available at `http://localhost:8501`.

## Project Structure

```
printer-factory-sim/
├── app/
│   ├── __init__.py          # Package init
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy database models
│   ├── schemas.py           # Pydantic schemas
│   ├── database.py          # Database configuration
│   ├── simulation.py        # Core simulation engine
│   ├── ui.py                # Streamlit dashboard
│   └── seed.py              # Database seeding script
├── scripts/
│   └── create-github-issues.sh
├── requirements.txt         # Python dependencies
├── start_api.sh             # Backend startup script
├── start_ui.sh              # Frontend startup script
└── SPECIFICATION.md         # Full project specification
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/calendar` | Current simulated day |
| POST | `/api/day/advance` | Run one day of simulation |
| GET | `/api/inventory` | Get inventory levels |
| GET | `/api/orders/pending` | Get pending orders |
| POST | `/api/orders/{id}/release` | Release an order |
| GET | `/api/suppliers` | Get supplier catalog |
| GET | `/api/products` | Get products |
| POST | `/api/purchases` | Create purchase order |
| GET | `/api/events` | Get event history |

## License

MIT
