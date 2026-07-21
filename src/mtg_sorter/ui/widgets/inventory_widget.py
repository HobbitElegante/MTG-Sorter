from PySide6.QtCore import Signal
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import InventoryService, ScryfallService


class InventoryWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._build_ui()
        self.refresh()

    def retranslate(self) -> None:
        self._search_input.setPlaceholderText(self._translator.t("inventory.search"))
        self._add_button.setText(self._translator.t("inventory.add"))
        self._quantity_label.setText(self._translator.t("inventory.quantity"))
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(self._translator.t("inventory.search"))
        form.addRow(self._search_input)

        qty_row = QHBoxLayout()
        self._quantity_label = QLabel(self._translator.t("inventory.quantity"))
        self._quantity_spin = QSpinBox()
        self._quantity_spin.setMinimum(1)
        self._quantity_spin.setMaximum(999)
        qty_row.addWidget(self._quantity_label)
        qty_row.addWidget(self._quantity_spin)
        qty_row.addStretch()
        form.addRow(qty_row)

        self._add_button = QPushButton(self._translator.t("inventory.add"))
        self._add_button.clicked.connect(self._add_card)
        form.addRow(self._add_button)

        layout.addLayout(form)

        self._list = QListWidget()
        layout.addWidget(self._list)

    def refresh(self) -> None:
        self._list.clear()
        with get_session() as session:
            service = InventoryService(session)
            copies = service.list_unassigned_copies()
            if not copies:
                self._list.addItem(self._translator.t("inventory.empty"))
                return
            for copy in copies:
                card = copy.card
                self._list.addItem(f"{card.name} (#{copy.id})")

    def _add_card(self) -> None:
        name = self._search_input.text().strip()
        if not name:
            return
        quantity = self._quantity_spin.value()
        try:
            with get_session() as session:
                scryfall = ScryfallService(session)
                try:
                    card = scryfall.fetch_and_cache(name)
                finally:
                    scryfall.close()
                InventoryService(session).add_copy(card.oracle_id, quantity)
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        self._search_input.clear()
        self.refresh()
        self.changed.emit()
