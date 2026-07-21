from PySide6.QtCore import QThread, Signal
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
from mtg_sorter.models.enums import DeckStatus
from mtg_sorter.services import BrowseService, ScryfallBulkService


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
        self._section_list.item(2).setText(self._translator.t("browse.section.decks"))
        self._section_list.item(3).setText(
            self._translator.t("browse.section.inventory")
        )
        self._section_list.item(4).setText(
            self._translator.t("browse.section.scryfall")
        )
        self._card_search.setPlaceholderText(self._translator.t("browse.cards.search"))
        self._sync_button.setText(self._translator.t("browse.scryfall.sync"))
        self._language_group.setTitle(self._translator.t("config.language"))
        self._language_label.setText(self._translator.t("config.language"))
        self._sync_language_combo()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()
        layout.addWidget(splitter)

        self._section_list = QListWidget()
        self._section_list.addItem(self._translator.t("browse.section.overview"))
        self._section_list.addItem(self._translator.t("browse.section.cards"))
        self._section_list.addItem(self._translator.t("browse.section.decks"))
        self._section_list.addItem(self._translator.t("browse.section.inventory"))
        self._section_list.addItem(self._translator.t("browse.section.scryfall"))
        splitter.addWidget(self._section_list)

        self._panels = QStackedWidget()
        splitter.addWidget(self._panels)
        splitter.setStretchFactor(1, 1)

        self._panels.addWidget(self._build_overview_panel())
        self._panels.addWidget(self._build_cards_panel())
        self._panels.addWidget(self._build_decks_panel())
        self._panels.addWidget(self._build_inventory_panel())
        self._panels.addWidget(self._build_scryfall_panel())

        self._section_list.currentRowChanged.connect(self._panels.setCurrentIndex)
        self._section_list.setCurrentRow(0)

    def _build_overview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
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
        self._card_search.returnPressed.connect(self._refresh_cards)
        search_button = QPushButton(self._translator.t("common.refresh"))
        search_button.clicked.connect(self._refresh_cards)
        search_row.addWidget(self._card_search)
        search_row.addWidget(search_button)
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

    def _build_decks_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        split = QSplitter()
        self._deck_list = QListWidget()
        self._deck_list.currentItemChanged.connect(self._refresh_deck_cards)
        split.addWidget(self._deck_list)

        self._deck_cards_table = QTableWidget(0, 3)
        self._deck_cards_table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.decks.quantity"),
                self._translator.t("browse.decks.role"),
            ]
        )
        self._deck_cards_table.horizontalHeader().setStretchLastSection(True)
        split.addWidget(self._deck_cards_table)
        split.setStretchFactor(1, 1)
        layout.addWidget(split)
        return panel

    def _build_inventory_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self._inventory_table = QTableWidget(0, 3)
        self._inventory_table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.inventory.copy"),
                self._translator.t("browse.cards.name"),
                self._translator.t("browse.inventory.assigned"),
            ]
        )
        self._inventory_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._inventory_table)
        return panel

    def _build_scryfall_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        group = QGroupBox(self._translator.t("browse.section.scryfall"))
        form = QFormLayout(group)
        self._scryfall_status_label = QLabel()
        self._scryfall_status_label.setWordWrap(True)
        form.addRow(self._scryfall_status_label)

        self._sync_progress_label = QLabel("")
        self._sync_progress_label.setWordWrap(True)
        form.addRow(self._sync_progress_label)

        self._sync_button = QPushButton(self._translator.t("browse.scryfall.sync"))
        self._sync_button.clicked.connect(self._start_bulk_sync)
        form.addRow(self._sync_button)
        layout.addWidget(group)

        info = QLabel(self._translator.t("browse.scryfall.info"))
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()
        return panel

    def refresh(self) -> None:
        self._refresh_overview()
        self._refresh_cards()
        self._refresh_decks()
        self._refresh_inventory()
        self._refresh_scryfall_status()

    def _refresh_overview(self) -> None:
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
        with get_session() as session:
            cards = BrowseService(session).list_cards(search)

        self._cards_table.setRowCount(len(cards))
        for row, card in enumerate(cards):
            flags: list[str] = []
            if card.is_basic_land:
                flags.append("basic")
            if card.is_token:
                flags.append("token")
            self._cards_table.setItem(row, 0, QTableWidgetItem(card.name))
            self._cards_table.setItem(row, 1, QTableWidgetItem(card.type_line or ""))
            self._cards_table.setItem(
                row, 2, QTableWidgetItem("" if card.cmc is None else str(card.cmc))
            )
            self._cards_table.setItem(row, 3, QTableWidgetItem(str(card.copy_count)))
            self._cards_table.setItem(row, 4, QTableWidgetItem(", ".join(flags)))

    def _refresh_decks(self) -> None:
        self._deck_list.clear()
        with get_session() as session:
            decks = BrowseService(session).list_decks()

        if not decks:
            self._deck_list.addItem(self._translator.t("decks.empty"))
            self._deck_cards_table.setRowCount(0)
            return

        for deck in decks:
            status = (
                self._translator.t("decks.status.armed")
                if deck.status == DeckStatus.ARMED
                else self._translator.t("decks.status.dismantled")
            )
            self._deck_list.addItem(
                f"[{status}] {deck.name} ({deck.total_cards})"
            )
            item = self._deck_list.item(self._deck_list.count() - 1)
            if item is not None:
                item.setData(256, deck.deck_id)

        if self._deck_list.count() > 0:
            self._deck_list.setCurrentRow(0)

    def _selected_deck_id(self) -> int | None:
        item = self._deck_list.currentItem()
        if item is None:
            return None
        deck_id = item.data(256)
        return deck_id if isinstance(deck_id, int) else None

    def _refresh_deck_cards(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            self._deck_cards_table.setRowCount(0)
            return

        with get_session() as session:
            rows = BrowseService(session).list_deck_cards(deck_id)

        self._deck_cards_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._deck_cards_table.setItem(index, 0, QTableWidgetItem(row.name))
            self._deck_cards_table.setItem(
                index, 1, QTableWidgetItem(str(row.quantity))
            )
            self._deck_cards_table.setItem(index, 2, QTableWidgetItem(row.role))

    def _refresh_inventory(self) -> None:
        with get_session() as session:
            rows = BrowseService(session).list_inventory()

        self._inventory_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._inventory_table.setItem(
                index, 0, QTableWidgetItem(str(row.copy_id))
            )
            self._inventory_table.setItem(index, 1, QTableWidgetItem(row.card_name))
            assigned = row.assigned_deck or self._translator.t("browse.inventory.free")
            self._inventory_table.setItem(index, 2, QTableWidgetItem(assigned))

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
