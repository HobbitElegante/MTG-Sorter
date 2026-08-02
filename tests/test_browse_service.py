from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import Base, Card, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.browse_service import BrowseService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def test_overview_counts(session: Session) -> None:
    card = Card(
        oracle_id="abc",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test Deck", status=DeckStatus.ARMED)
    session.add_all([card, deck, CardCopy(card_id="abc"), CardCopy(card_id="abc")])
    session.flush()
    session.add(
        DeckCard(
            deck_id=deck.id,
            card_id="abc",
            quantity=1,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()

    stats = BrowseService(session).overview()

    assert stats.cards == 1
    assert stats.copies == 2
    assert stats.unassigned_copies == 2
    assert stats.decks == 1
    assert stats.armed_decks == 1


def test_list_cards_excludes_art_series(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="1",
                name="Kellan, the Kid",
                type_line="Legendary Creature — Human Faerie Rogue",
                is_basic_land=False,
                is_token=False,
            ),
            Card(
                oracle_id="2",
                name="Kellan, the Kid // Kellan, the Kid",
                type_line="Card // Card",
                is_basic_land=False,
                is_token=False,
            ),
        ]
    )
    session.flush()

    cards = BrowseService(session).list_cards("kellan")

    assert len(cards) == 1
    assert cards[0].name == "Kellan, the Kid"


def test_list_inventory_groups_copies_by_card(session: Session) -> None:
    from mtg_sorter.models import CardAssignment

    card = Card(
        oracle_id="abc",
        name="Sol Ring",
        color_identity="",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test Deck", status=DeckStatus.ARMED)
    session.add_all([card, deck])
    session.flush()
    copies = [CardCopy(card_id="abc"), CardCopy(card_id="abc"), CardCopy(card_id="abc")]
    session.add_all(copies)
    session.flush()
    session.add(CardAssignment(card_copy_id=copies[0].id, deck_id=deck.id))
    session.flush()

    rows = BrowseService(session).list_inventory()

    assert len(rows) == 1
    assert rows[0].oracle_id == "abc"
    assert rows[0].card_name == "Sol Ring"
    assert rows[0].total_copies == 3
    assert rows[0].free_copies == 2
    assert rows[0].assigned_decks == ("Test Deck",)
    assert rows[0].assigned_deck_ids == frozenset({deck.id})
    assert rows[0].color_identity == ""


def test_list_inventory_includes_color_identity(session: Session) -> None:
    session.add(
        Card(
            oracle_id="xyz",
            name="Lightning Bolt",
            color_identity="R",
            is_basic_land=False,
            is_token=False,
        )
    )
    session.flush()
    session.add(CardCopy(card_id="xyz"))
    session.flush()

    rows = BrowseService(session).list_inventory()

    assert len(rows) == 1
    assert rows[0].color_identity == "R"


def test_list_cards_filters_by_name(session: Session) -> None:
    session.add_all(
        [
            Card(
                oracle_id="1",
                name="Sol Ring",
                is_basic_land=False,
                is_token=False,
            ),
            Card(
                oracle_id="2",
                name="Arcane Signet",
                is_basic_land=False,
                is_token=False,
            ),
        ]
    )
    session.flush()

    cards = BrowseService(session).list_cards("arcane")

    assert len(cards) == 1
    assert cards[0].name == "Arcane Signet"
