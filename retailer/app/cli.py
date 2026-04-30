"""retailer-cli — CLI for the retailer app."""
import json
import os
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Retailer CLI", no_args_is_help=True)
customers_app = typer.Typer(help="Customer order commands", no_args_is_help=True)
purchase_app = typer.Typer(help="Purchase order commands", no_args_is_help=True)
day_app = typer.Typer(help="Day commands", no_args_is_help=True)
price_app = typer.Typer(help="Price commands", no_args_is_help=True)

app.add_typer(customers_app, name="customers")
app.add_typer(purchase_app, name="purchase")
app.add_typer(day_app, name="day")
app.add_typer(price_app, name="price")

_CONFIG: dict = {}


def _load_config(config_path: str):
    global _CONFIG
    try:
        _CONFIG = json.loads(Path(config_path).read_text())
    except Exception:
        _CONFIG = {}
    os.environ["APP_CONFIG"] = config_path


def _get_db():
    from app.database import SessionLocal, init_db
    init_db()
    return SessionLocal()


def _pretty(obj):
    typer.echo(json.dumps(obj, indent=2, default=str))


def _mfr_url() -> str:
    return _CONFIG.get("retailer", {}).get("manufacturer", {}).get("url", "http://localhost:8002")


def _retailer_name() -> str:
    return _CONFIG.get("retailer", {}).get("name", "Retailer")


def _markup_pct() -> float:
    return float(_CONFIG.get("retailer", {}).get("markup_pct", 30))


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@app.command("catalog")
def show_catalog(
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Show catalog models and retail prices."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        items = services.get_catalog(db)
        _pretty([
            {"model": i.model, "retail_price": i.retail_price, "wholesale_price": i.wholesale_price}
            for i in items
        ])
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

@app.command("stock")
def show_stock(
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Show current inventory."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        items = services.get_stock(db)
        _pretty([{"model": s.model, "quantity": s.quantity} for s in items])
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Customer orders
# ---------------------------------------------------------------------------

@customers_app.command("orders")
def customers_orders(
    status: Optional[str] = typer.Option(None, "--status"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """List customer orders."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        orders = services.list_customer_orders(db, status)
        _pretty([
            {"id": o.id, "customer": o.customer, "model": o.model,
             "quantity": o.quantity, "placed_day": o.placed_day,
             "fulfilled_day": o.fulfilled_day, "status": o.status}
            for o in orders
        ])
    finally:
        db.close()


@customers_app.command("order")
def customers_order(
    order_id: int = typer.Argument(..., help="Customer order ID"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Show details of a customer order."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        order = services.get_customer_order(db, order_id)
        if not order:
            typer.echo(f"Order {order_id} not found", err=True)
            raise typer.Exit(1)
        _pretty({
            "id": order.id, "customer": order.customer, "model": order.model,
            "quantity": order.quantity, "placed_day": order.placed_day,
            "fulfilled_day": order.fulfilled_day, "status": order.status,
        })
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fulfill / Backorder
# ---------------------------------------------------------------------------

@app.command("fulfill")
def fulfill(
    order_id: int = typer.Argument(..., help="Customer order ID to fulfill"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Ship to customer from stock."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        order = services.fulfill_order(db, order_id)
        typer.echo(f"Order {order_id} fulfilled on day {order.fulfilled_day}.")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command("backorder")
def backorder(
    order_id: int = typer.Argument(..., help="Customer order ID to backorder"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Mark order as backordered."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        services.backorder_order(db, order_id)
        typer.echo(f"Order {order_id} marked as backordered.")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------

@purchase_app.command("list")
def purchase_list(
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """List purchase orders placed with manufacturer."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        pos = services.list_purchase_orders(db)
        _pretty([
            {"id": p.id, "model": p.model, "quantity": p.quantity,
             "status": p.status, "placed_day": p.placed_day,
             "expected_delivery_day": p.expected_delivery_day,
             "manufacturer_order_id": p.manufacturer_order_id}
            for p in pos
        ])
    finally:
        db.close()


@purchase_app.command("create")
def purchase_create(
    model: str = typer.Argument(..., help="Printer model to order"),
    qty: int = typer.Argument(..., help="Quantity"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Order printers from manufacturer."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        po = services.create_purchase_order(db, model, qty, _mfr_url(), _retailer_name())
        typer.echo(
            f"Purchase order {po.id} created. Status: {po.status}, "
            f"Manufacturer order ID: {po.manufacturer_order_id}"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------

@price_app.command("set")
def price_set(
    model: str = typer.Argument(..., help="Printer model"),
    price: float = typer.Argument(..., help="New retail price"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Set retail price for a model."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        item = services.set_price(db, model, price, _markup_pct())
        typer.echo(f"Price for '{item.model}' set to {item.retail_price}")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Day
# ---------------------------------------------------------------------------

@day_app.command("advance")
def day_advance(
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Advance one simulation day."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        new_day = services.advance_day(db, _mfr_url())
        typer.echo(f"Advanced to day {new_day}")
    finally:
        db.close()


@day_app.command("current")
def day_current(
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Show current simulation day."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        day = services._current_day(db)
        typer.echo(f"Current day: {day}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

@app.command("export")
def export(
    output: str = typer.Argument("retailer-export.json", help="Output file"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Export full state to JSON."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        state = services.export_state(db)
        Path(output).write_text(json.dumps(state, indent=2, default=str))
        typer.echo(f"State exported to {output}")
    finally:
        db.close()


@app.command("import")
def import_state(
    input_file: str = typer.Argument(..., help="JSON file to import"),
    config: str = typer.Option("config.json", "--config", "-c"),
):
    """Load state from JSON file."""
    _load_config(config)
    from app import services
    db = _get_db()
    try:
        data = json.loads(Path(input_file).read_text())
        services.import_state(db, data)
        typer.echo(f"State imported from {input_file}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Serve
# ---------------------------------------------------------------------------

@app.command("serve")
def serve(
    port: int = typer.Option(8003, "--port", "-p", help="Port to listen on"),
    config: str = typer.Option("config.json", "--config", "-c", help="Config file"),
):
    """Start the REST API server."""
    import uvicorn
    _load_config(config)
    actual_port = _CONFIG.get("retailer", {}).get("port", port)
    typer.echo(f"Starting retailer API on http://localhost:{actual_port}")
    uvicorn.run("app.api:app", host="0.0.0.0", port=actual_port, reload=False)


if __name__ == "__main__":
    app()
