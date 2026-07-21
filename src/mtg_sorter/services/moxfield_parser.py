import re
from dataclasses import dataclass

from mtg_sorter.models.enums import DeckCardRole

ROLE_PREFIXES: dict[str, DeckCardRole] = {
    "commander": DeckCardRole.COMMANDER,
    "partner": DeckCardRole.PARTNER,
    "companion": DeckCardRole.COMPANION,
    "background": DeckCardRole.BACKGROUND,
    "token": DeckCardRole.TOKEN,
    "sideboard": DeckCardRole.MAIN,
}

CATEGORY_HEADER_RE = re.compile(
    r"^(?:\/\/|#|creatures?\s*\(|instants?\s*\(|sorceries?\s*\(|enchantments?\s*\(|"
    r"artifacts?\s*\(|lands?\s*\(|planeswalkers?\s*\(|battles?\s*\(|"
    r"maybeboard|sideboard:|mainboard:)\b.*$",
    re.IGNORECASE,
)
MOXFIELD_LINE_RE = re.compile(
    r"^(?:(?P<role>[A-Za-z ]+):\s*)?"
    r"(?P<qty>\d+)\s*(?:x\s*)?"
    r"(?P<name>.+?)"
    r"(?:\s*\([A-Z0-9]+\)(?:\s+\d+)?(?:\s*\*F\*)?)?"
    r"\s*$"
)


@dataclass(frozen=True)
class ParsedDeckLine:
    quantity: int
    name: str
    role: DeckCardRole
    raw_line: str


def _parse_role_prefix(line: str) -> tuple[DeckCardRole | None, str]:
    if ":" not in line:
        return None, line
    prefix, remainder = line.split(":", 1)
    role_key = prefix.strip().lower()
    if role_key in ROLE_PREFIXES:
        return ROLE_PREFIXES[role_key], remainder.strip()
    return None, line


def parse_moxfield_line(line: str) -> ParsedDeckLine | None:
    stripped = line.strip()
    if not stripped:
        return None
    if CATEGORY_HEADER_RE.match(stripped):
        return None

    role, content = _parse_role_prefix(stripped)
    match = MOXFIELD_LINE_RE.match(content)
    if not match:
        return None

    parsed_role = role
    if parsed_role is None and match.group("role"):
        role_key = match.group("role").strip().lower()
        parsed_role = ROLE_PREFIXES.get(role_key)

    name = match.group("name").strip()
    if not name:
        return None

    return ParsedDeckLine(
        quantity=int(match.group("qty")),
        name=name,
        role=parsed_role or DeckCardRole.MAIN,
        raw_line=line,
    )


def parse_moxfield_export(text: str) -> list[ParsedDeckLine]:
    parsed: list[ParsedDeckLine] = []
    for line in text.splitlines():
        item = parse_moxfield_line(line)
        if item is not None:
            parsed.append(item)
    return parsed
