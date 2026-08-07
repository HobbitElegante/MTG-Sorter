"""Pure tests for viable simultaneous deck sets."""

from mtg_rebuilder.algorithms.viable_plans import (
    enumerate_max_viable_combinations,
    enumerate_viable_combinations,
    find_max_viable_size,
    is_combination_viable,
    is_combination_viable_respecting_locks,
    sum_requirements,
)


def test_sum_requirements() -> None:
    req = {1: {"a": 1, "b": 2}, 2: {"a": 1}, 3: {"c": 1}}
    assert sum_requirements((1, 2), req) == {"a": 2, "b": 2}


def test_global_viable_and_not() -> None:
    assert is_combination_viable({"a": 2, "b": 1}, {"a": 2, "b": 5})
    assert not is_combination_viable({"a": 3}, {"a": 2})


def test_enumerate_pairs() -> None:
    # Three decks; Sol Ring stock=1 so only disjoint pairs without Sol conflict.
    # A and B both need Sol → not viable together. A+C and B+C ok (C needs nothing shared).
    requirements = {
        1: {"sol": 1},
        2: {"sol": 1},
        3: {"cultivate": 1},
    }
    stock = {"sol": 1, "cultivate": 1}
    pairs, truncated = enumerate_viable_combinations(
        [1, 2, 3], requirements, stock, n=2
    )
    assert not truncated
    assert pairs == [(1, 3), (2, 3)]


def test_find_max_and_ties() -> None:
    requirements = {
        1: {"a": 1},
        2: {"b": 1},
        3: {"c": 1},
        4: {"a": 1},  # conflicts with 1
    }
    stock = {"a": 1, "b": 1, "c": 1}
    assert find_max_viable_size([1, 2, 3, 4], requirements, stock) == 3
    size, combos, truncated = enumerate_max_viable_combinations(
        [1, 2, 3, 4], requirements, stock
    )
    assert not truncated
    assert size == 3
    # Only {2,3,4} and {1,2,3} — wait: {1,2,3} needs a,b,c all 1 → ok; {2,3,4} needs b,c,a → ok
    # {1,2,4} needs a×2 → fail; {1,3,4} needs a×2 → fail
    assert combos == [(1, 2, 3), (2, 3, 4)]


def test_max_empty_when_no_pair_fits() -> None:
    requirements = {1: {"a": 1}, 2: {"a": 1}}
    stock = {"a": 1}
    assert find_max_viable_size([1, 2], requirements, stock) == 0
    size, combos, truncated = enumerate_max_viable_combinations(
        [1, 2], requirements, stock
    )
    assert size == 0
    assert combos == []
    assert not truncated


def test_enumerate_respects_limit() -> None:
    requirements = {i: {f"c{i}": 1} for i in range(1, 6)}
    stock = {f"c{i}": 1 for i in range(1, 6)}
    combos, truncated = enumerate_viable_combinations(
        list(range(1, 6)), requirements, stock, n=2, limit=2
    )
    assert truncated
    assert len(combos) == 2


def test_hybrid_locked_outside_reserves_stock() -> None:
    # Locked deck 9 holds the only Sol; unlocked 1 and 2 both need Sol.
    # Global: 1+2 needs 2 Sol, stock=1 → fail anyway.
    # Better case: stock=2 Sol; locked 9 has 1 assigned. Global 1+2 needs 2 → ok.
    # With respect locks: pool = 2-1 = 1 < 2 → fail.
    requirements = {1: {"sol": 1}, 2: {"sol": 1}, 9: {"sol": 1}}
    stock = {"sol": 2}
    locked_ids = {9}
    locked_assigned = {9: {"sol": 1}}
    assert is_combination_viable(sum_requirements((1, 2), requirements), stock)
    assert not is_combination_viable_respecting_locks(
        (1, 2),
        requirements,
        stock,
        locked_ids,
        locked_assigned,
    )


def test_hybrid_locked_in_combo_self_covers() -> None:
    # Locked 9 in the combo: its assigned Sol covers its own demand; unlocked 1
    # needs another Sol from pool. stock=2, assigned_all_locked=1 → pool=1.
    requirements = {1: {"sol": 1}, 9: {"sol": 1}}
    stock = {"sol": 2}
    locked_ids = {9}
    locked_assigned = {9: {"sol": 1}}
    assert is_combination_viable_respecting_locks(
        (1, 9),
        requirements,
        stock,
        locked_ids,
        locked_assigned,
    )


def test_hybrid_locked_excess_does_not_cover_others() -> None:
    # Locked has 2 Sol assigned but only needs 1; unlocked needs 2.
    # pool = 3 - 2 = 1; unlocked needs 2 → fail (excess locked cannot help).
    requirements = {1: {"sol": 2}, 9: {"sol": 1}}
    stock = {"sol": 3}
    locked_ids = {9}
    locked_assigned = {9: {"sol": 2}}
    assert not is_combination_viable_respecting_locks(
        (1, 9),
        requirements,
        stock,
        locked_ids,
        locked_assigned,
    )
    # Without respect: demand 3 ≤ stock 3 → ok
    assert is_combination_viable(sum_requirements((1, 9), requirements), stock)


def test_enumerate_with_respect_locks() -> None:
    requirements = {
        1: {"sol": 1},
        2: {"cultivate": 1},
        9: {"sol": 1},
    }
    stock = {"sol": 1, "cultivate": 1}
    locked_ids = {9}
    locked_assigned = {9: {"sol": 1}}
    # Global: (1,2) ok; (1,9) needs 2 sol → fail; (2,9) ok
    global_pairs, _ = enumerate_viable_combinations(
        [1, 2, 9], requirements, stock, n=2
    )
    assert global_pairs == [(1, 2), (2, 9)]
    # Respect: (1,2) fails (sol reserved by 9); (2,9) ok (9 self-covers sol)
    hybrid, _ = enumerate_viable_combinations(
        [1, 2, 9],
        requirements,
        stock,
        n=2,
        respect_locks=True,
        locked_ids=locked_ids,
        locked_assigned_by_deck=locked_assigned,
    )
    assert hybrid == [(2, 9)]
