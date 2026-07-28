from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import Base, Card, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.deck_service import DeckService
from mtg_sorter.services.house_ban_service import HouseBanService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def _seed_deck(session: Session) -> int:
    session.add(
        Card(
            oracle_id="sol",
            name="Sol Ring",
            type_line="Artifact",
            commander_legality="legal",
            is_basic_land=False,
            is_token=False,
        )
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED, sort_order=0)
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
    return deck.id


def test_house_ban_add_list_remove(session: Session) -> None:
    session.add(
        Card(
            oracle_id="dock",
            name="Dockside Extortionist",
            type_line="Creature",
            commander_legality="legal",
            is_basic_land=False,
            is_token=False,
        )
    )
    session.flush()
    service = HouseBanService(session)
    service.add("dock", "Dockside Extortionist")
    bans = service.list_bans()
    assert len(bans) == 1
    assert bans[0].oracle_id == "dock"
    assert service.oracle_ids() == {"dock"}
    assert service.remove("dock") is True
    assert service.list_bans() == []


def test_house_ban_issues_on_deck(session: Session) -> None:
    deck_id = _seed_deck(session)
    HouseBanService(session).add("sol", "Sol Ring")
    issues = HouseBanService(session).house_ban_issues(deck_id)
    assert len(issues) == 1
    assert issues[0].legality == "house_banned"
    assert issues[0].name == "Sol Ring"
    # Scryfall legality alone still clean.
    assert DeckService(session).commander_legality_issues(deck_id) == []
