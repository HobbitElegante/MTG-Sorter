"""Add rarity columns for inventory filtering.

Revision ID: 005_card_rarity
Revises: 004_house_bans
Create Date: 2026-08-02

Scryfall ``rarity`` is print-level. ``cards.rarity`` stores the representative
print from bulk/lookup (filter path A). ``card_prints.rarity`` stores rarity
per set from list_prints (path B when editions are tracked).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_card_rarity"
down_revision: Union[str, Sequence[str], None] = "004_house_bans"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cards") as batch:
        batch.add_column(sa.Column("rarity", sa.String(length=16), nullable=True))
    with op.batch_alter_table("card_prints") as batch:
        batch.add_column(sa.Column("rarity", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("card_prints") as batch:
        batch.drop_column("rarity")
    with op.batch_alter_table("cards") as batch:
        batch.drop_column("rarity")
