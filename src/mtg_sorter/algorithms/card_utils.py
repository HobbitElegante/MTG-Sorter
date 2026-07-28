BASIC_LAND_NAMES = frozenset(
    {
        "Plains",
        "Island",
        "Swamp",
        "Mountain",
        "Forest",
        "Wastes",
        "Snow-Covered Plains",
        "Snow-Covered Island",
        "Snow-Covered Swamp",
        "Snow-Covered Mountain",
        "Snow-Covered Forest",
    }
)


def is_basic_land_name(name: str) -> bool:
    return name.strip() in BASIC_LAND_NAMES


def is_basic_land_type_line(type_line: str | None) -> bool:
    if not type_line:
        return False
    return "Basic Land" in type_line


def is_token_type_line(type_line: str | None) -> bool:
    if not type_line:
        return False
    return "Token" in type_line


def is_art_series_type_line(type_line: str | None) -> bool:
    """Scryfall Art Series entries use the placeholder type 'Card // Card'."""
    return type_line == "Card // Card"


def is_scryfall_art_series(payload: dict) -> bool:
    if payload.get("layout") == "art_series":
        return True
    return is_art_series_type_line(payload.get("type_line"))


COMMANDER_LEGALITY_ISSUE_VALUES = frozenset(
    {"banned", "not_legal", "restricted", "house_banned"}
)
SCRYFALL_LEGALITY_ISSUE_VALUES = frozenset({"banned", "not_legal", "restricted"})


def commander_legality_from_payload(payload: dict) -> str | None:
    """Extract Scryfall legalities.commander (legal / not_legal / banned / restricted)."""
    legalities = payload.get("legalities")
    if not isinstance(legalities, dict):
        return None
    value = legalities.get("commander")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().casefold()


def is_commander_legality_issue(legality: str | None) -> bool:
    """True when the card should show a non-blocking Commander format warning."""
    if legality is None:
        return False
    return legality.casefold() in COMMANDER_LEGALITY_ISSUE_VALUES


def is_scryfall_legality_issue(legality: str | None) -> bool:
    """True for official Scryfall Commander legality issues (excludes house bans)."""
    if legality is None:
        return False
    return legality.casefold() in SCRYFALL_LEGALITY_ISSUE_VALUES
