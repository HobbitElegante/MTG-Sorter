from enum import StrEnum


class DeckStatus(StrEnum):
    ARMED = "ARMED"
    DISMANTLED = "DISMANTLED"


class DeckCardRole(StrEnum):
    MAIN = "MAIN"
    COMMANDER = "COMMANDER"
    PARTNER = "PARTNER"
    COMPANION = "COMPANION"
    BACKGROUND = "BACKGROUND"
    TOKEN = "TOKEN"
