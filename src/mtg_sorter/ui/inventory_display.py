from mtg_sorter.i18n import Translator
from mtg_sorter.services.browse_service import InventorySummaryRow


def format_color_identity(
    color_identity: str | None, translator: Translator
) -> str:
    """WUBRG string from Scryfall, or an empty-state placeholder."""
    if not color_identity:
        return translator.t("inventory.table.colorless")
    return color_identity


def format_inventory_decks(row: InventorySummaryRow, translator: Translator) -> str:
    """Deck names that hold assigned copies, or an empty-state placeholder."""
    if not row.assigned_decks:
        return translator.t("inventory.table.no_decks")
    return ", ".join(row.assigned_decks)


def format_inventory_assigned(row: InventorySummaryRow, translator: Translator) -> str:
    """Legacy mixed cell (kept for tests / callers that still need the blend)."""
    if row.free_copies == row.total_copies:
        return translator.t("browse.inventory.free")
    if row.free_copies == 0:
        return ", ".join(row.assigned_decks)
    if not row.assigned_decks:
        return translator.t("browse.inventory.free")
    return translator.t("browse.inventory.mixed").format(
        free=row.free_copies,
        decks=", ".join(row.assigned_decks),
    )


def format_availability_status(row: InventorySummaryRow, translator: Translator) -> str:
    if row.free_copies > 0:
        return translator.t("inventory.status.available").format(count=row.free_copies)
    return translator.t("inventory.status.unavailable").format(count=row.total_copies)
