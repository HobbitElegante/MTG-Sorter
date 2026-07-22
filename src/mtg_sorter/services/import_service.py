from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import is_basic_land_name
from mtg_sorter.models import Card, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.deck_service import DeckService, InventoryService
from mtg_sorter.services.moxfield_parser import ParsedDeckLine, parse_moxfield_export
from mtg_sorter.services.scryfall_service import ScryfallService

ROLE_EXPORT_PREFIX: dict[DeckCardRole, str] = {
    DeckCardRole.COMMANDER: "Commander",
    DeckCardRole.PARTNER: "Partner",
    DeckCardRole.COMPANION: "Companion",
    DeckCardRole.BACKGROUND: "Background",
    DeckCardRole.TOKEN: "Token",
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


class ImportService:
    def __init__(self, session: Session, scryfall: ScryfallService) -> None:
        self._session = session
        self._scryfall = scryfall

    def import_moxfield_text(
        self,
        *,
        deck_name: str,
        text: str,
        status: DeckStatus = DeckStatus.DISMANTLED,
        commander_name: str | None = None,
    ) -> ImportResult:
        parsed_lines = parse_moxfield_export(text)

        deck = Deck(name=deck_name, status=status)
        self._session.add(deck)
        self._session.flush()

        warnings = self._populate_deck_cards(
            deck.id,
            parsed_lines=parsed_lines,
            commander_name=commander_name,
        )

        self._session.refresh(deck)
        return ImportResult(deck=deck, warnings=warnings)

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
            deck_service.set_status(deck, DeckStatus.DISMANTLED)

        for deck_card in list(deck.cards):
            self._session.delete(deck_card)
        self._session.flush()

        parsed_lines = parse_moxfield_export(text)
        warnings = self._populate_deck_cards(
            deck.id,
            parsed_lines=parsed_lines,
            commander_name=commander_name,
        )

        if was_armed:
            deck_service.set_status(deck, DeckStatus.ARMED)

        self._session.refresh(deck)
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
                card = self._scryfall.fetch_and_cache(line.name)
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
            inventory.add_copy(oracle_id, quantity)
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
        card = self._session.scalar(
            select(Card).where(Card.name.ilike(commander_name)).limit(1)
        )
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
