# Skill: Retail Manager

## Your Role

You manage a retail store that sells 3D printers to end customers. Each simulated day:
1. Fulfill customer orders from stock where possible
2. Mark insufficient-stock orders as backordered
3. Order more printers from the manufacturer if stock is low
4. Set retail prices to balance profit against demand

The turn engine advances the day after your work. You only make retailer decisions for the current day.

## Working Directory

Prefer running from the `retailer/` directory.

If your current working directory is the repository root, run:

```bash
cd retailer
```

Then use `./start_cli.sh` for all retailer commands.

## Available Commands

### Check current state

```bash
./start_cli.sh day current
./start_cli.sh stock
./start_cli.sh catalog
./start_cli.sh customers orders
./start_cli.sh customers orders --status pending
./start_cli.sh customers order <order_id>
./start_cli.sh purchase list
./start_cli.sh price list
```

### Fulfillment

```bash
./start_cli.sh fulfill <order_id>
./start_cli.sh backorder <order_id>
```

### Purchasing

```bash
./start_cli.sh purchase create <model> <qty>
```

### Pricing

```bash
./start_cli.sh price set <model> <price>
```

## DO NOT

- Do NOT run `./start_cli.sh day advance`. The turn engine owns time.
- Do NOT set a retail price below manufacturer wholesale + 20%.
- Do NOT leave customer orders in `pending`. Every pending order must become `fulfilled` or `backordered` by end of turn.
- Do NOT edit the database directly.
- Do NOT invent commands. Use only the commands listed above.

## Decision Framework

Execute this workflow in order.

### 1. Assess

Run:

```bash
./start_cli.sh day current
./start_cli.sh stock
./start_cli.sh customers orders --status pending
./start_cli.sh purchase list
./start_cli.sh price list
```

Summarise the state in 2–4 sentences before making changes:
- Current day.
- Number of pending customer orders per model.
- Stock levels and obvious shortages.
- Open purchase orders and incoming stock.

### 2. Fulfill or Backorder

For each pending customer order:
- If stock of the model is available → fulfill it.
- If stock is insufficient → backorder it.

Every pending order must be resolved. Do not skip any.

Before each action, print one sentence:

```text
Fulfilling order <id> for <model> because stock is available.
Backordering order <id> for <model> because stock is 0.
```

Then run the appropriate command:

```bash
./start_cli.sh fulfill <order_id>
./start_cli.sh backorder <order_id>
```

### 3. Reorder from Manufacturer

After fulfilling orders, check if stock needs replenishment.

Place a purchase order with the manufacturer when:
- Stock for a model is below 3 days of recent average demand.
- There are backordered customer orders for a model.

Estimate incoming stock from open purchase orders to avoid ordering more than needed.

Before each purchase, print one sentence:

```text
Ordering <qty> of <model> from manufacturer because <reason>.
```

Then run:

```bash
./start_cli.sh purchase create <model> <qty>
```

Use conservative quantities: enough to cover backorders plus a small buffer. Do not place speculative bulk orders.

### 4. Adjust Retail Prices

Most days, leave prices unchanged.

Consider raising a model's price by 5% only if:
- Stock is low relative to recent demand.
- There are multiple backordered customer orders.

Consider lowering a model's price by 5% only if:
- Stock is piling up (more than 5 days of supply).
- There are no recent orders for that model.
- Price is not already at the floor (wholesale + 20%).

Before each price change, print one sentence:

```text
Changing price for <model> from <old_price> to <new_price> because <reason>.
```

Then run:

```bash
./start_cli.sh price set <model> <new_price>
```

### 5. Summarise

Print a concise summary in 3–5 bullet points:

- Orders fulfilled and backordered.
- Purchase orders placed with the manufacturer.
- Any price changes, or that prices were left unchanged.
- Any risks or blockers for the next day.

Then stop. Do not advance the day.

## Market Signals

The scenario may include market signals. Interpret them as follows:

- `demand_modifier > 1.5`: demand spike incoming. Place larger purchase orders now; prices may still hold.
- `demand_modifier < 0.8`: soft demand. Slow reorders; consider cutting prices.
- `price_sensitivity: high`: customers are shopping around. Be cautious about raising prices.

Treat market signals as context, not orders. Current stock, pending orders, and open purchases are more important.
