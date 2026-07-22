from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.deck_optimizer import DeckSupply, OptimizationResult, find_all_optimal_solutions
from mtg_sorter.models import Card, Deck
from mtg_sorter.services.deck_service import DeckService, InventoryService


@dataclass(frozen=True)
class AssemblyPlan:
    target_deck: Deck
    result: OptimizationResult
    free_inventory_used: dict[str, int]
    still_missing: dict[str, int]
    solution_labels: dict[frozenset[str], str]
    card_names: dict[str, str]
    deck_names: dict[str, str]


class OptimizationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._decks = DeckService(session)
        self._inventory = InventoryService(session)

    def plan_assembly(self, target_deck_id: int) -> AssemblyPlan:
        target = self._decks.get_deck(target_deck_id)
        if target is None:
            raise ValueError(f"Deck {target_deck_id} not found")

        requirements = self._decks.deck_requirements(target_deck_id)
        free = self._inventory.free_counts()

        needs: dict[str, int] = {}
        free_used: dict[str, int] = {}
        for card_id, required in requirements.items():
            available = free.get(card_id, 0)
            used = min(required, available)
            if used:
                free_used[card_id] = used
            remaining = required - used
            if remaining > 0:
                needs[card_id] = remaining

        armed = self._decks.armed_deck_supplies(exclude_deck_id=target_deck_id)
        supplies: dict[str, DeckSupply] = {}
        deck_names: dict[str, str] = {}
        for deck_id, cards in armed.items():
            deck = self._decks.get_deck(deck_id)
            if deck is None:
                continue
            deck_key = str(deck_id)
            supplies[deck_key] = DeckSupply(
                deck_id=deck_key,
                deck_name=deck.name,
                cards=cards,
            )
            deck_names[deck_key] = deck.name

        result = find_all_optimal_solutions(needs, supplies)

        labels = {
            solution: ", ".join(
                supplies[deck_id].deck_name for deck_id in sorted(solution)
            )
            for solution in result.solutions
        }

        card_ids = set(free_used) | set(result.unmet_needs)
        card_names = self._card_names(card_ids)

        return AssemblyPlan(
            target_deck=target,
            result=result,
            free_inventory_used=free_used,
            still_missing=result.unmet_needs,
            solution_labels=labels,
            card_names=card_names,
            deck_names=deck_names,
        )

    def _card_names(self, card_ids: set[str]) -> dict[str, str]:
        if not card_ids:
            return {}
        rows = self._session.scalars(
            select(Card).where(Card.oracle_id.in_(card_ids))
        ).all()
        return {card.oracle_id: card.name for card in rows}
