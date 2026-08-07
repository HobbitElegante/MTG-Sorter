from mtg_rebuilder.algorithms.deck_optimizer import DeckSupply, find_all_optimal_solutions


def test_no_dismantle_when_inventory_covers_everything() -> None:
    result = find_all_optimal_solutions({}, {})
    assert result.minimum_decks_to_dismantle == 0
    assert result.solutions == (frozenset(),)
    assert result.unmet_needs == {}


def test_single_deck_is_optimal() -> None:
    needs = {"sol_ring": 1, "cultivate": 1}
    supplies = {
        "1": DeckSupply(deck_id="1", deck_name="Deck A", cards={"sol_ring": 1, "cultivate": 1}),
        "2": DeckSupply(deck_id="2", deck_name="Deck B", cards={"sol_ring": 1}),
        "3": DeckSupply(deck_id="3", deck_name="Deck C", cards={"cultivate": 1}),
    }
    result = find_all_optimal_solutions(needs, supplies)
    assert result.minimum_decks_to_dismantle == 1
    assert frozenset({"1"}) in result.solutions
    assert result.unmet_needs == {}


def test_prefers_inventory_before_dismantling() -> None:
    needs = {"sol_ring": 1}
    supplies = {
        "1": DeckSupply(deck_id="1", deck_name="Deck A", cards={"sol_ring": 1}),
    }
    result = find_all_optimal_solutions({}, supplies)
    assert result.minimum_decks_to_dismantle == 0


def test_quantity_requires_multiple_decks() -> None:
    needs = {"sol_ring": 2}
    supplies = {
        "1": DeckSupply(deck_id="1", deck_name="Deck A", cards={"sol_ring": 1}),
        "2": DeckSupply(deck_id="2", deck_name="Deck B", cards={"sol_ring": 1}),
    }
    result = find_all_optimal_solutions(needs, supplies)
    assert result.minimum_decks_to_dismantle == 2
    assert frozenset({"1", "2"}) in result.solutions


def test_infeasible_when_supply_insufficient() -> None:
    needs = {"sol_ring": 3}
    supplies = {
        "1": DeckSupply(deck_id="1", deck_name="Deck A", cards={"sol_ring": 1}),
    }
    result = find_all_optimal_solutions(needs, supplies)
    assert result.solutions == ()
    assert result.unmet_needs == {"sol_ring": 3}


def test_multiple_optimal_solutions_returned() -> None:
    needs = {"sol_ring": 1}
    supplies = {
        "1": DeckSupply(deck_id="1", deck_name="Deck A", cards={"sol_ring": 1}),
        "2": DeckSupply(deck_id="2", deck_name="Deck B", cards={"sol_ring": 1}),
    }
    result = find_all_optimal_solutions(needs, supplies)
    assert result.minimum_decks_to_dismantle == 1
    assert len(result.solutions) == 2
