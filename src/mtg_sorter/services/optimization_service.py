from dataclasses import dataclass

from sqlalchemy.orm import Session

from mtg_sorter.algorithms.deck_optimizer import DeckSupply, OptimizationResult, find_all_optimal_solutions
from mtg_sorter.models import Deck
from mtg_sorter.services.deck_service import DeckService, InventoryService


@dataclass(frozen=True)
class AssemblyPlan:
    target_deck: Deck
    result: OptimizationResult
    free_inventory_used: dict[str, int]
    still_missing: dict[str, int]
    solution_labels: dict[frozenset[str], str]


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
        for deck_id, cards in armed.items():
            deck = self._decks.get_deck(deck_id)
            if deck is None:
                continue
            supplies[str(deck_id)] = DeckSupply(
                deck_id=str(deck_id),
                deck_name=deck.name,
                cards=cards,
            )

        result = find_all_optimal_solutions(needs, supplies)

        labels = {
            solution: ", ".join(
                supplies[deck_id].deck_name for deck_id in sorted(solution)
            )
            for solution in result.solutions
        }

        return AssemblyPlan(
            target_deck=target,
            result=result,
            free_inventory_used=free_used,
            still_missing=result.unmet_needs,
            solution_labels=labels,
        )
