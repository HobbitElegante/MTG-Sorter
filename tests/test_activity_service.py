from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import ActivityEvent, Base, Card, Deck, DeckCard
from mtg_sorter.models.enums import (
    ActivityCategory,
    ActivityEventType,
    DeckCardRole,
    DeckStatus,
)
from mtg_sorter.services.activity_service import ActivityService
from mtg_sorter.services.deck_service import DeckService, InventoryService
from mtg_sorter.services.optimization_service import OptimizationService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def _add_card(session: Session, oracle_id: str, name: str) -> Card:
    card = Card(
        oracle_id=oracle_id,
        name=name,
        is_basic_land=False,
        is_token=False,
    )
    session.add(card)
    session.flush()
    return card


def test_inventory_add_and_remove_record_activity(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    inventory = InventoryService(session)

    inventory.add_copy("sol", 2)
    removed = inventory.remove_free_copies("sol", 1)

    assert removed == 1
    events = ActivityService(session).list_events()
    assert [event.event_type for event in events] == [
        ActivityEventType.COPIES_REMOVED,
        ActivityEventType.COPIES_ADDED,
    ]
    assert events[1].payload["qty_delta"] == 2
    assert events[0].payload["qty_delta"] == 1


def test_inventory_can_skip_activity(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    InventoryService(session).add_copy("sol", 1, record_activity=False)
    assert session.scalar(select(ActivityEvent.id)) is None


def test_set_status_records_armed_and_dismantled(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    deck = Deck(name="Target", status=DeckStatus.DISMANTLED)
    session.add(deck)
    session.flush()
    session.add(
        DeckCard(
            deck_id=deck.id,
            card_id="sol",
            quantity=1,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()

    service = DeckService(session)
    service.set_status(deck, DeckStatus.ARMED)
    service.set_status(deck, DeckStatus.DISMANTLED)

    events = ActivityService(session).list_events(category=ActivityCategory.DECKS)
    assert [event.event_type for event in events] == [
        ActivityEventType.DECK_DISMANTLED,
        ActivityEventType.DECK_ARMED,
    ]


def test_apply_assembly_plan_records_single_plan_event(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    donor = Deck(name="Donor", status=DeckStatus.ARMED)
    session.add_all([target, donor])
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
    DeckService(session).set_status(donor, DeckStatus.ARMED)
    session.flush()

    # Clear arm event so we only assert on apply.
    for event in session.scalars(select(ActivityEvent)).all():
        session.delete(event)
    session.flush()

    OptimizationService(session).apply_assembly_plan(
        target.id, frozenset({str(donor.id)})
    )

    events = ActivityService(session).list_events()
    assert len(events) == 1
    assert events[0].event_type == ActivityEventType.PLAN_APPLIED
    assert events[0].payload["deck_name"] == "Target"
    assert events[0].payload["donor_names"] == ["Donor"]


def test_list_events_filters_inventory_vs_decks(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    InventoryService(session).add_copy("sol", 1)
    deck = Deck(name="Solo", status=DeckStatus.DISMANTLED)
    session.add(deck)
    session.flush()
    DeckService(session).delete_deck(deck.id)

    activity = ActivityService(session)
    inventory = activity.list_events(category=ActivityCategory.INVENTORY)
    decks = activity.list_events(category=ActivityCategory.DECKS)
    assert len(inventory) == 1
    assert inventory[0].event_type == ActivityEventType.COPIES_ADDED
    assert len(decks) == 1
    assert decks[0].event_type == ActivityEventType.DECK_DELETED
