"""Inventory filter dialog (type / decks / colors / rarity / mana value)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.algorithms.inventory_filters import (
    CARD_TYPE_OPTIONS,
    CMC_OPS,
    RARITY_CODES,
    CmcCondition,
    InventoryFilterState,
    WUBRG,
)
from mtg_sorter.i18n import Translator
from mtg_sorter.ui.combo import (
    SEARCHABLE_COMBO_CONTENTS_LENGTH,
    configure_data_combo,
)

class InventoryFilterDialog(QDialog):
    """Popup filter form. Emits ``filters_changed`` on any edit."""

    filters_changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._cmc_rows: list[tuple[QComboBox, QSpinBox, QPushButton]] = []
        self._selected_types: list[str] = []
        self._selected_decks: list[tuple[int, str]] = []
        self._armed_decks: list[tuple[int, str]] = []
        self.setModal(False)
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        body = QVBoxLayout(self)
        hint_font = self.font()
        hint_font.setPointSize(max(8, hint_font.pointSize() - 1))

        # --- Type (Optimize-style picker) ---
        self._type_label = QLabel()
        body.addWidget(self._type_label)
        self._type_hint = QLabel()
        self._type_hint.setWordWrap(True)
        self._type_hint.setFont(hint_font)
        body.addWidget(self._type_hint)

        type_picker = QHBoxLayout()
        self._type_combo = QComboBox()
        self._configure_searchable_combo(self._type_combo)
        for type_name in CARD_TYPE_OPTIONS:
            self._type_combo.addItem(type_name, type_name)
        self._type_combo.setCurrentIndex(-1)
        self._type_add_button = QPushButton()
        self._type_add_button.clicked.connect(self._add_selected_type)
        type_picker.addWidget(self._type_combo, 1)
        type_picker.addWidget(self._type_add_button)
        body.addLayout(type_picker)

        self._type_queue_group = QGroupBox()
        type_queue_layout = QVBoxLayout(self._type_queue_group)
        self._type_queue = QListWidget()
        self._type_queue.setMaximumHeight(100)
        self._type_queue.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._type_queue.itemDoubleClicked.connect(self._remove_type_item)
        type_queue_layout.addWidget(self._type_queue)
        self._type_remove_button = QPushButton()
        self._type_remove_button.clicked.connect(self._remove_selected_type)
        type_queue_layout.addWidget(self._type_remove_button)
        body.addWidget(self._type_queue_group)
        self._type_queue_group.setVisible(False)

        # --- Decks ---
        self._decks_label = QLabel()
        body.addWidget(self._decks_label)
        self._decks_hint = QLabel()
        self._decks_hint.setWordWrap(True)
        self._decks_hint.setFont(hint_font)
        body.addWidget(self._decks_hint)

        self._exclude_any_armed = QCheckBox()
        self._exclude_any_armed.toggled.connect(self._on_filters_edited)
        body.addWidget(self._exclude_any_armed)

        deck_picker = QHBoxLayout()
        self._deck_combo = QComboBox()
        self._configure_searchable_combo(self._deck_combo)
        self._deck_add_button = QPushButton()
        self._deck_add_button.clicked.connect(self._add_selected_deck)
        deck_picker.addWidget(self._deck_combo, 1)
        deck_picker.addWidget(self._deck_add_button)
        body.addLayout(deck_picker)

        self._deck_queue_group = QGroupBox()
        deck_queue_layout = QVBoxLayout(self._deck_queue_group)
        self._deck_queue = QListWidget()
        self._deck_queue.setMaximumHeight(100)
        self._deck_queue.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._deck_queue.itemDoubleClicked.connect(self._remove_deck_item)
        deck_queue_layout.addWidget(self._deck_queue)
        self._deck_remove_button = QPushButton()
        self._deck_remove_button.clicked.connect(self._remove_selected_deck)
        deck_queue_layout.addWidget(self._deck_remove_button)
        body.addWidget(self._deck_queue_group)
        self._deck_queue_group.setVisible(False)

        # --- Colors ---
        self._colors_label = QLabel()
        body.addWidget(self._colors_label)
        self._colors_hint = QLabel()
        self._colors_hint.setWordWrap(True)
        self._colors_hint.setFont(hint_font)
        body.addWidget(self._colors_hint)

        colors_row = QHBoxLayout()
        self._color_checks: dict[str, QCheckBox] = {}
        for letter in WUBRG:
            box = QCheckBox(letter)
            box.toggled.connect(self._on_filters_edited)
            self._color_checks[letter] = box
            colors_row.addWidget(box)
        colors_row.addStretch()
        body.addLayout(colors_row)

        # --- Rarity (same letter-checkbox style as colors) ---
        self._rarity_label = QLabel()
        body.addWidget(self._rarity_label)
        self._rarity_hint = QLabel()
        self._rarity_hint.setWordWrap(True)
        self._rarity_hint.setFont(hint_font)
        body.addWidget(self._rarity_hint)

        rarity_row = QHBoxLayout()
        self._rarity_checks: dict[str, QCheckBox] = {}
        for code in RARITY_CODES:
            box = QCheckBox(code)
            box.toggled.connect(self._on_filters_edited)
            self._rarity_checks[code] = box
            rarity_row.addWidget(box)
        rarity_row.addStretch()
        body.addLayout(rarity_row)

        # --- Mana value ---
        self._cmc_label = QLabel()
        body.addWidget(self._cmc_label)
        self._cmc_hint = QLabel()
        self._cmc_hint.setWordWrap(True)
        self._cmc_hint.setFont(hint_font)
        body.addWidget(self._cmc_hint)

        self._cmc_list_layout = QVBoxLayout()
        body.addLayout(self._cmc_list_layout)

        cmc_add_row = QHBoxLayout()
        self._cmc_op = QComboBox()
        configure_data_combo(self._cmc_op, min_contents=4)
        for op in CMC_OPS:
            self._cmc_op.addItem(op)
        self._cmc_value = QSpinBox()
        self._cmc_value.setRange(0, 99)
        self._cmc_value.setValue(1)
        self._cmc_add_button = QPushButton()
        self._cmc_add_button.clicked.connect(self._add_cmc_condition)
        cmc_add_row.addWidget(self._cmc_op)
        cmc_add_row.addWidget(self._cmc_value, 1)
        cmc_add_row.addWidget(self._cmc_add_button)
        body.addLayout(cmc_add_row)

        footer = QHBoxLayout()
        self._clear_button = QPushButton()
        self._clear_button.clicked.connect(self.clear_filters)
        footer.addWidget(self._clear_button)
        footer.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        self._close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        footer.addWidget(buttons)
        body.addLayout(footer)

        self.retranslate()

    def _configure_searchable_combo(self, combo: QComboBox) -> None:
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        configure_data_combo(
            combo, min_contents=SEARCHABLE_COMBO_CONTENTS_LENGTH
        )
        line_edit = combo.lineEdit()
        assert line_edit is not None
        line_edit.setClearButtonEnabled(True)
        search_icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_FileDialogContentsView
        )
        search_action = QAction(
            search_icon if not search_icon.isNull() else QIcon(),
            "",
            self,
        )
        search_action.setEnabled(False)
        line_edit.addAction(search_action, line_edit.ActionPosition.LeadingPosition)
        completer = QCompleter(combo.model(), combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.setCompleter(completer)
        combo.activated.connect(lambda *_: self._commit_combo(combo))
        line_edit.returnPressed.connect(lambda: self._commit_combo(combo))

    def retranslate(self) -> None:
        t = self._translator.t
        self.setWindowTitle(t("inventory.filters.title"))
        self._type_label.setText(t("inventory.filters.type"))
        self._type_hint.setText(t("inventory.filters.type_hint"))
        type_edit = self._type_combo.lineEdit()
        if type_edit is not None:
            type_edit.setPlaceholderText(t("inventory.filters.type_search"))
        self._type_add_button.setText(t("inventory.filters.type_add"))
        self._type_remove_button.setText(t("inventory.filters.type_remove"))
        self._type_queue_group.setTitle(t("inventory.filters.type_selected"))

        self._decks_label.setText(t("inventory.filters.decks"))
        self._decks_hint.setText(t("inventory.filters.decks_hint"))
        self._exclude_any_armed.setText(t("inventory.filters.decks_any_armed"))
        deck_edit = self._deck_combo.lineEdit()
        if deck_edit is not None:
            deck_edit.setPlaceholderText(t("inventory.filters.decks_search"))
        self._deck_add_button.setText(t("inventory.filters.decks_add"))
        self._deck_remove_button.setText(t("inventory.filters.decks_remove"))
        self._deck_queue_group.setTitle(t("inventory.filters.decks_selected"))

        self._colors_label.setText(t("inventory.filters.colors"))
        self._colors_hint.setText(t("inventory.filters.colors_hint"))
        self._rarity_label.setText(t("inventory.filters.rarity"))
        self._rarity_hint.setText(t("inventory.filters.rarity_hint"))
        for code, box in self._rarity_checks.items():
            box.setToolTip(t(f"inventory.filters.rarity.{code}"))
        self._cmc_label.setText(t("inventory.filters.cmc"))
        self._cmc_hint.setText(t("inventory.filters.cmc_hint"))
        self._cmc_add_button.setText(t("inventory.filters.cmc_add"))
        self._clear_button.setText(t("inventory.filters.clear"))
        if self._close_button is not None:
            self._close_button.setText(t("inventory.filters.close"))
        for _op, _spin, remove in self._cmc_rows:
            remove.setText(t("inventory.filters.cmc_remove"))

    def set_armed_decks(self, decks: list[tuple[int, str]]) -> None:
        """Refresh the armed-deck picker; drop queue entries that are no longer armed."""
        self._armed_decks = list(decks)
        valid_ids = {deck_id for deck_id, _name in self._armed_decks}

        kept = [(deck_id, name) for deck_id, name in self._selected_decks if deck_id in valid_ids]
        dropped = len(kept) != len(self._selected_decks)
        self._selected_decks = kept
        self._rebuild_deck_queue()

        current = self._deck_combo.currentData()
        self._deck_combo.blockSignals(True)
        self._deck_combo.clear()
        for deck_id, name in self._armed_decks:
            self._deck_combo.addItem(name, deck_id)
        completer = self._deck_combo.completer()
        if completer is not None:
            completer.setModel(self._deck_combo.model())
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
        if isinstance(current, int):
            index = self._deck_combo.findData(current)
            if index >= 0:
                self._deck_combo.setCurrentIndex(index)
            else:
                self._deck_combo.setCurrentIndex(-1)
                line_edit = self._deck_combo.lineEdit()
                if line_edit is not None:
                    line_edit.clear()
        else:
            self._deck_combo.setCurrentIndex(-1)
        self._deck_combo.blockSignals(False)

        if dropped:
            self.filters_changed.emit()

    def filter_state(self) -> InventoryFilterState:
        colors = {
            letter
            for letter, box in self._color_checks.items()
            if box.isChecked()
        }
        rarities = {
            code for code, box in self._rarity_checks.items() if box.isChecked()
        }
        conditions = tuple(
            CmcCondition(op.currentText(), float(spin.value()))
            for op, spin, _remove in self._cmc_rows
        )
        return InventoryFilterState(
            types=frozenset(self._selected_types),
            colors=frozenset(colors),
            rarities=frozenset(rarities),
            cmc_conditions=conditions,
            exclude_any_armed=self._exclude_any_armed.isChecked(),
            exclude_deck_ids=frozenset(deck_id for deck_id, _ in self._selected_decks),
        )

    def clear_filters(self) -> None:
        self._selected_types.clear()
        self._rebuild_type_queue()
        self._selected_decks.clear()
        self._rebuild_deck_queue()
        self._exclude_any_armed.blockSignals(True)
        self._exclude_any_armed.setChecked(False)
        self._exclude_any_armed.blockSignals(False)
        type_edit = self._type_combo.lineEdit()
        if type_edit is not None:
            type_edit.clear()
        self._type_combo.setCurrentIndex(-1)
        deck_edit = self._deck_combo.lineEdit()
        if deck_edit is not None:
            deck_edit.clear()
        self._deck_combo.setCurrentIndex(-1)
        for box in self._color_checks.values():
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)
        for box in self._rarity_checks.values():
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)
        while self._cmc_rows:
            self._remove_cmc_row(self._cmc_rows[0][2])
        self.filters_changed.emit()

    def _commit_combo(self, combo: QComboBox) -> None:
        data = self._combo_selection_data(combo)
        if data is None:
            return
        index = combo.findData(data)
        if index < 0:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def _combo_selection_data(self, combo: QComboBox) -> object | None:
        typed = combo.currentText().strip()
        if not typed:
            return None
        index = combo.currentIndex()
        if index >= 0 and combo.itemText(index) == typed:
            return combo.itemData(index)
        needle = typed.casefold()
        exact: list[object] = []
        partial: list[object] = []
        for i in range(combo.count()):
            label = combo.itemText(i)
            data = combo.itemData(i)
            if label.casefold() == needle:
                exact.append(data)
            elif needle in label.casefold():
                partial.append(data)
        if len(exact) == 1:
            return exact[0]
        if not exact and len(partial) == 1:
            return partial[0]
        return None

    def _add_selected_type(self) -> None:
        data = self._combo_selection_data(self._type_combo)
        if not isinstance(data, str):
            return
        if data in self._selected_types:
            return
        self._selected_types.append(data)
        self._rebuild_type_queue()
        line_edit = self._type_combo.lineEdit()
        if line_edit is not None:
            line_edit.clear()
        self._type_combo.setCurrentIndex(-1)
        self.filters_changed.emit()

    def _remove_type_item(self, item: QListWidgetItem) -> None:
        self._remove_type(item.text())

    def _remove_selected_type(self) -> None:
        item = self._type_queue.currentItem()
        if item is not None:
            self._remove_type(item.text())

    def _remove_type(self, type_name: str) -> None:
        if type_name not in self._selected_types:
            return
        self._selected_types = [t for t in self._selected_types if t != type_name]
        self._rebuild_type_queue()
        self.filters_changed.emit()

    def _rebuild_type_queue(self) -> None:
        self._type_queue.clear()
        for type_name in self._selected_types:
            self._type_queue.addItem(type_name)
        self._type_queue_group.setVisible(bool(self._selected_types))

    def _add_selected_deck(self) -> None:
        data = self._combo_selection_data(self._deck_combo)
        if not isinstance(data, int):
            return
        if any(deck_id == data for deck_id, _ in self._selected_decks):
            return
        name = next(
            (n for deck_id, n in self._armed_decks if deck_id == data),
            self._deck_combo.currentText().strip(),
        )
        self._selected_decks.append((data, name))
        self._rebuild_deck_queue()
        line_edit = self._deck_combo.lineEdit()
        if line_edit is not None:
            line_edit.clear()
        self._deck_combo.setCurrentIndex(-1)
        self.filters_changed.emit()

    def _remove_deck_item(self, item: QListWidgetItem) -> None:
        deck_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(deck_id, int):
            self._remove_deck(deck_id)

    def _remove_selected_deck(self) -> None:
        item = self._deck_queue.currentItem()
        if item is None:
            return
        deck_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(deck_id, int):
            self._remove_deck(deck_id)

    def _remove_deck(self, deck_id: int) -> None:
        before = len(self._selected_decks)
        self._selected_decks = [
            (did, name) for did, name in self._selected_decks if did != deck_id
        ]
        if len(self._selected_decks) == before:
            return
        self._rebuild_deck_queue()
        self.filters_changed.emit()

    def _rebuild_deck_queue(self) -> None:
        self._deck_queue.clear()
        for deck_id, name in self._selected_decks:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, deck_id)
            self._deck_queue.addItem(item)
        self._deck_queue_group.setVisible(bool(self._selected_decks))

    def _add_cmc_condition(self) -> None:
        op = QComboBox()
        configure_data_combo(op, min_contents=4)
        for symbol in CMC_OPS:
            op.addItem(symbol)
        op.setCurrentText(self._cmc_op.currentText())
        op.currentIndexChanged.connect(self._on_filters_edited)

        spin = QSpinBox()
        spin.setRange(0, 99)
        spin.setValue(self._cmc_value.value())
        spin.valueChanged.connect(self._on_filters_edited)

        remove = QPushButton(self._translator.t("inventory.filters.cmc_remove"))
        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(op)
        row.addWidget(spin, 1)
        row.addWidget(remove)
        remove.clicked.connect(lambda: self._remove_cmc_row(remove))

        self._cmc_list_layout.addWidget(row_widget)
        self._cmc_rows.append((op, spin, remove))
        self.filters_changed.emit()

    def _remove_cmc_row(self, remove_button: QPushButton) -> None:
        for index, (op, spin, button) in enumerate(self._cmc_rows):
            if button is not remove_button:
                continue
            widget = button.parentWidget()
            self._cmc_rows.pop(index)
            if widget is not None:
                self._cmc_list_layout.removeWidget(widget)
                widget.deleteLater()
            self.filters_changed.emit()
            return

    def _on_filters_edited(self, *_args: object) -> None:
        self.filters_changed.emit()
