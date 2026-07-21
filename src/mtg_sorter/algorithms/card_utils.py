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
