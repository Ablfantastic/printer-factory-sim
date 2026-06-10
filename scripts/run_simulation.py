#!/usr/bin/env python3
"""
Extended simulation runner — uses Claude skill agents for all three roles.

Each day:
  1. Apply the day's scenario signal to execution state.
  2. Inject customer demand into the retailer.
  3. Run the three Claude agents (provider → manufacturer → retailer) sequentially.
     Each agent receives the day number + market signal so it can act on it.
  4. Advance the day on all three apps in parallel.
  5. Collect a completed-day metrics snapshot and write it to CSV.

Usage:
    python scripts/run_simulation.py --scenario scenarios/calm-market.json --days 25
    python scripts/run_simulation.py --scenario scenarios/holiday-rush.json --days 25

Outputs per run:
    logs/metrics_{scenario}.csv       — numeric metrics per day (for charts)
    logs/narrative_{scenario}.md      — agent summaries per day per actor
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = REPO_ROOT / "logs"
SCRIPTS_DIR = Path(__file__).resolve().parent

# Make agent_runner importable from the same scripts/ folder
sys.path.insert(0, str(SCRIPTS_DIR))
from agent_runner import run_agent  # noqa: E402

# Maps scenario role → (skill file name, service working directory)
AGENT_CONFIG: dict[str, tuple[str, Path]] = {
    "provider":     ("provider-manager",     REPO_ROOT / "provider"),
    "manufacturer": ("manufacturer-manager", REPO_ROOT / "manufacturer"),
    "retailer":     ("retail-manager",       REPO_ROOT / "retailer"),
}

# Agent backend/model override — set by main() from CLI args.
_agent_backend: str = "codex"
_agent_model: str = "gpt-5.4-mini"
_retailer_mode: str = "direct"


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def safe_get(url: str, timeout: int = 30) -> list | dict:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [WARN] GET {url}: {exc}", flush=True)
        return {}


def safe_post(url: str, data: dict | None = None, timeout: int = 60) -> dict:
    try:
        r = requests.post(url, json=data or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"  [WARN] POST {url}: {exc}", flush=True)
        return {}


# ── Narrative logger ───────────────────────────────────────────────────────────

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

    def agent(self, role: str, summary: str) -> None:
        self._f.write(f"### {role.capitalize()} Agent\n\n")
        self._f.write(summary.strip() + "\n\n")
        self._f.flush()

    def separator(self) -> None:
        self._f.write("---\n\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()


# ── Scenario helpers ───────────────────────────────────────────────────────────

def scenario_for_day(scenario: dict, day: int) -> dict:
    """Return the merged signal for a given day (defaults + day-specific overrides)."""
    defaults = dict(scenario.get("demand", {}))
    day_signal = scenario.get("days", {}).get(str(day), {})
    if not day_signal:
        active_events = []
        for event in scenario.get("events", []):
            if event.get("start_day", 1) <= day <= event.get("end_day", 9999):
                active_events.append(event)
        if active_events:
            day_signal = {
                "label": " + ".join(event.get("name", "event") for event in active_events),
                "description": " | ".join(
                    event.get("description", "") for event in active_events if event.get("description")
                ),
                "demand_modifier": 1.0,
                "supply_modifier": 1.0,
                "lead_time_modifier": 1.0,
            }
            for event in active_events:
                day_signal["demand_modifier"] *= float(event.get("demand_modifier", 1.0))
                day_signal["supply_modifier"] *= float(event.get("supply_modifier", 1.0))
                day_signal["lead_time_modifier"] *= float(event.get("lead_time_modifier", 1.0))
                if event.get("price_sensitivity") == "high":
                    day_signal["price_sensitivity"] = "high"
                elif event.get("price_sensitivity") and "price_sensitivity" not in day_signal:
                    day_signal["price_sensitivity"] = event["price_sensitivity"]
            day_signal["event_composition"] = "overlapping events multiply demand/supply/lead-time modifiers"
    defaults.update(day_signal)
    defaults.setdefault("base_demand", {"mean": 4, "variance": 1.5})
    defaults.setdefault("demand_modifier", 1.0)
    defaults.setdefault("supply_modifier", 1.0)
    defaults.setdefault("lead_time_modifier", 1.0)
    defaults.setdefault("price_sensitivity", "normal")
    return defaults


def _load_provider_initial_stock() -> dict[str, int]:
    """Read initial_stock from provider/seed-provider.json (authoritative starting levels)."""
    seed_path = REPO_ROOT / "provider" / "seed-provider.json"
    try:
        data = json.loads(seed_path.read_text(encoding="utf-8"))
        return {p["name"]: p["initial_stock"] for p in data.get("products", [])}
    except Exception:
        return {}


def _fmt_action_command(commands: list[str]) -> str:
    return " && ".join(commands) if commands else "none"


def _legacy_fetch_provider_state(url: str) -> str:
    """Fetch and format provider state as human-readable text.

    Includes initial_stock so the agent can apply the 50%/150% restock rules.
    Only pending orders included (not history).
    """
    day    = (safe_get(f"{url}/api/day/current") or {}).get("current_day", "?")
    stock  = safe_get(f"{url}/api/stock") or []
    orders = safe_get(f"{url}/api/orders") or []
    catalog= safe_get(f"{url}/api/catalog") or []
    initial = _load_provider_initial_stock()

    # Only pending orders are actionable
    pending = [o for o in orders if isinstance(o, dict) and o.get("status") == "pending"]

    lines = [f"=== PROVIDER STATE (Day {day}) ==="]
    lines.append("STOCK (current / initial / 50%-threshold):")
    for s in stock:
        if isinstance(s, dict):
            name = s.get('product_name')
            qty  = s.get('quantity', 0)
            init = initial.get(name, 0)
            thresh = init // 2
            flag = " ← RESTOCK" if qty < thresh else ""
            lines.append(f"  {name}: {qty} / {init} (restock if < {thresh}){flag}")
    lines.append(f"PENDING ORDERS: {len(pending)}")
    for o in pending:
        lines.append(f"  order {o.get('id')}: {o.get('product_name')} x{o.get('quantity')}")
    lines.append("CATALOG (tiers):")
    for item in catalog:
        if isinstance(item, dict):
            tiers = item.get("pricing_tiers", [])
            tier_str = ", ".join(f"t{t.get('min_quantity')}={t.get('unit_price')}" for t in tiers)
            lines.append(f"  {item.get('name')}: [{tier_str}]")
    return "\n".join(lines)


def _legacy_fetch_manufacturer_state(url: str) -> str:
    """Fetch and format manufacturer state as human-readable text.

    Only includes actionable (non-completed) data to keep the prompt size stable.
    """
    day      = (safe_get(f"{url}/api/day/current") or {}).get("current_day", "?")
    orders   = safe_get(f"{url}/api/orders") or []
    stock    = safe_get(f"{url}/api/stock") or []
    finished = safe_get(f"{url}/api/finished-stock") or []
    capacity = safe_get(f"{url}/api/capacity") or {}
    purchases= safe_get(f"{url}/api/purchases") or []
    catalog  = safe_get(f"{url}/api/catalog") or []

    # Only show actionable orders (exclude completed/cancelled)
    DONE = {"completed", "delivered", "cancelled"}
    active_orders = [o for o in orders if isinstance(o, dict) and o.get("status") not in DONE]

    lines = [f"=== MANUFACTURER STATE (Day {day}) ==="]
    lines.append(f"ACTIVE SALES ORDERS ({len(active_orders)}):")
    for o in active_orders:
        lines.append(f"  id={o.get('id')} model={o.get('model')} qty={o.get('quantity')} status={o.get('status')}")
    lines.append("RAW PARTS STOCK:")
    for s in stock:
        if isinstance(s, dict):
            lines.append(f"  {s.get('product_name')}: {s.get('quantity')}")
    lines.append("FINISHED STOCK:")
    for s in finished:
        if isinstance(s, dict):
            lines.append(f"  {s.get('model')}: {s.get('quantity')}")
    lines.append(f"CAPACITY: {capacity.get('daily_capacity_total')} units/day, utilisation {capacity.get('utilisation_pct', 0):.0f}%")
    open_po = [p for p in purchases if isinstance(p, dict) and p.get("status") not in ("delivered",)]
    lines.append(f"OPEN PURCHASE ORDERS ({len(open_po)}):")
    for p in open_po:
        lines.append(f"  {p.get('product_name')} x{p.get('quantity')} arrives day {p.get('expected_day')}")
    lines.append("WHOLESALE PRICES:")
    for item in catalog:
        if isinstance(item, dict):
            lines.append(f"  {item.get('name')}: {item.get('wholesale_price')}")
    return "\n".join(lines)


def _legacy_fetch_retailer_state(url: str) -> str:
    """Fetch and format retailer state as human-readable text."""
    day      = (safe_get(f"{url}/api/day/current") or {}).get("current_day", "?")
    stock    = safe_get(f"{url}/api/stock") or []
    orders   = safe_get(f"{url}/api/orders") or []
    purchases= safe_get(f"{url}/api/purchases") or []
    catalog  = safe_get(f"{url}/api/catalog") or []

    lines = [f"=== RETAILER STATE (Day {day}) ==="]
    lines.append("STOCK:")
    for s in stock:
        if isinstance(s, dict):
            lines.append(f"  {s.get('model')}: {s.get('quantity')}")
    # Only actionable orders
    pending = [o for o in orders if isinstance(o, dict) and o.get("status") == "pending"]
    backordered = [o for o in orders if isinstance(o, dict) and o.get("status") == "backordered"]
    lines.append(f"PENDING CUSTOMER ORDERS ({len(pending)}):")
    for o in pending:
        lines.append(f"  id={o.get('id')} model={o.get('model')}")
    lines.append(f"BACKORDERED ORDERS ({len(backordered)}) - for context, already marked:")
    for o in backordered[-5:]:  # only last 5 to show recent trend
        lines.append(f"  id={o.get('id')} model={o.get('model')}")
    open_po = [p for p in purchases if isinstance(p, dict) and p.get("status") not in ("delivered", "failed", "cancelled")]
    lines.append(f"OPEN PURCHASE ORDERS ({len(open_po)}):")
    for p in open_po:
        lines.append(f"  {p.get('model')} x{p.get('quantity')} arrives day {p.get('expected_day')}")
    lines.append("RETAIL PRICES:")
    for item in catalog:
        if isinstance(item, dict):
            lines.append(f"  {item.get('model')}: {item.get('retail_price')} (wholesale: {item.get('wholesale_price')})")
    return "\n".join(lines)


def fetch_provider_state(url: str, signal: dict | None = None) -> str:
    """Fetch provider state plus a precomputed one-call action hint."""
    day = (safe_get(f"{url}/api/day/current") or {}).get("current_day", "?")
    stock = safe_get(f"{url}/api/stock") or []
    orders = safe_get(f"{url}/api/orders") or []
    catalog = safe_get(f"{url}/api/catalog") or []
    initial = _load_provider_initial_stock()

    supply_mod = float((signal or {}).get("supply_modifier", 1.0))
    demand_mod = float((signal or {}).get("demand_modifier", 1.0))

    # Raise restock threshold when demand is elevated (restock earlier)
    thresh_pct = 0.65 if demand_mod >= 2.0 else 0.50

    pending = [o for o in orders if isinstance(o, dict) and o.get("status") == "pending"]
    restock_commands: list[str] = []
    price_hints: list[str] = []

    # Build catalog lookup for price hint computation
    catalog_by_name = {item.get("name"): item for item in catalog if isinstance(item, dict)}

    lines = [f"=== PROVIDER STATE (Day {day}) ==="]
    lines.append(f"STOCK (current / initial / {thresh_pct*100:.0f}%-threshold):")
    for s in stock:
        if not isinstance(s, dict):
            continue
        name = s.get("product_name")
        qty = int(s.get("quantity", 0))
        init = initial.get(name, 0)
        thresh = int(init * thresh_pct)
        restock_qty = max(0, init - qty)
        flag = " <- RESTOCK" if qty < thresh else ""
        if qty < thresh and restock_qty > 0:
            restock_commands.append(f"./start_cli.sh restock {name} {restock_qty}")
        if init and qty > init * 1.5:
            price_hints.append(f"{name}: stock > 150% initial; consider lowering top tier 5-10%")
        elif init and qty < init * 0.3:
            price_hints.append(f"{name}: stock < 30% initial; consider raising top tier 5-10%")
        lines.append(f"  {name}: {qty} / {init} (restock if < {thresh}){flag}")

    lines.append(f"PENDING ORDERS: {len(pending)}")
    for o in pending:
        lines.append(f"  order {o.get('id')}: {o.get('product_name')} x{o.get('quantity')}")
    lines.append("CATALOG (tiers):")
    for item in catalog:
        if isinstance(item, dict):
            tiers = item.get("pricing_tiers", [])
            tier_str = ", ".join(f"t{t.get('min_quantity')}={t.get('unit_price')}" for t in tiers)
            lines.append(f"  {item.get('name')}: [{tier_str}]")

    # Compute supply-shortage price raise — one command raises ALL products at once
    supply_price_cmd = ""
    if supply_mod <= 0.6:
        raise_pct = 12 if supply_mod <= 0.4 else 8  # integer percent
        supply_price_cmd = f"./start_cli.sh price raise-all {raise_pct}"

    lines.append("ACTION HINT:")
    lines.append(f"  Recommended bash: {_fmt_action_command(restock_commands)}")
    lines.append(f"  Price hints: {'; '.join(price_hints) if price_hints else 'none'}")
    lines.append(
        f"  SUPPLY SHORTAGE PRICE RAISE (supply_modifier={supply_mod:.2f}): "
        f"{supply_price_cmd if supply_price_cmd else 'none'}"
    )
    return "\n".join(lines)


def fetch_manufacturer_state(url: str, signal: dict | None = None) -> str:
    """Fetch manufacturer state plus supplier catalog and one-call action hint."""
    day = (safe_get(f"{url}/api/day/current") or {}).get("current_day", "?")
    orders = safe_get(f"{url}/api/orders") or []
    stock = safe_get(f"{url}/api/stock") or []
    finished = safe_get(f"{url}/api/finished-stock") or []
    capacity = safe_get(f"{url}/api/capacity") or {}
    purchases = safe_get(f"{url}/api/purchases") or []
    catalog = safe_get(f"{url}/api/catalog") or []
    providers = safe_get(f"{url}/api/providers") or []

    demand_mod = float((signal or {}).get("demand_modifier", 1.0))
    # When demand is elevated, order extra buffer on top of strict shortage
    # modifier 1.0 → +0%, 1.5 → +30%, 2.0 → +60%, 3.0 → +80%
    buffer_factor = max(0.0, min(0.8, (demand_mod - 1.0) * 0.6))

    done = {"completed", "delivered", "cancelled"}
    active_orders = [o for o in orders if isinstance(o, dict) and o.get("status") not in done]
    pending_orders = [o for o in active_orders if o.get("status") == "pending"]
    # In-progress orders have already consumed their BOM when production starts.
    committed_orders = [o for o in active_orders if o.get("status") == "released"]
    catalog_by_model = {item.get("name"): item for item in catalog if isinstance(item, dict)}
    raw_stock = {s.get("product_name"): int(s.get("quantity", 0)) for s in stock if isinstance(s, dict)}
    finished_stock = {s.get("model"): int(s.get("quantity", 0)) for s in finished if isinstance(s, dict)}

    open_po = [p for p in purchases if isinstance(p, dict) and p.get("status") not in ("delivered",)]
    incoming: dict[str, int] = {}
    for p in open_po:
        product = p.get("product_name")
        incoming[product] = incoming.get(product, 0) + int(p.get("quantity", 0))

    supplier_name = None
    if isinstance(providers, list):
        ok_provider = next((p for p in providers if isinstance(p, dict) and p.get("status") == "ok"), None)
        any_provider = next((p for p in providers if isinstance(p, dict)), None)
        supplier_name = (ok_provider or any_provider or {}).get("name")
    supplier_catalog = safe_get(f"{url}/api/providers/{quote(supplier_name)}/catalog") if supplier_name else []
    supplier_products = {item.get("name") for item in supplier_catalog if isinstance(item, dict)}

    release_commands = [f"./start_cli.sh production release {o.get('id')}" for o in pending_orders]
    required_parts: dict[str, int] = {}
    for o in pending_orders + committed_orders:
        model = o.get("model")
        qty = int(o.get("quantity", 0))
        if o.get("status") == "pending" and finished_stock.get(model, 0) >= qty:
            finished_stock[model] -= qty
            continue
        bom = catalog_by_model.get(model, {}).get("bom", {})
        for part, per_unit in bom.items():
            required_parts[part] = required_parts.get(part, 0) + int(per_unit) * qty

    purchase_commands: list[str] = []
    parts_needing_orders: list[str] = []
    for part, required in sorted(required_parts.items()):
        target_required = max(required, round(required * (1 + buffer_factor)))
        shortage = target_required - raw_stock.get(part, 0) - incoming.get(part, 0)
        if shortage <= 0:
            continue
        if supplier_products and part not in supplier_products:
            continue
        parts_needing_orders.append(f"{part} x{shortage}")
        purchase_commands.append(
            f"./start_cli.sh purchase create --supplier {supplier_name or '<supplier>'} --product {part} --qty {shortage}"
        )

    # Wholesale price hint: raise when heavily overloaded or backlog is large
    util_pct = float(capacity.get("utilisation_pct", 0))
    n_active = len(active_orders)
    wholesale_price_cmd = ""
    if util_pct >= 200 or (demand_mod >= 2.0 and n_active >= 20):
        raise_pct_int = 8 if util_pct >= 300 else 5  # integer percent
        wholesale_price_cmd = f"./start_cli.sh price raise-all {raise_pct_int}"

    lines = [f"=== MANUFACTURER STATE (Day {day}) ==="]
    lines.append(f"ACTIVE SALES ORDERS ({len(active_orders)}):")
    for o in active_orders:
        lines.append(f"  id={o.get('id')} model={o.get('model')} qty={o.get('quantity')} status={o.get('status')}")
    lines.append("RAW PARTS STOCK:")
    for s in stock:
        if isinstance(s, dict):
            lines.append(f"  {s.get('product_name')}: {s.get('quantity')}")
    lines.append("FINISHED STOCK:")
    for s in finished:
        if isinstance(s, dict):
            lines.append(f"  {s.get('model')}: {s.get('quantity')}")
    lines.append(f"CAPACITY: {capacity.get('daily_capacity_total')} units/day, utilisation {capacity.get('utilisation_pct', 0):.0f}%")
    lines.append(f"OPEN PURCHASE ORDERS ({len(open_po)}):")
    for p in open_po:
        lines.append(f"  {p.get('product_name')} x{p.get('quantity')} arrives day {p.get('expected_day')}")
    lines.append("SUPPLIER CATALOG (pre-fetched; do not run suppliers catalog):")
    if supplier_name:
        lines.append(f"  supplier={supplier_name}; products={', '.join(sorted(supplier_products))}")
    else:
        lines.append("  no supplier available")
    lines.append("WHOLESALE PRICES:")
    for item in catalog:
        if isinstance(item, dict):
            lines.append(f"  {item.get('name')}: {item.get('wholesale_price')}")
    lines.append("ACTION HINT:")
    lines.append(f"  Recommended bash: {_fmt_action_command(release_commands + purchase_commands)}")
    lines.append(f"  Parts needing orders: {', '.join(parts_needing_orders) if parts_needing_orders else 'none'}")
    lines.append(
        f"  WHOLESALE PRICE RAISE (utilisation={util_pct:.0f}%, demand_modifier={demand_mod:.1f}): "
        f"{wholesale_price_cmd if wholesale_price_cmd else 'none'}"
    )
    return "\n".join(lines)


def fetch_retailer_state(url: str, signal: dict | None = None) -> str:
    """Fetch retailer state plus one-call process and purchase hint."""
    day = (safe_get(f"{url}/api/day/current") or {}).get("current_day", "?")
    stock = safe_get(f"{url}/api/stock") or []
    orders = safe_get(f"{url}/api/orders") or []
    purchases = safe_get(f"{url}/api/purchases") or []
    catalog = safe_get(f"{url}/api/catalog") or []

    demand_mod = float((signal or {}).get("demand_modifier", 1.0))
    price_sens = (signal or {}).get("price_sensitivity", "normal")

    # Buffer target = 3 days of expected demand (scales with demand_modifier)
    base_daily = 4  # scenario base_demand
    daily_est = max(4, round(base_daily * demand_mod))
    buffer = daily_est * 3  # 3-day safety stock

    stock_by_model = {s.get("model"): int(s.get("quantity", 0)) for s in stock if isinstance(s, dict)}
    pending = [o for o in orders if isinstance(o, dict) and o.get("status") == "pending"]
    backordered = [o for o in orders if isinstance(o, dict) and o.get("status") == "backordered"]
    pending_by_model: dict[str, int] = {}
    backordered_by_model: dict[str, int] = {}
    for o in pending:
        pending_by_model[o.get("model")] = pending_by_model.get(o.get("model"), 0) + int(o.get("quantity", 1))
    for o in backordered:
        backordered_by_model[o.get("model")] = backordered_by_model.get(o.get("model"), 0) + int(o.get("quantity", 1))

    open_po = [p for p in purchases if isinstance(p, dict) and p.get("status") not in ("delivered", "failed", "cancelled")]
    incoming_by_model: dict[str, int] = {}
    for p in open_po:
        incoming_by_model[p.get("model")] = incoming_by_model.get(p.get("model"), 0) + int(p.get("quantity", 0))

    action_commands = ["./start_cli.sh process-orders"]
    retail_price_cmds: list[str] = []
    for item in catalog:
        if not isinstance(item, dict):
            continue
        model = item.get("model")
        current_price = float(item.get("retail_price", 0))
        wholesale = float(item.get("wholesale_price", 0))
        pending_qty = pending_by_model.get(model, 0)
        backordered_qty = backordered_by_model.get(model, 0)
        post_process_stock = max(0, stock_by_model.get(model, 0) - pending_qty)
        target = max(buffer, pending_qty + backordered_qty + buffer)
        covered = post_process_stock + incoming_by_model.get(model, 0)
        qty = target - covered
        if qty > 0:
            action_commands.append(f"./start_cli.sh purchase create {model} {qty}")

        # Retail price hint computed per model, but we'll emit a single raise-all command below

    lines = [f"=== RETAILER STATE (Day {day}) ==="]
    lines.append(f"  (buffer target: {buffer} units/model = {daily_est} daily_est x 3 days)")
    lines.append("STOCK:")
    for s in stock:
        if isinstance(s, dict):
            lines.append(f"  {s.get('model')}: {s.get('quantity')}")
    lines.append(f"PENDING CUSTOMER ORDERS ({len(pending)}):")
    for o in pending:
        lines.append(f"  id={o.get('id')} model={o.get('model')}")
    lines.append(f"BACKORDERED ORDERS ({len(backordered)}) - for context, already marked:")
    for o in backordered[-5:]:
        lines.append(f"  id={o.get('id')} model={o.get('model')}")
    lines.append(f"OPEN PURCHASE ORDERS ({len(open_po)}):")
    for p in open_po:
        lines.append(f"  {p.get('model')} x{p.get('quantity')} arrives day {p.get('expected_day')}")
    lines.append("RETAIL PRICES:")
    for item in catalog:
        if isinstance(item, dict):
            lines.append(f"  {item.get('model')}: {item.get('retail_price')} (wholesale: {item.get('wholesale_price')})")
    # Single raise-all command for retail prices
    total_backlog = sum(backordered_by_model.values())
    any_stock_empty = any(stock_by_model.get(item.get("model"), 0) == 0 for item in catalog if isinstance(item, dict))
    retail_price_cmd = ""
    if demand_mod >= 2.0 and any_stock_empty and total_backlog >= 10:
        raise_pct_int = 10 if price_sens == "high" else 7
        retail_price_cmd = f"./start_cli.sh price raise-all {raise_pct_int}"
    elif demand_mod <= 0.8 and not any_stock_empty and total_backlog == 0:
        retail_price_cmd = "./start_cli.sh price raise-all -5"  # negative = lower

    lines = [f"=== RETAILER STATE (Day {day}) ==="]
    lines.append(f"  (buffer target: {buffer} units/model = {daily_est} daily_est x 3 days)")
    lines.append("STOCK:")
    for s in stock:
        if isinstance(s, dict):
            lines.append(f"  {s.get('model')}: {s.get('quantity')}")
    lines.append(f"PENDING CUSTOMER ORDERS ({len(pending)}):")
    for o in pending:
        lines.append(f"  id={o.get('id')} model={o.get('model')}")
    lines.append(f"BACKORDERED ORDERS ({len(backordered)}) - for context, already marked:")
    for o in backordered[-5:]:
        lines.append(f"  id={o.get('id')} model={o.get('model')}")
    lines.append(f"OPEN PURCHASE ORDERS ({len(open_po)}):")
    for p in open_po:
        lines.append(f"  {p.get('model')} x{p.get('quantity')} arrives day {p.get('expected_day')}")
    lines.append("RETAIL PRICES:")
    for item in catalog:
        if isinstance(item, dict):
            lines.append(f"  {item.get('model')}: {item.get('retail_price')} (wholesale: {item.get('wholesale_price')})")
    lines.append("ACTION HINT:")
    lines.append(f"  Recommended bash: {_fmt_action_command(action_commands)}")
    lines.append(
        f"  RETAIL PRICE CHANGE (demand_modifier={demand_mod:.1f}, backlog={total_backlog}): "
        f"{retail_price_cmd if retail_price_cmd else 'none'}"
    )
    return "\n".join(lines)


def build_agent_context(role: str, day: int, signal: dict, apps: dict) -> str:
    """Build the context string injected into the agent's user prompt.

    Pre-fetches current service state so the agent can skip the assess phase.
    """
    modifier = float(signal.get("demand_modifier", 1.0))
    label = signal.get("label", signal.get("name", ""))
    supply_mod = float(signal.get("supply_modifier", 1.0))
    lead_mod = float(signal.get("lead_time_modifier", 1.0))
    price_sens = signal.get("price_sensitivity", "normal")

    lines = [
        f"Today is simulation day {day}.",
        f"Market signal: {label or '(none)'}",
        f"  demand_modifier: {modifier:.2f}",
    ]
    if role in ("provider", "manufacturer"):
        lines.append(f"  supply_modifier: {supply_mod:.2f}")
    if role in ("provider", "manufacturer"):
        lines.append(f"  lead_time_modifier: {lead_mod:.2f}")
    if role == "retailer":
        lines.append(f"  price_sensitivity: {price_sens}")
    if signal.get("event_composition"):
        lines.append(f"  event_composition: {signal['event_composition']}")

    # Pre-fetch state so agent skips assess bash calls
    try:
        url = apps[role]["url"]
        if role == "provider":
            state_text = fetch_provider_state(url, signal)
        elif role == "manufacturer":
            state_text = fetch_manufacturer_state(url, signal)
        else:
            state_text = fetch_retailer_state(url, signal)
        lines.append("")
        lines.append(state_text)
        lines.append("")
        lines.append("State is already provided above. Do NOT run assessment commands. Go directly to actions.")
    except Exception as exc:
        lines.append(f"(State pre-fetch failed: {exc} — run assess manually)")

    return "\n".join(lines)


def apply_provider_market_signal(apps: dict, signal: dict) -> None:
    """Apply scenario supply/lead-time modifiers to provider execution state."""
    provider_url = apps["provider"]["url"]
    payload = {
        "supply_modifier": float(signal.get("supply_modifier", 1.0)),
        "lead_time_modifier": float(signal.get("lead_time_modifier", 1.0)),
        "label": signal.get("label", signal.get("name", "")),
    }
    result = safe_post(f"{provider_url}/api/market-signal", payload, timeout=30)
    if not result:
        print("  [WARN] Provider market signal was not applied", flush=True)


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


# ── Agent turns via Claude skills ──────────────────────────────────────────────

def retailer_direct_turn(day: int, signal: dict, apps: dict) -> str:
    """Run the retailer policy directly via REST instead of spending an LLM turn."""
    rurl = apps["retailer"]["url"]
    actions: list[str] = []

    safe_post(f"{rurl}/api/catalog/sync", timeout=30)

    stock_rows = safe_get(f"{rurl}/api/stock") or []
    stock_by_model = {
        row.get("model"): int(row.get("quantity", 0))
        for row in stock_rows if isinstance(row, dict)
    }

    pending = safe_get(f"{rurl}/api/orders?status=pending") or []
    fulfilled = 0
    backordered = 0
    for order in pending:
        if not isinstance(order, dict):
            continue
        model = order.get("model")
        qty = int(order.get("quantity", 1))
        order_id = order.get("id")
        if stock_by_model.get(model, 0) >= qty:
            result = safe_post(f"{rurl}/api/orders/{order_id}/fulfill", timeout=30)
            if result:
                stock_by_model[model] = stock_by_model.get(model, 0) - qty
                fulfilled += 1
        else:
            result = safe_post(f"{rurl}/api/orders/{order_id}/backorder", timeout=30)
            if result:
                backordered += 1
    actions.append(f"processed orders ({fulfilled} fulfilled, {backordered} backordered)")

    all_backorders = safe_get(f"{rurl}/api/orders?status=backordered") or []
    backordered_by_model: dict[str, int] = {}
    for order in all_backorders:
        if isinstance(order, dict):
            model = order.get("model")
            backordered_by_model[model] = backordered_by_model.get(model, 0) + int(order.get("quantity", 1))

    purchases = safe_get(f"{rurl}/api/purchases") or []
    incoming_by_model: dict[str, int] = {}
    for purchase in purchases:
        if isinstance(purchase, dict) and purchase.get("status") not in ("delivered", "failed", "cancelled"):
            model = purchase.get("model")
            incoming_by_model[model] = incoming_by_model.get(model, 0) + int(purchase.get("quantity", 0))

    catalog = safe_get(f"{rurl}/api/catalog") or []
    demand_mod = float(signal.get("demand_modifier", 1.0))
    price_sens = signal.get("price_sensitivity", "normal")
    daily_est = max(4, round(4 * demand_mod))
    buffer = daily_est * 3
    purchases_created: list[str] = []
    for item in catalog:
        if not isinstance(item, dict):
            continue
        model = item.get("model")
        target = max(buffer, backordered_by_model.get(model, 0) + buffer)
        covered = stock_by_model.get(model, 0) + incoming_by_model.get(model, 0)
        qty = target - covered
        if qty <= 0:
            continue
        result = safe_post(f"{rurl}/api/purchases", {"model": model, "quantity": qty}, timeout=60)
        if result:
            purchases_created.append(f"{model} x{qty}")
            incoming_by_model[model] = incoming_by_model.get(model, 0) + qty
    if purchases_created:
        actions.append("created purchase orders: " + ", ".join(purchases_created))
    else:
        actions.append("created purchase orders: none")

    total_backlog = sum(backordered_by_model.values())
    any_stock_empty = any(stock_by_model.get(item.get("model"), 0) == 0 for item in catalog if isinstance(item, dict))
    if demand_mod >= 2.0 and any_stock_empty and total_backlog >= 10:
        raise_pct = 10 if price_sens == "high" else 7
        changed: list[str] = []
        for item in catalog:
            if not isinstance(item, dict):
                continue
            model = item.get("model")
            current_price = float(item.get("retail_price") or 0)
            wholesale = float(item.get("wholesale_price") or 0)
            new_price = round(max(wholesale * 1.05, current_price * (1 + raise_pct / 100)), 2)
            query = urlencode({"model": model})
            result = safe_post(f"{rurl}/api/catalog/price?{query}", {"price": new_price}, timeout=30)
            if result:
                changed.append(f"{model} -> {new_price}")
        if changed:
            actions.append(f"raised retail prices {raise_pct}%: " + ", ".join(changed))

    final_stock = safe_get(f"{rurl}/api/stock") or []
    stock_text = ", ".join(
        f"{row.get('model')} {row.get('quantity')}"
        for row in final_stock if isinstance(row, dict)
    ) or "unknown"
    return (
        "Retailer direct policy executed without Claude.\n\n"
        "## END-OF-DAY SUMMARY\n"
        f"- Stock: {stock_text}\n"
        f"- Actions taken: {'; '.join(actions)}\n"
        f"- Risk: {total_backlog} customer units remain backordered; fulfillment depends on manufacturer deliveries."
    )


def run_role(role: str, day: int, signal: dict, apps: dict, model: str = "", max_turns: int = 8) -> str:
    """Run one Claude agent turn for the given role.

    Returns the agent's final text summary.
    """
    if role == "retailer" and _retailer_mode == "direct":
        print("  [retailer] direct policy starting...", flush=True)
        t0 = time.time()
        summary = retailer_direct_turn(day, signal, apps)
        elapsed = time.time() - t0
        print(f"  [retailer] done in {elapsed:.1f}s", flush=True)
        return summary

    skill_name, workdir = AGENT_CONFIG[role]
    context = build_agent_context(role, day, signal, apps)
    print(f"  [{role}] Claude agent starting...", flush=True)
    t0 = time.time()
    try:
        summary = run_agent(
            skill_name,
            workdir,
            model=model,
            extra_context=context,
            max_turns=max_turns,
            backend=_agent_backend,
        )
    except Exception as exc:
        summary = f"Agent turn failed: {exc}"
        print(f"  [{role}] ERROR: {exc}", flush=True)
    elapsed = time.time() - t0
    print(f"  [{role}] done in {elapsed:.1f}s", flush=True)
    return summary


# ── Metrics snapshot ───────────────────────────────────────────────────────────

def collect_metrics(apps: dict, day: int, scenario_name: str, modifier: float) -> dict:
    """Snapshot all numeric metrics for one simulation day.

    Columns captured
    ----------------
    Provider
      prov_total_stock, prov_stock_{product}
      prov_price_{product}  (lowest tier — backward compat)
      prov_price_{product}_t{min_qty}  (per tier)
      prov_orders_pending, prov_orders_in_transit, prov_orders_delivered
      prov_orders_delivered_today

    Manufacturer
      mfg_parts_total, mfg_part_{name}  (raw-parts inventory)
      mfg_finished_total, mfg_finished_{model}  (finished-printer stock)
      mfg_so_{status}  (sales orders by status: pending/released/in_progress/shipped/completed/delivered)
      mfg_price_{model}  (wholesale price)
      mfg_utilisation_pct, mfg_daily_capacity
      mfg_po_open  (open purchase orders to provider)

    Retailer
      ret_total_stock, ret_stock_{model}
      ret_price_{model}
      orders_placed_today, orders_fulfilled_today
      orders_backordered_today, orders_backordered_total
      ret_po_open  (open purchase orders to manufacturer)
    """
    row: dict = {"day": day, "scenario": scenario_name, "demand_modifier": modifier}

    purl = apps["provider"]["url"]
    murl = apps["manufacturer"]["url"]
    rurl = apps["retailer"]["url"]

    # ── Provider ──────────────────────────────────────────────────────────────
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
            # lowest tier for backward compat
            row[f"prov_price_{item['name']}"] = min(t.get("unit_price", 0) for t in tiers)
            # per-tier columns
            for tier in tiers:
                min_qty = tier.get("min_quantity", 0)
                row[f"prov_price_{item['name']}_t{min_qty}"] = tier.get("unit_price", 0)

    porders = safe_get(f"{purl}/api/orders") or []
    IN_TRANSIT = {"pending", "confirmed", "in_progress", "shipped"}
    row["prov_orders_pending"]   = sum(1 for o in porders if isinstance(o, dict) and o.get("status") == "pending")
    row["prov_orders_in_transit"]= sum(1 for o in porders if isinstance(o, dict) and o.get("status") in IN_TRANSIT - {"pending"})
    row["prov_orders_delivered"] = sum(1 for o in porders if isinstance(o, dict) and o.get("status") == "delivered")
    row["prov_orders_delivered_today"] = sum(
        1 for o in porders
        if isinstance(o, dict) and o.get("status") == "delivered" and o.get("delivered_day") == day
    )

    # ── Manufacturer — raw parts ──────────────────────────────────────────────
    mstock = safe_get(f"{murl}/api/stock") or []
    row["mfg_parts_total"] = sum(s.get("quantity", 0) for s in mstock if isinstance(s, dict))
    for s in mstock:
        if isinstance(s, dict):
            row[f"mfg_part_{s['product_name']}"] = s.get("quantity", 0)

    # ── Manufacturer — finished-printer stock ──────────────────────────────────
    mfinished = safe_get(f"{murl}/api/finished-stock") or []
    row["mfg_finished_total"] = sum(s.get("quantity", 0) for s in mfinished if isinstance(s, dict))
    for s in mfinished:
        if isinstance(s, dict):
            row[f"mfg_finished_{s['model']}"] = s.get("quantity", 0)

    # ── Manufacturer — sales orders by status ─────────────────────────────────
    morders = safe_get(f"{murl}/api/orders") or []
    for status in ("pending", "released", "in_progress", "shipped", "completed", "delivered"):
        row[f"mfg_so_{status}"] = sum(
            1 for o in morders if isinstance(o, dict) and o.get("status") == status
        )
    row["mfg_orders_shipped_today"] = sum(
        1 for o in morders if isinstance(o, dict) and o.get("shipped_day") == day
    )

    # ── Manufacturer — catalog prices + capacity ───────────────────────────────
    mcatalog = safe_get(f"{murl}/api/catalog") or []
    for item in mcatalog:
        if isinstance(item, dict):
            row[f"mfg_price_{item['name']}"] = item.get("wholesale_price", 0)

    mcapacity = safe_get(f"{murl}/api/capacity") or {}
    row["mfg_utilisation_pct"] = mcapacity.get("utilisation_pct", 0)
    row["mfg_daily_capacity"]  = mcapacity.get("daily_capacity_total", 0)

    # ── Manufacturer — open purchase orders to provider ────────────────────────
    mpurchases = safe_get(f"{murl}/api/purchases") or []
    row["mfg_po_open"] = sum(
        1 for p in mpurchases if isinstance(p, dict) and p.get("status") not in ("delivered",)
    )

    # ── Retailer — stock ───────────────────────────────────────────────────────
    rstock = safe_get(f"{rurl}/api/stock") or []
    row["ret_total_stock"] = sum(s.get("quantity", 0) for s in rstock if isinstance(s, dict))
    for s in rstock:
        if isinstance(s, dict):
            row[f"ret_stock_{s['model']}"] = s.get("quantity", 0)

    # ── Retailer — catalog prices ──────────────────────────────────────────────
    rcatalog = safe_get(f"{rurl}/api/catalog") or []
    for item in rcatalog:
        if isinstance(item, dict):
            row[f"ret_price_{item['model']}"] = item.get("retail_price", 0)

    # ── Retailer — customer order counts ──────────────────────────────────────
    rorders = safe_get(f"{rurl}/api/orders") or []
    row["orders_placed_today"]     = sum(1 for o in rorders if isinstance(o, dict) and o.get("placed_day") == day)
    row["orders_fulfilled_today"]  = sum(1 for o in rorders if isinstance(o, dict) and o.get("fulfilled_day") == day)
    row["orders_backordered_today"]= sum(
        1 for o in rorders
        if isinstance(o, dict) and o.get("status") == "backordered" and o.get("placed_day") == day
    )
    row["orders_backordered_total"]= sum(
        1 for o in rorders if isinstance(o, dict) and o.get("status") == "backordered"
    )

    # ── Retailer — open purchase orders to manufacturer ────────────────────────
    rpurchases = safe_get(f"{rurl}/api/purchases") or []
    row["ret_po_open"] = sum(
        1 for p in rpurchases if isinstance(p, dict) and p.get("status") not in ("delivered", "failed", "cancelled")
    )

    return row


# ── Day advance ────────────────────────────────────────────────────────────────

def advance_all(apps: dict) -> None:
    """Advance the day on all three apps in parallel."""
    def _advance(name_app):
        name, app = name_app
        result = safe_post(f"{app['url']}/api/day/advance", timeout=180)
        new_day = result.get("current_day") if isinstance(result, dict) else None
        if new_day is None:
            raise RuntimeError(f"{name} did not return current_day while advancing")
        return name, new_day

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


# ── Main simulation loop ───────────────────────────────────────────────────────

def run_simulation(scenario: dict, n_days: int, log: NarrativeLog, max_turns: int = 8) -> list[dict]:
    apps = scenario["apps"]
    scenario_name = scenario.get("name", "unnamed")
    seed = int(scenario.get("seed", 42))
    all_metrics: list[dict] = []

    for _turn in range(n_days):
        days = current_day_all(apps)
        day_values = list(days.values())

        if len(set(day_values)) != 1:
            raise RuntimeError(
                f"Apps out of sync before demand injection: {days}. "
                "Reset or repair app days before running a clean simulation."
            )
        else:
            day = day_values[0]

        signal = scenario_for_day(scenario, day)
        modifier = float(signal.get("demand_modifier", 1.0))
        label = signal.get("label", signal.get("name", ""))

        print(f"\n{'='*60}", flush=True)
        print(f"  DAY {day:3d}  |  modifier={modifier:.2f}  |  {label}", flush=True)
        print(f"{'='*60}", flush=True)

        log.day(day, modifier, label)

        # 1. Apply execution-level market signal before agents place upstream orders.
        apply_provider_market_signal(apps, signal)

        # 2. Generate and inject customer demand into retailer
        rng = random.Random(seed + day)
        catalog = safe_get(f"{apps['retailer']['url']}/api/catalog") or []
        demand = generate_customer_demand(day, signal, catalog, rng)
        if demand:
            for order in demand:
                safe_post(f"{apps['retailer']['url']}/api/orders", order)
            log.demand(demand)
            print(f"  Demand: {len(demand)} orders injected", flush=True)
        else:
            print("  Demand: 0 orders this day", flush=True)

        # 3. Agent turns — provider first (manufacturer may call it), then manufacturer, then retailer
        for role in ("provider", "manufacturer", "retailer"):
            print(f"  Running {role} agent...", flush=True)
            summary = run_role(role, day, signal, apps, model=_agent_model, max_turns=max_turns)
            log.agent(role, summary)

        # 4. Advance day on all apps
        print("  Advancing day...", flush=True)
        advance_all(apps)

        # 5. Metrics snapshot for the completed day (after actions and deliveries).
        row = collect_metrics(apps, day, scenario_name, modifier)
        row["supply_modifier"] = float(signal.get("supply_modifier", 1.0))
        row["lead_time_modifier"] = float(signal.get("lead_time_modifier", 1.0))
        row["event_label"] = label
        all_metrics.append(row)
        print(
            f"  Day {day} summary: "
            f"{row.get('orders_placed_today', 0)} customer orders / "
            f"{row.get('orders_fulfilled_today', 0)} fulfilled / "
            f"{row.get('orders_backordered_today', 0)} newly backordered / "
            f"{row.get('orders_backordered_total', 0)} total backlog",
            flush=True,
        )
        log.separator()

    return all_metrics


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a full supply-chain simulation using CLI skill agents."
    )
    parser.add_argument("--scenario", required=True, type=Path,
                        help="Path to scenario JSON file")
    parser.add_argument("--days", type=int, default=25,
                        help="Number of simulation days to run")
    parser.add_argument("--backend", choices=("codex", "claude"), default="codex",
                        help="Agent CLI backend for provider/manufacturer (default: codex).")
    parser.add_argument("--model", default="",
                        help="Model for provider/manufacturer agents (default: codex=gpt-5.4-mini, claude=CLI default).")
    parser.add_argument("--max-turns", type=int, default=15,
                        help="Max agentic turns per agent per day (default: 15).")
    parser.add_argument("--retailer-mode", choices=("direct", "claude"), default="direct",
                        help="Use deterministic REST policy for retailer by default; choose 'claude' to run the retail skill.")
    args = parser.parse_args()

    # Store model as a local that run_simulation passes down — no global needed
    global _agent_backend, _agent_model, _retailer_mode
    _agent_backend = args.backend
    _agent_model = args.model or ("gpt-5.4-mini" if args.backend == "codex" else "")
    _retailer_mode = args.retailer_mode

    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    scenario_name = scenario.get("name", args.scenario.stem)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    narrative_path = LOGS_DIR / f"narrative_{scenario_name}.md"
    log = NarrativeLog(narrative_path)
    log.header(scenario_name, args.days)

    print(f"\nScenario : {scenario_name}")
    print(f"Days     : {args.days}")
    print(f"Backend  : {_agent_backend}")
    print(f"Model    : {_agent_model or '(Claude Code default)'}")
    print(f"Max turns: {args.max_turns} per agent")
    print(f"Retailer : {_retailer_mode}")
    print(f"Narrative: {narrative_path}")
    t0 = time.time()

    try:
        all_metrics = run_simulation(scenario, args.days, log, max_turns=args.max_turns)
    finally:
        log.close()

    if not all_metrics:
        print("ERROR: No metrics collected.")
        return 1

    # Write CSV
    fieldnames = sorted({k for row in all_metrics for k in row})
    csv_path = LOGS_DIR / f"metrics_{scenario_name}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval=0, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_metrics)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Finished {args.days} days in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"  Metrics  : {csv_path}")
    print(f"  Narrative: {narrative_path}")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
