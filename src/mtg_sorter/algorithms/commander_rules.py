"""Commander game-rule checks (advisory only, never blocking).

Scryfall format legality lives in :mod:`card_utils`; this module covers the
rules a legal-in-format card can still break inside a specific deck: color
identity of the 99, whether the second command-zone card is a legal
partner/background/companion, singleton copies (basics, “any number of cards
named …”, and “up to N cards named …” with a quantity cap), and the 100-card
list size (Companion sits outside that total).

Everything here is pure: callers pass rows already read from the local cache.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

ROLE_MAIN = "MAIN"
ROLE_COMMANDER = "COMMANDER"
ROLE_PARTNER = "PARTNER"
ROLE_COMPANION = "COMPANION"
ROLE_BACKGROUND = "BACKGROUND"

WUBRG = "WUBRG"


class PartnerAbility(StrEnum):
    PARTNER = "partner"
    PARTNER_WITH = "partner_with"
    RESTRICTED_PARTNER = "restricted_partner"
    CHOOSE_A_BACKGROUND = "choose_a_background"
    FRIENDS_FOREVER = "friends_forever"
    DOCTORS_COMPANION = "doctors_companion"
    COMPANION = "companion"


class CommanderRuleKind(StrEnum):
    COLOR_IDENTITY = "color_identity"
    PAIRING = "pairing"
    MISSING_DATA = "missing_data"
    SINGLETON = "singleton"
    DECK_SIZE = "deck_size"


COMMANDER_DECK_SIZE = 100


@dataclass(frozen=True)
class CommanderCard:
    """A deck-list entry with the cached Scryfall fields the rules need."""

    oracle_id: str
    name: str
    role: str
    color_identity: str | None
    oracle_text: str | None
    type_line: str | None
    quantity: int = 1
    is_basic_land: bool = False


@dataclass(frozen=True)
class CommanderRuleIssue:
    kind: CommanderRuleKind
    name: str
    colors: str = ""
    allowed: str = ""
    commander: str = ""
    quantity: int = 0


# Oracle text keeps reminder text, so anchor on the start of a line and stop
# before the parenthesis: "Partner (You can have two commanders...)".
_PARTNER_WITH_RE = re.compile(r"^Partner with ([^(\n]+)", re.MULTILINE)
_RESTRICTED_PARTNER_RE = re.compile(r"^Partner[—-]\s*([^(\n]+)", re.MULTILINE)
_PLAIN_PARTNER_RE = re.compile(r"^Partner(?:\s*\(|\s*$)", re.MULTILINE)
_CHOOSE_BACKGROUND_RE = re.compile(r"^Choose a Background", re.MULTILINE | re.IGNORECASE)
_FRIENDS_FOREVER_RE = re.compile(r"^Friends forever", re.MULTILINE | re.IGNORECASE)
_DOCTORS_COMPANION_RE = re.compile(r"^Doctor's companion", re.MULTILINE | re.IGNORECASE)
_COMPANION_RE = re.compile(r"^Companion\s*[—-]", re.MULTILINE)
_ANY_NUMBER_NAMED_RE = re.compile(
    r"A deck can have any number of cards named",
    re.IGNORECASE,
)
_UP_TO_NAMED_RE = re.compile(
    r"A deck can have up to ([a-z0-9]+) cards? named",
    re.IGNORECASE,
)
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def partner_abilities(oracle_text: str | None) -> frozenset[PartnerAbility]:
    """Command-zone keywords printed on a card."""
    if not oracle_text:
        return frozenset()
    found: set[PartnerAbility] = set()
    if _PARTNER_WITH_RE.search(oracle_text):
        found.add(PartnerAbility.PARTNER_WITH)
    if _RESTRICTED_PARTNER_RE.search(oracle_text):
        found.add(PartnerAbility.RESTRICTED_PARTNER)
    if _PLAIN_PARTNER_RE.search(oracle_text):
        found.add(PartnerAbility.PARTNER)
    if _CHOOSE_BACKGROUND_RE.search(oracle_text):
        found.add(PartnerAbility.CHOOSE_A_BACKGROUND)
    if _FRIENDS_FOREVER_RE.search(oracle_text):
        found.add(PartnerAbility.FRIENDS_FOREVER)
    if _DOCTORS_COMPANION_RE.search(oracle_text):
        found.add(PartnerAbility.DOCTORS_COMPANION)
    if _COMPANION_RE.search(oracle_text):
        found.add(PartnerAbility.COMPANION)
    return frozenset(found)


def partner_with_names(oracle_text: str | None) -> frozenset[str]:
    if not oracle_text:
        return frozenset()
    return frozenset(
        match.group(1).strip().casefold()
        for match in _PARTNER_WITH_RE.finditer(oracle_text)
    )


def restricted_partner_labels(oracle_text: str | None) -> frozenset[str]:
    if not oracle_text:
        return frozenset()
    return frozenset(
        match.group(1).strip().casefold()
        for match in _RESTRICTED_PARTNER_RE.finditer(oracle_text)
    )


def is_background(type_line: str | None) -> bool:
    if not type_line:
        return False
    return "Background" in type_line


def is_doctor(type_line: str | None) -> bool:
    if not type_line:
        return False
    return "Doctor" in type_line and "Time Lord" in type_line


def color_identity_letters(color_identity: str | None) -> frozenset[str]:
    if not color_identity:
        return frozenset()
    return frozenset(letter for letter in color_identity.upper() if letter in WUBRG)


def format_identity(letters: frozenset[str]) -> str:
    """WUBRG order, so 'BW' and 'WB' never read as different identities."""
    return "".join(letter for letter in WUBRG if letter in letters)


def allowed_color_identity(cards: list[CommanderCard]) -> frozenset[str]:
    """Union of the command zone's identity.

    A companion sits outside the deck and does not widen what the 99 may
    contain; it has to fit inside the commander's identity itself.
    """
    allowed: set[str] = set()
    for card in cards:
        if card.role in (ROLE_COMMANDER, ROLE_PARTNER, ROLE_BACKGROUND):
            allowed |= color_identity_letters(card.color_identity)
    return frozenset(allowed)


def is_legal_pairing(commander: CommanderCard, secondary: CommanderCard) -> bool:
    """Whether ``secondary`` may share the command zone with ``commander``."""
    primary_abilities = partner_abilities(commander.oracle_text)
    second_abilities = partner_abilities(secondary.oracle_text)

    if secondary.role == ROLE_BACKGROUND:
        return (
            PartnerAbility.CHOOSE_A_BACKGROUND in primary_abilities
            and is_background(secondary.type_line)
        )

    if secondary.role == ROLE_COMPANION:
        return PartnerAbility.COMPANION in second_abilities

    if secondary.role != ROLE_PARTNER:
        return True

    if (
        PartnerAbility.PARTNER in primary_abilities
        and PartnerAbility.PARTNER in second_abilities
    ):
        return True
    if (
        PartnerAbility.FRIENDS_FOREVER in primary_abilities
        and PartnerAbility.FRIENDS_FOREVER in second_abilities
    ):
        return True
    if partner_with_names(commander.oracle_text) & {
        secondary.name.casefold()
    } or partner_with_names(secondary.oracle_text) & {commander.name.casefold()}:
        return True
    if restricted_partner_labels(commander.oracle_text) & restricted_partner_labels(
        secondary.oracle_text
    ):
        return True
    if PartnerAbility.DOCTORS_COMPANION in primary_abilities and is_doctor(
        secondary.type_line
    ):
        return True
    if PartnerAbility.DOCTORS_COMPANION in second_abilities and is_doctor(
        commander.type_line
    ):
        return True
    return False


def deck_list_size(cards: list[CommanderCard]) -> int:
    """Cards that count toward the 100: everything except Companion (outside)."""
    return sum(
        max(0, card.quantity)
        for card in cards
        if card.role != ROLE_COMPANION
    )


def allows_any_number_named(oracle_text: str | None) -> bool:
    """True for Relentless Rats–style unlimited copies."""
    return singleton_max_copies(oracle_text) is None


def singleton_max_copies(oracle_text: str | None) -> int | None:
    """Maximum copies of this card name allowed by printed text.

    Returns ``1`` for a normal singleton card, ``None`` when the card allows
    any number of copies, or ``N`` for “up to N cards named …” (Seven Dwarves).
    """
    if not oracle_text:
        return 1
    if _ANY_NUMBER_NAMED_RE.search(oracle_text):
        return None
    match = _UP_TO_NAMED_RE.search(oracle_text)
    if match is None:
        return 1
    token = match.group(1).casefold()
    if token.isdigit():
        return max(1, int(token))
    return _NUMBER_WORDS.get(token, 1)


def evaluate_deck(cards: list[CommanderCard]) -> list[CommanderRuleIssue]:
    """Advisory rule issues for one deck list.

    Returns an empty list when the deck has no commander yet: an incomplete
    list is a work in progress, not a rules violation.
    """
    commander = next(
        (card for card in cards if card.role == ROLE_COMMANDER),
        None,
    )
    if commander is None:
        return []

    issues: list[CommanderRuleIssue] = []

    size = deck_list_size(cards)
    if size != COMMANDER_DECK_SIZE:
        issues.append(
            CommanderRuleIssue(
                kind=CommanderRuleKind.DECK_SIZE,
                name=str(size),
                allowed=str(COMMANDER_DECK_SIZE),
                quantity=size,
            )
        )

    qty_by_oracle: dict[str, tuple[str, int, int | None]] = {}
    for card in cards:
        if card.is_basic_land or card.role == ROLE_COMPANION:
            continue
        cap = singleton_max_copies(card.oracle_text)
        prev = qty_by_oracle.get(card.oracle_id)
        if prev is None:
            qty_by_oracle[card.oracle_id] = (card.name, card.quantity, cap)
        else:
            prev_name, prev_qty, prev_cap = prev
            if prev_cap is None or cap is None:
                merged_cap: int | None = None
            else:
                merged_cap = max(prev_cap, cap)
            qty_by_oracle[card.oracle_id] = (
                prev_name,
                prev_qty + card.quantity,
                merged_cap,
            )
    for name, qty, cap in qty_by_oracle.values():
        if cap is None or qty <= cap:
            continue
        issues.append(
            CommanderRuleIssue(
                kind=CommanderRuleKind.SINGLETON,
                name=name,
                quantity=qty,
                allowed=str(cap),
            )
        )

    secondary = next(
        (
            card
            for card in cards
            if card.role in (ROLE_PARTNER, ROLE_BACKGROUND, ROLE_COMPANION)
        ),
        None,
    )
    if secondary is not None and not is_legal_pairing(commander, secondary):
        issues.append(
            CommanderRuleIssue(
                kind=CommanderRuleKind.PAIRING,
                name=secondary.name,
                commander=commander.name,
            )
        )

    allowed = allowed_color_identity(cards)
    allowed_label = format_identity(allowed)
    for card in cards:
        if card.role in (ROLE_COMMANDER, ROLE_PARTNER, ROLE_BACKGROUND):
            continue
        if card.is_basic_land:
            continue
        if card.color_identity is None:
            issues.append(
                CommanderRuleIssue(
                    kind=CommanderRuleKind.MISSING_DATA,
                    name=card.name,
                )
            )
            continue
        letters = color_identity_letters(card.color_identity)
        if letters - allowed:
            issues.append(
                CommanderRuleIssue(
                    kind=CommanderRuleKind.COLOR_IDENTITY,
                    name=card.name,
                    colors=format_identity(letters),
                    allowed=allowed_label,
                )
            )

    return sorted(issues, key=lambda issue: (issue.kind.value, issue.name.casefold()))
