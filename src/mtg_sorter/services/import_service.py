from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import is_basic_land_name
from mtg_sorter.api.moxfield_client import fetch_moxfield_deck
from mtg_sorter.models import Card, Deck, DeckCard
from mtg_sorter.models.enums import ActivityEventType, DeckCardRole, DeckStatus
from mtg_sorter.services.activity_service import ActivityService
from mtg_sorter.services.deck_service import DeckService, InventoryService
from mtg_sorter.services.decklist_parser import (
    ARENA_SECTION_RE,
    CATEGORY_HEADER_RE,
    DecklistFormat,
    ParsedDeckLine,
    detect_format,
    extract_moxfield_deck_id,
    parse_decklist,
    parse_moxfield_line,
)
from mtg_sorter.services.scryfall_service import ScryfallService

ROLE_EXPORT_PREFIX: dict[DeckCardRole, str] = {
    DeckCardRole.COMMANDER: "Commander",
    DeckCardRole.PARTNER: "Partner",
    DeckCardRole.COMPANION: "Companion",
    DeckCardRole.BACKGROUND: "Background",
    DeckCardRole.TOKEN: "Token",
}

SECONDARY_ROLE_FROM_NAME: dict[str, DeckCardRole] = {
    "partner": DeckCardRole.PARTNER,
    "companion": DeckCardRole.COMPANION,
    "background": DeckCardRole.BACKGROUND,
}


@dataclass
class ImportWarning:
    line: str
    message: str


@dataclass
class TrackableDeckCard:
    oracle_id: str
    name: str
    quantity: int


@dataclass
class ImportResult:
    deck: Deck
    warnings: list[ImportWarning] = field(default_factory=list)


@dataclass(frozen=True)
class InventoryListCard:
    oracle_id: str
    name: str
    list_quantity: int


@dataclass(frozen=True)
class InventoryListPreview:
    identified: list[InventoryListCard]
    unresolved_lines: list[str]


@dataclass(frozen=True)
class DeckListChange:
    oracle_id: str
    name: str
    before: int
    after: int

    @property
    def delta(self) -> int:
        return self.after - self.before


@dataclass(frozen=True)
class DeckListUpdatePreview:
    """Diff between a deck's stored list and a pasted/fetched replacement."""

    text: str
    deck_name: str | None
    commander_name: str | None
    secondary_role: DeckCardRole | None
    secondary_name: str | None
    added: list[DeckListChange]
    removed: list[DeckListChange]
    total_before: int
    total_after: int
    unresolved_lines: list[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed)


@dataclass(frozen=True)
class ResolvedDecklistInput:
    """Paste/file/URL materializado a texto de listado + metadatos opcionales."""

    text: str
    format: DecklistFormat
    deck_name: str | None = None
    commander_name: str | None = None
    secondary_role: DeckCardRole | None = None
    secondary_name: str | None = None


class ImportService:
    def __init__(self, session: Session, scryfall: ScryfallService) -> None:
        self._session = session
        self._scryfall = scryfall

    def resolve_decklist_input(
        self,
        text: str,
        *,
        fetch_url: bool = True,
    ) -> ResolvedDecklistInput:
        """Expand a Moxfield URL when needed; otherwise return text as-is."""
        stripped = text.strip()
        fmt = detect_format(stripped)
        if fmt != DecklistFormat.MOXFIELD_URL:
            return ResolvedDecklistInput(text=stripped, format=fmt)

        if not fetch_url:
            raise ValueError("Moxfield URL requires network fetch")

        deck_id = extract_moxfield_deck_id(stripped)
        if deck_id is None:
            raise ValueError("Could not parse Moxfield deck URL")

        export = fetch_moxfield_deck(deck_id)
        secondary_role = None
        if export.secondary_role:
            secondary_role = SECONDARY_ROLE_FROM_NAME.get(
                export.secondary_role.lower()
            )
        return ResolvedDecklistInput(
            text=export.list_text,
            format=DecklistFormat.MOXFIELD_MTGO,
            deck_name=export.name,
            commander_name=export.commander_name,
            secondary_role=secondary_role,
            secondary_name=export.secondary_name,
        )

    def preview_inventory_list(self, text: str) -> InventoryListPreview:
        """Resolve decklist text into inventoriable cards + unresolved lines.

        Basics and tokens are skipped (not trackable). Supports Moxfield/MTGO,
        Arena, Archidekt, MTGO .dek, and Moxfield URLs (fetched).
        """
        resolved = self.resolve_decklist_input(text)
        body = resolved.text
        fmt = resolved.format

        merged: dict[str, InventoryListCard] = {}
        unresolved: list[str] = []

        parsed_lines = parse_decklist(body)
        for parsed in parsed_lines:
            try:
                card = self._scryfall.fetch_and_cache(
                    parsed.name,
                    prefer_token=parsed.role == DeckCardRole.TOKEN,
                )
            except Exception:
                unresolved.append(parsed.raw_line.strip())
                continue

            if is_basic_land_name(parsed.name) or card.is_basic_land or card.is_token:
                continue

            existing = merged.get(card.oracle_id)
            if existing is None:
                merged[card.oracle_id] = InventoryListCard(
                    oracle_id=card.oracle_id,
                    name=card.name,
                    list_quantity=parsed.quantity,
                )
            else:
                merged[card.oracle_id] = InventoryListCard(
                    oracle_id=card.oracle_id,
                    name=card.name,
                    list_quantity=existing.list_quantity + parsed.quantity,
                )

        unresolved.extend(self._unparsed_lines(body, fmt, parsed_lines))

        identified = sorted(merged.values(), key=lambda c: c.name.casefold())
        return InventoryListPreview(
            identified=identified,
            unresolved_lines=unresolved,
        )

    def preview_deck_list_update(
        self,
        deck_id: int,
        text: str,
    ) -> DeckListUpdatePreview:
        """Diff a deck's current list against pasted text (or a Moxfield URL)."""
        deck = self._session.get(Deck, deck_id)
        if deck is None:
            raise ValueError(f"Deck {deck_id} not found")

        resolved = self.resolve_decklist_input(text)
        parsed_lines = parse_decklist(resolved.text)

        after: dict[str, int] = {}
        names: dict[str, str] = {}
        unresolved: list[str] = []
        for line in parsed_lines:
            try:
                card = self._scryfall.fetch_and_cache(
                    line.name,
                    prefer_token=line.role == DeckCardRole.TOKEN,
                )
            except Exception:
                unresolved.append(line.raw_line.strip())
                continue
            after[card.oracle_id] = after.get(card.oracle_id, 0) + line.quantity
            names[card.oracle_id] = card.name

        unresolved.extend(
            self._unparsed_lines(resolved.text, resolved.format, parsed_lines)
        )

        before: dict[str, int] = {}
        rows = self._session.execute(
            select(DeckCard, Card)
            .join(Card, Card.oracle_id == DeckCard.card_id)
            .where(DeckCard.deck_id == deck_id)
        ).all()
        for deck_card, card in rows:
            before[card.oracle_id] = before.get(card.oracle_id, 0) + deck_card.quantity
            names.setdefault(card.oracle_id, card.name)

        added: list[DeckListChange] = []
        removed: list[DeckListChange] = []
        for oracle_id in before.keys() | after.keys():
            old = before.get(oracle_id, 0)
            new = after.get(oracle_id, 0)
            if old == new:
                continue
            change = DeckListChange(
                oracle_id=oracle_id,
                name=names.get(oracle_id, oracle_id),
                before=old,
                after=new,
            )
            (added if new > old else removed).append(change)

        return DeckListUpdatePreview(
            text=resolved.text,
            deck_name=resolved.deck_name,
            commander_name=resolved.commander_name,
            secondary_role=resolved.secondary_role,
            secondary_name=resolved.secondary_name,
            added=sorted(added, key=lambda change: change.name.casefold()),
            removed=sorted(removed, key=lambda change: change.name.casefold()),
            total_before=sum(before.values()),
            total_after=sum(after.values()),
            unresolved_lines=unresolved,
        )

    def _unparsed_lines(
        self,
        body: str,
        fmt: DecklistFormat,
        parsed_lines: list[ParsedDeckLine],
    ) -> list[str]:
        """Non-empty lines that are neither headers nor valid card lines."""
        if fmt == DecklistFormat.MTGO_DEK:
            return []

        parsed_raw = {line.raw_line.strip() for line in parsed_lines}
        leftovers: list[str] = []
        for raw in body.splitlines():
            stripped = raw.strip()
            if not stripped:
                continue
            if CATEGORY_HEADER_RE.match(stripped) or ARENA_SECTION_RE.match(stripped):
                continue
            if stripped in parsed_raw:
                continue
            if parse_moxfield_line(raw) is not None:
                continue
            leftovers.append(stripped)
        return leftovers

    def import_decklist_text(
        self,
        *,
        deck_name: str,
        text: str,
        status: DeckStatus = DeckStatus.DISMANTLED,
        commander_name: str | None = None,
    ) -> ImportResult:
        resolved = self.resolve_decklist_input(text)
        parsed_lines = parse_decklist(resolved.text)

        deck = Deck(
            name=deck_name,
            status=status,
            sort_order=DeckService(self._session).next_sort_order(),
        )
        self._session.add(deck)
        self._session.flush()

        warnings = self._populate_deck_cards(
            deck.id,
            parsed_lines=parsed_lines,
            commander_name=commander_name,
        )

        self._session.refresh(deck)
        ActivityService(self._session).record(
            ActivityEventType.DECK_IMPORTED,
            "history.event.deck_imported",
            {
                "deck_id": deck.id,
                "deck_name": deck.name,
                "status": status.value,
            },
        )
        return ImportResult(deck=deck, warnings=warnings)

    def import_moxfield_text(
        self,
        *,
        deck_name: str,
        text: str,
        status: DeckStatus = DeckStatus.DISMANTLED,
        commander_name: str | None = None,
    ) -> ImportResult:
        """Backward-compatible alias for import_decklist_text."""
        return self.import_decklist_text(
            deck_name=deck_name,
            text=text,
            status=status,
            commander_name=commander_name,
        )

    def deck_to_moxfield_text(self, deck_id: int) -> str:
        rows = self._session.execute(
            select(DeckCard, Card)
            .join(Card, Card.oracle_id == DeckCard.card_id)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.role, Card.name)
        ).all()
        lines: list[str] = []
        for deck_card, card in rows:
            prefix = ROLE_EXPORT_PREFIX.get(deck_card.role)
            if prefix is not None and deck_card.role != DeckCardRole.MAIN:
                lines.append(f"{prefix}: {deck_card.quantity} {card.name}")
            else:
                lines.append(f"{deck_card.quantity} {card.name}")
        return "\n".join(lines)

    def replace_deck_list(
        self,
        deck_id: int,
        text: str,
        commander_name: str | None = None,
    ) -> list[ImportWarning]:
        deck = self._session.get(Deck, deck_id)
        if deck is None:
            raise ValueError(f"Deck {deck_id} not found")

        deck_service = DeckService(self._session)
        was_armed = deck.status == DeckStatus.ARMED
        if was_armed:
            deck_service.set_status(
                deck, DeckStatus.DISMANTLED, record_activity=False
            )

        for deck_card in list(deck.cards):
            self._session.delete(deck_card)
        self._session.flush()

        resolved = self.resolve_decklist_input(text)
        parsed_lines = parse_decklist(resolved.text)
        warnings = self._populate_deck_cards(
            deck.id,
            parsed_lines=parsed_lines,
            commander_name=commander_name,
        )

        if was_armed:
            deck_service.set_status(deck, DeckStatus.ARMED, record_activity=False)

        self._session.refresh(deck)
        ActivityService(self._session).record(
            ActivityEventType.DECK_LIST_EDITED,
            "history.event.deck_list_edited",
            {"deck_id": deck.id, "deck_name": deck.name},
        )
        return warnings

    def _populate_deck_cards(
        self,
        deck_id: int,
        *,
        parsed_lines: list[ParsedDeckLine],
        commander_name: str | None = None,
    ) -> list[ImportWarning]:
        warnings: list[ImportWarning] = []

        for line in parsed_lines:
            try:
                card = self._scryfall.fetch_and_cache(
                    line.name,
                    prefer_token=line.role == DeckCardRole.TOKEN,
                )
            except Exception as exc:
                warnings.append(
                    ImportWarning(line=line.raw_line, message=str(exc))
                )
                continue

            if is_basic_land_name(line.name):
                card.is_basic_land = True

            role = line.role
            if commander_name and line.name.lower() == commander_name.lower():
                role = DeckCardRole.COMMANDER

            self._upsert_deck_card(deck_id, card.oracle_id, line.quantity, role)

        if commander_name:
            self._promote_commander(deck_id, commander_name)

        self._session.flush()
        return warnings

    def list_trackable_cards(self, deck_id: int) -> list[TrackableDeckCard]:
        requirements = DeckService(self._session).deck_requirements(deck_id)
        cards: list[TrackableDeckCard] = []
        for oracle_id, quantity in requirements.items():
            card = self._session.get(Card, oracle_id)
            if card is None:
                continue
            cards.append(
                TrackableDeckCard(
                    oracle_id=oracle_id,
                    name=card.name,
                    quantity=quantity,
                )
            )
        return sorted(cards, key=lambda entry: entry.name.casefold())

    def apply_available_copies(self, quantities: dict[str, int]) -> int:
        inventory = InventoryService(self._session)
        added = 0
        for oracle_id, quantity in quantities.items():
            if quantity <= 0:
                continue
            inventory.add_copy(
                oracle_id, quantity, record_activity=True
            )
            added += quantity
        return added

    def _upsert_deck_card(
        self,
        deck_id: int,
        card_id: str,
        quantity: int,
        role: DeckCardRole,
    ) -> None:
        existing = self._session.scalar(
            select(DeckCard).where(
                DeckCard.deck_id == deck_id,
                DeckCard.card_id == card_id,
                DeckCard.role == role,
            )
        )
        if existing:
            existing.quantity += quantity
            return

        self._session.add(
            DeckCard(
                deck_id=deck_id,
                card_id=card_id,
                quantity=quantity,
                role=role,
            )
        )

    def _promote_commander(self, deck_id: int, commander_name: str) -> None:
        card = self._scryfall.lookup_local(commander_name)
        if card is None:
            return

        main_entry = self._session.scalar(
            select(DeckCard).where(
                DeckCard.deck_id == deck_id,
                DeckCard.card_id == card.oracle_id,
                DeckCard.role == DeckCardRole.MAIN,
            )
        )
        if main_entry is None:
            return

        if main_entry.quantity > 1:
            main_entry.quantity -= 1
        else:
            self._session.delete(main_entry)

        self._upsert_deck_card(deck_id, card.oracle_id, 1, DeckCardRole.COMMANDER)
