from pathlib import Path

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox,
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
from mtg_sorter.models.enums import DeckCardRole, DeckStatus
from mtg_sorter.services import (
    DeckService,
    ImportService,
    ScryfallService,
    SettingsService,
)
from mtg_sorter.services.decklist_parser import DecklistFormat, detect_format
from mtg_sorter.ui.inventory_display import format_commander_legality_tooltip
from mtg_sorter.ui.widgets.card_preview import CardPreviewPanel, build_preview_splitter
from mtg_sorter.ui.widgets.import_dialogs import (
    AvailableCopiesDialog,
    CommandZoneFields,
    DeckDetailsDialog,
    DeckEditDialog,
    DeckListUpdateDialog,
    DeleteDeckDialog,
    ExportDeckDialog,
    ImportStatusDialog,
)

DECK_NAME_ROLE = Qt.ItemDataRole.UserRole + 1
DECK_STATUS_ROLE = Qt.ItemDataRole.UserRole + 2
DECK_WARNING_ROLE = Qt.ItemDataRole.UserRole + 3


class DeckListItemDelegate(QStyledItemDelegate):
    """Paint deck name on the left; optional ⚠ then [Armed|Dismantled] flush right."""

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
        warning = str(index.data(DECK_WARNING_ROLE) or "")
        metrics = option.fontMetrics
        padding = 8
        gap = 6
        status_width = metrics.horizontalAdvance(status)
        warning_width = metrics.horizontalAdvance(warning) if warning else 0
        trailing = status_width + (gap + warning_width if warning else 0) + padding
        rect = option.rect.adjusted(padding, 0, -padding, 0)
        name_rect = QRect(
            rect.left(),
            rect.top(),
            max(0, rect.width() - trailing),
            rect.height(),
        )
        cursor_x = rect.right() - status_width + 1
        status_rect = QRect(
            cursor_x,
            rect.top(),
            status_width,
            rect.height(),
        )
        if warning:
            warn_rect = QRect(
                cursor_x - gap - warning_width,
                rect.top(),
                warning_width,
                rect.height(),
            )
            painter.drawText(
                warn_rect,
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                warning,
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
        self._status_filter: DeckStatus | None = None
        # Deck being re-synced from a paste/URL; None while importing a new deck.
        self._update_deck_id: int | None = None
        self._update_deck_name = ""
        with get_session() as session:
            self._show_card_images = SettingsService(session).get_show_card_images()
        self._build_ui()
        self.refresh()

    def set_show_card_images(self, enabled: bool) -> None:
        self._show_card_images = enabled
        self._command_zone_previews.setVisible(enabled)

    def retranslate(self) -> None:
        self._decks_group.setTitle(self._translator.t("decks.list.title"))
        self._show_import_button.setText(self._translator.t("decks.show_import"))
        self._load_file_button.setText(self._translator.t("decks.load_file"))
        self._cancel_import_button.setText(self._translator.t("decks.cancel_import"))
        self._update_list_button.setText(self._translator.t("decks.update_list"))
        self._retranslate_import_panel()
        self._name_input.setPlaceholderText(self._translator.t("decks.name"))
        self._import_text.setPlaceholderText(
            self._translator.t("decks.import.placeholder")
        )
        self._command_zone.retranslate()
        self._edit_details_button.setText(self._translator.t("decks.edit_details"))
        self._edit_button.setText(self._translator.t("decks.edit_list"))
        self._delete_button.setText(self._translator.t("decks.delete_list"))
        self._armed_button.setText(self._translator.t("decks.set_armed"))
        self._dismantled_button.setText(self._translator.t("decks.set_dismantled"))
        self._export_button.setText(self._translator.t("decks.export_list"))
        self._move_up_button.setText(self._translator.t("decks.move_up"))
        self._move_down_button.setText(self._translator.t("decks.move_down"))
        self._search.setPlaceholderText(self._translator.t("decks.search"))
        self._filter_label.setText(self._translator.t("decks.filter.label"))
        self._commander_preview.retranslate()
        self._secondary_preview.retranslate()
        self._retranslate_filter()
        self.refresh()

    def _retranslate_import_panel(self) -> None:
        """Import panel doubles as the update panel; labels follow the mode."""
        if self._update_deck_id is None:
            self._import_group.setTitle(self._translator.t("decks.import"))
            self._submit_import_button.setText(
                self._translator.t("decks.submit_import")
            )
            return
        self._import_group.setTitle(
            self._translator.t("decks.update.title").format(
                name=self._update_deck_name
            )
        )
        self._submit_import_button.setText(self._translator.t("decks.update.submit"))

    def _retranslate_filter(self) -> None:
        current = self._filter_combo.currentData()
        self._filter_combo.blockSignals(True)
        self._filter_combo.clear()
        self._filter_combo.addItem(self._translator.t("decks.filter.all"), None)
        self._filter_combo.addItem(
            self._translator.t("decks.filter.armed"), DeckStatus.ARMED
        )
        self._filter_combo.addItem(
            self._translator.t("decks.filter.dismantled"), DeckStatus.DISMANTLED
        )
        index = self._filter_combo.findData(current)
        self._filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self._filter_combo.blockSignals(False)

    def _build_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)

        self._decks_group = QGroupBox(self._translator.t("decks.list.title"))
        decks_layout = QVBoxLayout(self._decks_group)

        filter_row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(self._translator.t("decks.search"))
        self._search.textChanged.connect(self.refresh)
        self._filter_label = QLabel(self._translator.t("decks.filter.label"))
        self._filter_combo = QComboBox()
        self._filter_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._retranslate_filter()
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._move_up_button = QPushButton(self._translator.t("decks.move_up"))
        self._move_down_button = QPushButton(self._translator.t("decks.move_down"))
        self._move_up_button.clicked.connect(lambda: self._move_selected(-1))
        self._move_down_button.clicked.connect(lambda: self._move_selected(1))
        filter_row.addWidget(self._search, 1)
        filter_row.addWidget(self._filter_label)
        filter_row.addWidget(self._filter_combo)
        filter_row.addWidget(self._move_up_button)
        filter_row.addWidget(self._move_down_button)
        decks_layout.addLayout(filter_row)

        self._deck_list = QListWidget()
        self._deck_list.setItemDelegate(DeckListItemDelegate(self._deck_list))
        self._deck_list.currentItemChanged.connect(self._on_selection_changed)

        self._details = QLabel("")
        self._details.setWordWrap(True)

        list_column = QWidget()
        list_layout = QVBoxLayout(list_column)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addWidget(self._deck_list, 1)
        list_layout.addWidget(self._details)

        self._commander_preview = CardPreviewPanel(self._translator)
        self._secondary_preview = CardPreviewPanel(
            self._translator, show_title=False
        )
        self._secondary_preview.setVisible(False)
        self._command_zone_previews = QWidget()
        zone_layout = QVBoxLayout(self._command_zone_previews)
        zone_layout.setContentsMargins(0, 0, 0, 0)
        zone_layout.addWidget(self._commander_preview, 1)
        zone_layout.addWidget(self._secondary_preview, 1)
        self._command_zone_previews.setVisible(self._show_card_images)

        decks_layout.addWidget(
            build_preview_splitter(list_column, self._command_zone_previews), 1
        )

        self._deck_actions = QWidget()
        actions_layout = QHBoxLayout(self._deck_actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        self._edit_details_button = QPushButton(
            self._translator.t("decks.edit_details")
        )
        self._edit_details_button.clicked.connect(self._edit_selected_details)
        self._edit_button = QPushButton(self._translator.t("decks.edit_list"))
        self._edit_button.clicked.connect(self._edit_selected_deck)
        self._update_list_button = QPushButton(
            self._translator.t("decks.update_list")
        )
        self._update_list_button.clicked.connect(self._update_selected_deck_list)
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
        actions_layout.addWidget(self._update_list_button)
        actions_layout.addWidget(self._edit_details_button)
        actions_layout.addWidget(self._export_button)
        actions_layout.addWidget(self._delete_button)
        actions_layout.addStretch()
        actions_layout.addWidget(self._armed_button)
        actions_layout.addWidget(self._dismantled_button)
        decks_layout.addWidget(self._deck_actions)
        self._deck_actions.setVisible(False)

        # Stretch 1: list fills the tab until the import panel opens.
        self._main_layout.addWidget(self._decks_group, 1)

        trigger_row = QHBoxLayout()
        self._show_import_button = QPushButton(self._translator.t("decks.show_import"))
        self._show_import_button.clicked.connect(self._start_new_import)
        trigger_row.addWidget(self._show_import_button)
        trigger_row.addStretch()
        self._main_layout.addLayout(trigger_row)

        self._import_group = QGroupBox(self._translator.t("decks.import"))
        import_layout = QVBoxLayout(self._import_group)

        form = QFormLayout()
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText(self._translator.t("decks.name"))
        form.addRow(self._name_input)
        import_layout.addLayout(form)

        self._command_zone = CommandZoneFields(
            self._translator,
            labeled=False,
        )
        import_layout.addWidget(self._command_zone)

        self._import_text = QTextEdit()
        self._import_text.setPlaceholderText(
            self._translator.t("decks.import.placeholder")
        )
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
        # Stretch 0 while hidden; becomes 1 (full tab) when import is open.
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

    def _start_new_import(self) -> None:
        self._update_deck_id = None
        self._update_deck_name = ""
        self._name_input.setReadOnly(False)
        self._retranslate_import_panel()
        self._show_import_section()
        self._name_input.setFocus()

    def _show_import_section(self) -> None:
        self._decks_group.setVisible(False)
        self._show_import_button.setVisible(False)
        self._import_group.setVisible(True)
        self._main_layout.setStretchFactor(self._decks_group, 0)
        self._main_layout.setStretchFactor(self._import_group, 1)

    def _hide_import_section(self) -> None:
        self._update_deck_id = None
        self._update_deck_name = ""
        self._name_input.setReadOnly(False)
        self._retranslate_import_panel()
        self._import_group.setVisible(False)
        self._decks_group.setVisible(True)
        self._show_import_button.setVisible(True)
        self._main_layout.setStretchFactor(self._import_group, 0)
        self._main_layout.setStretchFactor(self._decks_group, 1)

    def _on_filter_changed(self) -> None:
        data = self._filter_combo.currentData()
        self._status_filter = data if isinstance(data, DeckStatus) else None
        self.refresh()

    def refresh(self) -> None:
        selected_id = self._selected_deck_id()
        self._deck_list.clear()
        needle = self._search.text().strip().casefold()
        with get_session() as session:
            service = DeckService(session)
            decks = service.list_decks(status=self._status_filter)
            if needle:
                decks = [
                    deck
                    for deck in decks
                    if needle in deck.name.casefold()
                    or needle
                    in (service.commander_name(deck.id) or "").casefold()
                ]
            if not decks:
                empty_key = (
                    "decks.empty_filtered"
                    if self._status_filter is not None or needle
                    else "decks.empty"
                )
                self._deck_list.addItem(self._translator.t(empty_key))
                self._deck_actions.setVisible(False)
                self._details.setText("")
                self._update_move_buttons()
                return
            for index, deck in enumerate(decks, start=1):
                name_label, status_label = self._format_deck_label(
                    index, deck.name, deck.status, self._translator
                )
                issues = service.commander_legality_issues(deck.id)
                item = QListWidgetItem(name_label)
                item.setData(Qt.ItemDataRole.UserRole, deck.id)
                item.setData(DECK_NAME_ROLE, name_label)
                item.setData(DECK_STATUS_ROLE, status_label)
                if issues:
                    item.setData(
                        DECK_WARNING_ROLE,
                        self._translator.t("decks.legality.warning"),
                    )
                    item.setToolTip(
                        format_commander_legality_tooltip(issues, self._translator)
                    )
                else:
                    item.setData(DECK_WARNING_ROLE, "")
                    item.setToolTip("")
                self._deck_list.addItem(item)
                if deck.id == selected_id:
                    self._deck_list.setCurrentItem(item)

        if self._deck_list.currentItem() is None and self._deck_list.count() > 0:
            first = self._deck_list.item(0)
            if first is not None and first.data(Qt.ItemDataRole.UserRole) is not None:
                self._deck_list.setCurrentRow(0)
        self._update_move_buttons()

    def _selected_deck_id(self) -> int | None:
        item = self._deck_list.currentItem()
        if item is None:
            return None
        deck_id = item.data(Qt.ItemDataRole.UserRole)
        return deck_id if isinstance(deck_id, int) else None

    def _update_move_buttons(self) -> None:
        row = self._deck_list.currentRow()
        count = self._deck_list.count()
        has_deck = self._selected_deck_id() is not None
        self._move_up_button.setEnabled(has_deck and row > 0)
        self._move_down_button.setEnabled(has_deck and row >= 0 and row < count - 1)

    def _update_status_buttons(self, status: DeckStatus) -> None:
        if status == DeckStatus.ARMED:
            self._armed_button.setVisible(False)
            self._dismantled_button.setVisible(True)
            return
        self._armed_button.setVisible(True)
        self._dismantled_button.setVisible(False)

    def _update_command_zone_previews(self, cards: list[tuple[str, str]]) -> None:
        if cards:
            self._commander_preview.set_card(cards[0][0], cards[0][1])
        else:
            self._commander_preview.clear()
        if len(cards) > 1:
            self._secondary_preview.set_card(cards[1][0], cards[1][1])
            self._secondary_preview.setVisible(True)
        else:
            self._secondary_preview.clear()
            self._secondary_preview.setVisible(False)

    def _on_selection_changed(self) -> None:
        deck_id = self._selected_deck_id()
        self._update_move_buttons()
        if deck_id is None:
            self._details.setText("")
            self._deck_actions.setVisible(False)
            self._update_command_zone_previews([])
            return

        self._deck_actions.setVisible(True)
        with get_session() as session:
            service = DeckService(session)
            deck = service.get_deck(deck_id)
            if deck is None:
                return
            self._update_command_zone_previews(service.command_zone_cards(deck_id))
            self._update_status_buttons(deck.status)
            card_count = sum(card.quantity for card in deck.cards)
            commander = service.commander_name(deck_id)
            secondary = service.secondary_command_zone(deck_id)
            lines: list[str] = []
            if deck.status == DeckStatus.ARMED:
                lines.append(
                    self._translator.t("decks.details.armed").format(count=card_count)
                )
            else:
                coverage = service.free_coverage_toward_deck(deck_id)
                lines.append(
                    self._translator.t("decks.details.dismantled").format(
                        count=card_count,
                        available=coverage.covered,
                        needed=coverage.required,
                    )
                )
            if commander:
                lines.append(
                    self._translator.t("decks.details.commander").format(name=commander)
                )
            else:
                lines.append(self._translator.t("decks.details.commander_none"))
            if secondary is not None:
                role, name = secondary
                role_i18n = {
                    DeckCardRole.PARTNER: "decks.role.partner",
                    DeckCardRole.COMPANION: "decks.role.companion",
                    DeckCardRole.BACKGROUND: "decks.role.background",
                }
                lines.append(
                    self._translator.t("decks.details.secondary").format(
                        role=self._translator.t(role_i18n[role]),
                        name=name,
                    )
                )
            self._details.setText("\n".join(lines))

    def _move_selected(self, direction: int) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return
        with get_session() as session:
            moved = DeckService(session).move_deck(
                deck_id,
                direction=direction,
                status=self._status_filter,
            )
        if moved:
            # Reorder only — do not emit changed (that refreshes Inventory/Browse).
            self.refresh()

    def _edit_selected_details(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return

        with get_session() as session:
            service = DeckService(session)
            deck = service.get_deck(deck_id)
            if deck is None:
                return
            deck_name = deck.name
            commander = service.commander_name(deck_id)
            secondary = service.secondary_command_zone(deck_id)

        dialog = DeckDetailsDialog(
            self._translator, deck_name, commander, secondary, self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_name = dialog.deck_name()
        new_commander = dialog.commander_name()
        secondary_role = dialog.secondary_role()
        secondary_name = dialog.secondary_name()
        try:
            with get_session() as session:
                service = DeckService(session)
                service.rename_deck(deck_id, new_name)
                scryfall = ScryfallService(session)
                try:
                    if new_commander is None:
                        service.set_commander(deck_id, None)
                    else:
                        card = scryfall.lookup_local(new_commander)
                        if card is None:
                            raise ValueError(
                                self._translator.t(
                                    "decks.details_edit.commander_not_found"
                                ).format(name=new_commander)
                            )
                        service.set_commander(deck_id, card.oracle_id)

                    if secondary_role is None or secondary_name is None:
                        service.set_secondary_command_zone(deck_id, None, None)
                    else:
                        card = scryfall.lookup_local(secondary_name)
                        if card is None:
                            raise ValueError(
                                self._translator.t(
                                    "decks.details_edit.commander_not_found"
                                ).format(name=secondary_name)
                            )
                        service.set_secondary_command_zone(
                            deck_id, secondary_role, card.oracle_id
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

        self.refresh()
        self.changed.emit()

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

    def _update_selected_deck_list(self) -> None:
        """Open the import panel bound to the selected deck (replace its list)."""
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return

        with get_session() as session:
            service = DeckService(session)
            deck = service.get_deck(deck_id)
            if deck is None:
                return
            deck_name = deck.name
            commander = service.commander_name(deck_id)
            secondary = service.secondary_command_zone(deck_id)

        self._update_deck_id = deck_id
        self._update_deck_name = deck_name
        self._name_input.setText(deck_name)
        self._name_input.setReadOnly(True)
        self._command_zone.clear()
        self._command_zone.set_commander_name(commander)
        if secondary is not None:
            self._command_zone.set_secondary(secondary[0], secondary[1])
        self._import_text.clear()
        self._retranslate_import_panel()
        self._show_import_section()
        self._import_text.setFocus()

    def _apply_list_update(self, deck_id: int, text: str) -> None:
        secondary_error = self._command_zone.validation_error()
        if secondary_error is not None:
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                secondary_error,
            )
            return

        commander = self._command_zone.commander_name()
        secondary_role = self._command_zone.secondary_role()
        secondary_name = self._command_zone.secondary_name()

        try:
            with get_session() as session:
                service = DeckService(session)
                deck = service.get_deck(deck_id)
                if deck is None:
                    return
                deck_name = deck.name
                armed = deck.status == DeckStatus.ARMED
                scryfall = ScryfallService(session)
                try:
                    preview = ImportService(
                        session, scryfall
                    ).preview_deck_list_update(deck_id, text)
                finally:
                    scryfall.close()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        dialog = DeckListUpdateDialog(
            self._translator,
            deck_name,
            preview,
            armed=armed,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            with get_session() as session:
                scryfall = ScryfallService(session)
                try:
                    importer = ImportService(session, scryfall)
                    # preview.text is the already-expanded list (URL fetched once).
                    warnings = importer.replace_deck_list(
                        deck_id,
                        preview.text,
                        commander_name=commander,
                    )
                    if secondary_role is not None and secondary_name is not None:
                        secondary_card = scryfall.lookup_local(secondary_name)
                        if secondary_card is None:
                            raise ValueError(
                                self._translator.t(
                                    "decks.details_edit.commander_not_found"
                                ).format(name=secondary_name)
                            )
                        DeckService(session).set_secondary_command_zone(
                            deck_id, secondary_role, secondary_card.oracle_id
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

        if warnings:
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                "\n".join(
                    f"{warning.line}: {warning.message}" for warning in warnings[:10]
                ),
            )

        self._name_input.clear()
        self._command_zone.clear()
        self._import_text.clear()
        self._hide_import_section()
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

    def _expand_moxfield_url(self, text: str) -> None:
        """Fetch a Moxfield deck into the form so the user can review it."""
        try:
            with get_session() as session:
                scryfall = ScryfallService(session)
                try:
                    resolved = ImportService(session, scryfall).resolve_decklist_input(
                        text
                    )
                finally:
                    scryfall.close()
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                self._translator.t("decks.import.url_failed").format(error=str(exc)),
            )
            return

        self._import_text.setPlainText(resolved.text)
        if resolved.deck_name and not self._name_input.text().strip():
            self._name_input.setText(resolved.deck_name)
        if resolved.commander_name and not self._command_zone.commander_name():
            self._command_zone.set_commander_name(resolved.commander_name)
        if (
            resolved.secondary_role is not None
            and resolved.secondary_name
            and self._command_zone.secondary_role() is None
        ):
            self._command_zone.set_secondary(
                resolved.secondary_role, resolved.secondary_name
            )
        QMessageBox.information(
            self,
            self._translator.t("decks.import"),
            self._translator.t("decks.import.url_filled"),
        )

    def _import_text_deck(self) -> None:
        text = self._import_text.toPlainText().strip()
        if not text:
            return

        # Expand Moxfield URL into the form so the user can review before arming.
        if detect_format(text) == DecklistFormat.MOXFIELD_URL:
            self._expand_moxfield_url(text)
            return

        if self._update_deck_id is not None:
            self._apply_list_update(self._update_deck_id, text)
            return

        name = self._name_input.text().strip()
        commander = self._command_zone.commander_name()
        secondary_role = self._command_zone.secondary_role()
        secondary_name = self._command_zone.secondary_name()
        if not name:
            return

        secondary_error = self._command_zone.validation_error()
        if secondary_error is not None:
            QMessageBox.warning(
                self,
                self._translator.t("common.error"),
                secondary_error,
            )
            return

        status_dialog = ImportStatusDialog(self._translator, self)
        if status_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        status = status_dialog.selected_status()

        try:
            with get_session() as session:
                scryfall = ScryfallService(session)
                try:
                    secondary_oracle_id: str | None = None
                    if (
                        secondary_role is not None
                        and secondary_name is not None
                    ):
                        secondary_card = scryfall.lookup_local(secondary_name)
                        if secondary_card is None:
                            raise ValueError(
                                self._translator.t(
                                    "decks.details_edit.commander_not_found"
                                ).format(name=secondary_name)
                            )
                        secondary_oracle_id = secondary_card.oracle_id

                    importer = ImportService(session, scryfall)
                    result = importer.import_decklist_text(
                        deck_name=name,
                        text=text,
                        status=status,
                        commander_name=commander,
                    )
                    deck_service = DeckService(session)
                    if (
                        secondary_role is not None
                        and secondary_oracle_id is not None
                    ):
                        deck_service.set_secondary_command_zone(
                            result.deck.id, secondary_role, secondary_oracle_id
                        )
                    if status == DeckStatus.ARMED:
                        deck_service.set_status(result.deck, DeckStatus.ARMED)
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
        self._command_zone.clear()
        self._import_text.clear()
        self._hide_import_section()
        self.refresh()
        self.changed.emit()

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._translator.t("decks.load_file.dialog_title"),
            str(Path.home()),
            "Text files (*.txt *.dek);;MTGO decks (*.dek);;All files (*)",
        )
        if not path:
            return
        content = Path(path).read_text(encoding="utf-8")
        self._import_text.setPlainText(content)
        if self._update_deck_id is None and not self._name_input.text().strip():
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
