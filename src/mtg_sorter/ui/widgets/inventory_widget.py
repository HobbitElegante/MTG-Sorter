from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.config import UNSPECIFIED_EDITION_LABEL
from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import (
    BrowseService,
    ImportService,
    InventoryService,
    ScryfallService,
    SettingsService,
)
from mtg_sorter.services.browse_service import CardSummary, InventorySummaryRow
from mtg_sorter.services.deck_service import CopyDetail
from mtg_sorter.ui.inventory_display import (
    format_color_identity,
    format_edition_summary,
    format_inventory_decks,
)
from mtg_sorter.ui.widgets.card_preview import (
    CardPreviewPanel,
    build_preview_splitter,
    card_images_enabled,
)
from mtg_sorter.ui.widgets.edition_picker import CopyEditionTable, EditionComboBox
from mtg_sorter.ui.widgets.import_dialogs import AddInventoryListDialog, QuantityStepper

ORACLE_ID_ROLE = Qt.ItemDataRole.UserRole

COL_NAME = 0
COL_COLOR = 1
COL_EDITION = 2
COL_TOTAL = 3
COL_FREE = 4
COL_ASSIGNED = 5
COL_DECKS = 6


class AddInventoryCardDialog(QDialog):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._results: list[CardSummary] = []
        self._selected: CardSummary | None = None
        self._quantity = 0
        self.setWindowTitle(self._translator.t("inventory.add_dialog.title"))
        self._preview: CardPreviewPanel | None = None
        self.resize(880 if card_images_enabled() else 560, 520)
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
        self._results_list.currentRowChanged.connect(self._on_result_selected)
        if card_images_enabled():
            self._preview = CardPreviewPanel(self._translator)
            layout.addWidget(build_preview_splitter(self._results_list, self._preview))
        else:
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

    def _on_result_selected(self) -> None:
        if self._preview is None:
            return
        card = self._selected_card()
        if card is None:
            self._preview.clear()
        else:
            self._preview.set_card(card.oracle_id, card.name)

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
        copies: list[CopyDetail] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._row = row
        self._total = row.total_copies
        self._copies = copies or []
        self._editions: dict[int, str | None] = {}
        assigned = row.total_copies - row.free_copies
        self.setWindowTitle(self._translator.t("inventory.edit_dialog.title"))
        self.resize(480, 420 if self._copies else 200)
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

        self._edition_table: CopyEditionTable | None = None
        if self._copies:
            group = QGroupBox(self._translator.t("inventory.editions.title"))
            group_layout = QVBoxLayout(group)
            hint = QLabel(self._translator.t("inventory.editions.hint"))
            hint.setWordWrap(True)
            group_layout.addWidget(hint)

            self._edition_table = CopyEditionTable(self._translator)
            self._edition_table.set_copies(
                [
                    (
                        copy.copy_id,
                        copy.oracle_id,
                        self._copy_label(number, copy),
                        copy.edition,
                    )
                    for number, copy in enumerate(self._copies, start=1)
                ]
            )
            group_layout.addWidget(self._edition_table, 1)

            apply_row = QHBoxLayout()
            self._apply_all_combo = EditionComboBox(
                self._row.oracle_id, None, self._translator
            )
            self._apply_all_button = QPushButton(
                self._translator.t("inventory.editions.apply_all")
            )
            self._apply_all_button.clicked.connect(self._apply_edition_to_all)
            apply_row.addWidget(self._apply_all_combo, 1)
            apply_row.addWidget(self._apply_all_button)
            group_layout.addLayout(apply_row)
            layout.addWidget(group, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _copy_label(self, number: int, copy: CopyDetail) -> str:
        where = copy.deck_name or self._translator.t("browse.inventory.free")
        return self._translator.t("inventory.editions.copy_label").format(
            number=number, where=where
        )

    def _apply_edition_to_all(self) -> None:
        if self._edition_table is not None:
            self._edition_table.apply_to_all(self._apply_all_combo.edition())

    def _accept(self) -> None:
        self._total = self._qty.value()
        if self._edition_table is not None:
            self._editions = self._edition_table.editions()
        self.accept()

    def total_copies(self) -> int:
        return self._total

    def copy_editions(self) -> dict[int, str | None]:
        return self._editions


class InventoryWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._rows: list[InventorySummaryRow] = []
        self._visible_rows: list[InventorySummaryRow] = []
        self._sort_column = COL_NAME
        self._sort_ascending = True
        with get_session() as session:
            settings = SettingsService(session)
            self._show_card_images = settings.get_show_card_images()
            self._track_editions = settings.get_track_editions()
        self._build_ui()
        self.refresh()

    def set_show_card_images(self, enabled: bool) -> None:
        self._show_card_images = enabled
        self._preview.setVisible(enabled)

    def set_track_editions(self, enabled: bool) -> None:
        self._track_editions = enabled
        self._table.setColumnHidden(COL_EDITION, not enabled)
        if self._sort_column == COL_EDITION and not enabled:
            self._sort_column = COL_NAME
            self._sort_ascending = True
        self.refresh()

    def retranslate(self) -> None:
        self._search.setPlaceholderText(
            self._translator.t("inventory.search.collection")
        )
        self._add_button.setText(self._translator.t("inventory.add_new"))
        self._add_list_button.setText(self._translator.t("inventory.add_list"))
        self._edit_button.setText(self._translator.t("inventory.edit_copies"))
        self._add_list_group.setTitle(self._translator.t("inventory.add_list.title"))
        self._import_text.setPlaceholderText(
            self._translator.t("inventory.add_list.placeholder")
        )
        self._load_file_button.setText(self._translator.t("decks.load_file"))
        self._submit_list_button.setText(self._translator.t("decks.submit_import"))
        self._cancel_list_button.setText(self._translator.t("decks.cancel_import"))
        self._table.setHorizontalHeaderLabels(self._header_labels())
        self._preview.retranslate()
        self._populate_table()

    def _header_labels(self) -> list[str]:
        return [
            self._translator.t("browse.cards.name"),
            self._translator.t("inventory.table.color"),
            self._translator.t("inventory.table.edition"),
            self._translator.t("inventory.table.total"),
            self._translator.t("inventory.table.free"),
            self._translator.t("inventory.table.assigned"),
            self._translator.t("inventory.table.decks"),
        ]

    def _build_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)

        self._collection_panel = QWidget()
        collection = QVBoxLayout(self._collection_panel)
        collection.setContentsMargins(0, 0, 0, 0)

        self._search = QLineEdit()
        self._search.setPlaceholderText(
            self._translator.t("inventory.search.collection")
        )
        self._search.textChanged.connect(self._populate_table)
        collection.addWidget(self._search)

        actions = QHBoxLayout()
        self._add_button = QPushButton(self._translator.t("inventory.add_new"))
        self._add_button.clicked.connect(self._add_card)
        actions.addWidget(self._add_button)

        self._add_list_button = QPushButton(self._translator.t("inventory.add_list"))
        self._add_list_button.clicked.connect(self._show_add_list_section)
        actions.addWidget(self._add_list_button)

        self._edit_button = QPushButton(self._translator.t("inventory.edit_copies"))
        self._edit_button.clicked.connect(self._edit_copies)
        self._edit_button.setVisible(False)
        actions.addWidget(self._edit_button)
        actions.addStretch()
        collection.addLayout(actions)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(self._header_labels())
        self._table.setColumnHidden(COL_EDITION, not self._track_editions)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_COLOR, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            COL_EDITION, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(COL_TOTAL, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_FREE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            COL_ASSIGNED, QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(COL_DECKS, QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(60)
        header.resizeSection(COL_DECKS, 220)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(COL_NAME, Qt.SortOrder.AscendingOrder)
        header.sectionClicked.connect(self._on_header_clicked)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        self._preview = CardPreviewPanel(self._translator)
        self._preview.setVisible(self._show_card_images)
        collection.addWidget(build_preview_splitter(self._table, self._preview))

        self._main_layout.addWidget(self._collection_panel, 1)

        self._add_list_group = QGroupBox(self._translator.t("inventory.add_list.title"))
        import_layout = QVBoxLayout(self._add_list_group)

        self._import_text = QTextEdit()
        self._import_text.setPlaceholderText(
            self._translator.t("inventory.add_list.placeholder")
        )
        import_layout.addWidget(self._import_text, 1)

        import_buttons = QHBoxLayout()
        self._load_file_button = QPushButton(self._translator.t("decks.load_file"))
        self._load_file_button.clicked.connect(self._load_list_file)
        self._submit_list_button = QPushButton(
            self._translator.t("decks.submit_import")
        )
        self._submit_list_button.clicked.connect(self._confirm_add_list)
        self._cancel_list_button = QPushButton(
            self._translator.t("decks.cancel_import")
        )
        self._cancel_list_button.clicked.connect(self._hide_add_list_section)
        import_buttons.addWidget(self._load_file_button)
        import_buttons.addWidget(self._submit_list_button)
        import_buttons.addWidget(self._cancel_list_button)
        import_buttons.addStretch()
        import_layout.addLayout(import_buttons)

        self._add_list_group.setVisible(False)
        self._main_layout.addWidget(self._add_list_group, 0)

    def _show_add_list_section(self) -> None:
        self._collection_panel.setVisible(False)
        self._add_list_group.setVisible(True)
        self._main_layout.setStretchFactor(self._collection_panel, 0)
        self._main_layout.setStretchFactor(self._add_list_group, 1)
        self._import_text.setFocus()

    def _hide_add_list_section(self) -> None:
        self._add_list_group.setVisible(False)
        self._collection_panel.setVisible(True)
        self._main_layout.setStretchFactor(self._add_list_group, 0)
        self._main_layout.setStretchFactor(self._collection_panel, 1)

    def refresh(self) -> None:
        with get_session() as session:
            self._rows = BrowseService(session).list_inventory(
                include_editions=self._track_editions
            )
        self._populate_table()

    def _on_header_clicked(self, column: int) -> None:
        if column == self._sort_column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            # Numbers: high → low first; text: A → Z first
            self._sort_ascending = column in (
                COL_NAME,
                COL_COLOR,
                COL_EDITION,
                COL_DECKS,
            )
        header = self._table.horizontalHeader()
        order = (
            Qt.SortOrder.AscendingOrder
            if self._sort_ascending
            else Qt.SortOrder.DescendingOrder
        )
        header.setSortIndicator(column, order)
        self._populate_table()

    def _sort_key(self, row: InventorySummaryRow):
        assigned = row.total_copies - row.free_copies
        if self._sort_column == COL_NAME:
            return row.card_name.casefold()
        if self._sort_column == COL_COLOR:
            return (row.color_identity or "").casefold()
        if self._sort_column == COL_EDITION:
            return format_edition_summary(row).casefold()
        if self._sort_column == COL_TOTAL:
            return row.total_copies
        if self._sort_column == COL_FREE:
            return row.free_copies
        if self._sort_column == COL_ASSIGNED:
            return assigned
        if self._sort_column == COL_DECKS:
            return ", ".join(row.assigned_decks).casefold()
        return row.card_name.casefold()

    def _populate_table(self) -> None:
        rows = self._rows
        search = self._search.text().strip()
        if search:
            needle = search.casefold()
            rows = [row for row in rows if needle in row.card_name.casefold()]
        rows = sorted(rows, key=self._sort_key, reverse=not self._sort_ascending)
        self._visible_rows = rows

        self._table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            assigned = row.total_copies - row.free_copies
            decks_text = format_inventory_decks(row, self._translator)
            color_text = format_color_identity(row.color_identity, self._translator)

            name_item = QTableWidgetItem(row.card_name)
            name_item.setData(ORACLE_ID_ROLE, row.oracle_id)

            color_item = QTableWidgetItem(color_text)
            color_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            edition_item = QTableWidgetItem(format_edition_summary(row))
            edition_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            total_item = QTableWidgetItem(str(row.total_copies))
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            free_item = QTableWidgetItem(str(row.free_copies))
            free_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            assigned_item = QTableWidgetItem(str(assigned))
            assigned_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            decks_item = QTableWidgetItem(decks_text)
            if row.assigned_decks:
                decks_item.setToolTip("\n".join(row.assigned_decks))

            self._table.setItem(index, COL_NAME, name_item)
            self._table.setItem(index, COL_COLOR, color_item)
            self._table.setItem(index, COL_EDITION, edition_item)
            self._table.setItem(index, COL_TOTAL, total_item)
            self._table.setItem(index, COL_FREE, free_item)
            self._table.setItem(index, COL_ASSIGNED, assigned_item)
            self._table.setItem(index, COL_DECKS, decks_item)
        self._on_selection_changed()

    def _selected_row(self) -> InventorySummaryRow | None:
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return None
        index = selected[0].row()
        if index < 0 or index >= len(self._visible_rows):
            return None
        return self._visible_rows[index]

    def _on_selection_changed(self) -> None:
        row = self._selected_row()
        self._edit_button.setVisible(row is not None)
        if row is None:
            self._preview.clear()
        else:
            self._preview.set_card(row.oracle_id, row.card_name)

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

    def _load_list_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translator.t("inventory.add_list.dialog_title"),
            str(Path.home()),
            "Text files (*.txt *.dek);;MTGO decks (*.dek);;All files (*)",
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return
        self._import_text.setPlainText(content)

    def _confirm_add_list(self) -> None:
        text = self._import_text.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self,
                self._translator.t("inventory.add_list.title"),
                self._translator.t("inventory.add_list.empty"),
            )
            return

        try:
            with get_session() as session:
                scryfall = ScryfallService(session)
                try:
                    preview = ImportService(
                        session, scryfall
                    ).preview_inventory_list(text)
                finally:
                    scryfall.close()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                self._translator.t("inventory.add_list.url_failed").format(
                    error=str(exc)
                )
                if "moxfield" in text.casefold()
                else str(exc),
            )
            return

        if not preview.identified and not preview.unresolved_lines:
            QMessageBox.information(
                self,
                self._translator.t("inventory.add_list.title"),
                self._translator.t("inventory.add_list.empty"),
            )
            return

        dialog = AddInventoryListDialog(
            self._translator,
            preview.identified,
            preview.unresolved_lines,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        quantities = dialog.quantities()
        if not quantities:
            return
        set_codes = dialog.set_codes() if self._track_editions else {}
        try:
            with get_session() as session:
                inventory = InventoryService(session)
                for oracle_id, quantity in quantities.items():
                    inventory.add_copy(
                        oracle_id, quantity, edition=set_codes.get(oracle_id)
                    )
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        self._import_text.clear()
        self._hide_add_list_section()
        self.refresh()
        self.changed.emit()

    def _edit_copies(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        copies: list[CopyDetail] = []
        if self._track_editions:
            with get_session() as session:
                copies = InventoryService(session).list_copies_with_deck(row.oracle_id)
        dialog = EditInventoryCopiesDialog(self._translator, row, copies, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with get_session() as session:
                inventory = InventoryService(session)
                editions = dialog.copy_editions()
                if editions:
                    inventory.set_copy_editions(editions)
                inventory.set_total_copies(row.oracle_id, dialog.total_copies())
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return
        self.refresh()
        self.changed.emit()
