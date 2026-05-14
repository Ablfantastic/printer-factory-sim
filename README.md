# 3D Printer Production Simulator

Simulador multi-app de una cadena de suministro de impresoras 3D:

```text
Retailer (:8003) -> Manufacturer (:8002) -> Provider (:8001)
```

Cada app mantiene su propia SQLite, expone una API REST y tiene CLI propia. El `turn engine` coordina un día simulado completo: genera demanda de clientes, ejecuta decisiones deterministas por rol, avanza las tres apps y registra lo ocurrido.

## Estado Actual

- **Provider**: vende piezas al manufacturer, gestiona stock, pedidos y entregas.
- **Manufacturer**: recibe órdenes de retailers, produce impresoras, compra piezas al provider y muestra una UI Streamlit.
- **Retailer**: recibe demanda de clientes, cumple desde stock y compra impresoras al manufacturer.
- **Turn engine**: script determinista para avanzar la cadena completa en lock-step.
- **Skill inicial**: `skills/manufacturer-manager.md`, preparado para usar con Claude Code en el rol de manufacturer manager.

## Quick Start

### Todo en uno

Desde la raíz del repo, con los puertos `8001`, `8002`, `8003` y `8501` libres:

```bash
./dev-stack.sh
```

Esto crea/usa `venv/`, instala dependencias, hace seed de las tres bases, arranca las APIs y abre la UI en:

```text
http://localhost:8501
```

Con `Ctrl+C` se detienen la UI y las tres APIs.

### Arranque Manual

En terminales separadas:

```bash
./provider/start_api.sh
./manufacturer/start_api.sh
./retailer/start_api.sh
./start_ui.sh
```

URLs principales:

| Servicio | URL |
|---|---|
| Provider API | `http://localhost:8001/docs` |
| Manufacturer API | `http://localhost:8002/docs` |
| Retailer API | `http://localhost:8003/docs` |
| Manufacturer UI | `http://localhost:8501` |

## Turn Engine

Ejecutar un día simulado completo:

```bash
python3 scripts/turn_engine.py --scenario scenarios/week7.json --days 1
```

El engine:

1. Lee señales del escenario.
2. Genera demanda determinista de clientes.
3. Inserta órdenes en el retailer.
4. Ejecuta decisiones deterministas para retailer, manufacturer y provider.
5. Avanza las tres apps a la vez.
6. Escribe un registro JSONL en `logs/turn-engine.jsonl`.

Ejecutar varios días:

```bash
python3 scripts/turn_engine.py --scenario scenarios/week7.json --days 5
```

## Reset de Simulación

Para volver todas las bases al día `1`, borrar órdenes/compras/eventos y restaurar stocks desde seeds:

```bash
python3 scripts/reset_simulation.py
```

Por defecto crea backups en `/tmp`. Para cambiar destino:

```bash
python3 scripts/reset_simulation.py --backup-dir ./backups
```

## Smoke Test

Con los puertos `8001`, `8002` y `8003` libres:

```bash
./scripts/check_supply_chain.sh
```

El test arranca las tres APIs, comprueba health checks, valida manufacturer -> provider y retailer -> manufacturer.

## Skill de Manufacturer

El primer skill de Claude Code vive en:

```text
skills/manufacturer-manager.md
```

Ejemplo de uso manual desde la raíz del repo:

```bash
claude --print --prompt "Read skills/manufacturer-manager.md and make today's manufacturer decisions. Do not advance the day."
```

El skill usa comandos reales del repo, principalmente `manufacturer/start_cli.sh`, y prohíbe explícitamente avanzar el día porque eso lo hace el turn engine.

## Estructura

```text
printer-factory-sim/
├── provider/
│   ├── app/                 # FastAPI, models, schemas, services, CLI
│   ├── provider.db
│   ├── seed-provider.json
│   ├── start_api.sh
│   └── start_cli.sh
├── manufacturer/
│   ├── app/                 # FastAPI, Streamlit UI, services, CLI
│   ├── config.json          # providers y retailers configurados
│   ├── manufacturer.db
│   ├── seed-manufacturer.json
│   ├── start_api.sh
│   ├── start_cli.sh
│   └── start_ui.sh
├── retailer/
│   ├── app/                 # FastAPI, services, CLI
│   ├── config.json          # manufacturer upstream
│   ├── retailer.db
│   ├── seed-retailer.json
│   ├── start_api.sh
│   └── start_cli.sh
├── scenarios/
│   └── week7.json           # escenario base para turn engine
├── scripts/
│   ├── check_supply_chain.sh
│   ├── reset_simulation.py
│   └── turn_engine.py
├── skills/
│   └── manufacturer-manager.md
├── logs/                    # generado localmente, ignorado por git
├── dev-stack.sh
├── start_api.sh             # wrapper manufacturer API
├── start_ui.sh              # wrapper manufacturer UI
└── week7.md
```

## APIs Principales

### Provider `:8001`

| Method | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/catalog` | Catálogo de piezas |
| GET | `/api/stock` | Stock de piezas |
| POST | `/api/orders` | Crear pedido de piezas |
| GET | `/api/orders` | Listar pedidos |
| POST | `/api/day/advance` | Avanzar día |
| GET | `/api/events` | Event log |

### Manufacturer `:8002`

| Method | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/catalog` | Modelos y precios wholesale |
| GET | `/api/stock` | Inventario de piezas |
| GET | `/api/finished-stock` | Stock de impresoras terminadas |
| GET | `/api/providers` | Providers configurados y estado |
| GET | `/api/retailers` | Retailers configurados y estado |
| POST | `/api/orders` | Recibir orden de retailer |
| GET | `/api/orders` | Listar órdenes de retailer |
| POST | `/api/production/release/{order_id}` | Liberar orden a producción |
| POST | `/api/purchases` | Comprar piezas al provider |
| POST | `/api/day/advance` | Avanzar día |
| GET | `/api/events` | Event log |

### Retailer `:8003`

| Method | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/catalog` | Catálogo retail |
| POST | `/api/catalog/sync` | Sincronizar wholesale desde manufacturer |
| GET | `/api/stock` | Stock de impresoras |
| POST | `/api/orders` | Recibir orden de cliente |
| GET | `/api/orders` | Listar órdenes de clientes |
| POST | `/api/purchases` | Comprar impresoras al manufacturer |
| GET | `/api/purchases` | Listar compras al manufacturer |
| POST | `/api/day/advance` | Avanzar día |
| GET | `/api/events` | Event log |

Consulta `/docs` en cada servicio para el OpenAPI completo.

## Notas

- El entorno virtual compartido vive en `venv/`.
- `logs/` y las bases SQLite son estado local de ejecución.
- Si cambias endpoints o config, reinicia las APIs para que `uvicorn` cargue el código nuevo.

## License

MIT
