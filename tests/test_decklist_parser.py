from pathlib import Path

import pytest

from mtg_sorter.api.moxfield_client import deck_export_from_payload
from mtg_sorter.models.enums import DeckCardRole
from mtg_sorter.services.decklist_parser import (
    DecklistFormat,
    detect_format,
    extract_moxfield_deck_id,
    parse_decklist,
    parse_moxfield_line,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("line", "expected_name"),
    [
        ("1 Catalog (PLST) SOI-51", "Catalog"),
        ("1 Clear the Mind (PLST) RNA-34", "Clear the Mind"),
        ("1 Deep Freeze (PLST) DOM-50", "Deep Freeze"),
        ("1 Turn Aside (PLST) EMN-78", "Turn Aside"),
        ("1 Borrowing 100,000 Arrows (PLST) A25-45", "Borrowing 100,000 Arrows"),
        ("1 Amoeboid Changeling (PLST) LRW-51", "Amoeboid Changeling"),
        ("1 Urza's Power Plant (CHR) 115a", "Urza's Power Plant"),
        ("1 Consider (PW22) 1", "Consider"),
        ("1 Opt (J25) 339 *F*", "Opt"),
        ("1x Sol Ring (C21) [Ramp]", "Sol Ring"),
        ("1 Sol Ring", "Sol Ring"),
    ],
)
def test_parse_strips_set_and_collector_number(line: str, expected_name: str) -> None:
    parsed = parse_moxfield_line(line)
    assert parsed is not None
    assert parsed.name == expected_name
    assert parsed.quantity == 1


def test_parse_kellan_deck_export() -> None:
    text = (FIXTURES / "kellan_deck.txt").read_text(encoding="utf-8")
    parsed = parse_decklist(text)

    assert len(parsed) == 79
    assert parsed[0].name == "Adarkar Wastes"
    assert parsed[0].quantity == 1

    forests = [line for line in parsed if line.name == "Forest"]
    assert len(forests) == 1
    assert forests[0].quantity == 10

    assert parsed[-1].name == "Kellan, the Kid"
    assert parsed[-1].quantity == 1


def test_parse_role_prefix() -> None:
    text = "Commander: 1 Atraxa, Praetors' Voice\n1 Sol Ring"
    parsed = parse_decklist(text)
    assert parsed[0].role == DeckCardRole.COMMANDER
    assert parsed[0].name == "Atraxa, Praetors' Voice"
    assert parsed[1].name == "Sol Ring"


def test_skips_blank_and_comment_lines() -> None:
    text = "// Sideboard\n\n1 Sol Ring\n"
    parsed = parse_decklist(text)
    assert len(parsed) == 1
    assert parsed[0].name == "Sol Ring"


def test_detect_and_parse_arena_fixture() -> None:
    text = (FIXTURES / "arena_sample.txt").read_text(encoding="utf-8")
    assert detect_format(text) == DecklistFormat.ARENA
    parsed = parse_decklist(text)
    names = {line.name: line for line in parsed}
    assert names["Atraxa, Praetors' Voice"].role == DeckCardRole.COMMANDER
    assert "Sol Ring" in names
    assert "Negate" not in names  # sideboard skipped


def test_detect_and_parse_archidekt_fixture() -> None:
    text = (FIXTURES / "archidekt_sample.txt").read_text(encoding="utf-8")
    assert detect_format(text) == DecklistFormat.ARCHIDEKT
    parsed = parse_decklist(text)
    names = {line.name for line in parsed}
    assert names == {
        "Sol Ring",
        "Arcane Signet",
        "Birds of Paradise",
        "Eternal Witness",
        "Lightning Greaves",
    }


def test_detect_and_parse_mtgo_dek_fixture() -> None:
    text = (FIXTURES / "mtgo_sample.dek").read_text(encoding="utf-8")
    assert detect_format(text) == DecklistFormat.MTGO_DEK
    parsed = parse_decklist(text)
    names = {line.name: line.quantity for line in parsed}
    assert names == {"Sol Ring": 1, "Arcane Signet": 1}


def test_extract_moxfield_deck_id() -> None:
    assert (
        extract_moxfield_deck_id("https://www.moxfield.com/decks/AbC_123-xyz")
        == "AbC_123-xyz"
    )
    assert extract_moxfield_deck_id("1 Sol Ring") is None
    assert detect_format("https://moxfield.com/decks/abc") == DecklistFormat.MOXFIELD_URL
    assert parse_decklist("https://moxfield.com/decks/abc") == []


def test_deck_export_from_moxfield_payload() -> None:
    payload = {
        "publicId": "pub1",
        "name": "Test Deck",
        "commanders": {
            "Atraxa, Praetors' Voice": {
                "quantity": 1,
                "card": {"name": "Atraxa, Praetors' Voice"},
            }
        },
        "companions": {},
        "mainboard": {
            "Sol Ring": {"quantity": 1, "card": {"name": "Sol Ring"}},
            "Arcane Signet": {"quantity": 1, "card": {"name": "Arcane Signet"}},
        },
    }
    export = deck_export_from_payload(payload)
    assert export.name == "Test Deck"
    assert export.commander_name == "Atraxa, Praetors' Voice"
    assert "Commander: 1 Atraxa, Praetors' Voice" in export.list_text
    assert "1 Sol Ring" in export.list_text
    parsed = parse_decklist(export.list_text)
    assert any(line.role == DeckCardRole.COMMANDER for line in parsed)
