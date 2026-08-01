"""Deck statistics for the Decks detail pane (counts, pips, mana curve).

Everything here is pure: callers pass rows already read from the local cache.
Multi-faced cards are classified by their front face (the cached ``type_line``
and ``mana_cost`` join faces with ``//``), which matches how the rest of the
app treats DFCs. Cards whose type line was never cached are reported apart as
``unknown_cards`` instead of skewing the numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Display order for the type breakdown; a card counts once per type it has
# (an artifact creature adds to both), the way deck sites break types down.
TYPE_ORDER = (
    "Creature",
    "Instant",
    "Sorcery",
    "Artifact",
    "Enchantment",
    "Planeswalker",
    "Battle",
)

PIP_ORDER = "WUBRGC"

# Mana values of 7 or more collapse into one trailing "7+" curve column.
CURVE_TOP_BUCKET = 7

_SYMBOL_RE = re.compile(r"\{([^}]+)\}")


@dataclass(frozen=True)
class DeckStatsCard:
    """A deck-list entry with the cached Scryfall fields the stats need."""

    name: str
    quantity: int
    type_line: str | None
    cmc: float | None
    mana_cost: str | None
    is_basic_land: bool = False


@dataclass(frozen=True)
class CurveColumn:
    """One mana-curve bar: quantity split into creatures vs other spells."""

    cmc: int
    creatures: int
    others: int

    @property
    def total(self) -> int:
        return self.creatures + self.others


@dataclass(frozen=True)
class DeckStatistics:
    total_cards: int
    lands: int
    basic_lands: int
    # Weighted by quantity, lands excluded; None when no card has a cached cmc.
    average_cmc: float | None
    # Same, but lands count too (a land with no cached cmc counts as 0).
    average_cmc_with_lands: float | None
    # (type name, quantity) following TYPE_ORDER; zero-count types are skipped.
    type_counts: tuple[tuple[str, int], ...]
    # (color letter, pip count) following PIP_ORDER; zero-count colors skipped.
    color_pips: tuple[tuple[str, int], ...]
    unknown_cards: int
    curve: tuple[CurveColumn, ...]

    @property
    def has_curve_data(self) -> bool:
        return any(column.total for column in self.curve)


def _front_face(joined: str | None) -> str | None:
    if joined is None:
        return None
    return joined.split(" // ", 1)[0]


def is_land_type_line(type_line: str | None) -> bool:
    front = _front_face(type_line)
    return front is not None and "Land" in front


def is_creature_type_line(type_line: str | None) -> bool:
    front = _front_face(type_line)
    return front is not None and "Creature" in front


def count_pips(mana_cost: str | None) -> dict[str, int]:
    """Colored mana symbols on the front face; hybrids count every color."""
    pips = {letter: 0 for letter in PIP_ORDER}
    front = _front_face(mana_cost)
    if not front:
        return pips
    for symbol in _SYMBOL_RE.findall(front):
        for letter in PIP_ORDER:
            if letter in symbol:
                pips[letter] += 1
    return pips


def compute_deck_statistics(cards: list[DeckStatsCard]) -> DeckStatistics:
    total_cards = sum(card.quantity for card in cards)
    lands = 0
    basic_lands = 0
    unknown = 0
    cmc_sum = 0.0
    cmc_quantity = 0
    cmc_sum_with_lands = 0.0
    cmc_quantity_with_lands = 0
    type_counts = {type_name: 0 for type_name in TYPE_ORDER}
    pips = {letter: 0 for letter in PIP_ORDER}
    curve = {
        bucket: {"creatures": 0, "others": 0}
        for bucket in range(CURVE_TOP_BUCKET + 1)
    }

    for card in cards:
        front_types = _front_face(card.type_line)
        if not front_types:
            unknown += card.quantity
            continue

        if card.is_basic_land or "Land" in front_types:
            lands += card.quantity
            if card.is_basic_land or "Basic" in front_types:
                basic_lands += card.quantity
            cmc_sum_with_lands += (card.cmc or 0.0) * card.quantity
            cmc_quantity_with_lands += card.quantity
            continue

        for type_name in TYPE_ORDER:
            if type_name in front_types:
                type_counts[type_name] += card.quantity

        for letter, count in count_pips(card.mana_cost).items():
            pips[letter] += count * card.quantity

        if card.cmc is None:
            continue
        cmc_sum += card.cmc * card.quantity
        cmc_quantity += card.quantity
        cmc_sum_with_lands += card.cmc * card.quantity
        cmc_quantity_with_lands += card.quantity
        bucket = min(max(int(card.cmc), 0), CURVE_TOP_BUCKET)
        key = "creatures" if "Creature" in front_types else "others"
        curve[bucket][key] += card.quantity

    return DeckStatistics(
        total_cards=total_cards,
        lands=lands,
        basic_lands=basic_lands,
        average_cmc=cmc_sum / cmc_quantity if cmc_quantity else None,
        average_cmc_with_lands=(
            cmc_sum_with_lands / cmc_quantity_with_lands
            if cmc_quantity_with_lands
            else None
        ),
        type_counts=tuple(
            (type_name, type_counts[type_name])
            for type_name in TYPE_ORDER
            if type_counts[type_name]
        ),
        color_pips=tuple(
            (letter, pips[letter]) for letter in PIP_ORDER if pips[letter]
        ),
        unknown_cards=unknown,
        curve=tuple(
            CurveColumn(
                cmc=bucket,
                creatures=curve[bucket]["creatures"],
                others=curve[bucket]["others"],
            )
            for bucket in range(CURVE_TOP_BUCKET + 1)
        ),
    )
