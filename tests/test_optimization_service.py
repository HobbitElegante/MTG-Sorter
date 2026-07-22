from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import Base, Card, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.optimization_service import OptimizationService


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
