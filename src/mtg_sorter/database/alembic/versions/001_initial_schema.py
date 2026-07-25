"""Initial schema (cards, copies, decks, activity, settings).

Revision ID: 001_initial
Revises:
Create Date: 2026-07-24

Baseline for v0.6.1+. Matches SQLAlchemy models at introduction of Alembic.
Legacy databases created before Alembic are bridged in
``mtg_sorter.database.migrate`` (column ensures + stamp), not via this file.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cards",
        sa.Column("oracle_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mana_cost", sa.String(length=64), nullable=True),
        sa.Column("type_line", sa.String(length=255), nullable=True),
        sa.Column("oracle_text", sa.Text(), nullable=True),
        sa.Column("colors", sa.String(length=16), nullable=True),
        sa.Column("color_identity", sa.String(length=16), nullable=True),
        sa.Column("cmc", sa.Float(), nullable=True),
        sa.Column("image_uri", sa.String(length=512), nullable=True),
        sa.Column("image_uri_back", sa.String(length=512), nullable=True),
        sa.Column("commander_legality", sa.String(length=16), nullable=True),
        sa.Column("is_basic_land", sa.Boolean(), nullable=False),
        sa.Column("is_token", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("oracle_id"),
    )
    op.create_index("ix_cards_name", "cards", ["name"], unique=False)

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activity_events_created_at",
        "activity_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_event_type",
        "activity_events",
        ["event_type"],
        unique=False,
    )

    op.create_table(
        "decks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "card_copies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("card_id", sa.String(length=36), nullable=False),
        sa.Column("edition", sa.String(length=16), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("foil", sa.Boolean(), nullable=False),
        sa.Column("condition", sa.String(length=32), nullable=True),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(["card_id"], ["cards.oracle_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "deck_cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deck_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["cards.oracle_id"]),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deck_id", "card_id", "role", name="uq_deck_card_role"),
    )

    op.create_table(
        "card_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("card_copy_id", sa.Integer(), nullable=False),
        sa.Column("deck_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["card_copy_id"], ["card_copies.id"]),
        sa.ForeignKeyConstraint(["deck_id"], ["decks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("card_copy_id"),
    )


def downgrade() -> None:
    op.drop_table("card_assignments")
    op.drop_table("deck_cards")
    op.drop_table("card_copies")
    op.drop_table("decks")
    op.drop_index("ix_activity_events_event_type", table_name="activity_events")
    op.drop_index("ix_activity_events_created_at", table_name="activity_events")
    op.drop_table("activity_events")
    op.drop_table("app_settings")
    op.drop_index("ix_cards_name", table_name="cards")
    op.drop_table("cards")
