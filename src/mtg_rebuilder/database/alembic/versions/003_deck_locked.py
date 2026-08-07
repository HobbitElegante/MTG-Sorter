"""Optional lock flag so Optimize will not dismantle a deck.

Revision ID: 003_deck_locked
Revises: 002_card_prints
Create Date: 2026-07-25

Locked armed decks stay out of the donor pool for assembly plans; they still
appear in “still missing” so the user can see where a card lives.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_deck_locked"
down_revision: Union[str, Sequence[str], None] = "002_card_prints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("decks") as batch:
        batch.add_column(
            sa.Column(
                "is_locked",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("decks") as batch:
        batch.drop_column("is_locked")
