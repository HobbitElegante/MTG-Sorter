from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from mtg_sorter.config import DATA_DIR, DATABASE_PATH
from mtg_sorter.models import Base


def get_database_url() -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATABASE_PATH}"


engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _ensure_deck_sort_order() -> None:
    """Add decks.sort_order on existing DBs created before v0.3.7."""
    with engine.begin() as conn:
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(decks)")).fetchall()
        }
        if not columns:
            return

        added = False
        if "sort_order" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE decks ADD COLUMN sort_order "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )
            added = True

        count = int(conn.execute(text("SELECT COUNT(*) FROM decks")).scalar() or 0)
        if count == 0:
            return

        distinct = int(
            conn.execute(text("SELECT COUNT(DISTINCT sort_order) FROM decks")).scalar()
            or 0
        )
        # Fresh column (all 0) or legacy single shared value → order by name.
        if added or distinct <= 1:
            rows = conn.execute(
                text("SELECT id FROM decks ORDER BY name COLLATE NOCASE, id")
            ).fetchall()
            for index, (deck_id,) in enumerate(rows):
                conn.execute(
                    text("UPDATE decks SET sort_order = :order WHERE id = :id"),
                    {"order": index, "id": deck_id},
                )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_deck_sort_order()


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
