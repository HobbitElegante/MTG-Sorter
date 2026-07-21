from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mtg_sorter.models import Card, CardAssignment, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus


class InventoryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_copy(self, oracle_id: str, quantity: int = 1) -> list[CardCopy]:
        copies: list[CardCopy] = []
        for _ in range(quantity):
            copy = CardCopy(card_id=oracle_id)
            self._session.add(copy)
            copies.append(copy)
        self._session.flush()
        return copies

    def free_counts(self) -> dict[str, int]:
        assigned_copy_ids = select(CardAssignment.card_copy_id)
        rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id))
            .where(CardCopy.id.not_in(assigned_copy_ids))
            .group_by(CardCopy.card_id)
        ).all()
        return {card_id: count for card_id, count in rows}

    def list_unassigned_copies(self) -> list[CardCopy]:
        assigned_copy_ids = select(CardAssignment.card_copy_id)
        return list(
            self._session.scalars(
                select(CardCopy)
                .where(CardCopy.id.not_in(assigned_copy_ids))
                .order_by(CardCopy.id)
            ).all()
        )


class DeckService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_decks(self) -> list[Deck]:
        return list(self._session.scalars(select(Deck).order_by(Deck.name)).all())

    def get_deck(self, deck_id: int) -> Deck | None:
        return self._session.get(Deck, deck_id)

    def set_status(self, deck: Deck, status: DeckStatus) -> None:
        deck.status = status
        if status == DeckStatus.DISMANTLED:
            for assignment in list(deck.assignments):
                self._session.delete(assignment)

    def deck_requirements(self, deck_id: int) -> dict[str, int]:
        rows = self._session.execute(
            select(DeckCard.card_id, func.sum(DeckCard.quantity))
            .join(Card, Card.oracle_id == DeckCard.card_id)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.role != DeckCardRole.TOKEN,
                Card.is_basic_land.is_(False),
                Card.is_token.is_(False),
            )
            .group_by(DeckCard.card_id)
        ).all()
        return {card_id: int(qty) for card_id, qty in rows}

    def armed_deck_supplies(self, exclude_deck_id: int | None = None) -> dict[int, dict[str, int]]:
        query = select(Deck).where(Deck.status == DeckStatus.ARMED)
        if exclude_deck_id is not None:
            query = query.where(Deck.id != exclude_deck_id)

        supplies: dict[int, dict[str, int]] = {}
        for deck in self._session.scalars(query).all():
            supplies[deck.id] = self.deck_requirements(deck.id)
        return supplies
