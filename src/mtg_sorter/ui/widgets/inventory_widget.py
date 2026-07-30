from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.algorithms.inventory_filters import filter_inventory_cards
from mtg_sorter.api.scryfall_client import ScryfallClient
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
    format_mana_value,
)
from mtg_sorter.ui.scryfall_icon import scryfall_icon
from mtg_sorter.ui.widgets.card_preview import (
    CardPreviewPanel,
    build_preview_splitter,
    card_images_enabled,
)
from mtg_sorter.ui.widgets.edition_picker import CopyEditionTable, EditionComboBox
from mtg_sorter.ui.widgets.import_dialogs import AddInventoryListDialog, QuantityStepper
from mtg_sorter.ui.widgets.inventory_filter_panel import InventoryFilterDialog

ORACLE_ID_ROLE = Qt.ItemDataRole.UserRole
SEARCH_DEBOUNCE_MS = 350
# Inventory Scryfall-syntax search (checkbox + logo). Hidden for now — local
# Filter dialog covers type / id≤ / CMC. Flip to True to re-enable the UI.
SCRYFALL_INVENTORY_SEARCH_ENABLED = False

COL_NAME = 0
COL_CMC = 1
COL_COLOR = 2
COL_EDITION = 3
COL_TOTAL = 4
COL_FREE = 5
COL_ASSIGNED = 6
COL_DECKS = 7


class InventorySearchWorker(QThread):
    finished_ok = Signal(object, object)  # query_text, oracle_ids set
    failed = Signal(object, object)  # query_text, error message

    def __init__(
        self,
        query_text: str,
        inventory_ids: set[str],
        parent: QWidget | None = None,
    ) -> None:
        # Do not parent to a QWidget — keeps thread lifetime independent of UI.
        super().__init__(parent)
        self._query_text = query_text
        self._inventory_ids = inventory_ids

    def run(self) -> None:
        client = ScryfallClient()
        try:
            oracle_ids = client.search_oracle_ids_in(
                self._query_text, self._inventory_ids, max_pages=15
            )
            if self.isInterruptionRequested():
                return
            self.finished_ok.emit(self._query_text, oracle_ids)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(self._query_text, str(exc))
        finally:
            client.close()


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
        self._search_worker: InventorySearchWorker | None = None
        self._scryfall_oracle_ids: set[str] | None = None
        self._scryfall_query_applied: str = ""
        self._scryfall_busy = False
        self._search_generation = 0
        self._ignore_scryfall_button = False
        with get_session() as session:
            settings = SettingsService(session)
            self._show_card_images = settings.get_show_card_images()
            self._track_editions = settings.get_track_editions()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._populate_table)
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
        self._update_search_placeholder()
        self._update_filter_button()
        self._filter_dialog.retranslate()
        if SCRYFALL_INVENTORY_SEARCH_ENABLED:
            self._scryfall_mode.setText(
                self._translator.t("inventory.search.scryfall_mode")
            )
            self._scryfall_mode.setToolTip(
                self._translator.t("inventory.search.scryfall_mode_tip")
            )
            self._scryfall_button.setToolTip(
                self._translator.t("inventory.search.scryfall_run")
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
        self._update_search_hint()
        self._populate_table()

    def _header_labels(self) -> list[str]:
        return [
            self._translator.t("browse.cards.name"),
            self._translator.t("inventory.table.cmc"),
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

        search_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self._search, 1)

        # Checkbox before the run button so enabling the button mid-click
        # cannot steal the mouse release (layout-shift click-through).
        self._scryfall_mode = QCheckBox()
        self._scryfall_mode.toggled.connect(self._on_scryfall_mode_toggled)
        search_row.addWidget(self._scryfall_mode)

        self._scryfall_button = QToolButton()
        # Warm both variants so the first checkbox toggle never paints.
        scryfall_icon(22, active=False)
        scryfall_icon(22, active=True)
        self._scryfall_button.setIcon(scryfall_icon(22, active=False))
        self._scryfall_button.setIconSize(QSize(28, 28))
        self._scryfall_button.setAutoRaise(True)
        self._scryfall_button.setEnabled(False)
        self._scryfall_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._scryfall_button.clicked.connect(self._run_scryfall_search)
        search_row.addWidget(self._scryfall_button)
        if not SCRYFALL_INVENTORY_SEARCH_ENABLED:
            self._scryfall_mode.hide()
            self._scryfall_button.hide()
        collection.addLayout(search_row)

        self._search_hint = QLabel("")
        self._search_hint.setWordWrap(True)
        self._search_hint.setVisible(False)
        hint_font = self._search_hint.font()
        hint_font.setPointSize(max(8, hint_font.pointSize() - 1))
        self._search_hint.setFont(hint_font)
        collection.addWidget(self._search_hint)
        if not SCRYFALL_INVENTORY_SEARCH_ENABLED:
            self._search_hint.hide()

        actions = QHBoxLayout()
        self._filter_button = QPushButton()
        self._filter_button.clicked.connect(self._open_filters)
        actions.addWidget(self._filter_button)

        self._edit_button = QPushButton()
        self._edit_button.clicked.connect(self._edit_copies)
        self._edit_button.setVisible(False)
        actions.addWidget(self._edit_button)
        actions.addStretch()

        self._add_button = QPushButton()
        self._add_button.clicked.connect(self._add_card)
        actions.addWidget(self._add_button)

        self._add_list_button = QPushButton()
        self._add_list_button.clicked.connect(self._show_add_list_section)
        actions.addWidget(self._add_list_button)
        collection.addLayout(actions)

        self._filter_dialog = InventoryFilterDialog(self._translator, self)
        self._filter_dialog.filters_changed.connect(self._on_filters_changed)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(self._header_labels())
        self._table.setColumnHidden(COL_EDITION, not self._track_editions)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        # Fixed/Interactive only — ResizeToContents rescans every cell on each
        # rebuild and freezes the UI with ~1.5k inventory rows when visible.
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_CMC, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_COLOR, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_EDITION, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_TOTAL, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_FREE, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_ASSIGNED, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(COL_DECKS, QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(60)
        header.resizeSection(COL_CMC, 56)
        header.resizeSection(COL_COLOR, 72)
        header.resizeSection(COL_EDITION, 110)
        header.resizeSection(COL_TOTAL, 64)
        header.resizeSection(COL_FREE, 64)
        header.resizeSection(COL_ASSIGNED, 80)
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

        self._add_list_group = QGroupBox()
        import_layout = QVBoxLayout(self._add_list_group)

        self._import_text = QTextEdit()
        import_layout.addWidget(self._import_text, 1)

        import_buttons = QHBoxLayout()
        self._load_file_button = QPushButton()
        self._load_file_button.clicked.connect(self._load_list_file)
        self._submit_list_button = QPushButton()
        self._submit_list_button.clicked.connect(self._confirm_add_list)
        self._cancel_list_button = QPushButton()
        self._cancel_list_button.clicked.connect(self._hide_add_list_section)
        import_buttons.addWidget(self._load_file_button)
        import_buttons.addWidget(self._submit_list_button)
        import_buttons.addWidget(self._cancel_list_button)
        import_buttons.addStretch()
        import_layout.addLayout(import_buttons)

        self._add_list_group.setVisible(False)
        self._main_layout.addWidget(self._add_list_group, 0)

        self.retranslate()
        self._update_search_placeholder()
        self._sync_scryfall_controls()

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
        if self._sort_column == COL_CMC:
            return -1.0 if row.cmc is None else float(row.cmc)
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

    def _on_search_text_changed(self) -> None:
        if (
            SCRYFALL_INVENTORY_SEARCH_ENABLED
            and self._scryfall_mode.isChecked()
        ):
            self._sync_scryfall_controls()
            current = self._search.text().strip()
            if not current:
                self._clear_scryfall_results()
                self._update_search_hint()
                self._populate_table()
            elif (
                self._scryfall_oracle_ids is not None
                and current != self._scryfall_query_applied
            ):
                # Text diverged from the last API result — wait for logo click.
                self._scryfall_oracle_ids = None
                self._scryfall_query_applied = ""
                self._update_search_hint()
                self._populate_table()
            else:
                self._update_search_hint()
            return
        self._search_timer.start()

    def _open_filters(self) -> None:
        self._filter_dialog.retranslate()
        self._filter_dialog.show()
        self._filter_dialog.raise_()
        self._filter_dialog.activateWindow()

    def _on_filters_changed(self) -> None:
        self._update_filter_button()
        self._populate_table()

    def _update_filter_button(self) -> None:
        label = self._translator.t("inventory.filters.toggle")
        if self._filter_dialog.filter_state().is_active:
            label = self._translator.t("inventory.filters.toggle_active")
        self._filter_button.setText(label)

    def _on_scryfall_mode_toggled(self, checked: bool) -> None:
        """Toggle mode only — never hits the Scryfall API here."""
        if not SCRYFALL_INVENTORY_SEARCH_ENABLED:
            return
        self._search_timer.stop()
        self._abandon_scryfall_worker()
        self._clear_scryfall_results()
        # Ignore accidental click-through onto the run button while the
        # checkbox click is still being delivered / layout is settling.
        self._ignore_scryfall_button = True
        self._scryfall_button.setEnabled(False)
        self._scryfall_button.setIcon(scryfall_icon(22, active=checked))
        self._update_search_placeholder()
        self._update_search_hint()
        # Defer so the checkbox paints before any table work.
        QTimer.singleShot(0, lambda: self._after_scryfall_mode_toggled(checked))

    def _after_scryfall_mode_toggled(self, checked: bool) -> None:
        if checked != self._scryfall_mode.isChecked():
            return
        self._ignore_scryfall_button = False
        self._sync_scryfall_controls()
        if not checked:
            # Re-apply name filter (may differ from the full list shown in mode).
            self._search_timer.start()
            return
        # Entering Scryfall mode ignores the name box until the logo runs.
        # Rebuild only when a name filter was active (otherwise the table
        # already shows the full panel-filtered collection).
        if self._search.text().strip():
            self._populate_table()

    def _update_search_placeholder(self) -> None:
        if (
            SCRYFALL_INVENTORY_SEARCH_ENABLED
            and self._scryfall_mode.isChecked()
        ):
            self._search.setPlaceholderText(
                self._translator.t("inventory.search.scryfall")
            )
        else:
            self._search.setPlaceholderText(
                self._translator.t("inventory.search.name")
            )

    def _sync_scryfall_controls(self) -> None:
        if not SCRYFALL_INVENTORY_SEARCH_ENABLED:
            return
        mode_on = self._scryfall_mode.isChecked()
        self._scryfall_button.setIcon(scryfall_icon(22, active=mode_on))
        if self._ignore_scryfall_button or self._scryfall_busy:
            self._scryfall_button.setEnabled(False)
            return
        has_query = bool(self._search.text().strip())
        self._scryfall_button.setEnabled(mode_on and has_query)

    def _clear_scryfall_results(self) -> None:
        self._scryfall_oracle_ids = None
        self._scryfall_query_applied = ""
        self._search_generation += 1

    def _abandon_scryfall_worker(self) -> None:
        worker = self._search_worker
        self._search_worker = None
        self._scryfall_busy = False
        if worker is None:
            return
        try:
            worker.finished_ok.disconnect()
        except RuntimeError:
            pass
        try:
            worker.failed.disconnect()
        except RuntimeError:
            pass
        worker.requestInterruption()
        if worker.isRunning():
            # Keep the QThread object alive until it finishes so Qt does not
            # destroy a running thread (which can wedge the process).
            worker.finished.connect(worker.deleteLater)
        else:
            worker.deleteLater()

    def _update_search_hint(self) -> None:
        if not SCRYFALL_INVENTORY_SEARCH_ENABLED:
            self._search_hint.clear()
            self._search_hint.setVisible(False)
            return
        if self._scryfall_busy:
            self._search_hint.setText(self._translator.t("inventory.search.scryfall_busy"))
            self._search_hint.setVisible(True)
            return
        if self._scryfall_mode.isChecked() and self._scryfall_query_applied:
            self._search_hint.setText(
                self._translator.t("inventory.search.scryfall_applied").format(
                    query=self._scryfall_query_applied,
                    count=len(self._scryfall_oracle_ids or ()),
                )
            )
            self._search_hint.setVisible(True)
            return
        if self._scryfall_mode.isChecked():
            self._search_hint.setText(
                self._translator.t("inventory.search.scryfall_idle")
            )
            self._search_hint.setVisible(True)
            return
        self._search_hint.clear()
        self._search_hint.setVisible(False)

    def _run_scryfall_search(self) -> None:
        if not SCRYFALL_INVENTORY_SEARCH_ENABLED:
            return
        if self._ignore_scryfall_button or self._scryfall_busy:
            return
        query_text = self._search.text().strip()
        if not query_text or not self._scryfall_mode.isChecked():
            return
        self._abandon_scryfall_worker()
        inventory_ids = {row.oracle_id for row in self._rows}
        self._search_generation += 1
        generation = self._search_generation
        self._scryfall_busy = True
        self._update_search_hint()
        self._sync_scryfall_controls()

        worker = InventorySearchWorker(query_text, inventory_ids)
        self._search_worker = worker

        def on_ok(done_query: object, oracle_ids: object) -> None:
            if generation != self._search_generation:
                return
            self._scryfall_busy = False
            self._search_worker = None
            if done_query != self._search.text().strip():
                self._sync_scryfall_controls()
                self._update_search_hint()
                return
            if not isinstance(oracle_ids, set):
                self._sync_scryfall_controls()
                self._update_search_hint()
                return
            self._scryfall_oracle_ids = oracle_ids
            self._scryfall_query_applied = str(done_query)
            self._update_search_hint()
            self._sync_scryfall_controls()
            self._populate_table()

        def on_fail(done_query: object, error: object) -> None:
            if generation != self._search_generation:
                return
            self._scryfall_busy = False
            self._search_worker = None
            self._scryfall_oracle_ids = None
            self._scryfall_query_applied = ""
            self._search_hint.setText(
                self._translator.t("inventory.search.scryfall_failed").format(
                    error=str(error)
                )
            )
            self._search_hint.setVisible(True)
            self._sync_scryfall_controls()
            self._populate_table()

        worker.finished_ok.connect(
            on_ok, Qt.ConnectionType.QueuedConnection
        )
        worker.failed.connect(on_fail, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _populate_table(self) -> None:
        scryfall_mode = (
            SCRYFALL_INVENTORY_SEARCH_ENABLED and self._scryfall_mode.isChecked()
        )
        name_query = "" if scryfall_mode else self._search.text()
        scryfall_ids = self._scryfall_oracle_ids if scryfall_mode else None
        # In Scryfall mode with no query run yet, show the full collection
        # (still panel-filtered). After a query, intersect.
        filtered = filter_inventory_cards(
            self._rows,
            name_query=name_query,
            panel=self._filter_dialog.filter_state(),
            scryfall_oracle_ids=scryfall_ids,
        )
        rows = sorted(
            filtered, key=self._sort_key, reverse=not self._sort_ascending
        )
        self._visible_rows = list(rows)

        table = self._table
        header = table.horizontalHeader()
        # Guard: if any column is still ResizeToContents, pin it Fixed for the
        # bulk insert — otherwise Qt measures every cell and freezes (~1.5k rows).
        pinned: list[tuple[int, int]] = []
        for col in range(table.columnCount()):
            mode = header.sectionResizeMode(col)
            if mode == QHeaderView.ResizeMode.ResizeToContents:
                pinned.append((col, header.sectionSize(col)))
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)

        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                assigned = row.total_copies - row.free_copies
                decks_text = format_inventory_decks(row, self._translator)
                color_text = format_color_identity(
                    row.color_identity, self._translator
                )

                name_item = QTableWidgetItem(row.card_name)
                name_item.setData(ORACLE_ID_ROLE, row.oracle_id)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                cmc_item = QTableWidgetItem(
                    format_mana_value(row.cmc, self._translator)
                )
                cmc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                cmc_item.setFlags(cmc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                color_item = QTableWidgetItem(color_text)
                color_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                color_item.setFlags(
                    color_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )

                edition_item = QTableWidgetItem(format_edition_summary(row))
                edition_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                edition_item.setFlags(
                    edition_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )

                total_item = QTableWidgetItem(str(row.total_copies))
                total_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                total_item.setFlags(
                    total_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )

                free_item = QTableWidgetItem(str(row.free_copies))
                free_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                free_item.setFlags(free_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                assigned_item = QTableWidgetItem(str(assigned))
                assigned_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                assigned_item.setFlags(
                    assigned_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )

                decks_item = QTableWidgetItem(decks_text)
                decks_item.setFlags(
                    decks_item.flags() & ~Qt.ItemFlag.ItemIsEditable
                )
                if row.assigned_decks:
                    decks_item.setToolTip("\n".join(row.assigned_decks))

                table.setItem(index, COL_NAME, name_item)
                table.setItem(index, COL_CMC, cmc_item)
                table.setItem(index, COL_COLOR, color_item)
                table.setItem(index, COL_EDITION, edition_item)
                table.setItem(index, COL_TOTAL, total_item)
                table.setItem(index, COL_FREE, free_item)
                table.setItem(index, COL_ASSIGNED, assigned_item)
                table.setItem(index, COL_DECKS, decks_item)
        finally:
            for col, width in pinned:
                header.resizeSection(col, width)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
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
                if any(
                    host in text.casefold()
                    for host in ("moxfield", "archidekt")
                )
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
