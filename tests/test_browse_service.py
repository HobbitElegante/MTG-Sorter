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
