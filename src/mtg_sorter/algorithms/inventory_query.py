"""Scryfall-lite inventory query parsing and local filtering.

Local tokens run against cached Card fields. Tokens that need the live
Scryfall index are classified as online so the caller can search the API
(or report them as ignored when offline).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class InventoryQueryCard(Protocol):
    oracle_id: str
    card_name: str
    type_line: str | None
    colors: str | None
    color_identity: str | None
    cmc: float | None
    oracle_text: str | None
    commander_legality: str | None
    is_basic_land: bool
    is_token: bool


_TOKEN_RE = re.compile(
    r"""
    (?P<field>[a-zA-Z]+)
    (?P<op>:|<=|>=|!=|<|>|=)
    (?P<value>"[^"]*"|'[^']*'|\S+)
    |
    (?P<bare>"[^"]*"|'[^']*'|\S+)
    """,
    re.VERBOSE,
)

_CMC_OPS = frozenset({":", "=", "<", ">", "<=", ">=", "!="})

# Keys handled entirely from the local Card cache.
_LOCAL_FIELDS = frozenset(
    {
        "t",
        "type",
        "c",
        "color",
        "ci",
        "id",
        "identity",
        "cmc",
        "manavalue",
        "mv",
        "o",
        "oracle",
        "name",
        "is",
        "legal",
        "f",
        "format",
    }
)

_LOCAL_IS_VALUES = frozenset({"token", "basic", "permanent"})
_LOCAL_LEGAL_VALUES = frozenset(
    {"commander", "banned", "not_legal", "restricted", "legal"}
)


@dataclass(frozen=True)
class QueryToken:
    raw: str
    kind: str  # "local" | "online"
    field: str | None = None
    op: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class ParsedInventoryQuery:
    tokens: tuple[QueryToken, ...]

    @property
    def local_tokens(self) -> tuple[QueryToken, ...]:
        return tuple(token for token in self.tokens if token.kind == "local")

    @property
    def online_tokens(self) -> tuple[QueryToken, ...]:
        return tuple(token for token in self.tokens if token.kind == "online")

    @property
    def online_raw(self) -> tuple[str, ...]:
        return tuple(token.raw for token in self.online_tokens)

    def online_query_string(self) -> str:
        return " ".join(self.online_raw)


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _classify_field(field: str, value: str) -> str:
    key = field.casefold()
    if key not in _LOCAL_FIELDS:
        return "online"
    if key == "is":
        return "local" if value.casefold() in _LOCAL_IS_VALUES else "online"
    if key in {"legal", "f", "format"}:
        return "local" if value.casefold() in _LOCAL_LEGAL_VALUES else "online"
    return "local"


def parse_inventory_query(text: str) -> ParsedInventoryQuery:
    tokens: list[QueryToken] = []
    for match in _TOKEN_RE.finditer(text.strip()):
        if match.group("field"):
            field = match.group("field")
            op = match.group("op")
            value = _strip_quotes(match.group("value"))
            raw = match.group(0)
            # Bare cmc comparisons sometimes arrive as cmc>=3 (op captured).
            if field.casefold() in {"cmc", "manavalue", "mv"} and op not in _CMC_OPS:
                tokens.append(QueryToken(raw=raw, kind="online", field=field, op=op, value=value))
                continue
            kind = _classify_field(field, value)
            tokens.append(
                QueryToken(raw=raw, kind=kind, field=field.casefold(), op=op, value=value)
            )
        else:
            bare = _strip_quotes(match.group("bare"))
            if not bare:
                continue
            tokens.append(
                QueryToken(
                    raw=match.group(0),
                    kind="local",
                    field="name",
                    op=":",
                    value=bare,
                )
            )
    return ParsedInventoryQuery(tokens=tuple(tokens))


def _color_letters(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(letter for letter in value.upper() if letter in "WUBRG")


def _parse_color_query(value: str) -> frozenset[str]:
    mapping = {
        "white": "W",
        "blue": "U",
        "black": "B",
        "red": "R",
        "green": "G",
        "w": "W",
        "u": "U",
        "b": "B",
        "r": "R",
        "g": "G",
    }
    lowered = value.casefold().strip()
    if lowered in {"c", "colorless"}:
        return frozenset()
    if lowered in mapping:
        return frozenset({mapping[lowered]})
    letters: set[str] = set()
    for part in re.split(r"[\s,]+", lowered):
        if part in mapping:
            letters.add(mapping[part])
            continue
        for ch in part.upper():
            if ch in "WUBRG":
                letters.add(ch)
    return frozenset(letters)


def _match_cmc(card_cmc: float | None, op: str, raw_value: str) -> bool:
    try:
        target = float(raw_value)
    except ValueError:
        return False
    actual = 0.0 if card_cmc is None else float(card_cmc)
    if op in {":", "="}:
        return actual == target
    if op == "!=":
        return actual != target
    if op == "<":
        return actual < target
    if op == ">":
        return actual > target
    if op == "<=":
        return actual <= target
    if op == ">=":
        return actual >= target
    return False


def _token_matches(card: InventoryQueryCard, token: QueryToken) -> bool:
    field = token.field or "name"
    value = token.value or ""
    op = token.op or ":"
    needle = value.casefold()

    if field == "name":
        return needle in card.card_name.casefold()

    if field in {"t", "type"}:
        return needle in (card.type_line or "").casefold()

    if field in {"o", "oracle"}:
        return needle in (card.oracle_text or "").casefold()

    if field in {"c", "color"}:
        wanted = _parse_color_query(value)
        have = _color_letters(card.colors)
        if not wanted:
            return not have
        return wanted <= have

    if field in {"ci", "id", "identity"}:
        wanted = _parse_color_query(value)
        have = _color_letters(card.color_identity)
        if not wanted:
            return not have
        return wanted <= have

    if field in {"cmc", "manavalue", "mv"}:
        return _match_cmc(card.cmc, op, value)

    if field == "is":
        flag = needle
        if flag == "token":
            return card.is_token
        if flag == "basic":
            return card.is_basic_land
        if flag == "permanent":
            type_line = (card.type_line or "").casefold()
            return not any(
                word in type_line
                for word in ("instant", "sorcery")
            )
        return True

    if field in {"legal", "f", "format"}:
        legality = (card.commander_legality or "").casefold()
        if needle == "commander":
            return legality == "legal"
        if needle in {"banned", "not_legal", "restricted", "legal"}:
            return legality == needle
        return True

    return True


def matches_local_query(card: InventoryQueryCard, parsed: ParsedInventoryQuery) -> bool:
    for token in parsed.local_tokens:
        if not _token_matches(card, token):
            return False
    return True


def filter_inventory_rows(
    rows: Sequence[InventoryQueryCard],
    parsed: ParsedInventoryQuery,
    *,
    online_oracle_ids: set[str] | None = None,
) -> list[InventoryQueryCard]:
    """Apply local filters, then optionally intersect with online oracle ids."""
    local_hits = [row for row in rows if matches_local_query(row, parsed)]
    if online_oracle_ids is None:
        return list(local_hits)
    return [row for row in local_hits if row.oracle_id in online_oracle_ids]


def build_online_search_query(parsed: ParsedInventoryQuery) -> str | None:
    if not parsed.online_tokens:
        return None
    return parsed.online_query_string()
