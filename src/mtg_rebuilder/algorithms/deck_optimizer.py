from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class DeckSupply:
    deck_id: str
    deck_name: str
    cards: dict[str, int]


@dataclass(frozen=True)
class OptimizationResult:
    minimum_decks_to_dismantle: int
    solutions: tuple[frozenset[str], ...]
    unmet_needs: dict[str, int]

    @property
    def has_feasible_solution(self) -> bool:
        return not self.unmet_needs and bool(self.solutions)


def _is_feasible(
    selected_deck_ids: frozenset[str],
    needs: dict[str, int],
    supplies: dict[str, DeckSupply],
) -> bool:
    for card_id, required in needs.items():
        if required <= 0:
            continue
        available = sum(
            supplies[deck_id].cards.get(card_id, 0)
            for deck_id in selected_deck_ids
            if deck_id in supplies
        )
        if available < required:
            return False
    return True


def _solve_optimal_count(
    needs: dict[str, int],
    supplies: dict[str, DeckSupply],
) -> int | None:
    active_needs = {card_id: qty for card_id, qty in needs.items() if qty > 0}
    if not active_needs:
        return 0

    deck_ids = list(supplies.keys())
    if not deck_ids:
        return None

    try:
        from ortools.linear_solver import pywraplp
    except ImportError as exc:
        raise RuntimeError("OR-Tools is required for deck optimization") from exc

    solver = pywraplp.Solver.CreateSolver("SCIP")
    if solver is None:
        raise RuntimeError("Could not create OR-Tools SCIP solver")

    variables = {
        deck_id: solver.BoolVar(f"x_{deck_id}") for deck_id in deck_ids
    }

    for card_id, required in active_needs.items():
        constraint = solver.Constraint(required, solver.infinity())
        for deck_id, supply in supplies.items():
            qty = supply.cards.get(card_id, 0)
            if qty:
                constraint.SetCoefficient(variables[deck_id], qty)

    objective = solver.Objective()
    for variable in variables.values():
        objective.SetCoefficient(variable, 1)
    objective.SetMinimization()

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        return None
    return int(round(solver.Objective().Value()))


def find_all_optimal_solutions(
    needs: dict[str, int],
    supplies: dict[str, DeckSupply],
) -> OptimizationResult:
    """Find every minimum-cardinality set of decks that satisfies card needs."""
    active_needs = {card_id: qty for card_id, qty in needs.items() if qty > 0}
    if not active_needs:
        return OptimizationResult(
            minimum_decks_to_dismantle=0,
            solutions=(frozenset(),),
            unmet_needs={},
        )

    if not supplies:
        return OptimizationResult(
            minimum_decks_to_dismantle=0,
            solutions=(),
            unmet_needs=active_needs,
        )

    optimal_count = _solve_optimal_count(active_needs, supplies)
    if optimal_count is None:
        return OptimizationResult(
            minimum_decks_to_dismantle=0,
            solutions=(),
            unmet_needs=active_needs,
        )

    deck_ids = list(supplies.keys())
    solutions: list[frozenset[str]] = []
    for combo in combinations(deck_ids, optimal_count):
        candidate = frozenset(combo)
        if _is_feasible(candidate, active_needs, supplies):
            solutions.append(candidate)

    if not solutions:
        return OptimizationResult(
            minimum_decks_to_dismantle=optimal_count,
            solutions=(),
            unmet_needs=active_needs,
        )

    return OptimizationResult(
        minimum_decks_to_dismantle=optimal_count,
        solutions=tuple(solutions),
        unmet_needs={},
    )
