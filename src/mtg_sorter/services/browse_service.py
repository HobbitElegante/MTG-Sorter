from dataclasses import dataclass

from sqlalchemy.orm import Session

from mtg_sorter.repositories import CardRepository, CopyRepository, DeckRepository
from mtg_sorter.services.scryfall_bulk_service import BulkSyncStatus, ScryfallBulkService


@dataclass(frozen=True)
class OverviewStats:
    cards: int
    copies: int
    unassigned_copies: int
    decks: int
    armed_decks: int
    deck_cards: int
    assignments: int


@dataclass(frozen=True)
class CardSummary:
    oracle_id: str
    name: str
    type_line: str | None
    cmc: float | None
    color_identity: str | None
    is_basic_land: bool
    is_token: bool
    copy_count: int
    commander_legality: str | None = None


@dataclass(frozen=True)
class InventorySummaryRow:
    oracle_id: str
    card_name: str
    total_copies: int
    free_copies: int
    assigned_decks: tuple[str, ...]
    color_identity: str | None = None
    # (set code or None for unspecified, copies) — only populated when the
    # edition-tracking setting is on.
    editions: tuple[tuple[str | None, int], ...] = ()
    type_line: str | None = None
    colors: str | None = None
    cmc: float | None = None
    oracle_text: str | None = None
    commander_legality: str | None = None
    is_basic_land: bool = False
    is_token: bool = False
    # Deck ids that currently hold a physical copy of this card.
    assigned_deck_ids: frozenset[int] = frozenset()


def _sorted_editions(
    counts: dict[str | None, int],
) -> tuple[tuple[str | None, int], ...]:
    """Most copies first; unspecified last so real set codes lead the summary."""
    return tuple(
        sorted(
            counts.items(),
            key=lambda item: (item[0] is None, -item[1], item[0] or ""),
        )
    )


class BrowseService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._cards = CardRepository(session)
        self._copies = CopyRepository(session)
        self._decks = DeckRepository(session)

    def overview(self) -> OverviewStats:
        return OverviewStats(
            cards=self._cards.count_playable(),
            copies=self._copies.count_all(),
            unassigned_copies=self._copies.count_unassigned(),
            decks=self._decks.count_all(),
            armed_decks=self._decks.count_armed(),
            deck_cards=self._decks.count_deck_cards(),
            assignments=self._copies.count_assignments(),
        )

    def list_cards(self, search: str = "") -> list[CardSummary]:
        copy_counts = self._copies.counts_by_card()
        return [
            CardSummary(
                oracle_id=card.oracle_id,
                name=card.name,
                type_line=card.type_line,
                cmc=card.cmc,
                color_identity=card.color_identity,
                is_basic_land=card.is_basic_land,
                is_token=card.is_token,
                copy_count=copy_counts.get(card.oracle_id, 0),
                commander_legality=card.commander_legality,
            )
            for card in self._cards.list_playable(search)
        ]

    def list_inventory(
        self, *, include_editions: bool = False
    ) -> list[InventorySummaryRow]:
        edition_counts = self._copies.edition_counts() if include_editions else {}
        summaries: list[InventorySummaryRow] = []
        for (
            oracle_id,
            name,
            color_identity,
            total,
            type_line,
            colors,
            cmc,
            oracle_text,
            commander_legality,
            is_basic_land,
            is_token,
        ) in self._decks.inventory_copy_rows():
            assigned_count = self._copies.count_assigned(oracle_id)
            summaries.append(
                InventorySummaryRow(
                    oracle_id=oracle_id,
                    card_name=name,
                    total_copies=total,
                    free_copies=total - assigned_count,
                    assigned_decks=self._decks.deck_names_for_card(oracle_id),
                    color_identity=color_identity,
                    editions=_sorted_editions(edition_counts.get(oracle_id, {})),
                    type_line=type_line,
                    colors=colors,
                    cmc=cmc,
                    oracle_text=oracle_text,
                    commander_legality=commander_legality,
                    is_basic_land=is_basic_land,
                    is_token=is_token,
                    assigned_deck_ids=self._decks.deck_ids_for_card(oracle_id),
                )
            )
        return summaries

    def scryfall_status(self) -> BulkSyncStatus:
        return ScryfallBulkService(self._session).status()
