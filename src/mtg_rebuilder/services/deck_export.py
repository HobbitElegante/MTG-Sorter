"""Format stored deck lists for paste into external tools (name + qty only)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import Session

from mtg_rebuilder.models.enums import DeckCardRole
from mtg_rebuilder.repositories import DeckRepository

ROLE_EXPORT_PREFIX: dict[DeckCardRole, str] = {
    DeckCardRole.COMMANDER: "Commander",
    DeckCardRole.PARTNER: "Partner",
    DeckCardRole.COMPANION: "Companion",
    DeckCardRole.BACKGROUND: "Background",
    DeckCardRole.TOKEN: "Token",
}

ARCHIDEKT_CATEGORY: dict[DeckCardRole, str] = {
    DeckCardRole.COMMANDER: "Commander",
    DeckCardRole.PARTNER: "Partner",
    DeckCardRole.COMPANION: "Companion",
    DeckCardRole.BACKGROUND: "Background",
    DeckCardRole.TOKEN: "Token",
}


class ExportFormat(StrEnum):
    MTGO = "mtgo"
    MOXFIELD = "moxfield"
    ARENA = "arena"
    ARCHIDEKT = "archidekt"
    MTGGOLDFISH = "mtggoldfish"


@dataclass(frozen=True)
class DeckExportCard:
    role: DeckCardRole
    quantity: int
    name: str


def load_deck_export_cards(session: Session, deck_id: int) -> list[DeckExportCard]:
    rows = DeckRepository(session).list_export_cards(deck_id)
    return [
        DeckExportCard(
            role=deck_card.role,
            quantity=deck_card.quantity,
            name=card.name,
        )
        for deck_card, card in rows
    ]


def format_deck_export(cards: list[DeckExportCard], fmt: ExportFormat) -> str:
    if fmt in (ExportFormat.MTGO, ExportFormat.MOXFIELD):
        return _format_mtgo(cards)
    if fmt == ExportFormat.ARENA:
        return _format_arena(cards)
    if fmt == ExportFormat.ARCHIDEKT:
        return _format_archidekt(cards)
    if fmt == ExportFormat.MTGGOLDFISH:
        return _format_mtggoldfish(cards)
    raise ValueError(f"Unsupported export format: {fmt}")


def _format_mtgo(cards: list[DeckExportCard]) -> str:
    lines: list[str] = []
    for card in cards:
        prefix = ROLE_EXPORT_PREFIX.get(card.role)
        if prefix is not None and card.role != DeckCardRole.MAIN:
            lines.append(f"{prefix}: {card.quantity} {card.name}")
        else:
            lines.append(f"{card.quantity} {card.name}")
    return "\n".join(lines)


def _format_arena(cards: list[DeckExportCard]) -> str:
    commanders = [
        c
        for c in cards
        if c.role
        in (
            DeckCardRole.COMMANDER,
            DeckCardRole.PARTNER,
            DeckCardRole.BACKGROUND,
        )
    ]
    companions = [c for c in cards if c.role == DeckCardRole.COMPANION]
    # Tokens are not a dedicated Arena section; include them under Deck.
    deck_cards = [
        c for c in cards if c.role in (DeckCardRole.MAIN, DeckCardRole.TOKEN)
    ]

    sections: list[str] = []
    if commanders:
        block = ["Commander"]
        block.extend(f"{c.quantity} {c.name}" for c in commanders)
        sections.append("\n".join(block))
    if companions:
        block = ["Companion"]
        block.extend(f"{c.quantity} {c.name}" for c in companions)
        sections.append("\n".join(block))
    if deck_cards:
        block = ["Deck"]
        block.extend(f"{c.quantity} {c.name}" for c in deck_cards)
        sections.append("\n".join(block))
    elif not sections:
        sections.append("Deck")
    return "\n\n".join(sections)


def _format_archidekt(cards: list[DeckExportCard]) -> str:
    lines: list[str] = []
    for card in cards:
        category = ARCHIDEKT_CATEGORY.get(card.role)
        if category is not None and card.role != DeckCardRole.MAIN:
            lines.append(f"{card.quantity}x {card.name} [{category}]")
        else:
            lines.append(f"{card.quantity}x {card.name}")
    return "\n".join(lines)


def _format_mtggoldfish(cards: list[DeckExportCard]) -> str:
    command_zone = [
        c
        for c in cards
        if c.role
        in (
            DeckCardRole.COMMANDER,
            DeckCardRole.PARTNER,
            DeckCardRole.COMPANION,
            DeckCardRole.BACKGROUND,
        )
    ]
    main = [c for c in cards if c.role == DeckCardRole.MAIN]
    tokens = [c for c in cards if c.role == DeckCardRole.TOKEN]

    sections: list[str] = []
    if command_zone:
        sections.append("\n".join(f"{c.quantity} {c.name}" for c in command_zone))
    if main:
        sections.append("\n".join(f"{c.quantity} {c.name}" for c in main))
    if tokens:
        sections.append("\n".join(f"{c.quantity} {c.name}" for c in tokens))
    return "\n\n".join(sections)
