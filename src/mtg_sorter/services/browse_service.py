from dataclasses import dataclass

from sqlalchemy import func, select
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
class DeckSummary:
    deck_id: int
    name: str
    status: DeckStatus
    card_entries: int
    total_cards: int


@dataclass(frozen=True)
class DeckCardRow:
    name: str
    quantity: int
    role: str


@dataclass(frozen=True)
class InventoryRow:
    copy_id: int
    card_name: str
    assigned_deck: str | None


class BrowseService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def overview(self) -> OverviewStats:
        assigned_copy_ids = select(CardAssignment.card_copy_id)
        return OverviewStats(
            cards=int(self._session.scalar(select(func.count()).select_from(Card)) or 0),
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

        query = select(Card).order_by(Card.name)
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

    def list_decks(self) -> list[DeckSummary]:
        summaries: list[DeckSummary] = []
        for deck in self._session.scalars(select(Deck).order_by(Deck.name)).all():
            card_entries = len(deck.cards)
            total_cards = sum(entry.quantity for entry in deck.cards)
            summaries.append(
                DeckSummary(
                    deck_id=deck.id,
                    name=deck.name,
                    status=deck.status,
                    card_entries=card_entries,
                    total_cards=total_cards,
                )
            )
        return summaries

    def list_deck_cards(self, deck_id: int) -> list[DeckCardRow]:
        rows = self._session.execute(
            select(Card.name, DeckCard.quantity, DeckCard.role)
            .join(Card, Card.oracle_id == DeckCard.card_id)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.role, Card.name)
        ).all()
        return [
            DeckCardRow(name=name, quantity=quantity, role=role.value)
            for name, quantity, role in rows
        ]

    def list_inventory(self) -> list[InventoryRow]:
        rows = self._session.execute(
            select(
                CardCopy.id,
                Card.name,
                Deck.name,
            )
            .join(Card, Card.oracle_id == CardCopy.card_id)
            .outerjoin(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
            .outerjoin(Deck, Deck.id == CardAssignment.deck_id)
            .order_by(Card.name, CardCopy.id)
        ).all()
        return [
            InventoryRow(copy_id=copy_id, card_name=card_name, assigned_deck=deck_name)
            for copy_id, card_name, deck_name in rows
        ]

    def scryfall_status(self) -> BulkSyncStatus:
        return ScryfallBulkService(self._session).status()
