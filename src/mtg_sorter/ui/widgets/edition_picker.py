"""Shared widgets for assigning a set code to physical copies."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from mtg_sorter.config import UNSPECIFIED_EDITION_LABEL
from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import ScryfallService


def normalize_edition(text: str) -> str | None:
    """Free-typed set codes are stored uppercase; blank means unspecified."""
    cleaned = text.strip().upper()
    if not cleaned or cleaned == UNSPECIFIED_EDITION_LABEL:
        return None
    return cleaned


class EditionComboBox(QComboBox):
    """Editable set-code picker that loads printings when first opened.

    The oracle cache has one row per card, so the list of sets is fetched from
    Scryfall the first time the user opens the popup and cached from then on.
    Offline it stays usable: the current value and free typing still work.
    """

    def __init__(
        self,
        oracle_id: str,
        current: str | None,
        translator: Translator,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._oracle_id = oracle_id
        self._translator = translator
        self._loaded = False
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._populate([], current)

    def _populate(self, prints: list[tuple[str, str | None]], current: str | None) -> None:
        self.blockSignals(True)
        self.clear()
        self.addItem(UNSPECIFIED_EDITION_LABEL, None)
        codes = {code for code, _ in prints}
        for code, set_name in prints:
            self.addItem(f"{code} — {set_name}" if set_name else code, code)
        if current and current not in codes:
            self.addItem(current, current)
        index = self.findData(current) if current else 0
        self.setCurrentIndex(index if index >= 0 else 0)
        self.blockSignals(False)

    def showPopup(self) -> None:
        if not self._loaded:
            self._loaded = True
            try:
                with get_session() as session:
                    service = ScryfallService(session)
                    try:
                        prints = service.list_prints(self._oracle_id)
                    finally:
                        service.close()
            except Exception:
                prints = []
            if prints:
                self._populate(prints, self.edition())
        super().showPopup()

    def edition(self) -> str | None:
        index = self.currentIndex()
        if index >= 0 and self.currentText() == self.itemText(index):
            data = self.itemData(index)
            return str(data) if data is not None else None
        return normalize_edition(self.currentText())

    def set_edition(self, edition: str | None) -> None:
        index = self.findData(edition) if edition else 0
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setEditText(edition or UNSPECIFIED_EDITION_LABEL)


class CopyEditionTable(QTableWidget):
    """One row per physical copy: what it is, where it lives, which edition."""

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(0, 2, parent)
        self._translator = translator
        self._combos: dict[int, EditionComboBox] = {}
        self.setHorizontalHeaderLabels(self._header_labels())
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

    def _header_labels(self) -> list[str]:
        return [
            self._translator.t("inventory.editions.copy"),
            self._translator.t("inventory.editions.edition"),
        ]

    def set_copies(self, copies: list[tuple[int, str, str, str | None]]) -> None:
        """``copies`` holds ``(copy_id, oracle_id, label, current_edition)``."""
        self._combos.clear()
        self.setRowCount(len(copies))
        for index, (copy_id, oracle_id, label, edition) in enumerate(copies):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.setItem(index, 0, item)
            combo = EditionComboBox(oracle_id, edition, self._translator)
            self.setCellWidget(index, 1, combo)
            self._combos[copy_id] = combo

    def apply_to_all(self, edition: str | None) -> None:
        for combo in self._combos.values():
            combo.set_edition(edition)

    def editions(self) -> dict[int, str | None]:
        return {copy_id: combo.edition() for copy_id, combo in self._combos.items()}

    def retranslate(self) -> None:
        self.setHorizontalHeaderLabels(self._header_labels())
