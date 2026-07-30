from mtg_sorter.api.moxfield_client import MoxfieldError
from mtg_sorter.i18n.translator import Translator
from mtg_sorter.ui.error_text import (
    format_deck_url_error,
    format_scryfall_job_error,
    network_failure_token,
)


def test_format_deck_url_error_moxfield_forbidden_en() -> None:
    text = format_deck_url_error(Translator("en"), MoxfieldError("forbidden", status=403))
    assert "403" in text
    assert "Copy for MTGO" in text
    assert "httpx" not in text.casefold()


def test_format_deck_url_error_moxfield_forbidden_es() -> None:
    text = format_deck_url_error(Translator("es"), MoxfieldError("forbidden", status=403))
    assert "403" in text
    assert "Copy for MTGO" in text
    assert "bloqueó" in text.casefold() or "bloqueo" in text.casefold()


def test_format_scryfall_job_error_network() -> None:
    text = format_scryfall_job_error(
        Translator("en"), network_failure_token(), kind="sync"
    )
    assert "Scryfall" in text
    assert "internet" in text.casefold() or "connection" in text.casefold()


def test_format_scryfall_job_error_wraps_detail() -> None:
    text = format_scryfall_job_error(Translator("en"), "boom detail", kind="sync")
    assert "Could not sync" in text
    assert "boom detail" in text
