"""Pure helpers for Decks list filtering and ephemeral sort (no Qt)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from mtg_sorter.models.enums import DeckStatus

DeckSortKey = Literal["number", "name", "status"]


@dataclass(frozen=True)
class DeckListRow:
    id: int
    name: str
    status: DeckStatus
    sort_order: int
    is_locked: bool
    commander_name: str | None
    has_warning: bool
    tooltip: str


def coerce_deck_status(value: object) -> DeckStatus | None:
    """Normalize QComboBox userData (often a plain str) back to DeckStatus."""
    if value is None:
        return None
    if isinstance(value, DeckStatus):
        return value
    if isinstance(value, str):
        try:
            return DeckStatus(value)
        except ValueError:
            return None
    return None


def filter_deck_rows(
    rows: list[DeckListRow],
    *,
    status: DeckStatus | None,
    needle: str,
) -> list[DeckListRow]:
    """Filter by armed/dismantled and casefold name/commander search."""
    needle = needle.strip().casefold()
    result: list[DeckListRow] = []
    for row in rows:
        if status is not None and row.status != status:
            continue
        if needle:
            commander = (row.commander_name or "").casefold()
            if needle not in row.name.casefold() and needle not in commander:
                continue
        result.append(row)
    return result


def sort_deck_rows(
    rows: list[DeckListRow],
    *,
    key: DeckSortKey,
    ascending: bool,
    status_label: Callable[[DeckStatus], str],
) -> list[DeckListRow]:
    """Ephemeral display order; does not mutate sort_order."""

    def sort_key(row: DeckListRow):
        if key == "name":
            return row.name.casefold()
        if key == "status":
            return status_label(row.status).casefold()
        return (row.sort_order, row.name.casefold(), row.id)

    return sorted(rows, key=sort_key, reverse=not ascending)
