"""Public Moxfield deck API client (unofficial api2.moxfield.com)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from mtg_sorter.config import MOXFIELD_API_BASE


@dataclass(frozen=True)
class MoxfieldDeckExport:
    """Deck metadata + MTGO-style text ready for ImportService."""

    public_id: str
    name: str
    list_text: str
    commander_name: str | None = None
    secondary_role: str | None = None  # partner | companion | background
    secondary_name: str | None = None


class MoxfieldClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=MOXFIELD_API_BASE,
            headers={"User-Agent": "MTG-Sorter/0.4"},
            timeout=30.0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch_deck(self, public_id: str) -> dict[str, Any]:
        response = self._client.get(f"/v3/decks/all/{public_id}")
        if response.status_code == 404:
            # Older path some clients still use.
            response = self._client.get(f"/v2/decks/all/{public_id}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected Moxfield response shape")
        return payload


def deck_export_from_payload(payload: dict[str, Any]) -> MoxfieldDeckExport:
    public_id = str(payload.get("publicId") or payload.get("id") or "")
    name = str(payload.get("name") or "Moxfield deck").strip() or "Moxfield deck"

    lines: list[str] = []
    commander_name: str | None = None
    secondary_role: str | None = None
    secondary_name: str | None = None

    commanders = _board_entries(payload.get("commanders"))
    for index, (card_name, quantity) in enumerate(commanders):
        if index == 0:
            commander_name = card_name
            lines.append(f"Commander: {quantity} {card_name}")
        else:
            secondary_role = "partner"
            secondary_name = card_name
            lines.append(f"Partner: {quantity} {card_name}")

    companions = _board_entries(payload.get("companions"))
    for card_name, quantity in companions:
        if secondary_role is None:
            secondary_role = "companion"
            secondary_name = card_name
        lines.append(f"Companion: {quantity} {card_name}")

    for card_name, quantity in _board_entries(payload.get("mainboard")):
        lines.append(f"{quantity} {card_name}")

    return MoxfieldDeckExport(
        public_id=public_id,
        name=name,
        list_text="\n".join(lines),
        commander_name=commander_name,
        secondary_role=secondary_role,
        secondary_name=secondary_name,
    )


def fetch_moxfield_deck(public_id: str) -> MoxfieldDeckExport:
    client = MoxfieldClient()
    try:
        payload = client.fetch_deck(public_id)
    finally:
        client.close()
    return deck_export_from_payload(payload)


def _board_entries(board: Any) -> list[tuple[str, int]]:
    if not isinstance(board, dict):
        return []
    entries: list[tuple[str, int]] = []
    for key, value in board.items():
        if not isinstance(value, dict):
            continue
        card = value.get("card")
        if isinstance(card, dict) and card.get("name"):
            card_name = str(card["name"])
        else:
            card_name = str(key)
        try:
            quantity = int(value.get("quantity") or 1)
        except (TypeError, ValueError):
            quantity = 1
        if quantity <= 0:
            continue
        entries.append((card_name, quantity))
    entries.sort(key=lambda item: item[0].casefold())
    return entries
