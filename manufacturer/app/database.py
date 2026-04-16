"""Database configuration and session management."""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./simulator.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def run_sqlite_migrations():
    """Apply lightweight SQLite schema updates (additive columns)."""
    if "sqlite" not in str(engine.url):
        return
    with engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(manufacturing_orders)")).fetchall()
        cols = {r[1] for r in rows}
        if cols and "units_produced" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE manufacturing_orders "
                    "ADD COLUMN units_produced INTEGER DEFAULT 0 NOT NULL"
                )
            )
            conn.commit()


def get_db():
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
