import json
from pathlib import Path
from typing import Optional

import typer

from app.database import Base, SessionLocal, engine
from app.services import ManufacturerService

app = typer.Typer(help="Manufacturer CLI", no_args_is_help=True)
suppliers_app = typer.Typer(help="Supplier/provider commands", no_args_is_help=True)
purchase_app = typer.Typer(help="Purchase order (parts) commands", no_args_is_help=True)
day_app = typer.Typer(help="Day commands", no_args_is_help=True)
sales_app = typer.Typer(help="Sales order commands (from retailers)", no_args_is_help=True)
production_app = typer.Typer(help="Production commands", no_args_is_help=True)
price_app = typer.Typer(help="Wholesale price commands", no_args_is_help=True)

app.add_typer(suppliers_app, name="suppliers")
app.add_typer(purchase_app, name="purchase")
app.add_typer(day_app, name="day")
app.add_typer(sales_app, name="sales")
app.add_typer(production_app, name="production")
app.add_typer(price_app, name="price")


def service() -> ManufacturerService:
    db = SessionLocal()
    return ManufacturerService(db)


def _pretty(obj):
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


# ------------------------------------------------------------------
# Stock
# ------------------------------------------------------------------

@app.command()
def stock():
    """Raw parts inventory."""
    svc = service()
    try:
        _pretty(svc.get_inventory())
    finally:
        svc.db.close()


@app.command("finished-stock")
def finished_stock():
    """Finished-printer inventory."""
    svc = service()
    try:
        _pretty(svc.get_finished_stock())
    finally:
        svc.db.close()


@app.command()
def capacity():
    """Daily capacity and utilisation."""
    svc = service()
    try:
        _pretty(svc.get_capacity())
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Suppliers / catalog
# ------------------------------------------------------------------

@suppliers_app.command("list")
def suppliers_list():
    """List configured providers."""
    svc = service()
    try:
        _pretty(svc.list_providers())
    finally:
        svc.db.close()


@suppliers_app.command("catalog")
def suppliers_catalog(supplier_name: str):
    """Show a provider's catalog."""
    svc = service()
    try:
        _pretty(svc.supplier_catalog(supplier_name))
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Purchase orders (outbound — parts)
# ------------------------------------------------------------------

@purchase_app.command("create")
def purchase_create(
    supplier: str = typer.Option(..., "--supplier"),
    product: str = typer.Option(..., "--product"),
    qty: int = typer.Option(..., "--qty"),
):
    """Order parts from a provider."""
    svc = service()
    try:
        _pretty(svc.create_purchase_order(supplier, product, qty))
    finally:
        svc.db.close()


@purchase_app.command("list")
def purchase_list():
    """List purchase orders placed with providers."""
    svc = service()
    try:
        _pretty(svc.list_purchase_orders())
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Sales orders (inbound — from retailers)
# ------------------------------------------------------------------

@sales_app.command("orders")
def sales_orders(status: Optional[str] = typer.Option(None, "--status")):
    """List sales orders received from retailers."""
    svc = service()
    try:
        _pretty(svc.list_sales_orders(status))
    finally:
        svc.db.close()


@sales_app.command("order")
def sales_order(order_id: int = typer.Argument(...)):
    """Show details of a sales order."""
    svc = service()
    try:
        order = svc.get_sales_order(order_id)
        if order is None:
            typer.echo(f"Order {order_id} not found", err=True)
            raise typer.Exit(1)
        _pretty(order)
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Production
# ------------------------------------------------------------------

@production_app.command("release")
def production_release(order_id: int = typer.Argument(...)):
    """Release a sales order to production."""
    svc = service()
    try:
        _pretty(svc.release_order(order_id))
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        svc.db.close()


@production_app.command("status")
def production_status():
    """Show orders currently in production."""
    svc = service()
    try:
        _pretty(svc.get_production_status())
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Wholesale prices
# ------------------------------------------------------------------

@price_app.command("list")
def price_list():
    """Show wholesale prices for all printer models."""
    svc = service()
    try:
        _pretty(svc.list_printer_models())
    finally:
        svc.db.close()


@price_app.command("set")
def price_set(
    model: str = typer.Argument(...),
    price: float = typer.Argument(...),
):
    """Set wholesale price for a printer model."""
    svc = service()
    try:
        _pretty(svc.set_wholesale_price(model, price))
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Day
# ------------------------------------------------------------------

@day_app.command("advance")
def day_advance():
    """Advance one simulation day (runs full production pipeline)."""
    svc = service()
    try:
        _pretty(svc.advance_day())
    finally:
        svc.db.close()


@day_app.command("current")
def day_current():
    """Show current simulation day."""
    svc = service()
    try:
        _pretty({"current_day": svc.current_day()})
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Export / Import
# ------------------------------------------------------------------

@app.command()
def export(output: str = typer.Argument("manufacturer-export.json", help="Output file")):
    """Export full state to JSON."""
    svc = service()
    try:
        Path(output).write_text(json.dumps(svc.export_state(), indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"Exported to {output}")
    finally:
        svc.db.close()


@app.command("import")
def import_state(input_file: str):
    """Load state from JSON file."""
    svc = service()
    try:
        payload = json.loads(Path(input_file).read_text(encoding="utf-8"))
        svc.import_state(payload)
        typer.echo(f"Imported state from {input_file}")
    finally:
        svc.db.close()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    Base.metadata.create_all(bind=engine)
    app()


if __name__ == "__main__":
    main()
