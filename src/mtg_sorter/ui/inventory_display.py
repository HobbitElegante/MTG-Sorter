from mtg_sorter.algorithms.card_utils import is_commander_legality_issue
from mtg_sorter.algorithms.commander_rules import CommanderRuleIssue, CommanderRuleKind
from mtg_sorter.config import UNSPECIFIED_EDITION_LABEL
from mtg_sorter.i18n import Translator
from mtg_sorter.services.browse_service import InventorySummaryRow
from mtg_sorter.services.deck_service import CommanderLegalityIssue


def format_color_identity(
    color_identity: str | None, translator: Translator
) -> str:
    """WUBRG string from Scryfall, or an empty-state placeholder."""
    if not color_identity:
        return translator.t("inventory.table.colorless")
    return color_identity


def format_edition_summary(row: InventorySummaryRow) -> str:
    """One set code when they all match, otherwise a per-edition breakdown."""
    if not row.editions:
        return UNSPECIFIED_EDITION_LABEL
    if len(row.editions) == 1:
        code, _ = row.editions[0]
        return code or UNSPECIFIED_EDITION_LABEL
    return ", ".join(
        f"{code or UNSPECIFIED_EDITION_LABEL} x{count}" for code, count in row.editions
    )


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


def format_commander_legality_label(legality: str, translator: Translator) -> str:
    key = f"decks.legality.{legality.casefold()}"
    label = translator.t(key)
    # Translator returns the key itself when missing in some setups; fall back.
    if label == key:
        return legality
    return label


def format_commander_legality_tooltip(
    issues: list[CommanderLegalityIssue], translator: Translator
) -> str:
    if not issues:
        return ""
    header = translator.t("decks.legality.tooltip_header")
    lines = [
        translator.t("decks.legality.tooltip_line").format(
            name=issue.name,
            status=format_commander_legality_label(issue.legality, translator),
        )
        for issue in issues
    ]
    return header + "\n" + "\n".join(lines)


def format_commander_rules_tooltip(
    issues: list[CommanderRuleIssue], translator: Translator
) -> str:
    if not issues:
        return ""
    colorless = translator.t("decks.rules.colorless")
    lines = []
    for issue in issues:
        if issue.kind is CommanderRuleKind.COLOR_IDENTITY:
            lines.append(
                translator.t("decks.rules.color_identity").format(
                    name=issue.name,
                    colors=issue.colors or colorless,
                    allowed=issue.allowed or colorless,
                )
            )
        elif issue.kind is CommanderRuleKind.PAIRING:
            lines.append(
                translator.t("decks.rules.pairing").format(
                    name=issue.name,
                    commander=issue.commander,
                )
            )
        elif issue.kind is CommanderRuleKind.SINGLETON:
            lines.append(
                translator.t("decks.rules.singleton").format(
                    name=issue.name,
                    qty=issue.quantity,
                    limit=issue.allowed or "1",
                )
            )
        elif issue.kind is CommanderRuleKind.DECK_SIZE:
            lines.append(
                translator.t("decks.rules.deck_size").format(
                    count=issue.name,
                    expected=issue.allowed or "100",
                )
            )
        else:
            lines.append(
                translator.t("decks.rules.missing_data").format(name=issue.name)
            )
    header = translator.t("decks.rules.tooltip_header")
    return header + "\n" + "\n".join(lines)


def format_deck_warning_tooltip(
    legality_issues: list[CommanderLegalityIssue],
    rule_issues: list[CommanderRuleIssue],
    translator: Translator,
) -> str:
    """Both advisory checks share one ⚠, so their tooltips are stacked."""
    blocks = [
        format_commander_legality_tooltip(legality_issues, translator),
        format_commander_rules_tooltip(rule_issues, translator),
    ]
    return "\n\n".join(block for block in blocks if block)


def format_card_legality_tooltip(
    name: str, legality: str | None, translator: Translator
) -> str:
    if not is_commander_legality_issue(legality):
        return ""
    assert legality is not None
    return translator.t("decks.legality.card_tooltip").format(
        name=name,
        status=format_commander_legality_label(legality, translator),
    )
