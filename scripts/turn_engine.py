#!/usr/bin/env python3
"""Advance the printer supply-chain simulation one deterministic turn at a time."""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_SCENARIO = Path("scenarios/week7.json")
DEFAULT_LOG = Path("logs/turn-engine.jsonl")
OPEN_STATUSES = {"pending", "confirmed", "released", "in_progress", "completed", "shipped"}


class ApiError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def api_request(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urlopen(request, timeout=10) as response:
            data = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"{method} {url} failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ApiError(f"{method} {url} failed: {exc.reason}") from exc

    if not data:
        return {}
    return json.loads(data.decode("utf-8"))


def get_json(base_url: str, path: str) -> Any:
    return api_request("GET", base_url, path)


def post_json(base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    return api_request("POST", base_url, path, payload or {})


def current_day(apps: dict[str, Any]) -> int:
    days = {
        name: get_json(app["url"], "/api/day/current")["current_day"]
        for name, app in apps.items()
    }
    if len(set(days.values())) != 1:
        raise ApiError(f"Apps are not on the same simulation day: {days}")
    return next(iter(days.values()))


def scenario_for_day(scenario: dict[str, Any], day: int) -> dict[str, Any]:
    defaults = scenario.get("demand", {})
    signal = dict(defaults)
    day_signal = scenario.get("days", {}).get(str(day), {})
    signal.update(day_signal)
    signal.setdefault("base_demand", {"mean": 5, "variance": 2})
    signal.setdefault("demand_modifier", 1.0)
    return signal


def model_name(item: dict[str, Any]) -> str:
    return item.get("model") or item.get("name")


def stock_map(rows: list[dict[str, Any]], key: str = "model") -> dict[str, int]:
    return {row[key]: int(row.get("quantity", 0)) for row in rows}


def generate_customer_demand(
    day: int,
    signal: dict[str, Any],
    retailer_catalog: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    base = signal.get("base_demand", {"mean": 5, "variance": 2})
    modifier = float(signal.get("demand_modifier", 1.0))
    base_price = float(signal.get("base_price") or average_price(retailer_catalog))
    orders: list[dict[str, Any]] = []

    for item in retailer_catalog:
        model = model_name(item)
        price = float(item.get("retail_price") or item.get("price") or base_price)
        mean_orders = float(base.get("mean", 5)) * modifier
        price_factor = max(0.2, 1.0 - (price - base_price) / base_price)
        adjusted_mean = mean_orders * price_factor
        count = max(0, int(rng.gauss(adjusted_mean, float(base.get("variance", 2)))))
        for index in range(count):
            orders.append(
                {
                    "customer": f"day-{day}-customer-{model}-{index + 1}",
                    "model": model,
                    "quantity": 1,
                }
            )
    return orders


def average_price(catalog: list[dict[str, Any]]) -> float:
    prices = [
        float(item.get("retail_price") or item.get("wholesale_price") or 0)
        for item in catalog
        if item.get("retail_price") or item.get("wholesale_price")
    ]
    return sum(prices) / len(prices) if prices else 1.0


def inject_customer_demand(retailer: dict[str, Any], orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    created = []
    for order in orders:
        created.append(post_json(retailer["url"], "/api/orders", order))
    return created


def retailer_turn(retailer: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    url = retailer["url"]
    actions: list[dict[str, Any]] = []

    try:
        post_json(url, "/api/catalog/sync")
    except ApiError as exc:
        actions.append({"action": "catalog_sync_failed", "error": str(exc)})

    stock = stock_map(get_json(url, "/api/stock"))
    pending = get_json(url, "/api/orders?status=pending")
    for order in pending:
        if stock.get(order["model"], 0) >= order["quantity"]:
            result = post_json(url, f"/api/orders/{order['id']}/fulfill")
            stock[order["model"]] = stock.get(order["model"], 0) - order["quantity"]
            actions.append({"action": "fulfilled_customer_order", "order": result})
        else:
            result = post_json(url, f"/api/orders/{order['id']}/backorder")
            actions.append({"action": "backordered_customer_order", "order": result})

    backorders = get_json(url, "/api/orders?status=backordered")
    purchases = get_json(url, "/api/purchases")
    incoming: dict[str, int] = {}
    for purchase in purchases:
        if purchase.get("status") in OPEN_STATUSES:
            incoming[purchase["model"]] = incoming.get(purchase["model"], 0) + int(purchase["quantity"])

    catalog = get_json(url, "/api/catalog")
    target_stock = int(policy.get("target_stock", 6))
    reorder_lot = int(policy.get("reorder_lot", 4))
    for item in catalog:
        model = item["model"]
        backordered_qty = sum(int(order["quantity"]) for order in backorders if order["model"] == model)
        desired = target_stock + backordered_qty
        covered = stock.get(model, 0) + incoming.get(model, 0)
        if covered < desired:
            quantity = max(reorder_lot, desired - covered)
            try:
                result = post_json(url, "/api/purchases", {"model": model, "quantity": quantity})
                actions.append({"action": "created_purchase_order", "purchase": result})
            except ApiError as exc:
                actions.append({"action": "purchase_order_failed", "model": model, "quantity": quantity, "error": str(exc)})

    return {"role": "retailer", "actions": actions}


def manufacturer_turn(manufacturer: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    url = manufacturer["url"]
    actions: list[dict[str, Any]] = []

    pending = get_json(url, "/api/orders?status=pending")
    for order in pending:
        try:
            result = post_json(url, f"/api/orders/{order['id']}/release")
            actions.append({"action": "released_sales_order", "order": result})
        except ApiError as exc:
            actions.append({"action": "release_failed", "order_id": order["id"], "error": str(exc)})

    catalog = {item["name"]: item for item in get_json(url, "/api/catalog")}
    inventory = {item["product_name"]: int(item["quantity"]) for item in get_json(url, "/api/stock")}
    released = get_json(url, "/api/orders?status=released")
    required_parts: dict[str, int] = {}
    for order in released:
        bom = catalog.get(order["model"], {}).get("bom", {})
        for part_name, per_unit in bom.items():
            required_parts[part_name] = required_parts.get(part_name, 0) + int(per_unit) * int(order["quantity"])

    open_purchases = get_json(url, "/api/purchases")
    incoming: dict[str, int] = {}
    for purchase in open_purchases:
        if purchase.get("status") in OPEN_STATUSES:
            incoming[purchase["product_name"]] = incoming.get(purchase["product_name"], 0) + int(purchase["quantity"])

    providers = [provider for provider in get_json(url, "/api/providers") if provider.get("status") == "ok"]
    if not providers:
        providers = get_json(url, "/api/providers")
    supplier_name = providers[0]["name"] if providers else None
    part_buffer = int(policy.get("part_buffer", 0))

    if supplier_name:
        supplier_catalog = {
            item["name"]: item
            for item in get_json(url, f"/api/providers/{quote(supplier_name)}/catalog")
        }
        for part_name, required in sorted(required_parts.items()):
            shortage = required + part_buffer - inventory.get(part_name, 0) - incoming.get(part_name, 0)
            if shortage <= 0:
                continue
            if part_name not in supplier_catalog:
                actions.append({"action": "part_not_in_supplier_catalog", "part": part_name})
                continue
            try:
                result = post_json(
                    url,
                    "/api/purchases",
                    {"supplier_name": supplier_name, "product_name": part_name, "quantity": shortage},
                )
                actions.append({"action": "created_part_purchase_order", "purchase": result})
            except ApiError as exc:
                actions.append({"action": "part_purchase_failed", "part": part_name, "quantity": shortage, "error": str(exc)})
    elif required_parts:
        actions.append({"action": "no_supplier_available", "required_parts": required_parts})

    return {"role": "manufacturer", "actions": actions}


def provider_turn(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "provider",
        "actions": [
            {
                "action": "observed_open_orders",
                "open_orders": len([o for o in get_json(provider["url"], "/api/orders") if o.get("status") in OPEN_STATUSES]),
            }
        ],
    }


def fetch_events(app: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return get_json(app["url"], "/api/events")
    except ApiError:
        try:
            exported = get_json(app["url"], "/api/export")
            return exported.get("events", [])
        except ApiError:
            return []


def new_events(before: dict[str, int], apps: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for name, app in apps.items():
        events = fetch_events(app)
        previous_id = before.get(name, 0)
        with_ids = [event for event in events if "id" in event]
        if with_ids:
            result[name] = [event for event in events if int(event.get("id", 0)) > previous_id]
        else:
            result[name] = events
    return result


def max_event_ids(apps: dict[str, Any]) -> dict[str, int]:
    result = {}
    for name, app in apps.items():
        events = fetch_events(app)
        result[name] = max([int(event.get("id", 0)) for event in events if "id" in event] or [0])
    return result


def advance_apps(apps: dict[str, Any]) -> dict[str, Any]:
    return {
        "retailer": post_json(apps["retailer"]["url"], "/api/day/advance"),
        "manufacturer": post_json(apps["manufacturer"]["url"], "/api/day/advance"),
        "provider": post_json(apps["provider"]["url"], "/api/day/advance"),
    }


def run_turn(scenario: dict[str, Any], log_path: Path) -> dict[str, Any]:
    apps = scenario["apps"]
    day = current_day(apps)
    signal = scenario_for_day(scenario, day)
    event_ids_before = max_event_ids(apps)

    seed = int(scenario.get("seed", 0)) + day
    rng = random.Random(seed)
    retailer_catalog = get_json(apps["retailer"]["url"], "/api/catalog")
    demand = generate_customer_demand(day, signal, retailer_catalog, rng)
    customer_orders = inject_customer_demand(apps["retailer"], demand)

    role_results = [
        retailer_turn(apps["retailer"], scenario.get("retailer_policy", {})),
        manufacturer_turn(apps["manufacturer"], scenario.get("manufacturer_policy", {})),
        provider_turn(apps["provider"]),
    ]
    advances = advance_apps(apps)

    record = {
        "timestamp": utc_now(),
        "scenario": scenario.get("name", "unnamed"),
        "day": day,
        "signal": signal,
        "customer_demand": demand,
        "customer_orders_created": customer_orders,
        "role_results": role_results,
        "day_advance": advances,
        "events": new_events(event_ids_before, apps),
    }
    write_jsonl(log_path, record)
    return record


def health_check(apps: dict[str, Any]) -> None:
    for name, app in apps.items():
        try:
            get_json(app["url"], "/health")
        except ApiError as exc:
            raise ApiError(f"{name} is not healthy at {app['url']}: {exc}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic supply-chain turns.")
    parser.add_argument("--scenario", type=Path, default=DEFAULT_SCENARIO)
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--skip-health", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenario = read_json(args.scenario)
    if not args.skip_health:
        health_check(scenario["apps"])

    records = []
    for _ in range(args.days):
        records.append(run_turn(scenario, args.log))

    print(json.dumps({
        "turns_run": len(records),
        "days": [record["day"] for record in records],
        "log": str(args.log),
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ApiError as exc:
        print(f"turn-engine error: {exc}", file=sys.stderr)
        raise SystemExit(1)
