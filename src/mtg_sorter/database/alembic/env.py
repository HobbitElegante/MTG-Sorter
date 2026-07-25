"""Alembic environment for MTG-Sorter (SQLite).

Supports:
- CLI: ``alembic -c alembic.ini revision --autogenerate``
- Runtime: ``upgrade_database(engine)`` passes an open connection via
  ``config.attributes["connection"]``.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from mtg_sorter.config import DATA_DIR, DATABASE_PATH
from mtg_sorter.models import Base

# Import models so Base.metadata is fully populated for autogenerate.
import mtg_sorter.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# CLI defaults to the app SQLite file; runtime upgrade injects a connection.
if config.attributes.get("connection") is None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{DATABASE_PATH}")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        # Caller owns the transaction (see upgrade_database).
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            transaction_per_migration=False,
        )
        context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as conn:
        context.configure(
            connection=conn,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
