from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import BrowseService, InventoryService
from mtg_sorter.services.browse_service import CardSummary, InventorySummaryRow
from mtg_sorter.ui.inventory_display import format_inventory_assigned
from mtg_sorter.ui.widgets.import_dialogs import QuantityStepper

ORACLE_ID_ROLE = Qt.ItemDataRole.UserRole


class AddInventoryCardDialog(QDialog):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._results: list[CardSummary] = []
        self._selected: CardSummary | None = None
        self._quantity = 0
        self.setWindowTitle(self._translator.t("inventory.add_dialog.title"))
        self.resize(560, 480)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            self._translator.t("inventory.add_dialog.search")
        )
        self._search.textChanged.connect(self._refresh_results)
        self._search.returnPressed.connect(self._refresh_results)
        layout.addWidget(self._search)

        self._results_list = QListWidget()
        layout.addWidget(self._results_list)

        form = QFormLayout()
        self._qty = QuantityStepper(99)
        self._qty.setMinimum(1)
        self._qty.setValue(1)
        form.addRow(self._translator.t("inventory.add_dialog.copies"), self._qty)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(self._translator.t("inventory.add_dialog.confirm"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_results(self) -> None:
        search = self._search.text().strip()
        with get_session() as session:
            cards = BrowseService(session).list_cards(search) if search else []
        self._results = [
            card
            for card in cards
            if not card.is_token and not card.is_basic_land
        ][:80]
        self._results_list.clear()
        for card in self._results:
            owned = f" · {card.copy_count}" if card.copy_count else ""
            self._results_list.addItem(f"{card.name}{owned}")

    def _selected_card(self) -> CardSummary | None:
        row = self._results_list.currentRow()
        if row < 0 or row >= len(self._results):
            return None
        return self._results[row]

    def _accept(self) -> None:
        card = self._selected_card()
        if card is None:
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                self._translator.t("inventory.add_dialog.no_selection"),
            )
            return
        self._selected = card
        self._quantity = self._qty.value()
        self.accept()

    def selected_card(self) -> CardSummary | None:
        return self._selected

    def quantity(self) -> int:
        return self._quantity


class EditInventoryCopiesDialog(QDialog):
    def __init__(
        self,
        translator: Translator,
        row: InventorySummaryRow,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._row = row
        self._total = row.total_copies
        assigned = row.total_copies - row.free_copies
        self.setWindowTitle(self._translator.t("inventory.edit_dialog.title"))
        self.resize(420, 200)
        self._build_ui(assigned)

    def _build_ui(self, assigned: int) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.addRow(
            self._translator.t("inventory.edit_dialog.card"),
            QLabel(self._row.card_name),
        )
        self._qty = QuantityStepper(max(self._row.total_copies + 99, assigned + 99))
        self._qty.setMinimum(assigned)
        self._qty.setValue(self._row.total_copies)
        form.addRow(self._translator.t("inventory.edit_dialog.total"), self._qty)
        layout.addLayout(form)

        if assigned > 0:
            note = QLabel(
                self._translator.t("inventory.edit_dialog.assigned_note").format(
                    count=assigned
                )
            )
            note.setWordWrap(True)
            layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self._total = self._qty.value()
        self.accept()

    def total_copies(self) -> int:
        return self._total


class InventoryWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._rows: list[InventorySummaryRow] = []
        self._visible_rows: list[InventorySummaryRow] = []
        self._build_ui()
        self.refresh()

    def retranslate(self) -> None:
        self._search.setPlaceholderText(
            self._translator.t("inventory.search.collection")
        )
        self._add_button.setText(self._translator.t("inventory.add_new"))
        self._edit_button.setText(self._translator.t("inventory.edit_copies"))
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

        actions = QHBoxLayout()
        self._add_button = QPushButton(self._translator.t("inventory.add_new"))
        self._add_button.clicked.connect(self._add_card)
        actions.addWidget(self._add_button)

        self._edit_button = QPushButton(self._translator.t("inventory.edit_copies"))
        self._edit_button.clicked.connect(self._edit_copies)
        self._edit_button.setVisible(False)
        actions.addWidget(self._edit_button)
        actions.addStretch()
        layout.addLayout(actions)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.inventory.copies"),
                self._translator.t("browse.inventory.assigned"),
            ]
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._sync_edit_button)
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
        self._visible_rows = rows

        self._table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            name_item = QTableWidgetItem(row.card_name)
            name_item.setData(ORACLE_ID_ROLE, row.oracle_id)
            copies_item = QTableWidgetItem(str(row.total_copies))
            copies_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(index, 0, name_item)
            self._table.setItem(index, 1, copies_item)
            self._table.setItem(
                index,
                2,
                QTableWidgetItem(format_inventory_assigned(row, self._translator)),
            )
        self._sync_edit_button()

    def _selected_row(self) -> InventorySummaryRow | None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self._visible_rows):
            return None
        return self._visible_rows[index]

    def _sync_edit_button(self) -> None:
        self._edit_button.setVisible(self._selected_row() is not None)

    def _add_card(self) -> None:
        dialog = AddInventoryCardDialog(self._translator, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        card = dialog.selected_card()
        quantity = dialog.quantity()
        if card is None or quantity <= 0:
            return
        try:
            with get_session() as session:
                InventoryService(session).add_copy(card.oracle_id, quantity)
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return
        self.refresh()
        self.changed.emit()

    def _edit_copies(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        dialog = EditInventoryCopiesDialog(self._translator, row, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with get_session() as session:
                InventoryService(session).set_total_copies(
                    row.oracle_id, dialog.total_copies()
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return
        self.refresh()
        self.changed.emit()
