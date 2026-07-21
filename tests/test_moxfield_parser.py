from pathlib import Path

import pytest

from mtg_sorter.services.moxfield_parser import parse_moxfield_export


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_kellan_deck_export() -> None:
    text = (FIXTURES / "kellan_deck.txt").read_text(encoding="utf-8")
    parsed = parse_moxfield_export(text)

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
    parsed = parse_moxfield_export(text)
    assert parsed[0].role.value == "COMMANDER"
    assert parsed[0].name == "Atraxa, Praetors' Voice"
    assert parsed[1].name == "Sol Ring"


def test_skips_blank_and_comment_lines() -> None:
    text = "// Sideboard\n\n1 Sol Ring\n"
    parsed = parse_moxfield_export(text)
    assert len(parsed) == 1
    assert parsed[0].name == "Sol Ring"
