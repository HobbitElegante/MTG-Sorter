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


def test_list_events_paginates_with_before_id(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    inventory = InventoryService(session)
    for _ in range(5):
        inventory.add_copy("sol", 1)

    activity = ActivityService(session)
    page1 = activity.list_events(limit=2)
    assert len(page1) == 2
    page2 = activity.list_events(limit=2, before_id=page1[-1].id)
    assert len(page2) == 2
    assert page2[0].id < page1[-1].id
    assert {row.id for row in page1}.isdisjoint({row.id for row in page2})


def test_events_csv_includes_header_and_rows(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    InventoryService(session).add_copy("sol", 1)
    csv_text = ActivityService(session).events_csv()
    lines = csv_text.strip().splitlines()
    assert lines[0] == "id,created_at,event_type,summary,payload_json"
    assert "COPIES_ADDED" in lines[1]


def test_undo_copies_added_and_removed(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    inventory = InventoryService(session)
    inventory.add_copy("sol", 2)
    activity = ActivityService(session)

    assert activity.can_undo_last()
    activity.undo_last()
    assert inventory.free_counts().get("sol", 0) == 0
    assert activity.latest_event().event_type == ActivityEventType.ACTIVITY_UNDONE
    assert not activity.can_undo_last()

    inventory.remove_free_copies("sol", 0)  # no-op
    inventory.add_copy("sol", 1)
    inventory.remove_free_copies("sol", 1)
    assert activity.can_undo_last()
    activity.undo_last()
    assert inventory.free_counts().get("sol", 0) == 1


def test_undo_copies_added_fails_without_free_copies(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    inventory = InventoryService(session)
    inventory.add_copy("sol", 1)
    # Consume the free copy without recording (simulate assigned elsewhere use).
    inventory.remove_free_copies("sol", 1, record_activity=False)

    activity = ActivityService(session)
    assert activity.can_undo_last()
    with pytest.raises(ValueError, match="Not enough free copies"):
        activity.undo_last()


def test_undo_arm_and_dismantle(session: Session) -> None:
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
    activity = ActivityService(session)
    service.set_status(deck, DeckStatus.ARMED)
    activity.undo_last()
    session.refresh(deck)
    assert deck.status == DeckStatus.DISMANTLED

    service.set_status(deck, DeckStatus.DISMANTLED)  # already dismantled, no event?
    # Record a dismantle after arming again.
    service.set_status(deck, DeckStatus.ARMED)
    service.set_status(deck, DeckStatus.DISMANTLED)
    activity.undo_last()
    session.refresh(deck)
    assert deck.status == DeckStatus.ARMED


def test_undo_plan_applied_restores_donors(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    target = Deck(name="Target", status=DeckStatus.DISMANTLED)
    donor_a = Deck(name="Donor A", status=DeckStatus.DISMANTLED)
    donor_b = Deck(name="Donor B", status=DeckStatus.DISMANTLED)
    session.add_all([target, donor_a, donor_b])
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
                deck_id=donor_a.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=donor_b.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
        ]
    )
    session.flush()
    decks = DeckService(session)
    decks.set_status(donor_a, DeckStatus.ARMED)
    decks.set_status(donor_b, DeckStatus.ARMED)
    for event in session.scalars(select(ActivityEvent)).all():
        session.delete(event)
    session.flush()

    OptimizationService(session).apply_assembly_plan(
        target.id, frozenset({str(donor_a.id), str(donor_b.id)})
    )
    activity = ActivityService(session)
    activity.undo_last()

    session.refresh(target)
    session.refresh(donor_a)
    session.refresh(donor_b)
    assert target.status == DeckStatus.DISMANTLED
    assert donor_a.status == DeckStatus.ARMED
    assert donor_b.status == DeckStatus.ARMED
    assert activity.latest_event().event_type == ActivityEventType.ACTIVITY_UNDONE


def test_cannot_undo_import_or_delete(session: Session) -> None:
    _add_card(session, "sol", "Sol Ring")
    deck = Deck(name="Gone", status=DeckStatus.DISMANTLED)
    session.add(deck)
    session.flush()
    DeckService(session).delete_deck(deck.id)

    activity = ActivityService(session)
    assert activity.latest_event().event_type == ActivityEventType.DECK_DELETED
    assert not activity.can_undo_last()
    with pytest.raises(ValueError, match="Nothing to undo"):
        activity.undo_last()
