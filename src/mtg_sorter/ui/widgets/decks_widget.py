from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.models.enums import DeckStatus
from mtg_sorter.services import DeckService, ImportService, ScryfallService


class DecksWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._build_ui()
        self.refresh()

    def retranslate(self) -> None:
        self._import_button.setText(self._translator.t("decks.import"))
        self._name_input.setPlaceholderText(self._translator.t("decks.name"))
        self._commander_input.setPlaceholderText(self._translator.t("decks.commander"))
        self._armed_button.setText(self._translator.t("decks.set_armed"))
        self._dismantled_button.setText(self._translator.t("decks.set_dismantled"))
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        import_group = QGroupBox(self._translator.t("decks.import"))
        import_layout = QVBoxLayout(import_group)

        form = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText(self._translator.t("decks.name"))
        form.addRow(self._name_input)

        self._commander_input = QLineEdit()
        self._commander_input.setPlaceholderText(self._translator.t("decks.commander"))
        form.addRow(self._commander_input)

        self._import_text = QTextEdit()
        self._import_text.setPlaceholderText("1 Sol Ring\n1 Arcane Signet")
        form.addRow(self._import_text)

        import_layout.addLayout(form)

        buttons = QHBoxLayout()
        self._import_button = QPushButton(self._translator.t("decks.import"))
        self._import_button.clicked.connect(self._import_text_deck)
        load_file_button = QPushButton("Load file…")
        load_file_button.clicked.connect(self._load_file)
        buttons.addWidget(self._import_button)
        buttons.addWidget(load_file_button)
        import_layout.addLayout(buttons)

        layout.addWidget(import_group)

        self._deck_list = QListWidget()
        self._deck_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._deck_list)

        status_row = QHBoxLayout()
        self._armed_button = QPushButton(self._translator.t("decks.set_armed"))
        self._dismantled_button = QPushButton(self._translator.t("decks.set_dismantled"))
        self._armed_button.clicked.connect(lambda: self._set_status(DeckStatus.ARMED))
        self._dismantled_button.clicked.connect(
            lambda: self._set_status(DeckStatus.DISMANTLED)
        )
        status_row.addWidget(self._armed_button)
        status_row.addWidget(self._dismantled_button)
        layout.addLayout(status_row)

        self._details = QLabel("")
        layout.addWidget(self._details)

    def refresh(self) -> None:
        self._deck_list.clear()
        with get_session() as session:
            decks = DeckService(session).list_decks()
            if not decks:
                self._deck_list.addItem(self._translator.t("decks.empty"))
                return
            for deck in decks:
                status = (
                    self._translator.t("decks.status.armed")
                    if deck.status == DeckStatus.ARMED
                    else self._translator.t("decks.status.dismantled")
                )
                self._deck_list.addItem(f"[{status}] {deck.name} (id={deck.id})")

    def _selected_deck_id(self) -> int | None:
        item = self._deck_list.currentItem()
        if item is None:
            return None
        text = item.text()
        if "id=" not in text:
            return None
        return int(text.rsplit("id=", maxsplit=1)[1].rstrip(")"))

    def _on_selection_changed(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            self._details.setText("")
            return
        with get_session() as session:
            deck = DeckService(session).get_deck(deck_id)
            if deck is None:
                return
            card_count = sum(card.quantity for card in deck.cards)
            self._details.setText(f"{deck.name}: {card_count} list entries")

    def _import_text_deck(self) -> None:
        name = self._name_input.text().strip()
        text = self._import_text.toPlainText().strip()
        commander = self._commander_input.text().strip() or None
        if not name or not text:
            return
        try:
            with get_session() as session:
                scryfall = ScryfallService(session)
                try:
                    result = ImportService(session, scryfall).import_moxfield_text(
                        deck_name=name,
                        text=text,
                        commander_name=commander,
                    )
                finally:
                    scryfall.close()
                if result.warnings:
                    warning_text = "\n".join(
                        f"{warning.line}: {warning.message}"
                        for warning in result.warnings[:10]
                    )
                    QMessageBox.warning(
                        self,
                        self._translator.t("common.error"),
                        warning_text,
                    )
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        self._name_input.clear()
        self._commander_input.clear()
        self._import_text.clear()
        self.refresh()
        self.changed.emit()

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Moxfield export",
            str(Path.home()),
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return
        content = Path(path).read_text(encoding="utf-8")
        self._import_text.setPlainText(content)
        if not self._name_input.text().strip():
            self._name_input.setText(Path(path).stem)

    def _set_status(self, status: DeckStatus) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return
        with get_session() as session:
            service = DeckService(session)
            deck = service.get_deck(deck_id)
            if deck is None:
                return
            service.set_status(deck, status)
        self.refresh()
        self.changed.emit()
