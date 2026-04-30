# Provider application

Parts supplier: catalog, stock, orders, simulated day, CLI, and REST API (port **8001**).

Uses the repository root virtualenv (`../venv/` when run from this folder).

## Start

From the repository root:

```bash
./provider/start_api.sh
```

CLI:

```bash
./provider/start_cli.sh day current
./provider/start_cli.sh catalog
./provider/start_cli.sh stock
./provider/start_cli.sh orders list
```

## With the manufacturer

`manufacturer/config.json` should list this service (default `http://localhost:8001`). Start the provider first, then `./start_api.sh` for the manufacturer.
