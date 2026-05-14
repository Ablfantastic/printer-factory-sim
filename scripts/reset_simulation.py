#!/usr/bin/env python3
"""Reset the local simulation databases to day 1.

Keeps catalogs/products/prices, clears transactional history, and restores stock
levels from the seed JSON files so a new turn-engine run starts cleanly.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATABASES = [
    ROOT / "provider/provider.db",
    ROOT / "manufacturer/manufacturer.db",
    ROOT / "retailer/retailer.db",
]


def has_table(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (name,),
    ).fetchone()
    return row is not None


def reset_sequence(conn: sqlite3.Connection, table_names: list[str]) -> None:
    if not has_table(conn, "sqlite_sequence"):
        return
    conn.executemany("delete from sqlite_sequence where name=?", [(name,) for name in table_names])


def set_day_one(conn: sqlite3.Connection) -> None:
    conn.execute(
        "insert into sim_state(key, value) values('current_day', '1') "
        "on conflict(key) do update set value='1'"
    )


def backup_databases(destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backups = []
    for src in DATABASES:
        if not src.exists():
            continue
        dst = destination / f"{src.parent.name}-{stamp}.db"
        shutil.copy2(src, dst)
        backups.append(dst)
    return backups


def reset_provider() -> None:
    seed = json.loads((ROOT / "provider/seed-provider.json").read_text(encoding="utf-8"))
    conn = sqlite3.connect(ROOT / "provider/provider.db")
    try:
        conn.execute("pragma foreign_keys=off")
        conn.execute("delete from events")
        conn.execute("delete from orders")
        set_day_one(conn)

        for product in seed["products"]:
            row = conn.execute("select id from products where name=?", (product["name"],)).fetchone()
            if row is None:
                continue
            conn.execute(
                "update stock set quantity=? where product_id=?",
                (product["initial_stock"], row[0]),
            )

        reset_sequence(conn, ["events", "orders"])
        conn.commit()
    finally:
        conn.close()


def reset_manufacturer() -> None:
    seed = json.loads((ROOT / "manufacturer/seed-manufacturer.json").read_text(encoding="utf-8"))
    conn = sqlite3.connect(ROOT / "manufacturer/manufacturer.db")
    try:
        conn.execute("pragma foreign_keys=off")
        conn.execute("delete from events")
        conn.execute("delete from purchase_orders")
        conn.execute("delete from sales_orders")
        set_day_one(conn)

        for item in seed["inventory"]:
            conn.execute(
                "update inventory set quantity=? where product_name=?",
                (item["quantity"], item["product"]),
            )
        for item in seed["finished_stock"]:
            conn.execute(
                "update finished_stock set quantity=? where model=?",
                (item["quantity"], item["model"]),
            )
        for item in seed["printer_models"]:
            conn.execute(
                "update printer_models "
                "set wholesale_price=?, production_days=?, daily_capacity=?, bom=? "
                "where name=?",
                (
                    item["wholesale_price"],
                    item["production_days"],
                    item["daily_capacity"],
                    json.dumps(item["bom"]),
                    item["name"],
                ),
            )

        reset_sequence(conn, ["events", "purchase_orders", "sales_orders"])
        conn.commit()
    finally:
        conn.close()


def reset_retailer() -> None:
    seed = json.loads((ROOT / "retailer/seed-retailer.json").read_text(encoding="utf-8"))
    conn = sqlite3.connect(ROOT / "retailer/retailer.db")
    try:
        conn.execute("pragma foreign_keys=off")
        conn.execute("delete from events")
        conn.execute("delete from purchase_orders")
        conn.execute("delete from customer_orders")
        set_day_one(conn)

        for item in seed["stock"]:
            conn.execute(
                "update stock set quantity=? where model=?",
                (item["quantity"], item["model"]),
            )
        for item in seed["catalog"]:
            conn.execute(
                "update catalog set retail_price=? where model=?",
                (item["retail_price"], item["model"]),
            )

        reset_sequence(conn, ["events", "purchase_orders", "customer_orders"])
        conn.commit()
    finally:
        conn.close()


def table_count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"select count(*) from {table}").fetchone()[0]
    finally:
        conn.close()


def current_day(db_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("select value from sim_state where key='current_day'").fetchone()
        return row[0] if row else "missing"
    finally:
        conn.close()


def print_summary() -> None:
    checks = {
        "provider/provider.db": ["orders", "events"],
        "manufacturer/manufacturer.db": ["sales_orders", "purchase_orders", "events"],
        "retailer/retailer.db": ["customer_orders", "purchase_orders", "events"],
    }
    for relative, tables in checks.items():
        db_path = ROOT / relative
        print(f"{relative}: current_day={current_day(db_path)}")
        for table in tables:
            print(f"  {table}={table_count(db_path, table)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset all local simulation DBs to day 1.")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path("/tmp"),
        help="Directory where DB backups are written before reset.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.no_backup:
        backups = backup_databases(args.backup_dir)
        for backup in backups:
            print(f"backup: {backup}")

    reset_provider()
    reset_manufacturer()
    reset_retailer()
    print("reset complete")
    print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
