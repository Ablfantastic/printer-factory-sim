import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_default_db = os.path.join(os.path.dirname(__file__), "..", "retailer.db")
DATABASE_URL = f"sqlite:///{os.path.abspath(_default_db)}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def configure_db(db_path: str):
    """Reconfigure the engine for a custom database path (multi-instance support)."""
    global engine, SessionLocal
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.bind = engine
