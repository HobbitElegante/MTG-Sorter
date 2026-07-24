from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services import BrowseService, ImportService, ScryfallService
from mtg_sorter.services.browse_service import CardSummary
from mtg_sorter.services.deck_service import (
    DeckDeleteCardImpact,
    DeckEditLine,
    DeckEditRow,
)
from mtg_sorter.services.import_service import InventoryListCard, TrackableDeckCard

SECONDARY_ROLES: tuple[DeckCardRole, ...] = (
    DeckCardRole.PARTNER,
    DeckCardRole.COMPANION,
    DeckCardRole.BACKGROUND,
)

_ROLE_I18N_KEY: dict[DeckCardRole, str] = {
    DeckCardRole.PARTNER: "decks.role.partner",
    DeckCardRole.COMPANION: "decks.role.companion",
    DeckCardRole.BACKGROUND: "decks.role.background",
}


class DeckDetailsDialog(QDialog):
    """Rename a deck and set commander plus optional partner/companion/background."""

    def __init__(
        self,
        translator: Translator,
        deck_name: str,
        commander_name: str | None,
        secondary: tuple[DeckCardRole, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._secondary_role: DeckCardRole | None = None
        self.setWindowTitle(translator.t("decks.details_edit.title"))
        self.resize(460, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._name_input = QLineEdit(deck_name)
        self._name_input.setPlaceholderText(translator.t("decks.name"))
        form.addRow(translator.t("decks.name"), self._name_input)

        commander_row = QWidget()
        commander_layout = QHBoxLayout(commander_row)
        commander_layout.setContentsMargins(0, 0, 0, 0)
        self._commander_input = QLineEdit(commander_name or "")
        self._commander_input.setPlaceholderText(
            translator.t("decks.commander")
        )
        self._add_secondary_button = QToolButton()
        self._add_secondary_button.setText("+")
        self._add_secondary_button.setToolTip(
            translator.t("decks.details_edit.add_secondary")
        )
        self._add_secondary_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        add_menu = QMenu(self._add_secondary_button)
        for role in SECONDARY_ROLES:
            action = QAction(translator.t(_ROLE_I18N_KEY[role]), add_menu)
            action.triggered.connect(
                lambda _checked=False, r=role: self._show_secondary(r)
            )
            add_menu.addAction(action)
        self._add_secondary_button.setMenu(add_menu)
        commander_layout.addWidget(self._commander_input, 1)
        commander_layout.addWidget(self._add_secondary_button)
        form.addRow(translator.t("decks.details_edit.commander"), commander_row)

        self._secondary_label = QLabel("")
        secondary_row = QWidget()
        secondary_layout = QHBoxLayout(secondary_row)
        secondary_layout.setContentsMargins(0, 0, 0, 0)
        self._secondary_input = QLineEdit()
        self._remove_secondary_button = QToolButton()
        self._remove_secondary_button.setText("−")
        self._remove_secondary_button.setToolTip(
            translator.t("decks.details_edit.remove_secondary")
        )
        self._remove_secondary_button.clicked.connect(self._hide_secondary)
        secondary_layout.addWidget(self._secondary_input, 1)
        secondary_layout.addWidget(self._remove_secondary_button)
        self._secondary_field = secondary_row
        form.addRow(self._secondary_label, self._secondary_field)
        layout.addLayout(form)

        self._secondary_label.setVisible(False)
        self._secondary_field.setVisible(False)

        hint = QLabel(translator.t("decks.details_edit.hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if secondary is not None:
            role, name = secondary
            self._show_secondary(role, name)

    def deck_name(self) -> str:
        return self._name_input.text().strip()

    def commander_name(self) -> str | None:
        text = self._commander_input.text().strip()
        return text or None

    def secondary_role(self) -> DeckCardRole | None:
        return self._secondary_role

    def secondary_name(self) -> str | None:
        if self._secondary_role is None:
            return None
        text = self._secondary_input.text().strip()
        return text or None

    def _show_secondary(
        self, role: DeckCardRole, name: str | None = None
    ) -> None:
        self._secondary_role = role
        self._secondary_label.setText(self._translator.t(_ROLE_I18N_KEY[role]))
        self._secondary_input.setPlaceholderText(
            self._translator.t("decks.details_edit.secondary_placeholder").format(
                role=self._translator.t(_ROLE_I18N_KEY[role])
            )
        )
        if name is not None:
            self._secondary_input.setText(name)
        elif not self._secondary_field.isVisible():
            self._secondary_input.clear()
        self._secondary_label.setVisible(True)
        self._secondary_field.setVisible(True)
        self._secondary_input.setFocus()

    def _hide_secondary(self) -> None:
        self._secondary_role = None
        self._secondary_input.clear()
        self._secondary_label.setVisible(False)
        self._secondary_field.setVisible(False)

    def _accept(self) -> None:
        if not self.deck_name():
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                self._translator.t("decks.details_edit.name_required"),
            )
            return
        if self._secondary_role is not None and not self.secondary_name():
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                self._translator.t("decks.details_edit.secondary_required").format(
                    role=self._translator.t(_ROLE_I18N_KEY[self._secondary_role])
                ),
            )
            return
        self.accept()


class ExportDeckDialog(QDialog):
    """Read-only MTGO / Moxfield text export for copy-paste."""

    def __init__(
        self,
        translator: Translator,
        deck_name: str,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self.setWindowTitle(
            translator.t("decks.export.title").format(name=deck_name)
        )
        self.resize(480, 560)

        layout = QVBoxLayout(self)
        hint = QLabel(translator.t("decks.export.hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlainText(text)
        self._text.selectAll()
        layout.addWidget(self._text, 1)

        buttons = QHBoxLayout()
        self._copy_button = QPushButton(translator.t("decks.export.copy"))
        self._copy_button.clicked.connect(self._copy_to_clipboard)
        buttons.addWidget(self._copy_button)
        buttons.addStretch()
        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.reject)
        buttons.addWidget(close_box)
        layout.addLayout(buttons)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def _copy_to_clipboard(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(self._text.toPlainText())
        self._status.setText(self._translator.t("decks.export.copied"))
        self._text.selectAll()
        self._text.setFocus()


class QuantityStepper(QWidget):
    """Numeric value with adjacent − / + buttons instead of spinbox arrows."""

    valueChanged = Signal(int)

    def __init__(
        self,
        maximum: int,
        parent: QWidget | None = None,
        *,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6 if not compact else 4)

        self._spin = QSpinBox()
        self._spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._spin.setRange(0, maximum)
        self._spin.setValue(0)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spin.setMinimumWidth(40 if compact else 56)
        layout.addWidget(self._spin, stretch=1)

        button_width = 28 if compact else 36
        self._minus = QPushButton("-")
        self._plus = QPushButton("+")
        for button in (self._minus, self._plus):
            button.setFixedWidth(button_width)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._minus.clicked.connect(self._step_down)
        self._plus.clicked.connect(self._step_up)
        layout.addWidget(self._minus)
        layout.addWidget(self._plus)

        if not compact:
            self.setMinimumWidth(140)

        self._spin.valueChanged.connect(self._on_value_changed)
        self._sync_buttons()

    def value(self) -> int:
        self._spin.interpretText()
        return self._spin.value()

    def setValue(self, value: int) -> None:
        self._spin.interpretText()
        self._spin.setValue(value)

    def setMaximum(self, maximum: int) -> None:
        self._spin.setMaximum(max(0, maximum))
        if self._spin.value() > self._spin.maximum():
            self._spin.setValue(self._spin.maximum())
        self._sync_buttons()

    def maximum(self) -> int:
        return self._spin.maximum()

    def setMinimum(self, minimum: int) -> None:
        self._spin.setMinimum(minimum)
        if self._spin.value() < self._spin.minimum():
            self._spin.setValue(self._spin.minimum())
        self._sync_buttons()

    def _step_down(self) -> None:
        self._spin.interpretText()
        self._spin.stepDown()

    def _step_up(self) -> None:
        self._spin.interpretText()
        self._spin.stepUp()

    def _on_value_changed(self, value: int) -> None:
        self._sync_buttons()
        self.valueChanged.emit(value)

    def _sync_buttons(self) -> None:
        value = self._spin.value()
        self._minus.setEnabled(value > self._spin.minimum())
        self._plus.setEnabled(value < self._spin.maximum())


class ImportStatusDialog(QDialog):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self.setWindowTitle(self._translator.t("decks.import.status.title"))
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._translator.t("decks.import.status.question")))

        self._armed_radio = QRadioButton(self._translator.t("decks.status.armed"))
        self._dismantled_radio = QRadioButton(
            self._translator.t("decks.status.dismantled")
        )
        self._dismantled_radio.setChecked(True)
        layout.addWidget(self._armed_radio)
        layout.addWidget(self._dismantled_radio)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_status(self) -> DeckStatus:
        if self._armed_radio.isChecked():
            return DeckStatus.ARMED
        return DeckStatus.DISMANTLED


class AvailableCopiesDialog(QDialog):
    def __init__(
        self,
        translator: Translator,
        cards: list[TrackableDeckCard],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._cards = cards
        self._steppers: list[QuantityStepper] = []
        self.setWindowTitle(self._translator.t("decks.import.available.title"))
        self.resize(640, 480)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._translator.t("decks.import.available.question")))

        self._table = QTableWidget(len(self._cards), 3)
        self._table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("decks.import.available.in_list"),
                self._translator.t("decks.import.available.available"),
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row, card in enumerate(self._cards):
            self._table.setItem(row, 0, QTableWidgetItem(card.name))
            in_list_item = QTableWidgetItem(str(card.quantity))
            in_list_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 1, in_list_item)

            stepper = QuantityStepper(card.quantity, compact=True)
            self._steppers.append(stepper)
            self._table.setCellWidget(row, 2, stepper)

        layout.addWidget(self._table)

        actions = QHBoxLayout()
        all_button = QPushButton(self._translator.t("decks.import.available.all"))
        all_button.clicked.connect(self._mark_all_available)
        actions.addWidget(all_button)
        actions.addStretch()
        layout.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _mark_all_available(self) -> None:
        for stepper, card in zip(self._steppers, self._cards, strict=True):
            stepper.setValue(card.quantity)

    def quantities(self) -> dict[str, int]:
        return {
            card.oracle_id: stepper.value()
            for card, stepper in zip(self._cards, self._steppers, strict=True)
            if stepper.value() > 0
        }


@dataclass
class EditableInventoryListLine:
    oracle_id: str
    name: str
    list_quantity: int
    add_quantity: int


class AddInventoryListDialog(QDialog):
    """Review a MTGO list: edit quantities for free inventory, show unresolved lines."""

    def __init__(
        self,
        translator: Translator,
        identified: list[InventoryListCard],
        unresolved_lines: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._lines = [
            EditableInventoryListLine(
                oracle_id=card.oracle_id,
                name=card.name,
                list_quantity=card.list_quantity,
                add_quantity=min(1, card.list_quantity),
            )
            for card in identified
        ]
        self._unresolved_lines = list(unresolved_lines)
        self._qty_steppers: list[QuantityStepper] = []
        self.setWindowTitle(self._translator.t("inventory.add_list.title"))
        self.resize(1000, 600)
        self._build_ui()
        self._rebuild_table()
        self._rebuild_unresolved()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        panes = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel(self._translator.t("inventory.add_list.identified")))
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("decks.import.available.in_list"),
                self._translator.t("inventory.add_list.add"),
                self._translator.t("decks.edit.replace"),
                self._translator.t("inventory.add_list.remove"),
            ]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        left.addWidget(self._table)
        panes.addLayout(left, stretch=3)

        right = QVBoxLayout()
        right.addWidget(QLabel(self._translator.t("inventory.add_list.unresolved")))
        hint = QLabel(self._translator.t("inventory.add_list.unresolved.hint"))
        hint.setWordWrap(True)
        right.addWidget(hint)
        self._unresolved_table = QTableWidget(0, 3)
        self._unresolved_table.setHorizontalHeaderLabels(
            [
                self._translator.t("inventory.add_list.unresolved.line"),
                self._translator.t("inventory.add_list.recheck"),
                self._translator.t("inventory.add_list.remove"),
            ]
        )
        unresolved_header = self._unresolved_table.horizontalHeader()
        unresolved_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        unresolved_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        unresolved_header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._unresolved_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.EditKeyPressed
            | QTableWidget.EditTrigger.SelectedClicked
        )
        right.addWidget(self._unresolved_table)
        panes.addLayout(right, stretch=2)

        root.addLayout(panes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(self._translator.t("inventory.add_list.confirm"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _rebuild_table(self) -> None:
        self._qty_steppers = []
        self._table.setRowCount(len(self._lines))
        for row, line in enumerate(self._lines):
            self._table.setItem(row, 0, QTableWidgetItem(line.name))

            in_list = QTableWidgetItem(str(line.list_quantity))
            in_list.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 1, in_list)

            stepper = QuantityStepper(line.list_quantity, compact=True)
            stepper.setMinimum(0)
            stepper.blockSignals(True)
            stepper.setValue(min(line.add_quantity, line.list_quantity))
            stepper.blockSignals(False)
            stepper.valueChanged.connect(
                lambda value, index=row: self._on_qty_changed(index, value)
            )
            self._qty_steppers.append(stepper)
            self._table.setCellWidget(row, 2, stepper)

            replace = QPushButton(self._translator.t("decks.edit.replace"))
            replace.clicked.connect(
                lambda _checked=False, index=row: self._replace_card(index)
            )
            self._table.setCellWidget(row, 3, replace)

            remove = QPushButton(self._translator.t("inventory.add_list.remove"))
            remove.clicked.connect(
                lambda _checked=False, index=row: self._remove_card(index)
            )
            self._table.setCellWidget(row, 4, remove)

    def _rebuild_unresolved(self) -> None:
        self._unresolved_table.setRowCount(len(self._unresolved_lines))
        for row, line in enumerate(self._unresolved_lines):
            item = QTableWidgetItem(line)
            item.setFlags(
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )
            self._unresolved_table.setItem(row, 0, item)

            recheck = QPushButton(self._translator.t("inventory.add_list.recheck"))
            recheck.clicked.connect(
                lambda _checked=False, index=row: self._recheck_unresolved(index)
            )
            self._unresolved_table.setCellWidget(row, 1, recheck)

            remove = QPushButton(self._translator.t("inventory.add_list.remove"))
            remove.clicked.connect(
                lambda _checked=False, index=row: self._remove_unresolved(index)
            )
            self._unresolved_table.setCellWidget(row, 2, remove)

    def _sync_unresolved_from_table(self) -> None:
        for row in range(self._unresolved_table.rowCount()):
            item = self._unresolved_table.item(row, 0)
            if item is None or row >= len(self._unresolved_lines):
                continue
            self._unresolved_lines[row] = item.text().strip()

    def _on_qty_changed(self, index: int, value: int) -> None:
        if index < 0 or index >= len(self._lines):
            return
        if value <= 0:
            del self._lines[index]
            self._rebuild_table()
            return
        self._lines[index].add_quantity = value

    def _remove_card(self, index: int) -> None:
        if index < 0 or index >= len(self._lines):
            return
        del self._lines[index]
        self._rebuild_table()

    def _remove_unresolved(self, index: int) -> None:
        self._sync_unresolved_from_table()
        if index < 0 or index >= len(self._unresolved_lines):
            return
        del self._unresolved_lines[index]
        self._rebuild_unresolved()

    def _merge_identified(self, card: InventoryListCard) -> None:
        for line in self._lines:
            if line.oracle_id == card.oracle_id:
                line.list_quantity += card.list_quantity
                line.add_quantity = min(
                    max(line.add_quantity, 1),
                    line.list_quantity,
                )
                return
        self._lines.append(
            EditableInventoryListLine(
                oracle_id=card.oracle_id,
                name=card.name,
                list_quantity=card.list_quantity,
                add_quantity=min(1, card.list_quantity),
            )
        )
        self._lines.sort(key=lambda entry: entry.name.casefold())

    def _recheck_unresolved(self, index: int) -> None:
        self._sync_unresolved_from_table()
        if index < 0 or index >= len(self._unresolved_lines):
            return
        text = self._unresolved_lines[index].strip()
        if not text:
            del self._unresolved_lines[index]
            self._rebuild_unresolved()
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
                str(exc),
            )
            return

        if preview.identified:
            for card in preview.identified:
                self._merge_identified(card)
            del self._unresolved_lines[index]
            # Keep any leftover unresolved fragments from the same recheck.
            for leftover in preview.unresolved_lines:
                self._unresolved_lines.insert(index, leftover)
                index += 1
            self._rebuild_table()
            self._rebuild_unresolved()
            return

        if preview.unresolved_lines:
            self._unresolved_lines[index] = preview.unresolved_lines[0]
            for extra in preview.unresolved_lines[1:]:
                self._unresolved_lines.insert(index + 1, extra)
            self._rebuild_unresolved()
            QMessageBox.information(
                self,
                self._translator.t("inventory.add_list.title"),
                self._translator.t("inventory.add_list.recheck.failed"),
            )
            return

        # Resolved as basic/token (or blank) — drop from unresolved.
        del self._unresolved_lines[index]
        self._rebuild_unresolved()
        QMessageBox.information(
            self,
            self._translator.t("inventory.add_list.title"),
            self._translator.t("inventory.add_list.recheck.skipped"),
        )

    def _replace_card(self, index: int) -> None:
        if index < 0 or index >= len(self._lines):
            return
        line = self._lines[index]
        dialog = CardPickDialog(
            self._translator,
            title=self._translator.t("decks.edit.replace"),
            max_quantity=max(1, line.list_quantity),
            show_available=False,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = dialog.result()
        if result is None:
            return
        if result.is_basic_land or result.is_token:
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                self._translator.t("inventory.add_list.not_trackable"),
            )
            return
        # Merge into existing row if the replacement is already in the table.
        for other_index, other in enumerate(self._lines):
            if other_index == index:
                continue
            if other.oracle_id == result.oracle_id:
                other.list_quantity += line.list_quantity
                other.add_quantity = min(
                    max(other.add_quantity, line.add_quantity),
                    other.list_quantity,
                )
                del self._lines[index]
                self._rebuild_table()
                return
        line.oracle_id = result.oracle_id
        line.name = result.name
        line.list_quantity = max(line.list_quantity, result.quantity)
        line.add_quantity = min(line.add_quantity, line.list_quantity)
        self._rebuild_table()

    def quantities(self) -> dict[str, int]:
        return {
            line.oracle_id: line.add_quantity
            for line in self._lines
            if line.add_quantity > 0
        }


class DeleteDeckDialog(QDialog):
    def __init__(
        self,
        translator: Translator,
        deck_name: str,
        impacts: list[DeckDeleteCardImpact],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._impacts = impacts
        self._steppers: list[QuantityStepper] = []
        self._remaining_items: list[QTableWidgetItem] = []
        self.setWindowTitle(self._translator.t("decks.delete.confirm.title"))
        self.resize(900, 560)
        self._build_ui(deck_name)

    def _build_ui(self, deck_name: str) -> None:
        layout = QVBoxLayout(self)
        question = QLabel(
            self._translator.t("decks.delete.confirm.question").format(name=deck_name)
        )
        question.setWordWrap(True)
        layout.addWidget(question)
        hint = QLabel(self._translator.t("decks.delete.copies.hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._table = QTableWidget(len(self._impacts), 5)
        self._table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("decks.import.available.in_list"),
                self._translator.t("decks.delete.copies.inventory"),
                self._translator.t("decks.delete.copies.remove"),
                self._translator.t("decks.delete.copies.remaining"),
            ]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(3, 160)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row, impact in enumerate(self._impacts):
            self._table.setItem(row, 0, QTableWidgetItem(impact.name))

            in_list = QTableWidgetItem(str(impact.list_quantity))
            in_list.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 1, in_list)

            inventory = QTableWidgetItem(self._inventory_label(impact))
            inventory.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if impact.assigned_elsewhere > 0:
                inventory.setToolTip(
                    self._translator.t("decks.delete.copies.elsewhere_tip").format(
                        count=impact.assigned_elsewhere
                    )
                )
            self._table.setItem(row, 2, inventory)

            stepper = QuantityStepper(impact.removable_copies)
            stepper.setEnabled(impact.removable_copies > 0)
            stepper.valueChanged.connect(
                lambda _value, index=row: self._update_remaining(index)
            )
            self._steppers.append(stepper)
            self._table.setCellWidget(row, 3, stepper)

            remaining = QTableWidgetItem(str(impact.total_copies))
            remaining.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._remaining_items.append(remaining)
            self._table.setItem(row, 4, remaining)

        layout.addWidget(self._table)

        actions = QHBoxLayout()
        keep_all = QPushButton(self._translator.t("decks.delete.copies.keep_all"))
        keep_all.clicked.connect(self._keep_all_copies)
        remove_all = QPushButton(self._translator.t("decks.delete.copies.remove_all"))
        remove_all.clicked.connect(self._remove_all_copies)
        actions.addWidget(keep_all)
        actions.addWidget(remove_all)
        actions.addStretch()
        layout.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText(self._translator.t("decks.delete_list"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _inventory_label(self, impact: DeckDeleteCardImpact) -> str:
        if impact.assigned_elsewhere <= 0:
            return str(impact.total_copies)
        return self._translator.t("decks.delete.copies.inventory_elsewhere").format(
            total=impact.total_copies,
            elsewhere=impact.assigned_elsewhere,
        )

    def _update_remaining(self, row: int) -> None:
        impact = self._impacts[row]
        remaining = impact.total_copies - self._steppers[row].value()
        self._remaining_items[row].setText(str(remaining))

    def _keep_all_copies(self) -> None:
        for stepper in self._steppers:
            stepper.setValue(0)

    def _remove_all_copies(self) -> None:
        for stepper, impact in zip(self._steppers, self._impacts, strict=True):
            stepper.setValue(impact.removable_copies)

    def removals(self) -> dict[str, int]:
        return {
            impact.oracle_id: stepper.value()
            for impact, stepper in zip(self._impacts, self._steppers, strict=True)
            if stepper.value() > 0
        }


@dataclass
class EditableDeckLine:
    oracle_id: str
    name: str
    quantity: int
    role: DeckCardRole
    is_basic_land: bool
    is_token: bool
    removable_copies: int
    baseline_free: int
    desired_free: int


@dataclass
class CardPickResult:
    oracle_id: str
    name: str
    quantity: int
    available: int
    is_basic_land: bool
    is_token: bool
    remove_outgoing: int = 0


class CardPickDialog(QDialog):
    def __init__(
        self,
        translator: Translator,
        *,
        title: str,
        max_quantity: int,
        outgoing: EditableDeckLine | None = None,
        show_available: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._max_quantity = max(1, max_quantity)
        self._outgoing = outgoing
        self._show_available = show_available
        self._results: list[CardSummary] = []
        self.setWindowTitle(title)
        self.resize(560, 480)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._search = QLineEdit()
        self._search.setPlaceholderText(self._translator.t("decks.edit.search"))
        self._search.textChanged.connect(self._refresh_results)
        self._search.returnPressed.connect(self._refresh_results)
        layout.addWidget(self._search)

        self._results_list = QListWidget()
        self._results_list.currentRowChanged.connect(lambda _row: self._sync_available_max())
        layout.addWidget(self._results_list)

        form = QFormLayout()
        self._qty = QuantityStepper(self._max_quantity)
        self._qty.setMinimum(1)
        default_qty = (
            1
            if self._outgoing is None
            else min(self._outgoing.quantity, self._max_quantity)
        )
        self._qty.setValue(max(1, default_qty))
        form.addRow(self._translator.t("decks.edit.quantity"), self._qty)

        self._available = QuantityStepper(self._max_quantity)
        self._available_label = QLabel(self._translator.t("decks.edit.available"))
        form.addRow(self._available_label, self._available)
        self._qty.valueChanged.connect(self._sync_available_max)
        layout.addLayout(form)
        if not self._show_available:
            self._available.setVisible(False)
            self._available_label.setVisible(False)
            self._available.setValue(0)

        self._remove_outgoing_check: QCheckBox | None = None
        self._remove_outgoing_stepper: QuantityStepper | None = None
        if self._outgoing is not None and not self._outgoing.is_basic_land:
            self._remove_outgoing_check = QCheckBox(
                self._translator.t("decks.edit.remove_outgoing")
            )
            layout.addWidget(self._remove_outgoing_check)
            self._remove_outgoing_stepper = QuantityStepper(
                self._outgoing.removable_copies
            )
            self._remove_outgoing_stepper.setEnabled(False)
            self._remove_outgoing_check.toggled.connect(
                self._remove_outgoing_stepper.setEnabled
            )
            form_out = QFormLayout()
            form_out.addRow(
                self._translator.t("decks.edit.remove_outgoing_qty"),
                self._remove_outgoing_stepper,
            )
            layout.addLayout(form_out)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(self._translator.t("decks.edit.pick"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._result: CardPickResult | None = None
        self._sync_available_max()
        self._refresh_results()

    def _sync_available_max(self) -> None:
        qty = self._qty.value()
        self._available.setMaximum(qty)
        selected = self._selected_card()
        unlimited = selected is not None and (
            selected.is_basic_land or selected.is_token
        )
        self._available.setEnabled(not unlimited)
        self._available_label.setEnabled(not unlimited)
        if unlimited:
            self._available.setValue(0)

    def _refresh_results(self) -> None:
        search = self._search.text().strip()
        with get_session() as session:
            cards = BrowseService(session).list_cards(search) if search else []
        self._results = cards[:80]
        self._results_list.clear()
        for card in self._results:
            self._results_list.addItem(card.name)

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
                self._translator.t("decks.edit.no_selection"),
            )
            return
        remove_outgoing = 0
        if (
            self._remove_outgoing_check is not None
            and self._remove_outgoing_check.isChecked()
            and self._remove_outgoing_stepper is not None
        ):
            remove_outgoing = self._remove_outgoing_stepper.value()
        available = 0
        if self._show_available and not (card.is_basic_land or card.is_token):
            available = self._available.value()
        self._result = CardPickResult(
            oracle_id=card.oracle_id,
            name=card.name,
            quantity=self._qty.value(),
            available=available,
            is_basic_land=card.is_basic_land,
            is_token=card.is_token,
            remove_outgoing=remove_outgoing,
        )
        self.accept()

    def result(self) -> CardPickResult | None:
        return self._result


class DeckEditDialog(QDialog):
    def __init__(
        self,
        translator: Translator,
        deck_name: str,
        rows: list[DeckEditRow],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._target_total = sum(row.quantity for row in rows)
        self._lines = [
            EditableDeckLine(
                oracle_id=row.oracle_id,
                name=row.name,
                quantity=row.quantity,
                role=row.role,
                is_basic_land=row.is_basic_land,
                is_token=row.is_token,
                removable_copies=row.removable_copies,
                baseline_free=row.free_copies,
                desired_free=row.free_copies,
            )
            for row in rows
        ]
        self._remove_copies: dict[str, int] = {}
        self._qty_steppers: list[QuantityStepper] = []
        self._free_steppers: list[QuantityStepper | None] = []
        self.setWindowTitle(f"{self._translator.t('decks.edit.title')} — {deck_name}")
        self.resize(960, 600)
        self._build_ui()
        self._rebuild_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._total_label = QLabel("")
        self._slots_label = QLabel("")
        layout.addWidget(self._total_label)
        layout.addWidget(self._slots_label)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(
            [
                self._translator.t("browse.cards.name"),
                self._translator.t("decks.import.available.in_list"),
                self._translator.t("decks.edit.free"),
                self._translator.t("decks.edit.replace"),
            ]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(1, 160)
        self._table.setColumnWidth(2, 160)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._add_button = QPushButton(self._translator.t("decks.edit.add"))
        self._add_button.clicked.connect(self._add_card)
        actions.addWidget(self._add_button)
        actions.addStretch()
        layout.addLayout(actions)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText(self._translator.t("decks.edit.save"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _current_total(self) -> int:
        return sum(line.quantity for line in self._lines)

    def _open_slots(self) -> int:
        return max(0, self._target_total - self._current_total())

    def _update_header(self) -> None:
        self._total_label.setText(
            self._translator.t("decks.edit.total").format(
                current=self._current_total(),
                target=self._target_total,
            )
        )
        slots = self._open_slots()
        self._slots_label.setText(
            self._translator.t("decks.edit.slots").format(slots=slots)
        )
        self._add_button.setEnabled(slots > 0)

    def _rebuild_table(self) -> None:
        self._qty_steppers.clear()
        self._free_steppers.clear()
        self._table.setRowCount(len(self._lines))
        for row, line in enumerate(self._lines):
            self._table.setItem(row, 0, QTableWidgetItem(line.name))

            max_qty = line.quantity + self._open_slots()
            stepper = QuantityStepper(max(max_qty, line.quantity, 1))
            stepper.setMinimum(0)
            stepper.setMaximum(max(max_qty, line.quantity))
            stepper.setValue(line.quantity)
            stepper.valueChanged.connect(
                lambda value, index=row: self._on_qty_changed(index, value)
            )
            self._qty_steppers.append(stepper)
            self._table.setCellWidget(row, 1, stepper)

            if line.is_basic_land or line.is_token:
                free_item = QTableWidgetItem("—")
                free_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, 2, free_item)
                self._free_steppers.append(None)
            else:
                free_stepper = QuantityStepper(max(line.desired_free + 99, 99))
                free_stepper.setMinimum(0)
                free_stepper.setMaximum(max(line.desired_free + 99, 99))
                free_stepper.setValue(line.desired_free)
                free_stepper.valueChanged.connect(
                    lambda value, index=row: self._on_free_changed(index, value)
                )
                self._free_steppers.append(free_stepper)
                self._table.setCellWidget(row, 2, free_stepper)

            replace = QPushButton(self._translator.t("decks.edit.replace"))
            replace.clicked.connect(lambda _checked=False, index=row: self._replace_card(index))
            self._table.setCellWidget(row, 3, replace)

        self._update_header()
        self._refresh_stepper_maxima()

    def _refresh_stepper_maxima(self) -> None:
        slots = self._open_slots()
        for line, stepper in zip(self._lines, self._qty_steppers, strict=True):
            stepper.setMaximum(line.quantity + slots)

    def _on_free_changed(self, index: int, value: int) -> None:
        if index < 0 or index >= len(self._lines):
            return
        line = self._lines[index]
        if line.is_basic_land or line.is_token:
            return
        line.desired_free = value
        stepper = self._free_steppers[index]
        if stepper is not None and value >= stepper.maximum() - 5:
            stepper.setMaximum(value + 99)

    def _on_qty_changed(self, index: int, value: int) -> None:
        if index < 0 or index >= len(self._lines):
            return
        line = self._lines[index]
        if value <= 0:
            del self._lines[index]
            self._rebuild_table()
            return
        # Prevent exceeding target
        others = self._current_total() - line.quantity
        if others + value > self._target_total:
            capped = self._target_total - others
            line.quantity = max(0, capped)
            self._qty_steppers[index].setValue(line.quantity)
            return
        line.quantity = value
        self._update_header()
        self._refresh_stepper_maxima()

    def _add_card(self) -> None:
        slots = self._open_slots()
        if slots <= 0:
            return
        dialog = CardPickDialog(
            self._translator,
            title=self._translator.t("decks.edit.add.title"),
            max_quantity=slots,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        picked = dialog.result()
        if picked is None:
            return
        self._lines.append(
            EditableDeckLine(
                oracle_id=picked.oracle_id,
                name=picked.name,
                quantity=picked.quantity,
                role=DeckCardRole.MAIN,
                is_basic_land=picked.is_basic_land,
                is_token=picked.is_token,
                removable_copies=0,
                baseline_free=0,
                desired_free=picked.available,
            )
        )
        self._rebuild_table()

    def _replace_card(self, index: int) -> None:
        if index < 0 or index >= len(self._lines):
            return
        outgoing = self._lines[index]
        dialog = CardPickDialog(
            self._translator,
            title=self._translator.t("decks.edit.replace.title"),
            max_quantity=outgoing.quantity,
            outgoing=outgoing,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        picked = dialog.result()
        if picked is None:
            return
        if picked.remove_outgoing > 0:
            self._remove_copies[outgoing.oracle_id] = (
                self._remove_copies.get(outgoing.oracle_id, 0) + picked.remove_outgoing
            )
        self._lines[index] = EditableDeckLine(
            oracle_id=picked.oracle_id,
            name=picked.name,
            quantity=picked.quantity,
            role=outgoing.role,
            is_basic_land=picked.is_basic_land,
            is_token=picked.is_token,
            removable_copies=0,
            baseline_free=0,
            desired_free=picked.available,
        )
        self._rebuild_table()

    def _accept(self) -> None:
        if self._current_total() > self._target_total:
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                self._translator.t("decks.edit.over_target"),
            )
            return
        self.accept()

    def edit_lines(self) -> list[DeckEditLine]:
        return [
            DeckEditLine(
                oracle_id=line.oracle_id,
                quantity=line.quantity,
                role=line.role,
            )
            for line in self._lines
            if line.quantity > 0
        ]

    def create_free_copies(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for line in self._lines:
            if line.is_basic_land or line.is_token:
                continue
            delta = line.desired_free - line.baseline_free
            if delta > 0:
                result[line.oracle_id] = result.get(line.oracle_id, 0) + delta
        return result

    def remove_copies(self) -> dict[str, int]:
        result = dict(self._remove_copies)
        for line in self._lines:
            if line.is_basic_land or line.is_token:
                continue
            delta = line.desired_free - line.baseline_free
            if delta < 0:
                result[line.oracle_id] = result.get(line.oracle_id, 0) + (-delta)
        return result
