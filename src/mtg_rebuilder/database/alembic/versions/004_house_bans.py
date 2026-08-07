"""House banlist table for user-defined Commander bans.

Revision ID: 004_house_bans
Revises: 003_deck_locked
Create Date: 2026-07-28

Cards on this list always show an advisory ⚠ on decks that include them,
independent of Scryfall format legality toggles.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_house_bans"
down_revision: Union[str, Sequence[str], None] = "003_deck_locked"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "house_bans",
        sa.Column("oracle_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["oracle_id"], ["cards.oracle_id"]),
        sa.PrimaryKeyConstraint("oracle_id"),
    )


def downgrade() -> None:
    op.drop_table("house_bans")
