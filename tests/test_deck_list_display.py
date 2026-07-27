from mtg_sorter.models.enums import DeckStatus
from mtg_sorter.ui.deck_list_display import (
    DeckListRow,
    filter_deck_rows,
    sort_deck_rows,
)


def _row(
    deck_id: int,
    name: str,
    status: DeckStatus,
    sort_order: int,
    *,
    commander: str | None = None,
) -> DeckListRow:
    return DeckListRow(
        id=deck_id,
        name=name,
        status=status,
        sort_order=sort_order,
        is_locked=False,
        commander_name=commander,
        has_warning=False,
        tooltip="",
    )


def test_filter_deck_rows_by_status_and_search() -> None:
    rows = [
        _row(1, "Alpha", DeckStatus.ARMED, 0, commander="Kellan"),
        _row(2, "Bravo", DeckStatus.DISMANTLED, 1, commander="Anje"),
        _row(3, "Charlie", DeckStatus.ARMED, 2, commander="Ghen"),
    ]
    armed = filter_deck_rows(rows, status=DeckStatus.ARMED, needle="")
    assert [r.name for r in armed] == ["Alpha", "Charlie"]

    by_commander = filter_deck_rows(rows, status=None, needle="anje")
    assert [r.name for r in by_commander] == ["Bravo"]

    by_name = filter_deck_rows(rows, status=DeckStatus.ARMED, needle="char")
    assert [r.name for r in by_name] == ["Charlie"]


def test_sort_deck_rows_number_name_status() -> None:
    rows = [
        _row(1, "Charlie", DeckStatus.ARMED, 2),
        _row(2, "Alpha", DeckStatus.DISMANTLED, 0),
        _row(3, "Bravo", DeckStatus.ARMED, 1),
    ]

    by_number = sort_deck_rows(
        rows,
        key="number",
        ascending=True,
        status_label=lambda s: s.value,
    )
    assert [r.name for r in by_number] == ["Alpha", "Bravo", "Charlie"]

    by_name_desc = sort_deck_rows(
        rows,
        key="name",
        ascending=False,
        status_label=lambda s: s.value,
    )
    assert [r.name for r in by_name_desc] == ["Charlie", "Bravo", "Alpha"]

    def label(status: DeckStatus) -> str:
        return "Armado" if status == DeckStatus.ARMED else "Desarmado"

    by_status = sort_deck_rows(
        rows, key="status", ascending=True, status_label=label
    )
    assert [r.name for r in by_status] == ["Charlie", "Bravo", "Alpha"]
