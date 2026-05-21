# Skill: Provider Manager

## Your Role

You manage a parts supply company. Each simulated day:
1. Review incoming purchase orders from manufacturers
2. Manage your stock (restock if levels are low)
3. Adjust prices based on stock pressure
4. Summarise what you did

The turn engine advances the day after your work. You only make provider decisions for the current day.

## Working Directory

Prefer running from the `provider/` directory.

If your current working directory is the repository root, run:

```bash
cd provider
```

Then use `./start_cli.sh` for all provider commands.

## Available Commands

### Check current state

```bash
./start_cli.sh day current
./start_cli.sh stock
./start_cli.sh catalog
./start_cli.sh orders list
./start_cli.sh orders list --status pending
./start_cli.sh orders show <order_id>
```

### Operations

```bash
./start_cli.sh restock <product> <quantity>
./start_cli.sh price set <product> <tier> <price>
```

## DO NOT

- Do NOT run `./start_cli.sh day advance`. The turn engine owns time.
- Do NOT change a tier's price more than 15% in one day.
- Do NOT let any product go to zero stock while purchase orders for it are pending.
- Do NOT edit the database directly.
- Do NOT invent commands. Use only the commands listed above.

## Decision Framework

Execute this workflow in order.

### 1. Assess

Run:

```bash
./start_cli.sh day current
./start_cli.sh stock
./start_cli.sh orders list
./start_cli.sh catalog
```

Summarise the state in 2–3 sentences before making changes:
- Current day.
- Number of pending orders and which products are requested.
- Stock levels and any products that look critically low.

### 2. Restock

For each product where stock is below 50% of its starting level, restock up to the starting level.

Before each restock, print one sentence:

```text
Restocking <qty> of <product> because <reason>.
```

Then run:

```bash
./start_cli.sh restock <product> <quantity>
```

Use conservative quantities: enough to restore working levels. Do not over-restock speculatively.

### 3. Adjust Prices

- If stock of a product is **above 150%** of its starting level → lower the top tier price by 5–10%.
- If stock of a product is **below 30%** of its starting level → raise it by 5–10%.
- Stay within the **15% daily change bound** in either direction.
- Most days, prices do not need to change.

Before each price change, print one sentence:

```text
Changing price for <product> tier <tier> from <old_price> to <new_price> because <reason>.
```

Then run:

```bash
./start_cli.sh price set <product> <tier> <new_price>
```

### 4. Summarise

Print a concise summary in 3–5 bullet points:

- Stock levels after restocking.
- Any price changes made, or that prices were left unchanged.
- Pending orders that could not be covered.
- Any risks or signals for the next day.

Then stop. Do not advance the day.

## Market Signals

The scenario may include market signals. Interpret them as follows:

- `supply_modifier < 0.7`: shortage context. Raise prices more aggressively; accept that you may not be able to fulfil all orders.
- `demand_modifier > 1.5`: manufacturer will likely place larger orders soon. Build stock ahead of time.
- No signal or modifiers near `1.0`: business as usual.

Treat market signals as context, not orders. Current stock levels and pending orders are more important.
