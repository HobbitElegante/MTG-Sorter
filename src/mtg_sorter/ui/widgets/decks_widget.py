from pathlib import Path

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.models.enums import DeckStatus
from mtg_sorter.services import DeckService, ImportService, ScryfallService
from mtg_sorter.ui.widgets.import_dialogs import (
    AvailableCopiesDialog,
    DeckEditDialog,
    DeleteDeckDialog,
    ExportDeckDialog,
    ImportStatusDialog,
)

DECK_NAME_ROLE = Qt.ItemDataRole.UserRole + 1
DECK_STATUS_ROLE = Qt.ItemDataRole.UserRole + 2


class DeckListItemDelegate(QStyledItemDelegate):
    """Paint deck name on the left and [Armed|Dismantled] flush right."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        self.initStyleOption(option, index)
        painter.save()

        style = option.widget.style() if option.widget is not None else None
        if style is not None:
            style.drawPrimitive(
                QStyle.PrimitiveElement.PE_PanelItemViewItem,
                option,
                painter,
                option.widget,
            )

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        painter.setPen(
            palette.color(
                palette.ColorRole.HighlightedText
                if selected
                else palette.ColorRole.Text
            )
        )
        painter.setFont(option.font)

        name = str(index.data(DECK_NAME_ROLE) or "")
        status = str(index.data(DECK_STATUS_ROLE) or "")
        metrics = option.fontMetrics
        padding = 8
        status_width = metrics.horizontalAdvance(status) + padding
        rect = option.rect.adjusted(padding, 0, -padding, 0)
        name_rect = QRect(rect.left(), rect.top(), max(0, rect.width() - status_width), rect.height())
        status_rect = QRect(
            rect.right() - status_width + padding,
            rect.top(),
            status_width - padding,
            rect.height(),
        )

        elided = metrics.elidedText(
            name, Qt.TextElideMode.ElideRight, name_rect.width()
        )
        painter.drawText(
            name_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elided,
        )
        painter.drawText(
            status_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            status,
        )
        painter.restore()


class DecksWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._build_ui()
        self.refresh()

    def retranslate(self) -> None:
        self._decks_group.setTitle(self._translator.t("decks.list.title"))
        self._import_group.setTitle(self._translator.t("decks.import"))
        self._show_import_button.setText(self._translator.t("decks.show_import"))
        self._load_file_button.setText(self._translator.t("decks.load_file"))
        self._submit_import_button.setText(self._translator.t("decks.submit_import"))
        self._cancel_import_button.setText(self._translator.t("decks.cancel_import"))
        self._name_input.setPlaceholderText(self._translator.t("decks.name"))
        self._commander_input.setPlaceholderText(self._translator.t("decks.commander"))
        self._edit_button.setText(self._translator.t("decks.edit_list"))
        self._delete_button.setText(self._translator.t("decks.delete_list"))
        self._armed_button.setText(self._translator.t("decks.set_armed"))
        self._dismantled_button.setText(self._translator.t("decks.set_dismantled"))
        self._export_button.setText(self._translator.t("decks.export_list"))
        self.refresh()

    def _build_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)

        self._decks_group = QGroupBox(self._translator.t("decks.list.title"))
        decks_layout = QVBoxLayout(self._decks_group)

        self._deck_list = QListWidget()
        self._deck_list.setItemDelegate(DeckListItemDelegate(self._deck_list))
        self._deck_list.currentItemChanged.connect(self._on_selection_changed)
        decks_layout.addWidget(self._deck_list, 1)

        self._details = QLabel("")
        self._details.setWordWrap(True)
        decks_layout.addWidget(self._details)

        self._deck_actions = QWidget()
        actions_layout = QHBoxLayout(self._deck_actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        self._edit_button = QPushButton(self._translator.t("decks.edit_list"))
        self._edit_button.clicked.connect(self._edit_selected_deck)
        self._delete_button = QPushButton(self._translator.t("decks.delete_list"))
        self._delete_button.clicked.connect(self._delete_selected_deck)
        self._armed_button = QPushButton(self._translator.t("decks.set_armed"))
        self._dismantled_button = QPushButton(
            self._translator.t("decks.set_dismantled")
        )
        self._export_button = QPushButton(self._translator.t("decks.export_list"))
        self._armed_button.clicked.connect(lambda: self._set_status(DeckStatus.ARMED))
        self._dismantled_button.clicked.connect(
            lambda: self._set_status(DeckStatus.DISMANTLED)
        )
        self._export_button.clicked.connect(self._export_selected_deck)
        actions_layout.addWidget(self._edit_button)
        actions_layout.addWidget(self._delete_button)
        actions_layout.addWidget(self._armed_button)
        actions_layout.addWidget(self._export_button)
        actions_layout.addWidget(self._dismantled_button)
        actions_layout.addStretch()
        decks_layout.addWidget(self._deck_actions)
        self._deck_actions.setVisible(False)

        # Stretch 1: list fills the tab until the import panel opens.
        self._main_layout.addWidget(self._decks_group, 1)

        trigger_row = QHBoxLayout()
        self._show_import_button = QPushButton(self._translator.t("decks.show_import"))
        self._show_import_button.clicked.connect(self._show_import_section)
        trigger_row.addWidget(self._show_import_button)
        trigger_row.addStretch()
        self._main_layout.addLayout(trigger_row)

        self._import_group = QGroupBox(self._translator.t("decks.import"))
        import_layout = QVBoxLayout(self._import_group)

        form = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText(self._translator.t("decks.name"))
        form.addRow(self._name_input)

        self._commander_input = QLineEdit()
        self._commander_input.setPlaceholderText(self._translator.t("decks.commander"))
        form.addRow(self._commander_input)

        import_layout.addLayout(form)

        self._import_text = QTextEdit()
        self._import_text.setPlaceholderText("1 Sol Ring\n1 Arcane Signet")
        import_layout.addWidget(self._import_text, 1)

        import_buttons = QHBoxLayout()
        self._load_file_button = QPushButton(self._translator.t("decks.load_file"))
        self._load_file_button.clicked.connect(self._load_file)
        self._submit_import_button = QPushButton(
            self._translator.t("decks.submit_import")
        )
        self._submit_import_button.clicked.connect(self._import_text_deck)
        self._cancel_import_button = QPushButton(
            self._translator.t("decks.cancel_import")
        )
        self._cancel_import_button.clicked.connect(self._hide_import_section)
        import_buttons.addWidget(self._load_file_button)
        import_buttons.addWidget(self._submit_import_button)
        import_buttons.addWidget(self._cancel_import_button)
        import_buttons.addStretch()
        import_layout.addLayout(import_buttons)

        self._import_group.setVisible(False)
        # Stretch 0 while hidden; becomes 1 when open so list/import share ~50/50.
        self._main_layout.addWidget(self._import_group, 0)

    @staticmethod
    def _format_deck_label(
        index: int, name: str, status: DeckStatus, translator: Translator
    ) -> tuple[str, str]:
        status_text = (
            translator.t("decks.status.armed")
            if status == DeckStatus.ARMED
            else translator.t("decks.status.dismantled")
        )
        return f"{index}. {name}", f"[{status_text}]"

    def _show_import_section(self) -> None:
        self._import_group.setVisible(True)
        self._main_layout.setStretchFactor(self._decks_group, 1)
        self._main_layout.setStretchFactor(self._import_group, 1)

    def _hide_import_section(self) -> None:
        self._import_group.setVisible(False)
        self._main_layout.setStretchFactor(self._import_group, 0)
        self._main_layout.setStretchFactor(self._decks_group, 1)

    def refresh(self) -> None:
        selected_id = self._selected_deck_id()
        self._deck_list.clear()
        with get_session() as session:
            decks = DeckService(session).list_decks()
            if not decks:
                self._deck_list.addItem(self._translator.t("decks.empty"))
                self._deck_actions.setVisible(False)
                self._details.setText("")
                return
            for index, deck in enumerate(decks, start=1):
                name_label, status_label = self._format_deck_label(
                    index, deck.name, deck.status, self._translator
                )
                item = QListWidgetItem(name_label)
                item.setData(Qt.ItemDataRole.UserRole, deck.id)
                item.setData(DECK_NAME_ROLE, name_label)
                item.setData(DECK_STATUS_ROLE, status_label)
                self._deck_list.addItem(item)
                if deck.id == selected_id:
                    self._deck_list.setCurrentItem(item)

        if self._deck_list.currentItem() is None and self._deck_list.count() > 0:
            first = self._deck_list.item(0)
            if first is not None and first.data(Qt.ItemDataRole.UserRole) is not None:
                self._deck_list.setCurrentRow(0)

    def _selected_deck_id(self) -> int | None:
        item = self._deck_list.currentItem()
        if item is None:
            return None
        deck_id = item.data(Qt.ItemDataRole.UserRole)
        return deck_id if isinstance(deck_id, int) else None

    def _update_status_buttons(self, status: DeckStatus) -> None:
        if status == DeckStatus.ARMED:
            self._armed_button.setVisible(False)
            self._dismantled_button.setVisible(True)
            return
        self._armed_button.setVisible(True)
        self._dismantled_button.setVisible(False)

    def _on_selection_changed(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            self._details.setText("")
            self._deck_actions.setVisible(False)
            return

        self._deck_actions.setVisible(True)
        with get_session() as session:
            service = DeckService(session)
            deck = service.get_deck(deck_id)
            if deck is None:
                return
            self._update_status_buttons(deck.status)
            card_count = sum(card.quantity for card in deck.cards)
            if deck.status == DeckStatus.ARMED:
                self._details.setText(
                    self._translator.t("decks.details.armed").format(count=card_count)
                )
            else:
                available = service.free_coverage_toward_deck(deck_id)
                self._details.setText(
                    self._translator.t("decks.details.dismantled").format(
                        count=card_count,
                        available=available,
                    )
                )

    def _export_selected_deck(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return

        try:
            with get_session() as session:
                deck = DeckService(session).get_deck(deck_id)
                if deck is None:
                    return
                deck_name = deck.name
                scryfall = ScryfallService(session)
                try:
                    text = ImportService(session, scryfall).deck_to_moxfield_text(
                        deck_id
                    )
                finally:
                    scryfall.close()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        ExportDeckDialog(self._translator, deck_name, text, self).exec()

    def _edit_selected_deck(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return

        with get_session() as session:
            service = DeckService(session)
            deck = service.get_deck(deck_id)
            if deck is None:
                return
            deck_name = deck.name
            rows = service.deck_edit_rows(deck_id)

        dialog = DeckEditDialog(self._translator, deck_name, rows, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            with get_session() as session:
                DeckService(session).apply_deck_edit(
                    deck_id,
                    dialog.edit_lines(),
                    create_free_copies=dialog.create_free_copies(),
                    remove_copies=dialog.remove_copies(),
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        self.refresh()
        self.changed.emit()

    def _delete_selected_deck(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return

        with get_session() as session:
            service = DeckService(session)
            deck = service.get_deck(deck_id)
            if deck is None:
                return
            deck_name = deck.name
            impacts = service.deck_delete_impact(deck_id)

        dialog = DeleteDeckDialog(self._translator, deck_name, impacts, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        with get_session() as session:
            DeckService(session).delete_deck(deck_id, dialog.removals())

        self.refresh()
        self.changed.emit()

    def _import_text_deck(self) -> None:
        name = self._name_input.text().strip()
        text = self._import_text.toPlainText().strip()
        commander = self._commander_input.text().strip() or None
        if not name or not text:
            return

        status_dialog = ImportStatusDialog(self._translator, self)
        if status_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        status = status_dialog.selected_status()

        try:
            with get_session() as session:
                scryfall = ScryfallService(session)
                try:
                    importer = ImportService(session, scryfall)
                    result = importer.import_moxfield_text(
                        deck_name=name,
                        text=text,
                        status=status,
                        commander_name=commander,
                    )
                    if status == DeckStatus.ARMED:
                        DeckService(session).set_status(result.deck, DeckStatus.ARMED)
                    deck_id = result.deck.id
                    warnings = list(result.warnings)
                finally:
                    scryfall.close()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        if status == DeckStatus.DISMANTLED:
            try:
                with get_session() as session:
                    scryfall = ScryfallService(session)
                    try:
                        trackable = ImportService(
                            session, scryfall
                        ).list_trackable_cards(deck_id)
                    finally:
                        scryfall.close()
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    self._translator.t("common.error"),
                    str(exc),
                )
                return

            if trackable:
                availability = AvailableCopiesDialog(
                    self._translator,
                    trackable,
                    self,
                )
                if availability.exec() == QDialog.DialogCode.Accepted:
                    quantities = availability.quantities()
                    if quantities:
                        try:
                            with get_session() as session:
                                scryfall = ScryfallService(session)
                                try:
                                    ImportService(
                                        session, scryfall
                                    ).apply_available_copies(quantities)
                                finally:
                                    scryfall.close()
                        except Exception as exc:
                            QMessageBox.critical(
                                self,
                                self._translator.t("common.error"),
                                str(exc),
                            )
                            return

        if warnings:
            warning_text = "\n".join(
                f"{warning.line}: {warning.message}" for warning in warnings[:10]
            )
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                warning_text,
            )

        self._name_input.clear()
        self._commander_input.clear()
        self._import_text.clear()
        self._hide_import_section()
        self.refresh()
        self.changed.emit()

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translator.t("decks.load_file.dialog_title"),
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
