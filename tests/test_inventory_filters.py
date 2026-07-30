"""Tests for inventory panel filters (type / id<= colors / CMC)."""

from mtg_sorter.algorithms.inventory_filters import (
    CmcCondition,
    InventoryFilterState,
    filter_inventory_cards,
    matches_color_identity_at_most,
    matches_panel_filters,
    matches_type_line,
)
from mtg_sorter.services.browse_service import InventorySummaryRow


def _row(
    *,
    name: str = "Lightning Bolt",
    oracle_id: str = "bolt",
    type_line: str = "Instant",
    color_identity: str | None = "R",
    cmc: float | None = 1,
) -> InventorySummaryRow:
    return InventorySummaryRow(
        oracle_id=oracle_id,
        card_name=name,
        total_copies=1,
        free_copies=1,
        assigned_decks=(),
        color_identity=color_identity,
        type_line=type_line,
        cmc=cmc,
    )


def test_color_at_most_includes_subsets_and_colorless() -> None:
    allowed = frozenset({"R", "B"})
    assert matches_color_identity_at_most("R", allowed)
    assert matches_color_identity_at_most("B", allowed)
    assert matches_color_identity_at_most("RB", allowed)
    assert matches_color_identity_at_most("BR", allowed)
    assert matches_color_identity_at_most("", allowed)
    assert matches_color_identity_at_most(None, allowed)
    assert not matches_color_identity_at_most("RBG", allowed)
    assert not matches_color_identity_at_most("W", allowed)


def test_color_filter_inactive_when_empty_or_all_five() -> None:
    assert not InventoryFilterState(colors=frozenset()).color_filter_active
    assert not InventoryFilterState(
        colors=frozenset("WUBRG")
    ).color_filter_active
    assert InventoryFilterState(colors=frozenset({"R", "B"})).color_filter_active


def test_type_match_is_or_across_selected() -> None:
    assert matches_type_line("Creature — Elf Druid", frozenset({"Creature"}))
    assert matches_type_line("Legendary Creature — Human", frozenset({"Legendary"}))
    assert matches_type_line("Artifact Creature — Construct", frozenset({"Instant", "Artifact"}))
    assert not matches_type_line("Instant", frozenset({"Creature", "Sorcery"}))


def test_cmc_multiple_conditions_and() -> None:
    bolt = _row(cmc=1)
    state = InventoryFilterState(
        cmc_conditions=(
            CmcCondition(">=", 1),
            CmcCondition("<=", 2),
        )
    )
    assert matches_panel_filters(bolt, state)
    assert not matches_panel_filters(
        _row(name="Big", oracle_id="big", cmc=5), state
    )


def test_filter_combines_name_panel_and_scryfall_ids() -> None:
    bolt = _row()
    bird = _row(
        name="Birds of Paradise",
        oracle_id="bop",
        type_line="Creature — Bird",
        color_identity="G",
        cmc=1,
    )
    wrath = _row(
        name="Wrath of God",
        oracle_id="wrath",
        type_line="Sorcery",
        color_identity="W",
        cmc=4,
    )
    panel = InventoryFilterState(types=frozenset({"Instant", "Sorcery"}))
    hits = filter_inventory_cards(
        [bolt, bird, wrath],
        name_query="o",
        panel=panel,
        scryfall_oracle_ids={"bolt", "bop", "wrath"},
    )
    assert [row.oracle_id for row in hits] == ["bolt", "wrath"]
