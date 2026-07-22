from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import Base, Card, CardAssignment, CardCopy, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.deck_service import DeckService
from mtg_sorter.services.import_service import ImportService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db_session:
        yield db_session


def test_list_trackable_cards_excludes_basic_lands(session: Session) -> None:
    land = Card(
        oracle_id="forest",
        name="Forest",
        is_basic_land=True,
        is_token=False,
    )
    ring = Card(
        oracle_id="sol",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([land, ring, deck])
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=deck.id,
                card_id="forest",
                quantity=10,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
        ]
    )
    session.flush()

    cards = ImportService(session, scryfall=_FakeScryfall(session)).list_trackable_cards(
        deck.id
    )

    assert len(cards) == 1
    assert cards[0].name == "Sol Ring"
    assert cards[0].quantity == 1


def test_apply_available_copies_adds_unassigned_inventory(session: Session) -> None:
    card = Card(
        oracle_id="sol",
        name="Sol Ring",
        is_basic_land=False,
        is_token=False,
    )
    deck = Deck(name="Test", status=DeckStatus.DISMANTLED)
    session.add_all([card, deck])
    session.flush()

    added = ImportService(session, scryfall=_FakeScryfall(session)).apply_available_copies(
        {"sol": 2}
    )

    assert added == 2
    assert session.scalar(select(func.count()).select_from(CardCopy)) == 2


def test_apply_available_copies_stacks_on_existing_free_inventory(
    session: Session,
) -> None:
    card = Card(
        oracle_id="banishing",
        name="Banishing Light",
        is_basic_land=False,
        is_token=False,
    )
    session.add(card)
    session.flush()
    importer = ImportService(session, scryfall=_FakeScryfall(session))
    importer.apply_available_copies({"banishing": 1})

    added = importer.apply_available_copies({"banishing": 1})

    assert added == 1
    assert session.scalar(select(func.count()).select_from(CardCopy)) == 2
    assert (
        session.scalar(
            select(func.count())
            .select_from(CardCopy)
            .where(
                CardCopy.card_id == "banishing",
                CardCopy.id.not_in(select(CardAssignment.card_copy_id)),
            )
        )
        == 2
    )


def test_armed_import_assigns_copies_before_status_is_set(session: Session) -> None:
    scryfall = _FakeScryfall(session)
    importer = ImportService(session, scryfall)
    result = importer.import_moxfield_text(
        deck_name="Test",
        text="1 Sol Ring",
        status=DeckStatus.ARMED,
    )

    DeckService(session).set_status(result.deck, DeckStatus.ARMED)

    assert result.deck.status == DeckStatus.ARMED
    assert session.scalar(select(func.count()).select_from(CardCopy)) == 1
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 1


def test_armed_import_creates_second_copy_when_first_is_assigned(
    session: Session,
) -> None:
    scryfall = _FakeScryfall(session)
    session.add(
        Card(
            oracle_id="sol",
            name="Sol Ring",
            is_basic_land=False,
            is_token=False,
        )
    )
    kellan = Deck(name="Kellan", status=DeckStatus.DISMANTLED)
    session.add(kellan)
    session.flush()
    session.add(
        DeckCard(
            deck_id=kellan.id,
            card_id="sol",
            quantity=1,
            role=DeckCardRole.MAIN,
        )
    )
    session.flush()
    DeckService(session).set_status(kellan, DeckStatus.ARMED)

    importer = ImportService(session, scryfall)
    result = importer.import_moxfield_text(
        deck_name="Athreos",
        text="1 Sol Ring",
        status=DeckStatus.ARMED,
    )
    DeckService(session).set_status(result.deck, DeckStatus.ARMED)

    assert (
        session.scalar(
            select(func.count())
            .select_from(CardCopy)
            .where(CardCopy.card_id == "sol")
        )
        == 2
    )
    assert session.scalar(select(func.count()).select_from(CardAssignment)) == 2


class _FakeScryfall:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_and_cache(self, name: str) -> Card:
        card = self._session.scalar(select(Card).where(Card.name == name))
        if card is None:
            card = Card(
                oracle_id="sol",
                name="Sol Ring",
                is_basic_land=False,
                is_token=False,
            )
            self._session.add(card)
            self._session.flush()
        return card

    def close(self) -> None:
        return None
