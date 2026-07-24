from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import Base, Card, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.optimization_service import (
    OptimizationService,
    allocate_solution_cards,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def test_plan_assembly_exposes_readable_card_and_deck_names(session: Session) -> None:
    sol = Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    cultivate = Card(
        oracle_id="cultivate",
        name="Cultivate",
        is_basic_land=False,
        is_token=False,
    )
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    donor = Deck(name="Donor Deck", status=DeckStatus.ARMED)
    session.add_all([sol, cultivate, target, donor])
    session.flush()

    session.add_all(
        [
            DeckCard(
                deck_id=target.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=target.id,
                card_id="cultivate",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=donor.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            CardCopy(card_id="cultivate"),
        ]
    )
    session.flush()

    plan = OptimizationService(session).plan_assembly(target.id)

    assert plan.free_inventory_used == {"cultivate": 1}
    assert plan.card_names["cultivate"] == "Cultivate"
    assert plan.deck_names[str(donor.id)] == "Donor Deck"
    assert plan.result.minimum_decks_to_dismantle == 1
    assert any("Donor Deck" in label for label in plan.solution_labels.values())


def test_plan_assembly_skips_already_armed_target(session: Session) -> None:
    sol = Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    target = Deck(name="Already Armed", status=DeckStatus.ARMED)
    donor = Deck(name="Donor Deck", status=DeckStatus.ARMED)
    session.add_all([sol, target, donor])
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=target.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=donor.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
        ]
    )
    session.flush()

    plan = OptimizationService(session).plan_assembly(target.id)

    assert plan.already_armed is True
    assert plan.free_inventory_used == {}
    assert plan.still_missing == {}
    assert plan.result.minimum_decks_to_dismantle == 0
    assert plan.result.solutions == (frozenset(),)
    assert plan.solution_labels == {}


def test_plan_assembly_names_still_missing_cards(session: Session) -> None:
    sol = Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    session.add_all([sol, target])
    session.flush()
    session.add(
        DeckCard(
            deck_id=target.id,
            card_id="sol",
            quantity=1,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()

    plan = OptimizationService(session).plan_assembly(target.id)

    assert plan.still_missing == {"sol": 1}
    assert plan.card_names["sol"] == "Sol Ring"
    assert plan.result.solutions == ()


def test_allocate_solution_cards_splits_needs_across_decks() -> None:
    residual = {"a": 2, "b": 1}
    supplies = {
        "1": {"a": 1, "b": 1},
        "2": {"a": 2},
    }
    names = {"1": "Alpha", "2": "Beta"}
    solution = frozenset({"1", "2"})

    taken = allocate_solution_cards(residual, supplies, names, solution)

    assert taken == {"1": {"a": 1, "b": 1}, "2": {"a": 1}}
    attributed = {}
    for cards in taken.values():
        for card_id, qty in cards.items():
            attributed[card_id] = attributed.get(card_id, 0) + qty
    assert attributed == residual


def test_plan_assembly_cards_taken_match_residual_needs(session: Session) -> None:
    ring = Card(oracle_id="ring", name="Sol Ring", is_basic_land=False, is_token=False)
    ramp = Card(oracle_id="ramp", name="Rampant Growth", is_basic_land=False, is_token=False)
    draw = Card(oracle_id="draw", name="Opt", is_basic_land=False, is_token=False)
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    athreos = Deck(name="Athreos Donor", status=DeckStatus.ARMED)
    ghen = Deck(name="Ghen Donor", status=DeckStatus.ARMED)
    session.add_all([ring, ramp, draw, target, athreos, ghen])
    session.flush()

    session.add_all(
        [
            DeckCard(deck_id=target.id, card_id="ring", quantity=1, role=DeckCardRole.MAIN),
            DeckCard(deck_id=target.id, card_id="ramp", quantity=1, role=DeckCardRole.MAIN),
            DeckCard(deck_id=target.id, card_id="draw", quantity=1, role=DeckCardRole.MAIN),
            DeckCard(deck_id=athreos.id, card_id="ring", quantity=1, role=DeckCardRole.MAIN),
            DeckCard(deck_id=ghen.id, card_id="ramp", quantity=1, role=DeckCardRole.MAIN),
            CardCopy(card_id="draw"),
        ]
    )
    session.flush()

    plan = OptimizationService(session).plan_assembly(target.id)

    assert plan.free_inventory_used == {"draw": 1}
    assert plan.residual_needs == {"ring": 1, "ramp": 1}
    assert plan.still_missing == {}
    assert plan.result.minimum_decks_to_dismantle == 2
    assert len(plan.result.solutions) == 1

    solution = plan.result.solutions[0]
    taken = plan.cards_taken_from_solution(solution)
    attributed: dict[str, int] = {}
    for cards in taken.values():
        for card_id, qty in cards.items():
            attributed[card_id] = attributed.get(card_id, 0) + qty
    assert attributed == plan.residual_needs


def test_apply_assembly_plan_dismantles_then_arms(session: Session) -> None:
    from mtg_sorter.models import CardAssignment

    ring = Card(oracle_id="ring", name="Sol Ring", is_basic_land=False, is_token=False)
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    donor = Deck(name="Donor", status=DeckStatus.ARMED)
    session.add_all([ring, target, donor])
    session.flush()
    session.add_all(
        [
            DeckCard(deck_id=target.id, card_id="ring", quantity=1, role=DeckCardRole.MAIN),
            DeckCard(deck_id=donor.id, card_id="ring", quantity=1, role=DeckCardRole.MAIN),
        ]
    )
    session.flush()
    copy = CardCopy(card_id="ring")
    session.add(copy)
    session.flush()
    session.add(CardAssignment(card_copy_id=copy.id, deck_id=donor.id))
    session.flush()

    service = OptimizationService(session)
    plan = service.plan_assembly(target.id)
    assert plan.result.solutions
    solution = plan.result.solutions[0]
    service.apply_assembly_plan(target.id, solution)
    session.refresh(target)
    session.refresh(donor)

    assert donor.status == DeckStatus.DISMANTLED
    assert target.status == DeckStatus.ARMED
    from sqlalchemy import func, select

    target_assigned = session.scalar(
        select(func.count())
        .select_from(CardAssignment)
        .where(CardAssignment.deck_id == target.id)
    )
    donor_assigned = session.scalar(
        select(func.count())
        .select_from(CardAssignment)
        .where(CardAssignment.deck_id == donor.id)
    )
    assert target_assigned == 1
    assert donor_assigned == 0
