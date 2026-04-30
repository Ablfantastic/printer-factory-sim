import json
from pathlib import Path

import typer

from app.database import Base, SessionLocal, engine
from app.services import ProviderService


app = typer.Typer(help="Provider CLI")
orders_app = typer.Typer()
price_app = typer.Typer()
day_app = typer.Typer()

app.add_typer(orders_app, name="orders")
app.add_typer(price_app, name="price")
app.add_typer(day_app, name="day")


def service() -> ProviderService:
    db = SessionLocal()
    return ProviderService(db)


@app.command()
def catalog():
    svc = service()
    try:
        typer.echo(json.dumps(svc.get_catalog(), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@app.command()
def stock():
    svc = service()
    try:
        typer.echo(json.dumps(svc.get_stock(), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@orders_app.command("list")
def orders_list(status: str | None = typer.Option(default=None, help="Optional order status filter.")):
    svc = service()
    try:
        typer.echo(json.dumps(svc.list_orders(status=status), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@orders_app.command("show")
def orders_show(order_id: int):
    svc = service()
    try:
        typer.echo(json.dumps(svc.get_order(order_id), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@price_app.command("set")
def price_set(product: str, tier: int, price: float):
    svc = service()
    try:
        typer.echo(json.dumps(svc.set_price(product, tier, price), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@app.command()
def restock(product: str, quantity: int):
    svc = service()
    try:
        typer.echo(json.dumps(svc.restock(product, quantity), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@day_app.command("advance")
def day_advance():
    svc = service()
    try:
        typer.echo(json.dumps(svc.advance_day(), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@day_app.command("current")
def day_current():
    svc = service()
    try:
        typer.echo(json.dumps({"current_day": svc.current_day()}, indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@app.command()
def export(output: str = "provider-export.json"):
    svc = service()
    try:
        Path(output).write_text(json.dumps(svc.export_state(), indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"Exported to {output}")
    finally:
        svc.db.close()


@app.command()
def import_state(input_file: str):
    svc = service()
    try:
        payload = json.loads(Path(input_file).read_text(encoding="utf-8"))
        svc.import_state(payload)
        typer.echo(f"Imported state from {input_file}")
    finally:
        svc.db.close()


@app.command()
def serve(port: int = 8001):
    typer.echo(f"Run the API with: uvicorn app.api:app --host 0.0.0.0 --port {port} --reload")


def main():
    Base.metadata.create_all(bind=engine)
    app()


if __name__ == "__main__":
    main()
