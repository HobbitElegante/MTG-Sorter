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


def test_preview_inventory_list_identifies_merges_and_skips_basics(
    session: Session,
) -> None:
    session.add_all(
        [
            Card(
                oracle_id="sol",
                name="Sol Ring",
                is_basic_land=False,
                is_token=False,
            ),
            Card(
                oracle_id="forest",
                name="Forest",
                is_basic_land=True,
                is_token=False,
            ),
            Card(
                oracle_id="token-angel",
                name="Angel",
                is_basic_land=False,
                is_token=True,
            ),
        ]
    )
    session.flush()
    scryfall = _StrictFakeScryfall(session)
    text = "\n".join(
        [
            "2 Sol Ring",
            "1 Sol Ring",
            "10 Forest",
            "Token: 1 Angel",
            "1 Completely Fake Card Name XYZ",
            "not a valid card line!!!",
            "// Creatures",
        ]
    )

    preview = ImportService(session, scryfall).preview_inventory_list(text)

    assert len(preview.identified) == 1
    assert preview.identified[0].name == "Sol Ring"
    assert preview.identified[0].list_quantity == 3
    assert "1 Completely Fake Card Name XYZ" in preview.unresolved_lines
    assert "not a valid card line!!!" in preview.unresolved_lines
    assert all("Forest" not in line for line in preview.unresolved_lines)
    assert all("Angel" not in line for line in preview.unresolved_lines)


def test_preview_inventory_list_empty_unresolved_when_all_resolve(
    session: Session,
) -> None:
    session.add(
        Card(
            oracle_id="sol",
            name="Sol Ring",
            is_basic_land=False,
            is_token=False,
        )
    )
    session.flush()

    preview = ImportService(session, _StrictFakeScryfall(session)).preview_inventory_list(
        "1 Sol Ring"
    )

    assert len(preview.identified) == 1
    assert preview.unresolved_lines == []


class _FakeScryfall:
    def __init__(self, session: Session) -> None:
        self._session = session

    def fetch_and_cache(self, name: str, *, prefer_token: bool = False) -> Card:
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

    def lookup_local(self, name: str, *, prefer_token: bool = False) -> Card | None:
        return self._session.scalar(select(Card).where(Card.name == name))

    def close(self) -> None:
        return None


class _StrictFakeScryfall(_FakeScryfall):
    def fetch_and_cache(self, name: str, *, prefer_token: bool = False) -> Card:
        card = self._session.scalar(select(Card).where(Card.name == name))
        if card is None:
            raise LookupError(f"Card '{name}' not found")
        return card
