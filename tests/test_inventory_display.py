from mtg_sorter.i18n import Translator
from mtg_sorter.services.browse_service import InventorySummaryRow
from mtg_sorter.ui.inventory_display import format_inventory_decks


def _row(
    *,
    free: int = 0,
    total: int = 1,
    decks: tuple[str, ...] = (),
) -> InventorySummaryRow:
    return InventorySummaryRow(
        oracle_id="oid",
        card_name="Sol Ring",
        total_copies=total,
        free_copies=free,
        assigned_decks=decks,
    )


def test_format_inventory_decks_empty() -> None:
    translator = Translator("en")
    assert format_inventory_decks(_row(free=2, total=2), translator) == "—"


def test_format_inventory_decks_lists_names_only() -> None:
    translator = Translator("en")
    text = format_inventory_decks(
        _row(free=1, total=3, decks=("Kellan", "Athreos")),
        translator,
    )
    assert text == "Kellan, Athreos"
    assert "free" not in text.casefold()
    assert "1" not in text


def test_format_inventory_decks_spanish_placeholder() -> None:
    translator = Translator("es")
    assert format_inventory_decks(_row(free=1, total=1), translator) == "—"
