from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import BrowseService, ScryfallBulkService
from mtg_sorter.ui.inventory_display import (
    format_availability_status,
    format_inventory_assigned,
)


class BulkSyncWorker(QThread):
    progress = Signal(str)
    finished_ok = Signal(int)
    failed = Signal(str)

    def run(self) -> None:
        try:
            with get_session() as session:
                bulk = ScryfallBulkService(session)
                try:
                    result = bulk.sync_oracle_cards(progress=self.progress.emit)
                finally:
                    bulk.close()
            self.finished_ok.emit(result.imported_cards)
        except Exception as exc:
            self.failed.emit(str(exc))


class BrowseWidget(QWidget):
    changed = Signal()
    locale_changed = Signal(str)

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._sync_worker: BulkSyncWorker | None = None
        self._build_ui()
        self.refresh()

    def retranslate(self) -> None:
        self._section_list.item(0).setText(self._translator.t("browse.section.overview"))
        self._section_list.item(1).setText(self._translator.t("browse.section.cards"))
        self._section_list.item(2).setText(
            self._translator.t("browse.section.availability")
        )
        self._section_list.item(3).setText(
            self._translator.t("browse.section.scryfall")
        )
        self._card_search.setPlaceholderText(self._translator.t("browse.cards.search"))
        self._sync_button.setText(self._translator.t("browse.scryfall.sync"))
        self._language_group.setTitle(self._translator.t("config.language"))
        self._language_label.setText(self._translator.t("config.language"))
        self._inventory_summary_group.setTitle(
            self._translator.t("inventory.summary.title")
        )
        self._inventory_search.setPlaceholderText(
            self._translator.t("inventory.search.collection")
        )
        self._inventory_hint.setText(self._translator.t("inventory.search.hint"))
        self._cards_table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.cards.type"),
                self._translator.t("browse.cards.cmc"),
                self._translator.t("browse.cards.copies"),
                self._translator.t("browse.cards.flags"),
            ]
        )
        self._card_refresh_button.setText(self._translator.t("common.refresh"))
        self._inventory_results_table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.inventory.copies"),
                self._translator.t("browse.inventory.assigned"),
            ]
        )
        self._scryfall_group.setTitle(self._translator.t("browse.section.scryfall"))
        self._sync_language_combo()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()
        layout.addWidget(splitter)

        self._section_list = QListWidget()
        self._section_list.addItem(self._translator.t("browse.section.overview"))
        self._section_list.addItem(self._translator.t("browse.section.cards"))
        self._section_list.addItem(self._translator.t("browse.section.availability"))
        self._section_list.addItem(self._translator.t("browse.section.scryfall"))
        splitter.addWidget(self._section_list)

        self._panels = QStackedWidget()
        splitter.addWidget(self._panels)
        splitter.setStretchFactor(1, 1)

        self._panels.addWidget(self._build_overview_panel())
        self._panels.addWidget(self._build_cards_panel())
        self._panels.addWidget(self._build_inventory_panel())
        self._panels.addWidget(self._build_scryfall_panel())

        self._section_list.currentRowChanged.connect(self._panels.setCurrentIndex)
        self._section_list.setCurrentRow(0)

    def _build_overview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self._greeting_label = QLabel()
        self._greeting_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        greeting_font = QFont("Monospace")
        greeting_font.setStyleHint(QFont.StyleHint.Monospace)
        self._greeting_label.setFont(greeting_font)
        layout.addWidget(self._greeting_label)

        self._tagline_label = QLabel()
        self._tagline_label.setWordWrap(True)
        layout.addWidget(self._tagline_label)

        self._overview_label = QLabel()
        self._overview_label.setWordWrap(True)
        layout.addWidget(self._overview_label)

        self._language_group = QGroupBox(self._translator.t("config.language"))
        language_form = QFormLayout(self._language_group)
        self._language_label = QLabel(self._translator.t("config.language"))
        self._language_combo = QComboBox()
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_form.addRow(self._language_label, self._language_combo)
        layout.addWidget(self._language_group)

        self._sync_language_combo()
        layout.addStretch()
        return panel

    def _sync_language_combo(self) -> None:
        self._language_combo.blockSignals(True)
        self._language_combo.clear()
        for code, label_key in (("en", "language.en"), ("es", "language.es")):
            self._language_combo.addItem(self._translator.t(label_key), code)
        index = self._language_combo.findData(self._translator.locale)
        self._language_combo.setCurrentIndex(index if index >= 0 else 0)
        self._language_combo.blockSignals(False)

    def _on_language_changed(self) -> None:
        locale = self._language_combo.currentData()
        if isinstance(locale, str) and locale != self._translator.locale:
            self.locale_changed.emit(locale)

    def _build_cards_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        search_row = QHBoxLayout()
        self._card_search = QLineEdit()
        self._card_search.setPlaceholderText(self._translator.t("browse.cards.search"))
        self._card_search.textChanged.connect(self._refresh_cards)
        self._card_search.returnPressed.connect(self._refresh_cards)
        self._card_refresh_button = QPushButton(self._translator.t("common.refresh"))
        self._card_refresh_button.clicked.connect(self._refresh_cards)
        search_row.addWidget(self._card_search)
        search_row.addWidget(self._card_refresh_button)
        layout.addLayout(search_row)

        self._cards_table = QTableWidget(0, 5)
        self._cards_table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.cards.type"),
                self._translator.t("browse.cards.cmc"),
                self._translator.t("browse.cards.copies"),
                self._translator.t("browse.cards.flags"),
            ]
        )
        self._cards_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._cards_table)
        return panel

    def _build_inventory_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self._inventory_summary_group = QGroupBox(
            self._translator.t("inventory.summary.title")
        )
        summary_layout = QVBoxLayout(self._inventory_summary_group)
        self._inventory_summary_label = QLabel()
        self._inventory_summary_label.setWordWrap(True)
        summary_layout.addWidget(self._inventory_summary_label)
        layout.addWidget(self._inventory_summary_group)

        self._inventory_search = QLineEdit()
        self._inventory_search.setPlaceholderText(
            self._translator.t("inventory.search.collection")
        )
        self._inventory_search.textChanged.connect(self._refresh_inventory)
        layout.addWidget(self._inventory_search)

        self._inventory_status = QLabel("")
        self._inventory_status.setWordWrap(True)
        layout.addWidget(self._inventory_status)

        self._inventory_hint = QLabel(self._translator.t("inventory.search.hint"))
        self._inventory_hint.setWordWrap(True)
        layout.addWidget(self._inventory_hint)

        self._inventory_results_table = QTableWidget(0, 3)
        self._inventory_results_table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.inventory.copies"),
                self._translator.t("browse.inventory.assigned"),
            ]
        )
        self._inventory_results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._inventory_results_table)
        return panel

    def _build_scryfall_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self._scryfall_group = QGroupBox(self._translator.t("browse.section.scryfall"))
        form = QFormLayout(self._scryfall_group)
        self._scryfall_status_label = QLabel()
        self._scryfall_status_label.setWordWrap(True)
        form.addRow(self._scryfall_status_label)

        self._sync_progress_label = QLabel("")
        self._sync_progress_label.setWordWrap(True)
        form.addRow(self._sync_progress_label)

        self._sync_button = QPushButton(self._translator.t("browse.scryfall.sync"))
        self._sync_button.clicked.connect(self._start_bulk_sync)
        form.addRow(self._sync_button)
        layout.addWidget(self._scryfall_group)

        info = QLabel(self._translator.t("browse.scryfall.info"))
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()
        return panel

    def refresh(self) -> None:
        self._refresh_overview()
        self._refresh_cards()
        self._refresh_inventory()
        self._refresh_scryfall_status()

    def refresh_collection_stats(self) -> None:
        """Update overview + availability after deck/inventory changes.

        Skips rebuilding the full Scryfall cards table (tens of thousands of rows).
        """
        self._refresh_overview()
        self._refresh_inventory()
        if self._card_search.text().strip():
            self._refresh_cards()

    def _refresh_overview(self) -> None:
        self._greeting_label.setText(self._translator.t("browse.overview.greeting"))
        self._tagline_label.setText(self._translator.t("browse.overview.tagline"))
        with get_session() as session:
            stats = BrowseService(session).overview()
        self._overview_label.setText(
            self._translator.t("browse.overview.body").format(
                cards=stats.cards,
                copies=stats.copies,
                unassigned=stats.unassigned_copies,
                decks=stats.decks,
                armed=stats.armed_decks,
                deck_cards=stats.deck_cards,
                assignments=stats.assignments,
            )
        )

    def _refresh_cards(self) -> None:
        search = self._card_search.text().strip()
        if not search:
            # Avoid loading the full ~36k oracle-cards cache into the table.
            self._cards_table.setRowCount(0)
            return

        with get_session() as session:
            cards = BrowseService(session).list_cards(search)

        self._cards_table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            flags: list[str] = []
            if card.is_basic_land:
                flags.append(self._translator.t("browse.cards.flag.basic"))
            if card.is_token:
                flags.append(self._translator.t("browse.cards.flag.token"))
            self._cards_table.setItem(row, 0, QTableWidgetItem(card.name))
            self._cards_table.setItem(row, 1, QTableWidgetItem(card.type_line or ""))
            self._cards_table.setItem(
                row, 2, QTableWidgetItem("" if card.cmc is None else str(card.cmc))
            )
            self._cards_table.setItem(row, 3, QTableWidgetItem(str(card.copy_count)))
            self._cards_table.setItem(row, 4, QTableWidgetItem(", ".join(flags)))

    def _refresh_inventory(self) -> None:
        with get_session() as session:
            all_rows = BrowseService(session).list_inventory()

        if not all_rows:
            self._inventory_summary_label.setText(
                self._translator.t("inventory.summary.empty")
            )
        else:
            total_copies = sum(row.total_copies for row in all_rows)
            free_copies = sum(row.free_copies for row in all_rows)
            assigned_copies = total_copies - free_copies
            self._inventory_summary_label.setText(
                self._translator.t("inventory.summary.body").format(
                    unique=len(all_rows),
                    copies=total_copies,
                    free=free_copies,
                    assigned=assigned_copies,
                )
            )

        search = self._inventory_search.text().strip()
        rows = all_rows
        if search:
            needle = search.casefold()
            rows = [row for row in rows if needle in row.card_name.casefold()]

        self._inventory_results_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            copies_item = QTableWidgetItem(str(row.total_copies))
            copies_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._inventory_results_table.setItem(
                index, 0, QTableWidgetItem(row.card_name)
            )
            self._inventory_results_table.setItem(index, 1, copies_item)
            self._inventory_results_table.setItem(
                index,
                2,
                QTableWidgetItem(format_inventory_assigned(row, self._translator)),
            )

        if not search:
            self._inventory_status.setText("")
            self._inventory_hint.setVisible(True)
            self._inventory_results_table.setVisible(False)
            return

        self._inventory_hint.setVisible(False)
        self._inventory_results_table.setVisible(True)

        if not rows:
            self._inventory_status.setText(self._translator.t("inventory.not_owned"))
            return

        if len(rows) == 1:
            self._inventory_status.setText(
                format_availability_status(rows[0], self._translator)
            )
            return

        self._inventory_status.setText(
            self._translator.t("inventory.matches").format(count=len(rows))
        )

    def _refresh_scryfall_status(self) -> None:
        with get_session() as session:
            status = BrowseService(session).scryfall_status()

        imported = (
            str(status.imported_cards)
            if status.imported_cards is not None
            else self._translator.t("browse.scryfall.never")
        )
        self._scryfall_status_label.setText(
            self._translator.t("browse.scryfall.status").format(
                cached=status.cached_cards,
                bulk_updated=status.bulk_updated_at
                or self._translator.t("browse.scryfall.never"),
                last_synced=status.last_synced_at
                or self._translator.t("browse.scryfall.never"),
                imported=imported,
            )
        )

    def _start_bulk_sync(self) -> None:
        if self._sync_worker is not None and self._sync_worker.isRunning():
            return

        self._sync_button.setEnabled(False)
        self._sync_progress_label.setText(self._translator.t("browse.scryfall.starting"))

        self._sync_worker = BulkSyncWorker()
        self._sync_worker.progress.connect(self._sync_progress_label.setText)
        self._sync_worker.finished_ok.connect(self._on_sync_finished)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _on_sync_finished(self, imported_cards: int) -> None:
        self._sync_button.setEnabled(True)
        self._sync_progress_label.setText(
            self._translator.t("browse.scryfall.done").format(count=imported_cards)
        )
        self.refresh()
        self.changed.emit()

    def _on_sync_failed(self, message: str) -> None:
        self._sync_button.setEnabled(True)
        self._sync_progress_label.setText("")
        QMessageBox.critical(
            self,
            self._translator.t("common.error"),
            message,
        )
