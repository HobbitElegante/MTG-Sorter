from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mtg_sorter.config import DATA_DIR, DATABASE_PATH
from mtg_sorter.database.migrate import upgrade_database


def get_database_url() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATABASE_PATH}"


engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create/upgrade the SQLite schema via Alembic."""
    upgrade_database(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
