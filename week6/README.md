# Week 6 Supply Chain

This folder contains the Week 6 implementation only.

It introduces two independent applications:

- `provider/`: a parts supplier with its own catalog, stock, orders, simulated day, CLI, and REST API
- `manufacturer/`: a Week-6-specific manufacturer app that tracks local inventory and purchase orders, and polls the provider over HTTP

Both services have their own SQLite database, API server, and CLI. The goal for Week 6 is to prove that two apps can share a coherent simulated world through a REST contract.

## Ports

- Provider API: `http://localhost:8001`
- Manufacturer API: `http://localhost:8002`
- Manufacturer UI: `http://localhost:8502`

## Suggested Week 6 flow

1. Start the provider API
2. Start the manufacturer API
3. Use both CLIs to inspect day state and stock
4. Query the provider catalog from the manufacturer
5. Place a purchase order from the manufacturer
6. Advance provider first, then manufacturer, one day at a time
7. Verify delivery in both databases and event logs

## Start commands

From this `week6/` folder:

```bash
./provider/start_api.sh
```

In a second terminal:

```bash
./manufacturer/start_api.sh
```

Optional manufacturer UI:

```bash
./manufacturer/start_ui.sh
```

Provider CLI examples:

```bash
./provider/start_cli.sh day current
./provider/start_cli.sh catalog
./provider/start_cli.sh stock
./provider/start_cli.sh orders list
```

Manufacturer CLI examples:

```bash
./manufacturer/start_cli.sh day current
./manufacturer/start_cli.sh stock
./manufacturer/start_cli.sh suppliers list
./manufacturer/start_cli.sh suppliers catalog "ChipSupply Co"
./manufacturer/start_cli.sh purchase create --supplier "ChipSupply Co" --product pcb --qty 50
./manufacturer/start_cli.sh purchase list
```
