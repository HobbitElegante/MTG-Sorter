from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from mtg_sorter.algorithms.card_utils import is_basic_land_name
from mtg_sorter.models import Card, Deck, DeckCard
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services.moxfield_parser import parse_moxfield_export
from mtg_sorter.services.scryfall_service import ScryfallService


@dataclass
class ImportWarning:
    line: str
    message: str


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
        warnings: list[ImportWarning] = []

        deck = Deck(name=deck_name, status=status)
        self._session.add(deck)
        self._session.flush()

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

            self._upsert_deck_card(deck.id, card.oracle_id, line.quantity, role)

        if commander_name:
            self._promote_commander(deck.id, commander_name)

        self._session.refresh(deck)
        return ImportResult(deck=deck, warnings=warnings)

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
