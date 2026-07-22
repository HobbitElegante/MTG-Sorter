from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import BrowseService
from mtg_sorter.services.browse_service import InventorySummaryRow
from mtg_sorter.ui.inventory_display import format_inventory_assigned


class InventoryWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._rows: list[InventorySummaryRow] = []
        self._build_ui()
        self.refresh()

    def retranslate(self) -> None:
        self._search.setPlaceholderText(
            self._translator.t("inventory.search.collection")
        )
        self._table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.inventory.copies"),
                self._translator.t("browse.inventory.assigned"),
            ]
        )
        self._populate_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            self._translator.t("inventory.search.collection")
        )
        self._search.textChanged.connect(self._populate_table)
        layout.addWidget(self._search)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.inventory.copies"),
                self._translator.t("browse.inventory.assigned"),
            ]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def refresh(self) -> None:
        with get_session() as session:
            self._rows = BrowseService(session).list_inventory()
        self._populate_table()

    def _populate_table(self) -> None:
        rows = self._rows
        search = self._search.text().strip()
        if search:
            needle = search.casefold()
            rows = [row for row in rows if needle in row.card_name.casefold()]

        self._table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            copies_item = QTableWidgetItem(str(row.total_copies))
            copies_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(index, 0, QTableWidgetItem(row.card_name))
            self._table.setItem(index, 1, copies_item)
            self._table.setItem(
                index,
                2,
                QTableWidgetItem(format_inventory_assigned(row, self._translator)),
            )
