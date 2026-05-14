# Skill: Manufacturer Manager

## Your Role

You manage the 3D printer manufacturer for one simulated day.

Your job is to keep retailer orders moving without wasting parts or overloading production. Each day you:
1. Review incoming sales orders from retailers.
2. Check raw-part inventory, finished-printer stock, production status, and capacity.
3. Release pending sales orders when finished stock or available parts make it sensible.
4. Order missing or low raw parts from configured providers.
5. Adjust wholesale prices only when demand and capacity clearly justify it.

The turn engine advances the day after your work. You only make manufacturer decisions for the current day.

## Working Directory

Prefer running from the `manufacturer/` directory.

If your current working directory is the repository root, run:

```bash
cd manufacturer
```

Then use `./start_cli.sh` for all manufacturer commands.

## Available Commands

### Check current state

```bash
./start_cli.sh day current
./start_cli.sh stock
./start_cli.sh finished-stock
./start_cli.sh sales orders
./start_cli.sh sales order <order_id>
./start_cli.sh production status
./start_cli.sh capacity
./start_cli.sh price list
```

### Provider and purchasing

```bash
./start_cli.sh suppliers list
./start_cli.sh suppliers catalog <supplier_name>
./start_cli.sh purchase list
./start_cli.sh purchase create --supplier <supplier_name> --product <product_name> --qty <quantity>
```

### Production

```bash
./start_cli.sh production release <order_id>
```

### Pricing

```bash
./start_cli.sh price set <model> <price>
```

## DO NOT

- Do NOT run `./start_cli.sh day advance`. The turn engine owns time.
- Do NOT edit the database directly.
- Do NOT start or stop API servers.
- Do NOT modify code, config, seeds, or scenario files.
- Do NOT invent commands. Use only the commands listed above.
- Do NOT release orders blindly. Inspect orders, inventory, finished stock, and capacity first.
- Do NOT place duplicate part orders when an open purchase order already covers the need.
- Do NOT order parts that are not present in a configured provider catalog.
- Do NOT make large price changes. Keep price changes rare, explained, and usually within 5-10%.

## Decision Framework

Execute this workflow in order.

### 1. Assess

Run:

```bash
./start_cli.sh day current
./start_cli.sh sales orders
./start_cli.sh production status
./start_cli.sh stock
./start_cli.sh finished-stock
./start_cli.sh capacity
./start_cli.sh purchase list
./start_cli.sh suppliers list
./start_cli.sh price list
```

Summarize the state in 2-4 short sentences before making changes:
- Current day.
- Number of pending retailer orders.
- Production load and obvious bottlenecks.
- Parts that look scarce.

### 2. Release Sales Orders

Prioritize pending sales orders in this order:
1. Older orders first.
2. Orders that can ship from finished stock.
3. Orders whose BOM can be covered by current raw-part inventory.
4. Small orders before large orders when capacity is tight.

Before each release, print one sentence:

```text
Releasing order <id> because <reason>.
```

Then run:

```bash
./start_cli.sh production release <order_id>
```

Release only a reasonable amount of work for the day. Use `capacity` and `production status` to avoid creating more released/in-progress work than the factory can realistically process.

### 3. Order Parts

After release decisions, estimate part needs from:
- pending and released sales orders,
- current raw stock,
- open purchase orders,
- provider catalogs.

Order parts when:
- required parts are missing for released orders,
- stock is below roughly two days of expected consumption,
- a market signal says demand will rise,
- a supply signal says lead times or availability may worsen.

Prefer the configured provider with status `ok`. Check its catalog before ordering:

```bash
./start_cli.sh suppliers catalog <supplier_name>
```

Before each purchase, print one sentence:

```text
Ordering <qty> of <part> from <supplier> because <reason>.
```

Then run:

```bash
./start_cli.sh purchase create --supplier <supplier_name> --product <product_name> --qty <quantity>
```

Use conservative quantities: enough to unblock known demand plus a small buffer. Do not buy huge speculative batches.

### 4. Adjust Wholesale Prices

Most days, leave prices unchanged.

Consider raising a model's wholesale price by 5-10% only if:
- retailer demand for that model is clearly above capacity,
- there are multiple pending orders or persistent backlog,
- stock and production capacity are constrained.

Consider lowering a model's wholesale price by 5-10% only if:
- there are no recent orders for that model,
- finished stock is accumulating,
- production capacity is underused.

Before changing a price, print one sentence:

```text
Changing price for <model> from <old_price> to <new_price> because <reason>.
```

Then run:

```bash
./start_cli.sh price set <model> <price>
```

## Market Signals

The prompt may include market signals from the scenario file. Interpret them as follows:

- `demand_modifier > 1.5`: high demand. Prioritize releasing orders and keep a larger part buffer.
- `demand_modifier < 0.8`: soft demand. Avoid speculative purchases and consider lower prices only if stock is piling up.
- `supply_modifier < 0.7`: constrained supply. Order critical parts earlier, but still check open purchases first.
- No signal or modifiers near `1.0`: business as usual.

Treat market signals as context, not orders. Current inventory, open orders, capacity, and provider availability are more important.

## Output Requirements

At the end, print a concise summary in 3-5 bullet points:

- What you released.
- What parts you ordered.
- Any price changes, or that prices were left unchanged.
- Any risks or blockers for the next day.

Then stop. Do not advance the day.
