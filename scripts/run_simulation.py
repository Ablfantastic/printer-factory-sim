#!/usr/bin/env python3
"""
Extended simulation runner with metrics collection and agent narrative log.

Usage:
    python scripts/run_simulation.py --scenario scenarios/calm-market.json --days 25
    python scripts/run_simulation.py --scenario scenarios/holiday-rush.json --days 25

Outputs per run:
    logs/metrics_{scenario}.csv        — numeric metrics per day (for charts)
    logs/narrative_{scenario}.md       — agent reasoning per day per actor
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = REPO_ROOT / "logs"
OPEN_STATUSES = {"pending", "confirmed", "released", "in_progress", "completed", "shipped"}


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def safe_get(url: str, timeout: int = 60) -> list | dict:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [WARN] GET {url}: {exc}", flush=True)
        return {}


def safe_post(url: str, data: dict | None = None, timeout: int = 120) -> dict:
    try:
        r = requests.post(url, json=data or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [WARN] POST {url}: {exc}", flush=True)
        return {}


# ── Narrative logger ──────────────────────────────────────────────────────────

class NarrativeLog:
    """Writes a human-readable markdown log of each agent's decisions."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(path, "w", encoding="utf-8")

    def header(self, scenario_name: str, n_days: int) -> None:
        self._f.write(f"# Agent Narrative Log — {scenario_name}\n\n")
        self._f.write(f"Scenario: **{scenario_name}** | Days: **{n_days}**\n\n")
        self._f.write("---\n\n")
        self._f.flush()

    def day(self, day: int, modifier: float, label: str) -> None:
        self._f.write(f"## Day {day}  |  demand_modifier={modifier:.2f}  |  *{label}*\n\n")
        self._f.flush()

    def demand(self, orders: list) -> None:
        by_model: dict = {}
        for o in orders:
            by_model[o["model"]] = by_model.get(o["model"], 0) + 1
        summary = ", ".join(f"{m}: {n}" for m, n in sorted(by_model.items()))
        self._f.write(f"**Customer demand injected:** {len(orders)} orders ({summary})\n\n")
        self._f.flush()

    def agent(self, role: str, lines: list[str]) -> None:
        self._f.write(f"### {role}\n\n")
        for line in lines:
            self._f.write(f"{line}\n")
        self._f.write("\n")
        self._f.flush()

    def separator(self) -> None:
        self._f.write("---\n\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()


# ── Scenario helpers ──────────────────────────────────────────────────────────

def scenario_for_day(scenario: dict, day: int) -> dict:
    defaults = dict(scenario.get("demand", {}))
    day_signal = scenario.get("days", {}).get(str(day), {})
    defaults.update(day_signal)
    defaults.setdefault("base_demand", {"mean": 4, "variance": 1.5})
    defaults.setdefault("demand_modifier", 1.0)
    return defaults


def generate_customer_demand(day: int, signal: dict, catalog: list, rng: random.Random) -> list:
    base = signal.get("base_demand", {"mean": 4, "variance": 1.5})
    modifier = float(signal.get("demand_modifier", 1.0))
    prices = [float(i.get("retail_price") or i.get("price") or 450) for i in catalog if isinstance(i, dict)]
    base_price = sum(prices) / len(prices) if prices else 450.0
    orders = []
    for item in catalog:
        if not isinstance(item, dict):
            continue
        model = item.get("model") or item.get("name")
        price = float(item.get("retail_price") or item.get("price") or base_price)
        mean_orders = float(base.get("mean", 4)) * modifier
        price_factor = max(0.2, 1.0 - (price - base_price) / base_price)
        count = max(0, int(rng.gauss(mean_orders * price_factor, float(base.get("variance", 1.5)))))
        for i in range(count):
            orders.append({"customer": f"d{day}-{model}-{i+1}", "model": model, "quantity": 1})
    return orders


# ── Agent turns with narrative ────────────────────────────────────────────────

def retailer_turn(rurl: str, policy: dict, log: NarrativeLog, day: int) -> None:
    lines: list[str] = []

    try:
        safe_post(f"{rurl}/api/catalog/sync")
    except Exception:
        pass

    rstock_raw = safe_get(f"{rurl}/api/stock") or []
    stock = {s["model"]: int(s.get("quantity", 0)) for s in rstock_raw if isinstance(s, dict)}
    lines.append(f"**Stock at start of turn:** {', '.join(f'{k}: {v}' for k,v in sorted(stock.items()))}")

    pending = safe_get(f"{rurl}/api/orders?status=pending") or []
    fulfilled_count = backordered_count = 0

    for order in pending:
        if not isinstance(order, dict):
            continue
        model = order.get("model", "?")
        qty = int(order.get("quantity", 1))
        if stock.get(model, 0) >= qty:
            safe_post(f"{rurl}/api/orders/{order['id']}/fulfill")
            stock[model] = stock.get(model, 0) - qty
            fulfilled_count += 1
        else:
            safe_post(f"{rurl}/api/orders/{order['id']}/backorder")
            backordered_count += 1

    if pending:
        lines.append(f"- Fulfilled **{fulfilled_count}** orders, backordered **{backordered_count}** "
                     f"(stock insufficient)")
    else:
        lines.append("- No pending orders to process")

    backorders = safe_get(f"{rurl}/api/orders?status=backordered") or []
    total_bo = len(backorders)
    purchases = safe_get(f"{rurl}/api/purchases") or []
    incoming: dict = {}
    for p in purchases:
        if isinstance(p, dict) and p.get("status") in OPEN_STATUSES:
            incoming[p["model"]] = incoming.get(p["model"], 0) + int(p.get("quantity", 0))

    if incoming:
        lines.append(f"- Incoming from manufacturer: {', '.join(f'{k}: {v}' for k,v in sorted(incoming.items()))}")

    catalog = safe_get(f"{rurl}/api/catalog") or []
    target = int(policy.get("target_stock", 6))
    lot = int(policy.get("reorder_lot", 4))
    orders_placed: list[str] = []

    for item in catalog:
        if not isinstance(item, dict):
            continue
        model = item["model"]
        bo_qty = sum(int(o["quantity"]) for o in backorders if isinstance(o, dict) and o.get("model") == model)
        desired = target + bo_qty
        covered = stock.get(model, 0) + incoming.get(model, 0)
        if covered < desired:
            qty = max(lot, desired - covered)
            result = safe_post(f"{rurl}/api/purchases", {"model": model, "quantity": qty})
            if result:
                eta = result.get("expected_delivery_day", "?")
                orders_placed.append(f"{model} ×{qty} (ETA day {eta}, bo={bo_qty}, covered={covered}→{covered+qty})")

    if orders_placed:
        lines.append(f"- **Purchase orders placed:** {'; '.join(orders_placed)}")
    else:
        lines.append(f"- No new purchase orders needed (covered={sum(stock.values())+sum(incoming.values())})")

    if total_bo > 0:
        lines.append(f"- ⚠️ Total backordered customer orders outstanding: **{total_bo}**")

    log.agent("Retailer (PrinterWorld)", lines)


def manufacturer_turn(murl: str, policy: dict, log: NarrativeLog, day: int) -> None:
    lines: list[str] = []

    pending = safe_get(f"{murl}/api/orders?status=pending") or []
    released_ids: list[str] = []
    for order in pending:
        if isinstance(order, dict):
            result = safe_post(f"{murl}/api/orders/{order['id']}/release")
            if result:
                released_ids.append(f"#{order['id']} {order.get('model','?')} ×{order.get('quantity','?')}")

    if released_ids:
        lines.append(f"- Released sales orders: {', '.join(released_ids)}")
    else:
        lines.append("- No pending sales orders to release")

    catalog = {
        item["name"]: item
        for item in (safe_get(f"{murl}/api/catalog") or [])
        if isinstance(item, dict)
    }
    inventory = {
        item["product_name"]: int(item["quantity"])
        for item in (safe_get(f"{murl}/api/stock") or [])
        if isinstance(item, dict)
    }
    critical = [f"{k}: {v}" for k, v in sorted(inventory.items()) if v < 10]
    lines.append(f"**Parts stock:** total={sum(inventory.values())}"
                 + (f" | ⚠️ Critical (<10): {', '.join(critical)}" if critical else " | all OK"))

    released = safe_get(f"{murl}/api/orders?status=released") or []
    in_progress = safe_get(f"{murl}/api/orders?status=in_progress") or []
    lines.append(f"- Production: {len(released)} released, {len(in_progress)} in-progress")

    required: dict = {}
    for order in released:
        if not isinstance(order, dict):
            continue
        bom = catalog.get(order.get("model", ""), {}).get("bom", {})
        for part, per_unit in bom.items():
            required[part] = required.get(part, 0) + int(per_unit) * int(order.get("quantity", 0))

    open_pos = safe_get(f"{murl}/api/purchases") or []
    incoming: dict = {}
    for p in open_pos:
        if isinstance(p, dict) and p.get("status") in OPEN_STATUSES:
            incoming[p["product_name"]] = incoming.get(p["product_name"], 0) + int(p.get("quantity", 0))

    providers = [p for p in (safe_get(f"{murl}/api/providers") or []) if isinstance(p, dict) and p.get("status") == "ok"]
    if not providers:
        providers = safe_get(f"{murl}/api/providers") or []
    supplier = providers[0]["name"] if providers else None
    buffer = int(policy.get("part_buffer", 5))

    parts_ordered: list[str] = []
    if supplier:
        sup_catalog = {
            item["name"]: item
            for item in (safe_get(f"{murl}/api/providers/{quote(supplier)}/catalog") or [])
            if isinstance(item, dict)
        }
        for part, needed in sorted(required.items()):
            shortage = needed + buffer - inventory.get(part, 0) - incoming.get(part, 0)
            if shortage > 0 and part in sup_catalog:
                result = safe_post(
                    f"{murl}/api/purchases",
                    {"supplier_name": supplier, "product_name": part, "quantity": shortage},
                )
                if result:
                    eta = result.get("expected_delivery_day", "?")
                    parts_ordered.append(f"{part} ×{shortage} from {supplier} (ETA day {eta})")

    if parts_ordered:
        lines.append(f"- **Parts ordered:** {'; '.join(parts_ordered)}")
    elif required:
        lines.append("- All required parts already covered by stock + open orders")
    else:
        lines.append("- No released orders requiring parts")

    log.agent("Manufacturer (Factory)", lines)


def provider_turn(purl: str, log: NarrativeLog, day: int) -> None:
    lines: list[str] = []

    pstock = safe_get(f"{purl}/api/stock") or []
    stock_map = {s["product_name"]: s["quantity"] for s in pstock if isinstance(s, dict)}
    low = [f"{k}: {v}" for k, v in sorted(stock_map.items()) if v < 50]
    lines.append(f"**Stock:** total={sum(stock_map.values())}"
                 + (f" | ⚠️ Low (<50): {', '.join(low)}" if low else " | all levels OK"))

    orders = safe_get(f"{purl}/api/orders") or []
    pending = [o for o in orders if isinstance(o, dict) and o.get("status") == "pending"]
    shipped = [o for o in orders if isinstance(o, dict) and o.get("status") == "shipped"]
    lines.append(f"- Orders: {len(pending)} pending, {len(shipped)} shipped")

    if pending:
        by_product: dict = {}
        for o in pending:
            p = o.get("product_name", "?")
            by_product[p] = by_product.get(p, 0) + int(o.get("quantity", 0))
        lines.append(f"- Pending demand: {', '.join(f'{k}: {v}' for k,v in sorted(by_product.items()))}")

    log.agent("Provider (ChipSupply Co)", lines)


# ── Metrics snapshot ──────────────────────────────────────────────────────────

def collect_metrics(apps: dict, day: int, scenario_name: str, modifier: float) -> dict:
    row: dict = {"day": day, "scenario": scenario_name, "demand_modifier": modifier}

    purl = apps["provider"]["url"]
    murl = apps["manufacturer"]["url"]
    rurl = apps["retailer"]["url"]

    pstock = safe_get(f"{purl}/api/stock") or []
    row["prov_total_stock"] = sum(s.get("quantity", 0) for s in pstock if isinstance(s, dict))
    for s in pstock:
        if isinstance(s, dict):
            row[f"prov_stock_{s['product_name']}"] = s.get("quantity", 0)
    pcatalog = safe_get(f"{purl}/api/catalog") or []
    for item in pcatalog:
        if not isinstance(item, dict):
            continue
        tiers = item.get("pricing_tiers", [])
        if tiers:
            row[f"prov_price_{item['name']}"] = min(t.get("unit_price", 0) for t in tiers)

    mstock = safe_get(f"{murl}/api/stock") or []
    row["mfg_parts_total"] = sum(s.get("quantity", 0) for s in mstock if isinstance(s, dict))
    morders = safe_get(f"{murl}/api/orders") or []
    row["mfg_orders_pending"] = sum(1 for o in morders if isinstance(o, dict) and o.get("status") == "pending")
    row["mfg_orders_in_progress"] = sum(1 for o in morders if isinstance(o, dict) and o.get("status") == "in_progress")
    row["mfg_orders_shipped_today"] = sum(1 for o in morders if isinstance(o, dict) and o.get("shipped_day") == day)
    mcatalog = safe_get(f"{murl}/api/catalog") or []
    for item in mcatalog:
        if isinstance(item, dict):
            row[f"mfg_price_{item['name']}"] = item.get("wholesale_price", 0)

    rstock = safe_get(f"{rurl}/api/stock") or []
    row["ret_total_stock"] = sum(s.get("quantity", 0) for s in rstock if isinstance(s, dict))
    for s in rstock:
        if isinstance(s, dict):
            row[f"ret_stock_{s['model']}"] = s.get("quantity", 0)
    rcatalog = safe_get(f"{rurl}/api/catalog") or []
    for item in rcatalog:
        if isinstance(item, dict):
            row[f"ret_price_{item['model']}"] = item.get("retail_price", 0)
    rorders = safe_get(f"{rurl}/api/orders") or []
    row["orders_placed_today"] = sum(1 for o in rorders if isinstance(o, dict) and o.get("placed_day") == day)
    row["orders_fulfilled_today"] = sum(1 for o in rorders if isinstance(o, dict) and o.get("fulfilled_day") == day)
    row["orders_backordered_today"] = sum(
        1 for o in rorders
        if isinstance(o, dict) and o.get("status") == "backordered" and o.get("placed_day") == day
    )
    row["orders_backordered_total"] = sum(1 for o in rorders if isinstance(o, dict) and o.get("status") == "backordered")

    return row


# ── Day advance ───────────────────────────────────────────────────────────────

def advance_all(apps: dict) -> None:
    def _advance(name_app):
        name, app = name_app
        result = safe_post(f"{app['url']}/api/day/advance", timeout=90)
        return name, result.get("current_day", "?")

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(_advance, item): item[0] for item in apps.items()}
        for fut in as_completed(futures):
            name, new_day = fut.result()
            print(f"    {name}: day {new_day}", flush=True)


def current_day_all(apps: dict) -> dict:
    return {
        name: (safe_get(f"{app['url']}/api/day/current") or {}).get("current_day", -1)
        for name, app in apps.items()
    }


# ── Main simulation loop ──────────────────────────────────────────────────────

def run_simulation(scenario: dict, n_days: int, log: NarrativeLog) -> list[dict]:
    apps = scenario["apps"]
    scenario_name = scenario.get("name", "unnamed")
    seed = int(scenario.get("seed", 42))
    all_metrics: list[dict] = []

    for _turn in range(n_days):
        days = current_day_all(apps)
        day_values = list(days.values())

        if len(set(day_values)) != 1:
            print(f"  [WARN] Out of sync: {days}", flush=True)
            day = min(v for v in day_values if v > 0)
        else:
            day = day_values[0]

        signal = scenario_for_day(scenario, day)
        modifier = float(signal.get("demand_modifier", 1.0))
        label = signal.get("label", "")

        print(f"\n{'='*55}", flush=True)
        print(f"  DAY {day:3d}  |  modifier={modifier:.2f}  |  {label}", flush=True)
        print(f"{'='*55}", flush=True)

        log.day(day, modifier, label)

        # 1. Metrics snapshot (start of day)
        row = collect_metrics(apps, day, scenario_name, modifier)
        all_metrics.append(row)

        # 2. Generate and inject customer demand
        rng = random.Random(seed + day)
        catalog = safe_get(f"{apps['retailer']['url']}/api/catalog") or []
        demand = generate_customer_demand(day, signal, catalog, rng)
        if demand:
            for order in demand:
                safe_post(f"{apps['retailer']['url']}/api/orders", order)
            log.demand(demand)
            print(f"  Demand: {len(demand)} orders injected", flush=True)

        # 3. Agent turns (with narrative)
        print("  Provider turn...", flush=True)
        provider_turn(apps["provider"]["url"], log, day)

        print("  Manufacturer turn...", flush=True)
        manufacturer_turn(apps["manufacturer"]["url"], scenario.get("manufacturer_policy", {}), log, day)

        print("  Retailer turn...", flush=True)
        retailer_turn(apps["retailer"]["url"], scenario.get("retailer_policy", {}), log, day)

        # 4. Advance day
        print("  Advancing day...", flush=True)
        advance_all(apps)
        log.separator()

        time.sleep(0.3)

    return all_metrics


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, type=Path)
    parser.add_argument("--days", type=int, default=25)
    args = parser.parse_args()

    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    scenario_name = scenario.get("name", args.scenario.stem)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    narrative_path = LOGS_DIR / f"narrative_{scenario_name}.md"
    log = NarrativeLog(narrative_path)
    log.header(scenario_name, args.days)

    print(f"\nScenario : {scenario_name}")
    print(f"Days     : {args.days}")
    print(f"Narrative: {narrative_path}")
    t0 = time.time()

    try:
        all_metrics = run_simulation(scenario, args.days, log)
    finally:
        log.close()

    if not all_metrics:
        print("ERROR: No metrics collected.")
        return 1

    fieldnames = sorted({k for row in all_metrics for k in row})
    csv_path = LOGS_DIR / f"metrics_{scenario_name}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval=0, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_metrics)

    elapsed = time.time() - t0
    print(f"\n{'='*55}")
    print(f"  Finished {args.days} days in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Metrics  : {csv_path}")
    print(f"  Narrative: {narrative_path}")
    print(f"{'='*55}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
