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
