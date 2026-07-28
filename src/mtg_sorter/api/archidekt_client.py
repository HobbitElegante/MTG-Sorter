"""Public Archidekt deck API client (unofficial archidekt.com/api)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from mtg_sorter.config import ARCHIDEKT_API_BASE

_SKIP_CATEGORIES = frozenset({"maybeboard", "token", "tokens", "consider", "wishlist"})
_SIDEBOARD_CATEGORIES = frozenset({"sideboard"})
_COMMANDER_CATEGORIES = frozenset({"commander"})
_PARTNER_CATEGORIES = frozenset({"partner"})
_COMPANION_CATEGORIES = frozenset({"companion"})
_BACKGROUND_CATEGORIES = frozenset({"background"})


@dataclass(frozen=True)
class ArchidektDeckExport:
    """Deck metadata + MTGO-style text ready for ImportService."""

    deck_id: int
    name: str
    list_text: str
    commander_name: str | None = None
    secondary_role: str | None = None  # partner | companion | background
    secondary_name: str | None = None


class ArchidektClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=ARCHIDEKT_API_BASE,
            headers={
                "User-Agent": "MTG-Sorter/0.8",
                "Accept": "application/json",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch_deck(self, deck_id: int | str) -> dict[str, Any]:
        response = self._client.get(f"/api/decks/{deck_id}/")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected Archidekt response shape")
        if "error" in payload and "cards" not in payload:
            raise ValueError(str(payload.get("error") or "Archidekt deck not found"))
        return payload


def deck_export_from_payload(payload: dict[str, Any]) -> ArchidektDeckExport:
    deck_id_raw = payload.get("id")
    try:
        deck_id = int(deck_id_raw)
    except (TypeError, ValueError):
        deck_id = 0
    name = str(payload.get("name") or "Archidekt deck").strip() or "Archidekt deck"

    included_by_category = _included_map(payload.get("categories"))
    commanders: list[tuple[str, int, str | None]] = []
    partners: list[tuple[str, int, str | None]] = []
    companions: list[tuple[str, int, str | None]] = []
    backgrounds: list[tuple[str, int, str | None]] = []
    mainboard: list[tuple[str, int, str | None]] = []

    cards = payload.get("cards")
    if not isinstance(cards, list):
        cards = []

    for entry in cards:
        if not isinstance(entry, dict):
            continue
        parsed = _parse_card_entry(entry, included_by_category)
        if parsed is None:
            continue
        card_name, quantity, set_code, bucket = parsed
        item = (card_name, quantity, set_code)
        if bucket == "commander":
            commanders.append(item)
        elif bucket == "partner":
            partners.append(item)
        elif bucket == "companion":
            companions.append(item)
        elif bucket == "background":
            backgrounds.append(item)
        else:
            mainboard.append(item)

    # Archidekt often tags Partner decks with two "Commander" categories.
    if len(commanders) > 1 and not partners:
        partners = commanders[1:]
        commanders = commanders[:1]

    lines: list[str] = []
    commander_name: str | None = None
    secondary_role: str | None = None
    secondary_name: str | None = None

    for index, (card_name, quantity, set_code) in enumerate(commanders):
        if index == 0:
            commander_name = card_name
            lines.append(_format_line("Commander", quantity, card_name, set_code))
        else:
            if secondary_role is None:
                secondary_role = "partner"
                secondary_name = card_name
            lines.append(_format_line("Partner", quantity, card_name, set_code))

    for card_name, quantity, set_code in partners:
        if secondary_role is None:
            secondary_role = "partner"
            secondary_name = card_name
        lines.append(_format_line("Partner", quantity, card_name, set_code))

    for card_name, quantity, set_code in companions:
        if secondary_role is None:
            secondary_role = "companion"
            secondary_name = card_name
        lines.append(_format_line("Companion", quantity, card_name, set_code))

    for card_name, quantity, set_code in backgrounds:
        if secondary_role is None:
            secondary_role = "background"
            secondary_name = card_name
        lines.append(_format_line("Background", quantity, card_name, set_code))

    mainboard.sort(key=lambda item: item[0].casefold())
    for card_name, quantity, set_code in mainboard:
        lines.append(_format_line(None, quantity, card_name, set_code))

    return ArchidektDeckExport(
        deck_id=deck_id,
        name=name,
        list_text="\n".join(lines),
        commander_name=commander_name,
        secondary_role=secondary_role,
        secondary_name=secondary_name,
    )


def fetch_archidekt_deck(deck_id: int | str) -> ArchidektDeckExport:
    client = ArchidektClient()
    try:
        payload = client.fetch_deck(deck_id)
    finally:
        client.close()
    return deck_export_from_payload(payload)


def _included_map(categories: Any) -> dict[str, bool]:
    result: dict[str, bool] = {}
    if not isinstance(categories, list):
        return result
    for cat in categories:
        if not isinstance(cat, dict) or not cat.get("name"):
            continue
        name = str(cat["name"]).casefold()
        result[name] = bool(cat.get("includedInDeck", True))
    return result


def _parse_card_entry(
    entry: dict[str, Any],
    included_by_category: dict[str, bool],
) -> tuple[str, int, str | None, str] | None:
    categories = [
        str(name).casefold()
        for name in (entry.get("categories") or [])
        if name
    ]
    is_companion_flag = bool(entry.get("companion"))

    if any(cat in _SKIP_CATEGORIES for cat in categories):
        return None
    if any(included_by_category.get(cat, True) is False for cat in categories):
        # Companion often sits in Sideboard; keep it via the flag / category.
        if not (
            is_companion_flag
            or any(cat in _COMPANION_CATEGORIES for cat in categories)
            or any(cat in _BACKGROUND_CATEGORIES for cat in categories)
        ):
            return None
    if any(cat in _SIDEBOARD_CATEGORIES for cat in categories):
        if not (
            is_companion_flag
            or any(cat in _COMPANION_CATEGORIES for cat in categories)
            or any(cat in _BACKGROUND_CATEGORIES for cat in categories)
        ):
            return None

    card = entry.get("card")
    if not isinstance(card, dict):
        return None
    oracle = card.get("oracleCard")
    if isinstance(oracle, dict) and oracle.get("name"):
        card_name = str(oracle["name"]).strip()
    elif card.get("displayName"):
        card_name = str(card["displayName"]).strip()
    else:
        return None
    if not card_name:
        return None

    try:
        quantity = int(entry.get("quantity") or 1)
    except (TypeError, ValueError):
        quantity = 1
    if quantity <= 0:
        return None

    set_code: str | None = None
    edition = card.get("edition")
    if isinstance(edition, dict) and edition.get("editioncode"):
        set_code = str(edition["editioncode"]).upper()

    if is_companion_flag or any(cat in _COMPANION_CATEGORIES for cat in categories):
        bucket = "companion"
    elif any(cat in _BACKGROUND_CATEGORIES for cat in categories):
        bucket = "background"
    elif any(cat in _PARTNER_CATEGORIES for cat in categories):
        bucket = "partner"
    elif any(cat in _COMMANDER_CATEGORIES for cat in categories):
        bucket = "commander"
    else:
        bucket = "main"

    return card_name, quantity, set_code, bucket


def _format_line(
    role: str | None,
    quantity: int,
    name: str,
    set_code: str | None,
) -> str:
    body = f"{quantity} {name}"
    if set_code:
        body = f"{body} ({set_code})"
    if role:
        return f"{role}: {body}"
    return body
