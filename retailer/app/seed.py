"""Seed the retailer database from seed-retailer.json."""
import json
import os
from pathlib import Path


def seed():
    from app.database import SessionLocal, init_db
    from app.models import CatalogItem, SimState, Stock

    init_db()
    db = SessionLocal()
    try:
        if db.query(CatalogItem).count() > 0:
            return

        seed_file = Path(os.path.dirname(__file__), "..", "seed-retailer.json")
        data = json.loads(seed_file.read_text())

        for item in data.get("catalog", []):
            db.add(CatalogItem(model=item["model"], retail_price=item["retail_price"]))
        for item in data.get("stock", []):
            db.add(Stock(model=item["model"], quantity=item["quantity"]))

        existing = db.query(SimState).filter_by(key="current_day").first()
        if not existing:
            db.add(SimState(key="current_day", value="1"))

        db.commit()
        print("Retailer database seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
