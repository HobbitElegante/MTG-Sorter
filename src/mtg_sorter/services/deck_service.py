from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import is_commander_legality_issue
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
    commander_legality: str | None = None


@dataclass(frozen=True)
class DeckEditLine:
    oracle_id: str
    quantity: int
    role: DeckCardRole


@dataclass(frozen=True)
class FreeCoverage:
    """Free-inventory coverage of a dismantled deck's trackable list slots."""

    covered: int
    required: int


@dataclass(frozen=True)
class CommanderLegalityIssue:
    """A list card that Scryfall marks as not fully legal in Commander."""

    oracle_id: str
    name: str
    legality: str


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

    def remove_free_copies(self, oracle_id: str, quantity: int) -> int:
        """Delete up to `quantity` unassigned copies. Returns how many were removed."""
        if quantity <= 0:
            return 0
        assigned_copy_ids = select(CardAssignment.card_copy_id)
        free_copies = list(
            self._session.scalars(
                select(CardCopy)
                .where(
                    CardCopy.card_id == oracle_id,
                    CardCopy.id.not_in(assigned_copy_ids),
                )
                .order_by(CardCopy.id)
                .limit(quantity)
            ).all()
        )
        for copy in free_copies:
            self._session.delete(copy)
        self._session.flush()
        return len(free_copies)

    def set_total_copies(self, oracle_id: str, total: int) -> None:
        """Set physical copy count. Cannot go below copies assigned to armed decks."""
        if total < 0:
            raise ValueError("Copy count cannot be negative")

        current_total = int(
            self._session.scalar(
                select(func.count())
                .select_from(CardCopy)
                .where(CardCopy.card_id == oracle_id)
            )
            or 0
        )
        assigned = int(
            self._session.scalar(
                select(func.count())
                .select_from(CardCopy)
                .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
                .where(CardCopy.card_id == oracle_id)
            )
            or 0
        )
        if total < assigned:
            raise ValueError(
                f"Cannot set total below {assigned} copies assigned to armed decks"
            )

        if total > current_total:
            self.add_copy(oracle_id, total - current_total)
        elif total < current_total:
            removed = self.remove_free_copies(oracle_id, current_total - total)
            if removed != current_total - total:
                raise ValueError("Not enough free copies to remove")

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

    def list_decks(self, status: DeckStatus | None = None) -> list[Deck]:
        query = select(Deck).order_by(Deck.sort_order, Deck.name, Deck.id)
        if status is not None:
            query = query.where(Deck.status == status)
        return list(self._session.scalars(query).all())

    def get_deck(self, deck_id: int) -> Deck | None:
        return self._session.get(Deck, deck_id)

    def next_sort_order(self) -> int:
        current = self._session.scalar(select(func.max(Deck.sort_order)))
        return 0 if current is None else int(current) + 1

    def rename_deck(self, deck_id: int, name: str) -> Deck:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("Deck name cannot be empty")
        deck = self.get_deck(deck_id)
        if deck is None:
            raise ValueError(f"Deck {deck_id} not found")
        deck.name = cleaned
        self._session.flush()
        return deck

    def commander_name(self, deck_id: int) -> str | None:
        return self.role_card_name(deck_id, DeckCardRole.COMMANDER)

    def role_card_name(self, deck_id: int, role: DeckCardRole) -> str | None:
        row = self._session.execute(
            select(Card.name)
            .join(DeckCard, DeckCard.card_id == Card.oracle_id)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.role == role,
            )
            .order_by(Card.name)
            .limit(1)
        ).first()
        return row[0] if row else None

    def secondary_command_zone(
        self, deck_id: int
    ) -> tuple[DeckCardRole, str] | None:
        """First Partner / Companion / Background entry, if any."""
        rows = self._session.execute(
            select(DeckCard.role, Card.name)
            .join(Card, Card.oracle_id == DeckCard.card_id)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.role.in_(
                    (
                        DeckCardRole.PARTNER,
                        DeckCardRole.COMPANION,
                        DeckCardRole.BACKGROUND,
                    )
                ),
            )
        ).all()
        if not rows:
            return None
        priority = {
            DeckCardRole.PARTNER: 0,
            DeckCardRole.COMPANION: 1,
            DeckCardRole.BACKGROUND: 2,
        }
        role, name = min(rows, key=lambda item: (priority[item[0]], item[1].casefold()))
        return role, name

    def set_commander(self, deck_id: int, oracle_id: str | None) -> None:
        self.set_role_card(deck_id, DeckCardRole.COMMANDER, oracle_id)

    def set_role_card(
        self,
        deck_id: int,
        role: DeckCardRole,
        oracle_id: str | None,
    ) -> None:
        """Assign a special-zone role (commander / partner / companion / background).

        Pass ``None`` to clear that role (demoting previous holders to MAIN).
        If ``oracle_id`` is not yet on the list, it is added with quantity 1.
        """
        if role not in {
            DeckCardRole.COMMANDER,
            DeckCardRole.PARTNER,
            DeckCardRole.COMPANION,
            DeckCardRole.BACKGROUND,
        }:
            raise ValueError(f"Unsupported command-zone role: {role}")

        deck = self.get_deck(deck_id)
        if deck is None:
            raise ValueError(f"Deck {deck_id} not found")

        if oracle_id is not None and self._session.get(Card, oracle_id) is None:
            raise ValueError(f"Card {oracle_id} not found")

        holders = list(
            self._session.scalars(
                select(DeckCard).where(
                    DeckCard.deck_id == deck_id,
                    DeckCard.role == role,
                )
            ).all()
        )
        for entry in holders:
            if oracle_id is not None and entry.card_id == oracle_id:
                continue
            existing_main = self._session.scalar(
                select(DeckCard).where(
                    DeckCard.deck_id == deck_id,
                    DeckCard.card_id == entry.card_id,
                    DeckCard.role == DeckCardRole.MAIN,
                )
            )
            if existing_main is not None:
                existing_main.quantity += entry.quantity
                self._session.delete(entry)
            else:
                entry.role = DeckCardRole.MAIN

        self._session.flush()

        if oracle_id is None:
            return

        already = self._session.scalar(
            select(DeckCard).where(
                DeckCard.deck_id == deck_id,
                DeckCard.card_id == oracle_id,
                DeckCard.role == role,
            )
        )
        if already is not None:
            return

        # Drop the card from any other special role before assigning.
        for other_role in (
            DeckCardRole.COMMANDER,
            DeckCardRole.PARTNER,
            DeckCardRole.COMPANION,
            DeckCardRole.BACKGROUND,
        ):
            if other_role == role:
                continue
            other = self._session.scalar(
                select(DeckCard).where(
                    DeckCard.deck_id == deck_id,
                    DeckCard.card_id == oracle_id,
                    DeckCard.role == other_role,
                )
            )
            if other is not None:
                self._session.delete(other)
        self._session.flush()

        main_entry = self._session.scalar(
            select(DeckCard).where(
                DeckCard.deck_id == deck_id,
                DeckCard.card_id == oracle_id,
                DeckCard.role == DeckCardRole.MAIN,
            )
        )
        if main_entry is not None:
            if main_entry.quantity > 1:
                main_entry.quantity -= 1
            else:
                self._session.delete(main_entry)
            self._session.flush()

        self._session.add(
            DeckCard(
                deck_id=deck_id,
                card_id=oracle_id,
                quantity=1,
                role=role,
            )
        )
        self._session.flush()

    def set_secondary_command_zone(
        self,
        deck_id: int,
        role: DeckCardRole | None,
        oracle_id: str | None,
    ) -> None:
        """Set exactly one of Partner / Companion / Background, clearing the others."""
        secondary = {
            DeckCardRole.PARTNER,
            DeckCardRole.COMPANION,
            DeckCardRole.BACKGROUND,
        }
        if role is not None and role not in secondary:
            raise ValueError(f"Secondary role must be partner/companion/background: {role}")
        if role is not None and oracle_id is None:
            raise ValueError("Secondary role requires a card")

        for candidate in secondary:
            if role is not None and candidate == role:
                continue
            self.set_role_card(deck_id, candidate, None)

        if role is not None and oracle_id is not None:
            self.set_role_card(deck_id, role, oracle_id)

    def move_deck(
        self,
        deck_id: int,
        *,
        direction: int,
        status: DeckStatus | None = None,
    ) -> bool:
        """Swap sort_order with the adjacent deck in the (optionally filtered) list.

        ``direction`` is -1 (up) or +1 (down). Returns False if no move occurred.
        """
        if direction not in (-1, 1):
            raise ValueError("direction must be -1 or +1")

        decks = self.list_decks(status=status)
        index = next((i for i, deck in enumerate(decks) if deck.id == deck_id), None)
        if index is None:
            return False
        neighbor_index = index + direction
        if neighbor_index < 0 or neighbor_index >= len(decks):
            return False

        current = decks[index]
        neighbor = decks[neighbor_index]
        current.sort_order, neighbor.sort_order = (
            neighbor.sort_order,
            current.sort_order,
        )
        self._session.flush()
        return True

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
                commander_legality=card.commander_legality,
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

    def deck_basic_lands(self, deck_id: int) -> dict[str, int]:
        """Basic land quantities on the list (unlimited pool; not optimized)."""
        rows = self._session.execute(
            select(DeckCard.card_id, func.sum(DeckCard.quantity))
            .join(Card, Card.oracle_id == DeckCard.card_id)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.role != DeckCardRole.TOKEN,
                Card.is_basic_land.is_(True),
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

    def free_coverage_toward_deck(self, deck_id: int) -> FreeCoverage:
        """How many trackable list copies are already covered by free inventory."""
        requirements = self.deck_requirements(deck_id)
        required = sum(requirements.values())
        if required == 0:
            return FreeCoverage(covered=0, required=0)
        free = InventoryService(self._session).free_counts()
        covered = sum(
            min(need, free.get(card_id, 0))
            for card_id, need in requirements.items()
        )
        return FreeCoverage(covered=covered, required=required)

    def commander_legality_issues(
        self, deck_id: int
    ) -> list[CommanderLegalityIssue]:
        """Cards on the list with Scryfall Commander legality issues (advisory)."""
        rows = self._session.execute(
            select(Card.oracle_id, Card.name, Card.commander_legality)
            .join(DeckCard, DeckCard.card_id == Card.oracle_id)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.role != DeckCardRole.TOKEN,
            )
            .distinct()
        ).all()
        issues: list[CommanderLegalityIssue] = []
        for oracle_id, name, legality in rows:
            if not is_commander_legality_issue(legality):
                continue
            issues.append(
                CommanderLegalityIssue(
                    oracle_id=oracle_id,
                    name=name,
                    legality=str(legality),
                )
            )
        return sorted(issues, key=lambda item: item.name.casefold())
