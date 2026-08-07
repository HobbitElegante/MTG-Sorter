"""Cache of printings per card, for the optional edition picker.

Revision ID: 002_card_prints
Revises: 001_initial
Create Date: 2026-07-24

The oracle bulk pack keeps one row per card, so the sets a card was printed in
are fetched on demand and cached here. ``card_copies.edition`` already exists
since the baseline; this only adds the lookup table that feeds the picker.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_card_prints"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_prints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("oracle_id", sa.String(length=36), nullable=False),
        sa.Column("set_code", sa.String(length=16), nullable=False),
        sa.Column("set_name", sa.String(length=255), nullable=True),
        sa.Column("released_at", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(["oracle_id"], ["cards.oracle_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("oracle_id", "set_code", name="uq_card_print_set"),
    )
    op.create_index(
        op.f("ix_card_prints_oracle_id"),
        "card_prints",
        ["oracle_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_card_prints_oracle_id"), table_name="card_prints")
    op.drop_table("card_prints")
