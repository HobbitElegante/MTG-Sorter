"""Run Alembic migrations against the app database.

On startup the desktop app calls ``upgrade_database(engine)``. Developers can
also use the CLI: ``alembic -c alembic.ini upgrade head``.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

ALEMBIC_SCRIPT_LOCATION = Path(__file__).resolve().parent / "alembic"
# Baseline revision id (must match versions/001_initial_schema.py). Legacy
# databases are bridged up to this point and stamped with it; later revisions
# are then applied normally.
BASELINE_REVISION = "001_initial"


def alembic_config(database_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _table_columns(conn, table: str) -> set[str]:
    return {
        row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    }


def _bridge_legacy_schema(connection) -> None:
    """Bring pre-Alembic SQLite DBs up to the baseline schema.

    Historically ``init_db`` used ``create_all`` plus ad-hoc ``_ensure_*``
    ALTER TABLE helpers. Existing user databases have no ``alembic_version``
    row; we apply the same column fixes once before stamping ``001_initial``.
    """
    tables = {
        row[0]
        for row in connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    }

    if "decks" in tables:
        columns = _table_columns(connection, "decks")
        added_sort = False
        if "sort_order" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE decks ADD COLUMN sort_order "
                    "INTEGER NOT NULL DEFAULT 0"
                )
            )
            added_sort = True

        count = int(
            connection.execute(text("SELECT COUNT(*) FROM decks")).scalar() or 0
        )
        if count > 0:
            distinct = int(
                connection.execute(
                    text("SELECT COUNT(DISTINCT sort_order) FROM decks")
                ).scalar()
                or 0
            )
            if added_sort or distinct <= 1:
                rows = connection.execute(
                    text("SELECT id FROM decks ORDER BY name COLLATE NOCASE, id")
                ).fetchall()
                for index, (deck_id,) in enumerate(rows):
                    connection.execute(
                        text("UPDATE decks SET sort_order = :order WHERE id = :id"),
                        {"order": index, "id": deck_id},
                    )

    if "cards" in tables:
        columns = _table_columns(connection, "cards")
        if "commander_legality" not in columns:
            connection.execute(
                text("ALTER TABLE cards ADD COLUMN commander_legality VARCHAR(16)")
            )
        if "image_uri_back" not in columns:
            connection.execute(
                text("ALTER TABLE cards ADD COLUMN image_uri_back VARCHAR(512)")
            )


def upgrade_database(engine: Engine) -> None:
    """Apply pending migrations (or bridge + stamp legacy databases)."""
    cfg = alembic_config(str(engine.url))
    existing_tables = set(inspect(engine).get_table_names())

    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        if existing_tables and "alembic_version" not in existing_tables:
            _bridge_legacy_schema(connection)
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")
