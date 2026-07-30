"""Inventory filter dialog (type / colors / mana value)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.algorithms.inventory_filters import (
    CARD_TYPE_OPTIONS,
    CMC_OPS,
    CmcCondition,
    InventoryFilterState,
    WUBRG,
)
from mtg_sorter.i18n import Translator


class InventoryFilterDialog(QDialog):
    """Popup filter form. Emits ``filters_changed`` on any edit."""

    filters_changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._cmc_rows: list[tuple[QComboBox, QSpinBox, QPushButton]] = []
        self._selected_types: set[str] = set()
        self.setModal(False)
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        body = QVBoxLayout(self)

        # --- Type ---
        self._type_label = QLabel()
        body.addWidget(self._type_label)
        self._type_hint = QLabel()
        self._type_hint.setWordWrap(True)
        hint_font = self._type_hint.font()
        hint_font.setPointSize(max(8, hint_font.pointSize() - 1))
        self._type_hint.setFont(hint_font)
        body.addWidget(self._type_hint)

        self._type_search = QLineEdit()
        self._type_search.textChanged.connect(self._filter_type_list)
        body.addWidget(self._type_search)

        self._type_available = QListWidget()
        self._type_available.setMinimumHeight(120)
        self._type_available.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        for type_name in CARD_TYPE_OPTIONS:
            self._type_available.addItem(type_name)
        self._type_available.itemDoubleClicked.connect(self._add_type_item)
        body.addWidget(self._type_available)

        type_buttons = QHBoxLayout()
        self._type_add_button = QPushButton()
        self._type_add_button.clicked.connect(self._add_current_type)
        self._type_remove_button = QPushButton()
        self._type_remove_button.clicked.connect(self._remove_current_type)
        type_buttons.addWidget(self._type_add_button)
        type_buttons.addWidget(self._type_remove_button)
        type_buttons.addStretch()
        body.addLayout(type_buttons)

        self._type_selected_label = QLabel()
        body.addWidget(self._type_selected_label)
        self._type_selected = QListWidget()
        self._type_selected.setMinimumHeight(80)
        self._type_selected.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self._type_selected.itemDoubleClicked.connect(self._remove_type_item)
        body.addWidget(self._type_selected)

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

    def retranslate(self) -> None:
        t = self._translator.t
        self.setWindowTitle(t("inventory.filters.title"))
        self._type_label.setText(t("inventory.filters.type"))
        self._type_hint.setText(t("inventory.filters.type_hint"))
        self._type_search.setPlaceholderText(t("inventory.filters.type_search"))
        self._type_selected_label.setText(t("inventory.filters.type_selected"))
        self._type_add_button.setText(t("inventory.filters.type_add"))
        self._type_remove_button.setText(t("inventory.filters.type_remove"))
        self._colors_label.setText(t("inventory.filters.colors"))
        self._colors_hint.setText(t("inventory.filters.colors_hint"))
        self._cmc_label.setText(t("inventory.filters.cmc"))
        self._cmc_hint.setText(t("inventory.filters.cmc_hint"))
        self._cmc_add_button.setText(t("inventory.filters.cmc_add"))
        self._clear_button.setText(t("inventory.filters.clear"))
        if self._close_button is not None:
            self._close_button.setText(t("inventory.filters.close"))
        for _op, _spin, remove in self._cmc_rows:
            remove.setText(t("inventory.filters.cmc_remove"))

    def filter_state(self) -> InventoryFilterState:
        colors = {
            letter
            for letter, box in self._color_checks.items()
            if box.isChecked()
        }
        conditions = tuple(
            CmcCondition(op.currentText(), float(spin.value()))
            for op, spin, _remove in self._cmc_rows
        )
        return InventoryFilterState(
            types=frozenset(self._selected_types),
            colors=frozenset(colors),
            cmc_conditions=conditions,
        )

    def clear_filters(self) -> None:
        self._selected_types.clear()
        self._type_selected.clear()
        self._type_search.clear()
        for box in self._color_checks.values():
            box.blockSignals(True)
            box.setChecked(False)
            box.blockSignals(False)
        while self._cmc_rows:
            self._remove_cmc_row(self._cmc_rows[0][2])
        self.filters_changed.emit()

    def _filter_type_list(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self._type_available.count()):
            item = self._type_available.item(index)
            if item is None:
                continue
            item.setHidden(bool(needle) and needle not in item.text().casefold())

    def _add_type_item(self, item: QListWidgetItem) -> None:
        self._add_type(item.text())

    def _add_current_type(self) -> None:
        item = self._type_available.currentItem()
        if item is not None:
            self._add_type(item.text())

    def _add_type(self, type_name: str) -> None:
        if type_name in self._selected_types:
            return
        self._selected_types.add(type_name)
        self._type_selected.addItem(type_name)
        self.filters_changed.emit()

    def _remove_type_item(self, item: QListWidgetItem) -> None:
        self._remove_type(item.text())

    def _remove_current_type(self) -> None:
        item = self._type_selected.currentItem()
        if item is not None:
            self._remove_type(item.text())

    def _remove_type(self, type_name: str) -> None:
        if type_name not in self._selected_types:
            return
        self._selected_types.discard(type_name)
        for index in range(self._type_selected.count()):
            item = self._type_selected.item(index)
            if item is not None and item.text() == type_name:
                self._type_selected.takeItem(index)
                break
        self.filters_changed.emit()

    def _add_cmc_condition(self) -> None:
        op = QComboBox()
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
