from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from mtg_sorter.models import Card, CardAssignment, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckStatus
from mtg_sorter.services.scryfall_bulk_service import BulkSyncStatus, ScryfallBulkService


@dataclass(frozen=True)
class OverviewStats:
    cards: int
    copies: int
    unassigned_copies: int
    decks: int
    armed_decks: int
    deck_cards: int
    assignments: int


@dataclass(frozen=True)
class CardSummary:
    oracle_id: str
    name: str
    type_line: str | None
    cmc: float | None
    color_identity: str | None
    is_basic_land: bool
    is_token: bool
    copy_count: int


@dataclass(frozen=True)
class InventorySummaryRow:
    oracle_id: str
    card_name: str
    total_copies: int
    free_copies: int
    assigned_decks: tuple[str, ...]
    color_identity: str | None = None


class BrowseService:
    @staticmethod
    def _playable_card_clause():
        return or_(Card.type_line.is_(None), Card.type_line != "Card // Card")

    def __init__(self, session: Session) -> None:
        self._session = session

    def overview(self) -> OverviewStats:
        assigned_copy_ids = select(CardAssignment.card_copy_id)
        return OverviewStats(
            cards=int(
                self._session.scalar(
                    select(func.count())
                    .select_from(Card)
                    .where(self._playable_card_clause())
                )
                or 0
            ),
            copies=int(
                self._session.scalar(select(func.count()).select_from(CardCopy)) or 0
            ),
            unassigned_copies=int(
                self._session.scalar(
                    select(func.count())
                    .select_from(CardCopy)
                    .where(CardCopy.id.not_in(assigned_copy_ids))
                )
                or 0
            ),
            decks=int(self._session.scalar(select(func.count()).select_from(Deck)) or 0),
            armed_decks=int(
                self._session.scalar(
                    select(func.count())
                    .select_from(Deck)
                    .where(Deck.status == DeckStatus.ARMED)
                )
                or 0
            ),
            deck_cards=int(
                self._session.scalar(select(func.count()).select_from(DeckCard)) or 0
            ),
            assignments=int(
                self._session.scalar(select(func.count()).select_from(CardAssignment))
                or 0
            ),
        )

    def list_cards(self, search: str = "") -> list[CardSummary]:
        copy_counts = dict(
            self._session.execute(
                select(CardCopy.card_id, func.count(CardCopy.id)).group_by(
                    CardCopy.card_id
                )
            ).all()
        )

        query = (
            select(Card)
            .where(self._playable_card_clause())
            .order_by(Card.name)
        )
        trimmed = search.strip()
        if trimmed:
            query = query.where(Card.name.ilike(f"%{trimmed}%"))

        return [
            CardSummary(
                oracle_id=card.oracle_id,
                name=card.name,
                type_line=card.type_line,
                cmc=card.cmc,
                color_identity=card.color_identity,
                is_basic_land=card.is_basic_land,
                is_token=card.is_token,
                copy_count=copy_counts.get(card.oracle_id, 0),
            )
            for card in self._session.scalars(query).all()
        ]

    def list_inventory(self) -> list[InventorySummaryRow]:
        copy_rows = self._session.execute(
            select(
                Card.oracle_id,
                Card.name,
                Card.color_identity,
                func.count(CardCopy.id),
            )
            .join(Card, Card.oracle_id == CardCopy.card_id)
            .group_by(Card.oracle_id, Card.name, Card.color_identity)
            .order_by(Card.name)
        ).all()

        summaries: list[InventorySummaryRow] = []
        for oracle_id, name, color_identity, total in copy_rows:
            assigned_count = int(
                self._session.scalar(
                    select(func.count())
                    .select_from(CardCopy)
                    .join(
                        CardAssignment,
                        CardAssignment.card_copy_id == CardCopy.id,
                    )
                    .where(CardCopy.card_id == oracle_id)
                )
                or 0
            )
            deck_names = tuple(
                self._session.scalars(
                    select(Deck.name)
                    .join(CardAssignment, CardAssignment.deck_id == Deck.id)
                    .join(CardCopy, CardCopy.id == CardAssignment.card_copy_id)
                    .where(CardCopy.card_id == oracle_id)
                    .distinct()
                    .order_by(Deck.name)
                ).all()
            )
            summaries.append(
                InventorySummaryRow(
                    oracle_id=oracle_id,
                    card_name=name,
                    total_copies=int(total),
                    free_copies=int(total) - assigned_count,
                    assigned_decks=deck_names,
                    color_identity=color_identity,
                )
            )
        return summaries

    def scryfall_status(self) -> BulkSyncStatus:
        return ScryfallBulkService(self._session).status()
