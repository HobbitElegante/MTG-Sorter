from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import pytest

from mtg_sorter.models import Base, Card, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.deck_export import (
    ExportFormat,
    format_deck_export,
    load_deck_export_cards,
)
from mtg_sorter.services.decklist_parser import parse_decklist
from mtg_sorter.services.import_service import ImportService
from mtg_sorter.services.scryfall_service import ScryfallService


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session


def _seed_deck(session: Session) -> int:
    commander = Card(
        oracle_id="cmd",
        name="Atraxa, Praetors' Voice",
        is_basic_land=False,
        is_token=False,
    )
    sol = Card(oracle_id="sol", name="Sol Ring", is_basic_land=False, is_token=False)
    token = Card(
        oracle_id="token",
        name="Saproling",
        is_basic_land=False,
        is_token=True,
    )
    deck = Deck(name="Export Me", status=DeckStatus.DISMANTLED)
    session.add_all([commander, sol, token, deck])
    session.flush()
    session.add_all(
        [
            DeckCard(
                deck_id=deck.id,
                card_id="cmd",
                quantity=1,
                role=DeckCardRole.COMMANDER,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="sol",
                quantity=1,
                role=DeckCardRole.MAIN,
            ),
            DeckCard(
                deck_id=deck.id,
                card_id="token",
                quantity=3,
                role=DeckCardRole.TOKEN,
            ),
        ]
    )
    session.flush()
    return deck.id


def test_format_mtgo_and_moxfield_match(session: Session) -> None:
    deck_id = _seed_deck(session)
    cards = load_deck_export_cards(session, deck_id)
    mtgo = format_deck_export(cards, ExportFormat.MTGO)
    moxfield = format_deck_export(cards, ExportFormat.MOXFIELD)
    assert mtgo == moxfield
    assert mtgo == (
        "Commander: 1 Atraxa, Praetors' Voice\n"
        "1 Sol Ring\n"
        "Token: 3 Saproling"
    )


def test_format_arena_sections(session: Session) -> None:
    deck_id = _seed_deck(session)
    cards = load_deck_export_cards(session, deck_id)
    text = format_deck_export(cards, ExportFormat.ARENA)
    assert text == (
        "Commander\n"
        "1 Atraxa, Praetors' Voice\n"
        "\n"
        "Deck\n"
        "1 Sol Ring\n"
        "3 Saproling"
    )
    parsed = parse_decklist(text)
    assert {(line.name, line.quantity, line.role) for line in parsed} >= {
        ("Atraxa, Praetors' Voice", 1, DeckCardRole.COMMANDER),
        ("Sol Ring", 1, DeckCardRole.MAIN),
    }


def test_format_archidekt_categories(session: Session) -> None:
    deck_id = _seed_deck(session)
    cards = load_deck_export_cards(session, deck_id)
    text = format_deck_export(cards, ExportFormat.ARCHIDEKT)
    assert text == (
        "1x Atraxa, Praetors' Voice [Commander]\n"
        "1x Sol Ring\n"
        "3x Saproling [Token]"
    )
    parsed = parse_decklist(text)
    names = {line.name for line in parsed}
    assert names == {"Atraxa, Praetors' Voice", "Sol Ring", "Saproling"}
    assert sum(line.quantity for line in parsed if line.name == "Saproling") == 3


def test_format_mtggoldfish_blocks(session: Session) -> None:
    deck_id = _seed_deck(session)
    cards = load_deck_export_cards(session, deck_id)
    text = format_deck_export(cards, ExportFormat.MTGGOLDFISH)
    assert text == (
        "1 Atraxa, Praetors' Voice\n"
        "\n"
        "1 Sol Ring\n"
        "\n"
        "3 Saproling"
    )


def test_import_service_deck_to_text_delegates(session: Session) -> None:
    deck_id = _seed_deck(session)
    scryfall = ScryfallService(session)
    try:
        text = ImportService(session, scryfall).deck_to_text(
            deck_id, ExportFormat.ARENA
        )
    finally:
        scryfall.close()
    assert text.startswith("Commander\n")
