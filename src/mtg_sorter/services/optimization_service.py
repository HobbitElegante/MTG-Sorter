from dataclasses import dataclass

from sqlalchemy.orm import Session

from mtg_sorter.algorithms.deck_optimizer import DeckSupply, OptimizationResult, find_all_optimal_solutions
from mtg_sorter.models.enums import ActivityEventType, DeckStatus
from mtg_sorter.repositories import CardRepository
from mtg_sorter.services.activity_service import ActivityService
from mtg_sorter.services.deck_service import DeckService, InventoryService


def allocate_solution_cards(
    residual_needs: dict[str, int],
    deck_supplies: dict[str, dict[str, int]],
    deck_names: dict[str, str],
    solution: frozenset[str],
) -> dict[str, dict[str, int]]:
    """Greedy stable allocation of residual needs to decks in a solution.

    Decks are processed in name order; cards within a deck by card id.
    Only cards required by the target (residual after free inventory) are
    attributed — not the full donor deck list.
    """
    remaining = {card_id: qty for card_id, qty in residual_needs.items() if qty > 0}
    ordered_decks = sorted(
        (deck_id for deck_id in solution if deck_id in deck_supplies),
        key=lambda deck_id: deck_names.get(deck_id, deck_id).lower(),
    )
    taken: dict[str, dict[str, int]] = {}
    for deck_id in ordered_decks:
        supply = deck_supplies[deck_id]
        for card_id in sorted(supply.keys()):
            need = remaining.get(card_id, 0)
            if need <= 0:
                continue
            available = supply.get(card_id, 0)
            if available <= 0:
                continue
            use = min(need, available)
            taken.setdefault(deck_id, {})[card_id] = use
            remaining[card_id] = need - use
    return taken


def remaining_after_allocation(
    needs: dict[str, int],
    taken: dict[str, dict[str, int]],
) -> dict[str, int]:
    """Subtract allocated quantities from needs; drop zeros."""
    leftover = dict(needs)
    for cards in taken.values():
        for card_id, qty in cards.items():
            leftover[card_id] = leftover.get(card_id, 0) - qty
            if leftover.get(card_id, 0) <= 0:
                leftover.pop(card_id, None)
    return {card_id: qty for card_id, qty in leftover.items() if qty > 0}


@dataclass(frozen=True)
class AssemblyPlan:
    target_deck_id: int
    target_deck_name: str
    result: OptimizationResult
    free_inventory_used: dict[str, int]
    still_missing: dict[str, int]
    residual_needs: dict[str, int]
    deck_supplies: dict[str, dict[str, int]]
    solution_labels: dict[frozenset[str], str]
    card_names: dict[str, str]
    deck_names: dict[str, str]
    already_armed: bool = False

    def cards_taken_from_solution(
        self, solution: frozenset[str]
    ) -> dict[str, dict[str, int]]:
        return allocate_solution_cards(
            self.residual_needs,
            self.deck_supplies,
            self.deck_names,
            solution,
        )

    def missing_by_source(
        self,
    ) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
        """Group unmet needs by armed decks vs not findable anywhere.

        Returns ``(by_deck, need_to_find)`` where ``by_deck`` maps armed deck
        ids to cards they could cover from ``still_missing``, and
        ``need_to_find`` is the remainder not present in free inventory or
        any armed deck.
        """
        if not self.still_missing:
            return {}, {}
        all_armed = frozenset(self.deck_supplies.keys())
        by_deck = allocate_solution_cards(
            self.still_missing,
            self.deck_supplies,
            self.deck_names,
            all_armed,
        )
        need_to_find = remaining_after_allocation(self.still_missing, by_deck)
        return by_deck, need_to_find


class OptimizationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._decks = DeckService(session)
        self._inventory = InventoryService(session)
        self._cards = CardRepository(session)

    def plan_assembly(self, target_deck_id: int) -> AssemblyPlan:
        target = self._decks.get_deck(target_deck_id)
        if target is None:
            raise ValueError(f"Deck {target_deck_id} not found")

        if target.status == DeckStatus.ARMED:
            return AssemblyPlan(
                target_deck_id=target.id,
                target_deck_name=target.name,
                result=OptimizationResult(
                    minimum_decks_to_dismantle=0,
                    solutions=(frozenset(),),
                    unmet_needs={},
                ),
                free_inventory_used={},
                still_missing={},
                residual_needs={},
                deck_supplies={},
                solution_labels={},
                card_names={},
                deck_names={},
                already_armed=True,
            )

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

        # Basics are unlimited: always "take from the pool" and show in the
        # free-inventory section so reassembly knows how many to pull.
        for card_id, qty in self._decks.deck_basic_lands(target_deck_id).items():
            if qty > 0:
                free_used[card_id] = qty

        armed = self._decks.armed_deck_supplies(exclude_deck_id=target_deck_id)
        supplies: dict[str, DeckSupply] = {}
        deck_names: dict[str, str] = {}
        deck_supplies: dict[str, dict[str, int]] = {}
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
            deck_supplies[deck_key] = dict(cards)

        result = find_all_optimal_solutions(needs, supplies)

        labels = {
            solution: ", ".join(
                supplies[deck_id].deck_name for deck_id in sorted(solution)
            )
            for solution in result.solutions
        }

        card_ids = set(free_used) | set(result.unmet_needs) | set(needs)
        for cards in deck_supplies.values():
            card_ids.update(cards)
        card_names = self._card_names(card_ids)

        return AssemblyPlan(
            target_deck_id=target.id,
            target_deck_name=target.name,
            result=result,
            free_inventory_used=free_used,
            still_missing=result.unmet_needs,
            residual_needs=needs,
            deck_supplies=deck_supplies,
            solution_labels=labels,
            card_names=card_names,
            deck_names=deck_names,
        )

    def apply_assembly_plan(
        self,
        target_deck_id: int,
        solution: frozenset[str],
    ) -> None:
        """Dismantle each deck in ``solution``, then arm the target."""
        target = self._decks.get_deck(target_deck_id)
        if target is None:
            raise ValueError(f"Deck {target_deck_id} not found")
        if target.status == DeckStatus.ARMED:
            raise ValueError("Target deck is already armed")

        donor_names: list[str] = []
        donor_ids: list[int] = []
        for deck_key in sorted(solution):
            try:
                deck_id = int(deck_key)
            except ValueError as exc:
                raise ValueError(f"Invalid deck id in solution: {deck_key}") from exc
            deck = self._decks.get_deck(deck_id)
            if deck is None:
                raise ValueError(f"Deck {deck_id} not found")
            if deck.status != DeckStatus.ARMED:
                raise ValueError(f"Deck {deck.name} is not armed")
            donor_names.append(deck.name)
            donor_ids.append(deck_id)
            self._decks.set_status(deck, DeckStatus.DISMANTLED, record_activity=False)

        self._session.refresh(target)
        self._decks.set_status(target, DeckStatus.ARMED, record_activity=False)
        ActivityService(self._session).record(
            ActivityEventType.PLAN_APPLIED,
            "history.event.plan_applied",
            {
                "deck_id": target.id,
                "deck_name": target.name,
                "donor_deck_ids": donor_ids,
                "donor_names": donor_names,
            },
        )

    def _card_names(self, card_ids: set[str]) -> dict[str, str]:
        return self._cards.names_by_ids(card_ids)
