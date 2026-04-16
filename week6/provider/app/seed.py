from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.services import load_seed


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        load_seed(db, Path(__file__).resolve().parent.parent / "seed-provider.json")
    finally:
        db.close()


if __name__ == "__main__":
    main()
