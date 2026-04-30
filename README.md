# 3D Printer Production Simulator

Multi-app supply chain: **manufacturer** (factory) and **provider** (parts supplier) talk over REST on separate ports.

## Quick start

### 1. Provider API (port 8001)

```bash
./provider/start_api.sh
```

### 2. Manufacturer API (port 8000)

In another terminal:

```bash
./start_api.sh
```

(`./start_api.sh` runs `manufacturer/start_api.sh`.)

`manufacturer/config.json` points at `http://localhost:8001` for the external provider.

### 3. Manufacturer dashboard (optional, port 8501)

```bash
./start_ui.sh
```

### Smoke test (ports 8000 and 8001 must be free)

```bash
./scripts/check_supply_chain.sh
```

### Todo en uno (APIs + UI)

Desde la raíz del repo, con los puertos **8000**, **8001** y **8501** libres:

```bash
./dev-stack.sh
```

(o `bash scripts/dev-stack.sh` si ves **Permission denied** al ejecutar el `.sh` directamente.)

Crea/usa `venv/`, instala dependencias, hace seed del provider y del manufacturer, levanta ambas APIs y abre Streamlit en **http://localhost:8501**. Con **Ctrl+C** se cierra la UI y el script apaga las dos APIs.

## Project structure

- **`manufacturer/`** — inventory, purchase orders against the provider REST API, CLI, Streamlit; SQLite `manufacturer/manufacturer.db`; API **:8000**
- **`provider/`** — catalog, stock, orders, day advance; API **:8001**

```
printer-factory-sim/
├── manufacturer/
│   ├── app/
│   │   ├── main.py           # FastAPI
│   │   ├── services.py       # business logic + ProviderClient
│   │   ├── provider_client.py
│   │   ├── models.py
│   │   ├── cli.py
│   │   └── ...
│   ├── config.json           # provider URLs
│   ├── seed-manufacturer.json
│   ├── manufacturer.db       # created at runtime
│   ├── start_api.sh
│   ├── start_cli.sh
│   └── start_ui.sh
├── provider/
│   ├── app/
│   ├── start_api.sh
│   └── start_cli.sh
├── scripts/
│   ├── check_supply_chain.sh
│   └── create-github-issues.sh
├── start_api.sh              # → manufacturer API
├── start_ui.sh               # → manufacturer Streamlit
└── SPECIFICATION.md
```

The virtual environment lives at the repository root (`venv/`) and is shared by these scripts.

## Manufacturer API (high level)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/day/current` | Current simulation day |
| POST | `/api/day/advance` | Advance day (polls provider for deliveries) |
| GET | `/api/inventory`, `/api/stock` | Local inventory |
| GET | `/api/providers` | Configured providers + reachability |
| GET | `/api/providers/{name}/catalog` | Proxy to provider catalog |
| POST | `/api/purchases` | Create PO on provider (`supplier_name`, `product_name`, `quantity`) |
| GET | `/api/purchases` | List local POs |
| GET | `/api/events` | Event log |

See `/docs` on each service for the full OpenAPI schema.

## License

MIT
