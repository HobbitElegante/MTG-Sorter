from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mtg_sorter.models.base import Base


class Card(Base):
    __tablename__ = "cards"

    oracle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    mana_cost: Mapped[str | None] = mapped_column(String(64))
    type_line: Mapped[str | None] = mapped_column(String(255))
    oracle_text: Mapped[str | None] = mapped_column(Text)
    colors: Mapped[str | None] = mapped_column(String(16))
    color_identity: Mapped[str | None] = mapped_column(String(16))
    cmc: Mapped[float | None] = mapped_column()
    image_uri: Mapped[str | None] = mapped_column(String(512))
    is_basic_land: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_token: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    copies: Mapped[list["CardCopy"]] = relationship(back_populates="card")


class CardCopy(Base):
    __tablename__ = "card_copies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.oracle_id"), nullable=False)
    edition: Mapped[str | None] = mapped_column(String(16))
    language: Mapped[str | None] = mapped_column(String(8))
    foil: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    condition: Mapped[str | None] = mapped_column(String(32))
    location: Mapped[str | None] = mapped_column(String(128))

    card: Mapped["Card"] = relationship(back_populates="copies")
    assignment: Mapped["CardAssignment | None"] = relationship(
        back_populates="card_copy",
        uselist=False,
    )


from mtg_sorter.models.deck import CardAssignment  # noqa: E402
