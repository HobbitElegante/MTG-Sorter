from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import Base, Card, CardAssignment, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.deck_service import DeckService, InventoryService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def test_armed_deck_creates_assignments_from_list(session: Session) -> None:
    card = Card(
        oracle_id="sol",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([card, deck])
    session.flush()
    session.add(
        DeckCard(
            deck_id=deck.id,
            card_id="sol",
            quantity=2,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()

    DeckService(session).set_status(deck, DeckStatus.ARMED)

    assert deck.status == DeckStatus.ARMED
    assert (
        session.scalar(select(func.count()).select_from(CardAssignment)) == 2
    )
    assert session.scalar(select(func.count()).select_from(CardCopy)) == 2


def test_armed_deck_uses_free_inventory_before_creating_copies(
    session: Session,
) -> None:
    card = Card(
        oracle_id="sol",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([card, deck])
    session.flush()
    InventoryService(session).add_copy("sol", quantity=1)
    session.add(
        DeckCard(
            deck_id=deck.id,
            card_id="sol",
            quantity=1,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()

    DeckService(session).set_status(deck, DeckStatus.ARMED)

    assert session.scalar(select(func.count()).select_from(CardCopy)) == 1
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 1


def test_dismantled_deck_releases_assignments(session: Session) -> None:
    card = Card(
        oracle_id="sol",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([card, deck])
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

    assert deck.status == DeckStatus.DISMANTLED
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 0
    assert session.scalar(select(func.count()).select_from(CardCopy)) == 1
    assert InventoryService(session).free_counts() == {"sol": 1}


def test_armed_deck_skips_basic_lands(session: Session) -> None:
    land = Card(
        oracle_id="forest",
        name="Forest",
        is_basic_land=True,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([land, deck])
    session.flush()
    session.add(
        DeckCard(
            deck_id=deck.id,
            card_id="forest",
            quantity=10,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()

    DeckService(session).set_status(deck, DeckStatus.ARMED)

    assert session.scalar(select(func.count()).select_from(CardCopy)) == 0
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 0


def test_delete_deck_removes_list_and_frees_assigned_copies(session: Session) -> None:
    card = Card(
        oracle_id="sol",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([card, deck])
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
    deck_id = deck.id

    assert service.delete_deck(deck_id) is True

    assert session.get(Deck, deck_id) is None
    assert session.scalar(select(func.count()).select_from(DeckCard)) == 0
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 0
    assert session.scalar(select(func.count()).select_from(CardCopy)) == 1
    assert InventoryService(session).free_counts() == {"sol": 1}


def test_delete_deck_can_remove_selected_copies(session: Session) -> None:
    card = Card(
        oracle_id="sol",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    other = Deck(name="Other", status=DeckStatus.ARMED)
    session.add_all([card, deck, other])
    session.flush()
    session.add(
        DeckCard(
            deck_id=deck.id,
            card_id="sol",
            quantity=1,
            role=DeckCardRole.MAIN,
        )
    )
    free_copy = CardCopy(card_id="sol")
    other_copy = CardCopy(card_id="sol")
    session.add_all([free_copy, other_copy])
    session.flush()
    session.add(CardAssignment(card_copy_id=other_copy.id, deck_id=other.id))
    session.flush()

    service = DeckService(session)
    impact = {item.oracle_id: item for item in service.deck_delete_impact(deck.id)}
    assert impact["sol"].total_copies == 2
    assert impact["sol"].removable_copies == 1

    assert service.delete_deck(deck.id, {"sol": 1}) is True

    assert session.scalar(select(func.count()).select_from(CardCopy)) == 1
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 1
    assert InventoryService(session).free_counts() == {}


def test_apply_deck_edit_replace_keeps_outgoing_copies_and_creates_free(
    session: Session,
) -> None:
    from mtg_sorter.services.deck_service import DeckEditLine

    old = Card(oracle_id="old", name="Old Card", is_basic_land=False, is_token=False)
    new = Card(oracle_id="new", name="New Card", is_basic_land=False, is_token=False)
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([old, new, deck])
    session.flush()
    session.add(
        DeckCard(deck_id=deck.id, card_id="old", quantity=1, role=DeckCardRole.MAIN)
    )
    session.add(CardCopy(card_id="old"))
    session.flush()

    DeckService(session).apply_deck_edit(
        deck.id,
        [DeckEditLine(oracle_id="new", quantity=1, role=DeckCardRole.MAIN)],
        create_free_copies={"new": 1},
    )

    assert session.scalar(select(func.count()).select_from(DeckCard)) == 1
    assert session.scalar(select(DeckCard.card_id)) == "new"
    free = InventoryService(session).free_counts()
    assert free.get("old") == 1
    assert free.get("new") == 1


def test_apply_deck_edit_replace_can_remove_outgoing_copies(session: Session) -> None:
    from mtg_sorter.services.deck_service import DeckEditLine

    old = Card(oracle_id="old", name="Old Card", is_basic_land=False, is_token=False)
    new = Card(oracle_id="new", name="New Card", is_basic_land=False, is_token=False)
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([old, new, deck])
    session.flush()
    session.add(
        DeckCard(deck_id=deck.id, card_id="old", quantity=1, role=DeckCardRole.MAIN)
    )
    session.add(CardCopy(card_id="old"))
    session.flush()

    DeckService(session).apply_deck_edit(
        deck.id,
        [DeckEditLine(oracle_id="new", quantity=1, role=DeckCardRole.MAIN)],
        remove_copies={"old": 1},
    )

    assert InventoryService(session).free_counts() == {}
    assert session.scalar(select(func.count()).select_from(CardCopy)) == 0


def test_apply_deck_edit_armed_roundtrip(session: Session) -> None:
    from mtg_sorter.services.deck_service import DeckEditLine

    sol = Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    signet = Card(
        oracle_id="signet", name="Arcane Signet", is_basic_land=False, is_token=False
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([sol, signet, deck])
    session.flush()
    session.add(
        DeckCard(deck_id=deck.id, card_id="sol", quantity=1, role=DeckCardRole.MAIN)
    )
    session.flush()

    service = DeckService(session)
    service.set_status(deck, DeckStatus.ARMED)
    service.apply_deck_edit(
        deck.id,
        [DeckEditLine(oracle_id="signet", quantity=1, role=DeckCardRole.MAIN)],
        create_free_copies={"signet": 1},
    )

    assert deck.status == DeckStatus.ARMED
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 1
    assigned = session.scalar(
        select(CardCopy.card_id)
        .join(CardAssignment, CardAssignment.card_copy_id == CardCopy.id)
        .where(CardAssignment.deck_id == deck.id)
    )
    assert assigned == "signet"
    assert InventoryService(session).free_counts().get("sol") == 1


def test_free_coverage_toward_deck_counts_matching_free_copies(
    session: Session,
) -> None:
    sol = Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    cultivate = Card(
        oracle_id="cultivate",
        name="Cultivate",
        is_basic_land=False,
        is_token=False,
    )
    forest = Card(
        oracle_id="forest",
        name="Forest",
        is_basic_land=True,
        is_token=False,
    )
    deck = Deck(name="Target", status=DeckStatus.DISMANTLED)
    session.add_all([sol, cultivate, forest, deck])
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=deck.id, card_id="sol", quantity=1, role=DeckCardRole.MAIN
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="cultivate",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id, card_id="forest", quantity=10, role=DeckCardRole.MAIN
            ),
            CardCopy(card_id="sol"),
            CardCopy(card_id="sol"),
        ]
    )
    session.flush()

    assert DeckService(session).free_coverage_toward_deck(deck.id) == 1
