from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from mtg_rebuilder.models.base import Base


class HouseBan(Base):
    """User-defined house banlist entry (advisory ⚠ on decks that include it)."""

    __tablename__ = "house_bans"

    oracle_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cards.oracle_id"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
