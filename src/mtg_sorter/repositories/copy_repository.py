from collections.abc import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from mtg_sorter.models import CardAssignment, CardCopy


class CopyRepository:
    """Physical card-copy persistence (free vs assigned inventory)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _assigned_copy_ids():
        return select(CardAssignment.card_copy_id)

    def add(self, card_id: str) -> CardCopy:
        copy = CardCopy(card_id=card_id)
        self._session.add(copy)
        return copy

    def add_many(self, card_id: str, quantity: int) -> list[CardCopy]:
        copies = [CardCopy(card_id=card_id) for _ in range(quantity)]
        for copy in copies:
            self._session.add(copy)
        self._session.flush()
        return copies

    def delete_copies(self, copies: Iterable[CardCopy]) -> None:
        for copy in copies:
            self._session.delete(copy)
        self._session.flush()

    def count_total(self, oracle_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(CardCopy)
                .where(CardCopy.card_id == oracle_id)
            )
            or 0
        )

    def count_assigned(self, oracle_id: str) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(CardCopy)
                .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
                .where(CardCopy.card_id == oracle_id)
            )
            or 0
        )

    def count_all(self) -> int:
        return int(
            self._session.scalar(select(func.count()).select_from(CardCopy)) or 0
        )

    def count_unassigned(self) -> int:
        return int(
            self._session.scalar(
                select(func.count())
                .select_from(CardCopy)
                .where(CardCopy.id.not_in(self._assigned_copy_ids()))
            )
            or 0
        )

    def count_assignments(self) -> int:
        return int(
            self._session.scalar(select(func.count()).select_from(CardAssignment))
            or 0
        )

    def free_counts(self) -> dict[str, int]:
        rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id))
            .where(CardCopy.id.not_in(self._assigned_copy_ids()))
            .group_by(CardCopy.card_id)
        ).all()
        return {card_id: count for card_id, count in rows}

    def counts_by_card(self) -> dict[str, int]:
        rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id)).group_by(CardCopy.card_id)
        ).all()
        return {card_id: count for card_id, count in rows}

    def totals_for_cards(self, oracle_ids: Iterable[str]) -> dict[str, int]:
        ids = list(oracle_ids)
        if not ids:
            return {}
        rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id))
            .where(CardCopy.card_id.in_(ids))
            .group_by(CardCopy.card_id)
        ).all()
        return {card_id: count for card_id, count in rows}

    def list_free(self, oracle_id: str, *, limit: int | None = None) -> list[CardCopy]:
        query = (
            select(CardCopy)
            .where(
                CardCopy.card_id == oracle_id,
                CardCopy.id.not_in(self._assigned_copy_ids()),
            )
            .order_by(CardCopy.id)
        )
        if limit is not None:
            query = query.limit(limit)
        return list(self._session.scalars(query).all())

    def list_all_unassigned(self) -> list[CardCopy]:
        return list(
            self._session.scalars(
                select(CardCopy)
                .where(CardCopy.id.not_in(self._assigned_copy_ids()))
                .order_by(CardCopy.id)
            ).all()
        )

    def list_assigned_to_deck(
        self,
        deck_id: int,
        oracle_id: str,
        *,
        limit: int | None = None,
    ) -> list[CardCopy]:
        query = (
            select(CardCopy)
            .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
            .where(
                CardAssignment.deck_id == deck_id,
                CardCopy.card_id == oracle_id,
            )
            .order_by(CardCopy.id)
        )
        if limit is not None:
            query = query.limit(limit)
        return list(self._session.scalars(query).all())

    def assigned_counts_for_deck(
        self, deck_id: int, oracle_ids: Iterable[str]
    ) -> dict[str, int]:
        ids = list(oracle_ids)
        if not ids:
            return {}
        rows = self._session.execute(
            select(CardCopy.card_id, func.count(CardCopy.id))
            .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
            .where(
                CardAssignment.deck_id == deck_id,
                CardCopy.card_id.in_(ids),
            )
            .group_by(CardCopy.card_id)
        ).all()
        return {card_id: count for card_id, count in rows}

    def delete_assignment_for_copy(self, card_copy_id: int) -> None:
        self._session.execute(
            delete(CardAssignment).where(CardAssignment.card_copy_id == card_copy_id)
        )

    def add_assignment(self, card_copy_id: int, deck_id: int) -> CardAssignment:
        assignment = CardAssignment(card_copy_id=card_copy_id, deck_id=deck_id)
        self._session.add(assignment)
        return assignment

    def distinct_card_ids(self) -> set[str]:
        return set(self._session.scalars(select(CardCopy.card_id).distinct()).all())
