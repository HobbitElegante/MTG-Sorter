from mtg_sorter.algorithms.inventory_query import (
    build_online_search_query,
    filter_inventory_rows,
    matches_local_query,
    parse_inventory_query,
)
from mtg_sorter.services.browse_service import InventorySummaryRow


def _row(
    *,
    name: str = "Lightning Bolt",
    oracle_id: str = "bolt",
    type_line: str = "Instant",
    colors: str | None = "R",
    color_identity: str | None = "R",
    cmc: float | None = 1,
    oracle_text: str | None = "Lightning Bolt deals 3 damage to any target.",
    commander_legality: str | None = "legal",
    is_basic_land: bool = False,
    is_token: bool = False,
) -> InventorySummaryRow:
    return InventorySummaryRow(
        oracle_id=oracle_id,
        card_name=name,
        total_copies=1,
        free_copies=1,
        assigned_decks=(),
        color_identity=color_identity,
        type_line=type_line,
        colors=colors,
        cmc=cmc,
        oracle_text=oracle_text,
        commander_legality=commander_legality,
        is_basic_land=is_basic_land,
        is_token=is_token,
    )


def test_parse_classifies_local_and_online_tokens() -> None:
    parsed = parse_inventory_query('t:creature c:r set:mh3 o:"draw a card"')
    kinds = {token.raw: token.kind for token in parsed.tokens}
    assert kinds["t:creature"] == "local"
    assert kinds["c:r"] == "local"
    assert kinds["set:mh3"] == "online"
    assert kinds['o:"draw a card"'] == "local"
    assert build_online_search_query(parsed) == "set:mh3"


def test_local_filters_type_color_cmc_name() -> None:
    bolt = _row()
    bird = _row(
        name="Birds of Paradise",
        oracle_id="bop",
        type_line="Creature — Bird",
        colors="G",
        color_identity="G",
        cmc=1,
        oracle_text="{T}: Add one mana of any color.",
    )
    parsed = parse_inventory_query("t:instant c:r cmc=1 bolt")
    assert matches_local_query(bolt, parsed)
    assert not matches_local_query(bird, parsed)


def test_filter_intersects_online_ids() -> None:
    bolt = _row()
    bird = _row(name="Birds of Paradise", oracle_id="bop", type_line="Creature — Bird")
    parsed = parse_inventory_query("set:lea")
    hits = filter_inventory_rows([bolt, bird], parsed, online_oracle_ids={"bolt"})
    assert [row.oracle_id for row in hits] == ["bolt"]


def test_offline_online_tokens_skipped_keeps_local_only() -> None:
    bolt = _row()
    parsed = parse_inventory_query("c:r set:mh3")
    # No online intersection → local filters only.
    hits = filter_inventory_rows([bolt], parsed)
    assert [row.oracle_id for row in hits] == ["bolt"]
    assert parsed.online_raw == ("set:mh3",)
