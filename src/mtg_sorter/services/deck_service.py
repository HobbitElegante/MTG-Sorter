from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from mtg_sorter.models import Card, CardAssignment, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus


@dataclass(frozen=True)
class DeckDeleteCardImpact:
    oracle_id: str
    name: str
    list_quantity: int
    total_copies: int
    removable_copies: int

    @property
    def assigned_elsewhere(self) -> int:
        return max(0, self.total_copies - self.removable_copies)


@dataclass(frozen=True)
class DeckEditRow:
    oracle_id: str
    name: str
    quantity: int
    role: DeckCardRole
    free_copies: int
    is_basic_land: bool
    is_token: bool
    removable_copies: int


@dataclass(frozen=True)
class DeckEditLine:
    oracle_id: str
    quantity: int
    role: DeckCardRole


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

    def deck_delete_impact(self, deck_id: int) -> list[DeckDeleteCardImpact]:
        """Inventory impact per trackable card when deleting a deck list."""
        requirements = self.deck_requirements(deck_id)
        if not requirements:
            return []

        total_rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id))
            .where(CardCopy.card_id.in_(requirements.keys()))
            .group_by(CardCopy.card_id)
        ).all()
        totals = {card_id: count for card_id, count in total_rows}

        assigned_here_rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id))
            .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
            .where(
                CardAssignment.deck_id == deck_id,
                CardCopy.card_id.in_(requirements.keys()),
            )
            .group_by(CardCopy.card_id)
        ).all()
        assigned_here = {card_id: count for card_id, count in assigned_here_rows}

        free = InventoryService(self._session).free_counts()

        impacts: list[DeckDeleteCardImpact] = []
        for oracle_id, list_qty in requirements.items():
            card = self._session.get(Card, oracle_id)
            if card is None:
                continue
            total = totals.get(oracle_id, 0)
            removable = assigned_here.get(oracle_id, 0) + free.get(oracle_id, 0)
            impacts.append(
                DeckDeleteCardImpact(
                    oracle_id=oracle_id,
                    name=card.name,
                    list_quantity=list_qty,
                    total_copies=total,
                    removable_copies=removable,
                )
            )
        return sorted(impacts, key=lambda item: item.name.casefold())

    def delete_deck(
        self,
        deck_id: int,
        remove_copies: dict[str, int] | None = None,
    ) -> bool:
        """Remove a deck list and optionally delete physical copies.

        Removable copies are those assigned to this deck or currently free.
        Copies assigned to other armed decks are never deleted.
        """
        deck = self.get_deck(deck_id)
        if deck is None:
            return False

        removals = {
            oracle_id: qty
            for oracle_id, qty in (remove_copies or {}).items()
            if qty > 0
        }
        if removals:
            self._delete_removable_copies(deck_id, removals)

        self._session.execute(
            delete(CardAssignment).where(CardAssignment.deck_id == deck.id)
        )
        self._session.execute(delete(DeckCard).where(DeckCard.deck_id == deck.id))
        self._session.delete(deck)
        self._session.flush()
        return True

    def _delete_removable_copies(
        self, deck_id: int, removals: dict[str, int]
    ) -> None:
        for oracle_id, quantity in removals.items():
            remaining = quantity
            if remaining <= 0:
                continue

            assigned = list(
                self._session.scalars(
                    select(CardCopy)
                    .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
                    .where(
                        CardAssignment.deck_id == deck_id,
                        CardCopy.card_id == oracle_id,
                    )
                    .order_by(CardCopy.id)
                    .limit(remaining)
                ).all()
            )
            for copy in assigned:
                self._session.execute(
                    delete(CardAssignment).where(
                        CardAssignment.card_copy_id == copy.id
                    )
                )
                self._session.delete(copy)
                remaining -= 1

            if remaining <= 0:
                continue

            assigned_copy_ids = select(CardAssignment.card_copy_id)
            free_copies = list(
                self._session.scalars(
                    select(CardCopy)
                    .where(
                        CardCopy.card_id == oracle_id,
                        CardCopy.id.not_in(assigned_copy_ids),
                    )
                    .order_by(CardCopy.id)
                    .limit(remaining)
                ).all()
            )
            for copy in free_copies:
                self._session.delete(copy)

        self._session.flush()

    def deck_edit_rows(self, deck_id: int) -> list[DeckEditRow]:
        rows = self._session.execute(
            select(DeckCard, Card)
            .join(Card, Card.oracle_id == DeckCard.card_id)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.role != DeckCardRole.TOKEN,
            )
            .order_by(Card.name, DeckCard.role)
        ).all()
        if not rows:
            return []

        oracle_ids = {card.oracle_id for _, card in rows}
        free = InventoryService(self._session).free_counts()
        assigned_here = self._assigned_counts_for_deck(deck_id, oracle_ids)

        return [
            DeckEditRow(
                oracle_id=card.oracle_id,
                name=card.name,
                quantity=deck_card.quantity,
                role=deck_card.role,
                free_copies=free.get(card.oracle_id, 0),
                is_basic_land=card.is_basic_land,
                is_token=card.is_token,
                removable_copies=(
                    assigned_here.get(card.oracle_id, 0) + free.get(card.oracle_id, 0)
                ),
            )
            for deck_card, card in rows
        ]

    def apply_deck_edit(
        self,
        deck_id: int,
        lines: list[DeckEditLine],
        *,
        create_free_copies: dict[str, int] | None = None,
        remove_copies: dict[str, int] | None = None,
    ) -> None:
        deck = self.get_deck(deck_id)
        if deck is None:
            raise ValueError(f"Deck {deck_id} not found")

        was_armed = deck.status == DeckStatus.ARMED
        if was_armed:
            self.set_status(deck, DeckStatus.DISMANTLED)

        removals = {
            oracle_id: qty
            for oracle_id, qty in (remove_copies or {}).items()
            if qty > 0
        }
        if removals:
            self._delete_removable_copies(deck_id, removals)

        creations = {
            oracle_id: qty
            for oracle_id, qty in (create_free_copies or {}).items()
            if qty > 0
        }
        if creations:
            inventory = InventoryService(self._session)
            for oracle_id, qty in creations.items():
                inventory.add_copy(oracle_id, qty)

        self._session.execute(delete(DeckCard).where(DeckCard.deck_id == deck.id))
        self._session.flush()

        merged: dict[tuple[str, DeckCardRole], int] = {}
        for line in lines:
            if line.quantity <= 0:
                continue
            key = (line.oracle_id, line.role)
            merged[key] = merged.get(key, 0) + line.quantity

        for (oracle_id, role), quantity in merged.items():
            self._session.add(
                DeckCard(
                    deck_id=deck.id,
                    card_id=oracle_id,
                    quantity=quantity,
                    role=role,
                )
            )
        self._session.flush()

        if was_armed:
            self.set_status(deck, DeckStatus.ARMED)

        self._session.refresh(deck)

    def _assigned_counts_for_deck(
        self, deck_id: int, oracle_ids: set[str]
    ) -> dict[str, int]:
        if not oracle_ids:
            return {}
        rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id))
            .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
            .where(
                CardAssignment.deck_id == deck_id,
                CardCopy.card_id.in_(oracle_ids),
            )
            .group_by(CardCopy.card_id)
        ).all()
        return {card_id: count for card_id, count in rows}

    def set_status(self, deck: Deck, status: DeckStatus) -> None:
        if status == DeckStatus.DISMANTLED:
            self._session.execute(
                delete(CardAssignment).where(CardAssignment.deck_id == deck.id)
            )
            self._session.flush()
            deck.status = status
            return

        if status == DeckStatus.ARMED:
            deck.status = status
            self._ensure_assignments(deck)
            return

        deck.status = status

    def _ensure_assignments(self, deck: Deck) -> None:
        assigned_counts: dict[str, int] = {}
        for assignment in deck.assignments:
            card_id = assignment.card_copy.card_id
            assigned_counts[card_id] = assigned_counts.get(card_id, 0) + 1

        assigned_copy_ids = select(CardAssignment.card_copy_id)

        for card_id, required in self.deck_requirements(deck.id).items():
            missing = required - assigned_counts.get(card_id, 0)
            if missing <= 0:
                continue

            free_copies = list(
                self._session.scalars(
                    select(CardCopy)
                    .where(
                        CardCopy.card_id == card_id,
                        CardCopy.id.not_in(assigned_copy_ids),
                    )
                    .order_by(CardCopy.id)
                    .limit(missing)
                ).all()
            )
            for copy in free_copies:
                self._session.add(
                    CardAssignment(card_copy_id=copy.id, deck_id=deck.id)
                )
                missing -= 1

            for _ in range(missing):
                copy = CardCopy(card_id=card_id)
                self._session.add(copy)
                self._session.flush()
                self._session.add(
                    CardAssignment(card_copy_id=copy.id, deck_id=deck.id)
                )

        self._session.flush()

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

    def free_coverage_toward_deck(self, deck_id: int) -> int:
        """How many trackable list copies are already covered by free inventory."""
        requirements = self.deck_requirements(deck_id)
        if not requirements:
            return 0
        free = InventoryService(self._session).free_counts()
        return sum(
            min(required, free.get(card_id, 0))
            for card_id, required in requirements.items()
        )
