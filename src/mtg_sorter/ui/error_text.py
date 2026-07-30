"""User-facing error text for UI dialogs."""

from __future__ import annotations

import httpx

from mtg_sorter.api.moxfield_client import MoxfieldError
from mtg_sorter.i18n.translator import Translator

_NETWORK_SENTINEL = "NETWORK"


def network_failure_token() -> str:
    """Worker → UI token for connectivity failures (translated in the GUI thread)."""
    return _NETWORK_SENTINEL


def is_network_failure_token(message: str) -> bool:
    return message == _NETWORK_SENTINEL


def format_deck_url_error(translator: Translator, exc: BaseException) -> str:
    """Friendly EN/ES text when a Moxfield/Archidekt URL fetch fails."""
    if isinstance(exc, MoxfieldError):
        if exc.code == "forbidden":
            return translator.t("import.moxfield.forbidden")
        if exc.code == "not_found":
            return translator.t("import.moxfield.not_found")
        if exc.code == "http":
            return translator.t("import.moxfield.http").format(
                status=exc.status if exc.status is not None else "?"
            )
        if exc.code == "bad_response":
            return translator.t("import.moxfield.bad_response")
    if isinstance(exc, httpx.HTTPError):
        return translator.t("import.url.network")
    return translator.t("decks.import.url_failed").format(error=str(exc))


def format_scryfall_job_error(
    translator: Translator,
    message: str,
    *,
    kind: str,
) -> str:
    """Wrap bulk / image / card-data worker failures for QMessageBox."""
    if is_network_failure_token(message):
        return translator.t("browse.scryfall.network_failed")
    key = f"browse.scryfall.{kind}_failed"
    return translator.t(key).format(detail=message)
