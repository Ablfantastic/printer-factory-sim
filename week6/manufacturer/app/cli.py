import json
from pathlib import Path

import typer

from app.database import Base, SessionLocal, engine
from app.services import ManufacturerService


app = typer.Typer(help="Manufacturer CLI")
suppliers_app = typer.Typer()
purchase_app = typer.Typer()
day_app = typer.Typer()

app.add_typer(suppliers_app, name="suppliers")
app.add_typer(purchase_app, name="purchase")
app.add_typer(day_app, name="day")


def service() -> ManufacturerService:
    db = SessionLocal()
    return ManufacturerService(db)


@app.command()
def stock():
    svc = service()
    try:
        typer.echo(json.dumps(svc.get_inventory(), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@suppliers_app.command("list")
def suppliers_list():
    svc = service()
    try:
        typer.echo(json.dumps(svc.list_providers(), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@suppliers_app.command("catalog")
def suppliers_catalog(supplier_name: str):
    svc = service()
    try:
        typer.echo(json.dumps(svc.supplier_catalog(supplier_name), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@purchase_app.command("create")
def purchase_create(
    supplier: str = typer.Option(..., "--supplier"),
    product: str = typer.Option(..., "--product"),
    qty: int = typer.Option(..., "--qty"),
):
    svc = service()
    try:
        typer.echo(json.dumps(svc.create_purchase_order(supplier, product, qty), indent=2, ensure_ascii=False))
    finally:
        svc.db.close()


@purchase_app.command("list")
def purchase_list():
    svc = service()
    try:
        typer.echo(json.dumps(svc.list_purchase_orders(), indent=2, ensure_ascii=False))
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
def export(output: str = "manufacturer-export.json"):
    svc = service()
    try:
        Path(output).write_text(json.dumps(svc.export_state(), indent=2, ensure_ascii=False), encoding="utf-8")
        typer.echo(f"Exported to {output}")
    finally:
        svc.db.close()


@app.command("import")
def import_state(input_file: str):
    svc = service()
    try:
        payload = json.loads(Path(input_file).read_text(encoding="utf-8"))
        svc.import_state(payload)
        typer.echo(f"Imported state from {input_file}")
    finally:
        svc.db.close()


def main():
    Base.metadata.create_all(bind=engine)
    app()


if __name__ == "__main__":
    main()
