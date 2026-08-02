from mtg_sorter.i18n import Translator
from mtg_sorter.services.browse_service import InventorySummaryRow
from mtg_sorter.ui.inventory_display import (
    format_color_identity,
    format_inventory_decks,
    format_rarity_summary,
    rarity_sort_rank,
)


def _row(
    *,
    free: int = 0,
    total: int = 1,
    decks: tuple[str, ...] = (),
    color_identity: str | None = None,
    rarity: str | None = None,
    rarities: frozenset[str] = frozenset(),
) -> InventorySummaryRow:
    return InventorySummaryRow(
        oracle_id="oid",
        card_name="Sol Ring",
        total_copies=total,
        free_copies=free,
        assigned_decks=decks,
        color_identity=color_identity,
        rarity=rarity,
        rarities=rarities or (frozenset({rarity}) if rarity else frozenset()),
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


def test_format_color_identity_wubrg() -> None:
    translator = Translator("en")
    assert format_color_identity("WUB", translator) == "WUB"


def test_format_color_identity_empty() -> None:
    translator = Translator("en")
    assert format_color_identity(None, translator) == "—"
    assert format_color_identity("", translator) == "—"


def test_format_rarity_summary_letters() -> None:
    translator = Translator("en")
    assert format_rarity_summary(_row(rarity="common"), translator) == "C"
    assert format_rarity_summary(_row(rarity="mythic"), translator) == "M"
    assert format_rarity_summary(_row(), translator) == "—"
    assert (
        format_rarity_summary(
            _row(rarities=frozenset({"mythic", "common"})), translator
        )
        == "C, M"
    )


def test_rarity_sort_rank_curm_order() -> None:
    assert rarity_sort_rank(_row(rarity="common")) < rarity_sort_rank(
        _row(rarity="uncommon")
    )
    assert rarity_sort_rank(_row(rarity="uncommon")) < rarity_sort_rank(
        _row(rarity="rare")
    )
    assert rarity_sort_rank(_row(rarity="rare")) < rarity_sort_rank(
        _row(rarity="mythic")
    )
    # Mixed: sort by lowest rarity present (C before M).
    assert rarity_sort_rank(
        _row(rarities=frozenset({"mythic", "common"}))
    ) == rarity_sort_rank(_row(rarity="common"))
