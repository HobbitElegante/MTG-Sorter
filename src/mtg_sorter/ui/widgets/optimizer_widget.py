from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.models.enums import DeckStatus
from mtg_sorter.services import DeckService, InventoryService, OptimizationService
from mtg_sorter.services.optimization_service import AssemblyPlan, MovedCopy
from mtg_sorter.services.settings_service import SettingsService
from mtg_sorter.ui.widgets.edition_picker import CopyEditionTable


class SpecifyEditionsDialog(QDialog):
    """Optional prompt after a rebuild: which edition is each moved copy?"""

    def __init__(
        self,
        translator: Translator,
        deck_name: str,
        copies: list[MovedCopy],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._editions: dict[int, str | None] = {}
        self.setWindowTitle(self._translator.t("inventory.editions.prompt_title"))
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        hint = QLabel(
            self._translator.t("inventory.editions.prompt_hint").format(deck=deck_name)
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._table = CopyEditionTable(self._translator)
        self._table.set_copies(
            [
                (copy.copy_id, copy.oracle_id, copy.card_name, None)
                for copy in copies
            ]
        )
        layout.addWidget(self._table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save)
        skip = buttons.addButton(
            self._translator.t("inventory.editions.skip"),
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        skip.clicked.connect(self.reject)
        buttons.accepted.connect(self._accept)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self._editions = {
            copy_id: edition
            for copy_id, edition in self._table.editions().items()
            if edition is not None
        }
        self.accept()

    def editions(self) -> dict[int, str | None]:
        return self._editions


class OptimizerWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._queue: list[int] = []
        self._plans: list[AssemblyPlan] = []
        self._chosen_solutions: dict[int, frozenset[str]] = {}
        self._current_plan: AssemblyPlan | None = None
        self._selection_committed = False
        self._recomputing_queue = False
        with get_session() as session:
            self._track_editions = SettingsService(session).get_track_editions()
        self._build_ui()
        self.refresh_decks()

    def set_track_editions(self, enabled: bool) -> None:
        self._track_editions = enabled

    def retranslate(self) -> None:
        self._target_label.setText(self._translator.t("optimize.target"))
        self._add_button.setText(self._translator.t("optimize.add"))
        self._queue_group.setTitle(self._translator.t("optimize.queue"))
        self._remove_button.setText(self._translator.t("optimize.queue.remove"))
        self._confirm_button.setText(self._translator.t("optimize.confirm"))
        self._cancel_button.setText(self._translator.t("optimize.cancel"))
        line_edit = self._deck_combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(
                self._translator.t("optimize.target.search")
            )
        self._apply_section_titles_from_plan()
        self._refresh_queue_list()
        if self._current_plan is not None:
            self._refresh_plan_display()
        else:
            self.refresh_decks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        picker_row = QHBoxLayout()
        self._deck_combo = QComboBox()
        self._deck_combo.setEditable(True)
        self._deck_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._deck_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._deck_combo.setMinimumContentsLength(32)
        line_edit = self._deck_combo.lineEdit()
        line_edit.setPlaceholderText(self._translator.t("optimize.target.search"))
        line_edit.setClearButtonEnabled(True)
        search_icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_FileDialogContentsView
        )
        search_action = QAction(search_icon if not search_icon.isNull() else QIcon(), self)
        search_action.setEnabled(False)
        line_edit.addAction(search_action, line_edit.ActionPosition.LeadingPosition)
        completer = QCompleter(self._deck_combo.model(), self._deck_combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._deck_combo.setCompleter(completer)
        self._deck_combo.activated.connect(self._commit_combo_selection)
        line_edit.textChanged.connect(self._on_combo_text_changed)
        line_edit.returnPressed.connect(self._commit_combo_selection)
        self._add_button = QPushButton(self._translator.t("optimize.add"))
        self._add_button.clicked.connect(self._add_selected_to_queue)
        picker_row.addWidget(self._deck_combo, 1)
        picker_row.addWidget(self._add_button)
        self._target_label = QLabel(self._translator.t("optimize.target"))
        form.addRow(self._target_label, picker_row)
        layout.addLayout(form)

        self._queue_group = QGroupBox(self._translator.t("optimize.queue"))
        queue_layout = QVBoxLayout(self._queue_group)
        self._queue_list = QListWidget()
        self._queue_list.setMaximumHeight(140)
        self._queue_list.currentRowChanged.connect(self._on_queue_selection_changed)
        queue_layout.addWidget(self._queue_list)
        self._remove_button = QPushButton(self._translator.t("optimize.queue.remove"))
        self._remove_button.clicked.connect(self._remove_selected_from_queue)
        queue_layout.addWidget(self._remove_button)
        layout.addWidget(self._queue_group)
        self._queue_group.setVisible(False)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_font = QFont(self._summary.font())
        summary_font.setPointSize(summary_font.pointSize() + 5)
        summary_font.setBold(True)
        self._summary.setFont(summary_font)
        self._summary.setMinimumHeight(48)
        layout.addWidget(self._summary)

        self._inventory_group = QGroupBox()
        inventory_layout = QVBoxLayout(self._inventory_group)
        self._inventory_list = QListWidget()
        self._inventory_list.setMaximumHeight(160)
        inventory_layout.addWidget(self._inventory_list)
        layout.addWidget(self._inventory_group)

        self._solution_group = QGroupBox()
        solution_layout = QVBoxLayout(self._solution_group)
        self._solution_combo = QComboBox()
        self._solution_combo.currentIndexChanged.connect(self._on_solution_changed)
        solution_layout.addWidget(self._solution_combo)
        self._solution_tree = QTreeWidget()
        self._solution_tree.setHeaderHidden(True)
        self._solution_tree.setRootIsDecorated(True)
        self._solution_tree.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        solution_layout.addWidget(self._solution_tree, stretch=1)
        buttons = QHBoxLayout()
        self._confirm_button = QPushButton(self._translator.t("optimize.confirm"))
        self._cancel_button = QPushButton(self._translator.t("optimize.cancel"))
        self._confirm_button.clicked.connect(self._confirm_plan)
        self._cancel_button.clicked.connect(self._cancel_plan)
        buttons.addWidget(self._confirm_button)
        buttons.addWidget(self._cancel_button)
        solution_layout.addLayout(buttons)
        layout.addWidget(self._solution_group, stretch=1)
        self._set_plan_actions_visible(False)

        self._missing_group = QGroupBox()
        missing_layout = QVBoxLayout(self._missing_group)
        self._missing_tree = QTreeWidget()
        self._missing_tree.setHeaderHidden(True)
        self._missing_tree.setRootIsDecorated(True)
        self._missing_tree.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        missing_layout.addWidget(self._missing_tree, stretch=1)
        layout.addWidget(self._missing_group, stretch=1)
        self._missing_group.setVisible(False)

        self._set_section_titles(0, 0, 0)

    def _set_plan_actions_visible(self, visible: bool) -> None:
        self._confirm_button.setVisible(visible)
        self._cancel_button.setVisible(visible)

    def _counted_title(self, label_key: str, count: int, unit_key: str) -> str:
        return (
            f"{self._translator.t(label_key)} - {count} "
            f"{self._translator.t(unit_key)}"
        )

    def _set_section_titles(
        self,
        inventory_cards: int,
        decks: int,
        missing_cards: int,
    ) -> None:
        self._inventory_group.setTitle(
            self._counted_title(
                "optimize.from_inventory",
                inventory_cards,
                "optimize.unit.cards",
            )
        )
        self._solution_group.setTitle(
            self._counted_title(
                "optimize.decks_to_dismantle",
                decks,
                "optimize.unit.decks",
            )
        )
        self._missing_group.setTitle(
            self._counted_title(
                "optimize.missing",
                missing_cards,
                "optimize.unit.cards",
            )
        )

    def _apply_section_titles_from_plan(self) -> None:
        plan = self._current_plan
        if plan is None:
            self._set_section_titles(0, 0, 0)
            return
        inventory_cards = sum(plan.free_inventory_used.values())
        missing_cards = sum(plan.still_missing.values())
        decks = 0
        if not plan.still_missing and plan.result.solutions:
            decks = plan.result.minimum_decks_to_dismantle
        self._set_section_titles(inventory_cards, decks, missing_cards)

    def _card_qty_label(self, card_id: str, qty: int) -> str:
        plan = self._current_plan
        name = plan.card_names.get(card_id, card_id) if plan else card_id
        return self._translator.t("optimize.card_qty").format(name=name, qty=qty)

    @staticmethod
    def _deck_label(name: str, commander: str | None) -> str:
        if commander:
            return f"{name} — {commander}"
        return name

    def _set_combo_committed(self, committed: bool) -> None:
        self._selection_committed = committed
        line_edit = self._deck_combo.lineEdit()
        if line_edit is None:
            return
        line_edit.setReadOnly(committed)
        if committed:
            line_edit.home(False)

    def _on_combo_text_changed(self, text: str) -> None:
        if not text.strip():
            self._set_combo_committed(False)
            self._deck_combo.setCurrentIndex(-1)

    def _commit_combo_selection(self, *_args) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            self._set_combo_committed(False)
            return
        index = self._deck_combo.findData(deck_id)
        if index < 0:
            self._set_combo_committed(False)
            return
        self._deck_combo.blockSignals(True)
        self._deck_combo.setCurrentIndex(index)
        self._deck_combo.blockSignals(False)
        self._set_combo_committed(True)

    def refresh_decks(self) -> None:
        current = self._deck_combo.currentData()
        self._deck_combo.blockSignals(True)
        self._deck_combo.clear()
        with get_session() as session:
            service = DeckService(session)
            for deck in service.list_decks():
                if deck.status == DeckStatus.ARMED:
                    continue
                commander = service.commander_name(deck.id)
                label = self._deck_label(deck.name, commander)
                self._deck_combo.addItem(label, deck.id)
        completer = self._deck_combo.completer()
        if completer is not None:
            completer.setModel(self._deck_combo.model())
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
        if current is not None:
            index = self._deck_combo.findData(current)
            if index >= 0:
                self._deck_combo.setCurrentIndex(index)
                self._set_combo_committed(True)
            else:
                self._deck_combo.setCurrentIndex(-1)
                line_edit = self._deck_combo.lineEdit()
                if line_edit is not None:
                    line_edit.clear()
                self._set_combo_committed(False)
        else:
            self._deck_combo.setCurrentIndex(-1)
            self._set_combo_committed(False)
        self._deck_combo.blockSignals(False)
        if self._queue:
            self._recompute_queue_plans(select_deck_id=self._selected_queue_deck_id())

    def _selected_deck_id(self) -> int | None:
        typed = self._deck_combo.currentText().strip()
        if not typed:
            return None
        index = self._deck_combo.currentIndex()
        if index >= 0 and self._deck_combo.itemText(index) == typed:
            data = self._deck_combo.itemData(index)
            if isinstance(data, int):
                return data
        needle = typed.casefold()
        exact: list[int] = []
        partial: list[int] = []
        for i in range(self._deck_combo.count()):
            label = self._deck_combo.itemText(i)
            data = self._deck_combo.itemData(i)
            if not isinstance(data, int):
                continue
            folded = label.casefold()
            if folded == needle:
                exact.append(data)
            elif needle in folded:
                partial.append(data)
        if len(exact) == 1:
            return exact[0]
        if len(partial) == 1:
            return partial[0]
        return None

    def _selected_queue_deck_id(self) -> int | None:
        item = self._queue_list.currentItem()
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, int) else None

    def _clear_plan_panels(self) -> None:
        self._inventory_list.clear()
        self._solution_tree.clear()
        self._solution_combo.blockSignals(True)
        self._solution_combo.clear()
        self._solution_combo.blockSignals(False)
        self._missing_tree.clear()
        self._summary.setText("")
        self._current_plan = None
        self._set_section_titles(0, 0, 0)
        self._missing_group.setVisible(False)
        self._set_plan_actions_visible(False)
        self._inventory_group.setVisible(True)
        self._solution_group.setVisible(True)

    def _clear_queue(self) -> None:
        self._queue.clear()
        self._plans.clear()
        self._chosen_solutions.clear()
        self._queue_list.clear()
        self._queue_group.setVisible(False)
        self._clear_plan_panels()

    def _add_selected_to_queue(self) -> None:
        self._commit_combo_selection()
        deck_id = self._selected_deck_id()
        if deck_id is None or deck_id in self._queue:
            return
        self._queue.append(deck_id)
        self._recompute_queue_plans(select_deck_id=deck_id)
        line_edit = self._deck_combo.lineEdit()
        if line_edit is not None:
            line_edit.clear()
        self._deck_combo.setCurrentIndex(-1)
        self._set_combo_committed(False)

    def _remove_selected_from_queue(self) -> None:
        deck_id = self._selected_queue_deck_id()
        if deck_id is None:
            return
        self._queue = [item for item in self._queue if item != deck_id]
        self._chosen_solutions.pop(deck_id, None)
        if not self._queue:
            self._clear_queue()
            return
        self._recompute_queue_plans()

    def _recompute_queue_plans(self, select_deck_id: int | None = None) -> None:
        if not self._queue:
            self._clear_queue()
            return
        self._recomputing_queue = True
        try:
            try:
                with get_session() as session:
                    self._plans = OptimizationService(session).plan_assembly_sequence(
                        self._queue, self._chosen_solutions
                    )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    self._translator.t("common.error"),
                    str(exc),
                )
                return
            self._queue_group.setVisible(True)
            keep = select_deck_id if select_deck_id in self._queue else None
            if keep is None:
                keep = self._selected_queue_deck_id()
            self._refresh_queue_list(select_deck_id=keep)
        finally:
            self._recomputing_queue = False

    def _queue_status_label(self, plan: AssemblyPlan) -> str:
        if plan.already_armed:
            return self._translator.t("optimize.queue.armed")
        if plan.still_missing or not plan.result.solutions:
            return self._translator.t("optimize.queue.missing")
        return self._translator.t("optimize.queue.viable")

    def _refresh_queue_list(self, select_deck_id: int | None = None) -> None:
        self._queue_list.blockSignals(True)
        self._queue_list.clear()
        plans_by_id = {plan.target_deck_id: plan for plan in self._plans}
        for index, deck_id in enumerate(self._queue, start=1):
            plan = plans_by_id.get(deck_id)
            name = plan.target_deck_name if plan else str(deck_id)
            status = self._queue_status_label(plan) if plan else "?"
            mark = "✓" if plan and not plan.already_armed and not plan.still_missing and plan.result.solutions else "✗"
            if plan and plan.already_armed:
                mark = "—"
            item = QListWidgetItem(f"{index}. {name}  {mark} {status}")
            item.setData(Qt.ItemDataRole.UserRole, deck_id)
            self._queue_list.addItem(item)
            if deck_id == select_deck_id:
                self._queue_list.setCurrentItem(item)
        if self._queue_list.currentItem() is None and self._queue_list.count() > 0:
            self._queue_list.setCurrentRow(0)
        self._queue_list.blockSignals(False)
        self._on_queue_selection_changed(self._queue_list.currentRow())

    def _on_queue_selection_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._plans):
            self._clear_plan_panels()
            return
        self._current_plan = self._plans[row]
        self._refresh_plan_display()

    def _on_solution_changed(self, _index: int = 0) -> None:
        if self._recomputing_queue:
            return
        plan = self._current_plan
        if plan is None:
            return
        solution = self._solution_combo.currentData()
        if isinstance(solution, frozenset):
            previous = self._chosen_solutions.get(plan.target_deck_id)
            self._chosen_solutions[plan.target_deck_id] = solution
            if previous != solution and any(
                deck_id != plan.target_deck_id for deck_id in self._queue
            ):
                self._recompute_queue_plans(select_deck_id=plan.target_deck_id)
                return
        self._show_selected_solution()

    def _refresh_plan_display(self) -> None:
        plan = self._current_plan
        if plan is None:
            return

        self._inventory_list.clear()
        self._solution_tree.clear()
        self._solution_combo.blockSignals(True)
        self._solution_combo.clear()
        self._solution_combo.blockSignals(False)
        self._missing_tree.clear()
        self._apply_section_titles_from_plan()

        if plan.already_armed:
            self._summary.setText(self._translator.t("optimize.already_armed"))
            self._inventory_group.setVisible(False)
            self._solution_group.setVisible(False)
            self._missing_group.setVisible(False)
            self._set_plan_actions_visible(False)
            return

        self._inventory_group.setVisible(True)
        if plan.free_inventory_used:
            for card_id, qty in sorted(
                plan.free_inventory_used.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                self._inventory_list.addItem(self._card_qty_label(card_id, qty))
        else:
            self._inventory_list.addItem("—")

        if plan.still_missing:
            self._summary.setText(self._translator.t("optimize.no_solutions"))
            self._solution_group.setVisible(False)
            self._set_plan_actions_visible(False)
            self._missing_group.setVisible(True)
            self._populate_missing_tree(plan)
            self._cancel_button.setVisible(True)
            return

        self._missing_group.setVisible(False)
        result = plan.result
        if not result.solutions:
            self._summary.setText(self._translator.t("optimize.no_solutions"))
            self._solution_group.setVisible(False)
            self._set_plan_actions_visible(False)
            self._cancel_button.setVisible(True)
            return

        self._solution_group.setVisible(True)
        count = result.minimum_decks_to_dismantle
        if count == 0:
            summary = self._translator.t("optimize.summary.inventory_only")
        else:
            summary = self._translator.t("optimize.summary.dismantle").format(
                count=count
            )
        if len(result.solutions) > 1:
            summary = f"{summary}\n{self._translator.t('optimize.multiple')}"
        self._summary.setText(summary)

        preferred = self._chosen_solutions.get(plan.target_deck_id)
        select_index = 0
        self._solution_combo.blockSignals(True)
        for index, solution in enumerate(result.solutions):
            label = plan.solution_labels.get(solution, ", ".join(sorted(solution)))
            if index == 0 and len(result.solutions) > 1:
                label = f"{label} — {self._translator.t('optimize.solution.suggested')}"
            self._solution_combo.addItem(label, solution)
            if preferred == solution:
                select_index = index
        self._solution_combo.setCurrentIndex(select_index)
        self._solution_combo.setVisible(len(result.solutions) > 1)
        self._solution_combo.blockSignals(False)
        self._show_selected_solution()

    def _populate_missing_tree(self, plan: AssemblyPlan) -> None:
        """Group unmet cards by armed deck; leftover under Need to find."""
        self._missing_tree.clear()
        by_deck, need_to_find = plan.missing_by_source()

        for deck_id in sorted(
            by_deck.keys(),
            key=lambda item: plan.deck_names.get(item, item).lower(),
        ):
            deck_name = plan.deck_names.get(deck_id, deck_id)
            parent = QTreeWidgetItem([deck_name])
            self._missing_tree.addTopLevelItem(parent)
            cards = by_deck[deck_id]
            for card_id, qty in sorted(
                cards.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                parent.addChild(QTreeWidgetItem([self._card_qty_label(card_id, qty)]))
            parent.setExpanded(True)

        if need_to_find:
            find_parent = QTreeWidgetItem(
                [self._translator.t("optimize.missing.need_to_find")]
            )
            self._missing_tree.addTopLevelItem(find_parent)
            for card_id, qty in sorted(
                need_to_find.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                find_parent.addChild(
                    QTreeWidgetItem([self._card_qty_label(card_id, qty)])
                )
            find_parent.setExpanded(True)

        if not by_deck and not need_to_find:
            for card_id, qty in sorted(
                plan.still_missing.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                self._missing_tree.addTopLevelItem(
                    QTreeWidgetItem([self._card_qty_label(card_id, qty)])
                )

    def _show_selected_solution(self) -> None:
        plan = self._current_plan
        self._solution_tree.clear()
        if plan is None:
            self._set_plan_actions_visible(False)
            return

        solution = self._solution_combo.currentData()
        if solution is None:
            self._set_plan_actions_visible(False)
            return

        taken = plan.cards_taken_from_solution(solution)
        for deck_id in sorted(
            solution,
            key=lambda item: plan.deck_names.get(item, item).lower(),
        ):
            deck_name = plan.deck_names.get(deck_id, deck_id)
            parent = QTreeWidgetItem([deck_name])
            self._solution_tree.addTopLevelItem(parent)
            cards = taken.get(deck_id, {})
            for card_id, qty in sorted(
                cards.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                parent.addChild(QTreeWidgetItem([self._card_qty_label(card_id, qty)]))
            parent.setExpanded(True)

        if not solution:
            self._solution_tree.addTopLevelItem(QTreeWidgetItem(["—"]))

        self._set_plan_actions_visible(True)

    def _confirm_plan(self) -> None:
        plan = self._current_plan
        if plan is None or plan.already_armed or plan.still_missing:
            return
        solution = self._solution_combo.currentData()
        if solution is None:
            return

        deck_names = [
            plan.deck_names.get(deck_id, deck_id)
            for deck_id in sorted(
                solution,
                key=lambda item: plan.deck_names.get(item, item).lower(),
            )
        ]
        if not deck_names:
            decks_text = "—"
        else:
            decks_text = "\n".join(f"• {name}" for name in deck_names)
        body = self._translator.t("optimize.apply.confirm_body").format(
            decks=decks_text,
            target=plan.target_deck_name,
        )
        reply = QMessageBox.question(
            self,
            self._translator.t("optimize.apply.confirm_title"),
            body,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        target_id = plan.target_deck_id
        target_name = plan.target_deck_name
        try:
            with get_session() as session:
                moved = OptimizationService(session).apply_assembly_plan(
                    target_id, solution
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        self._queue = [deck_id for deck_id in self._queue if deck_id != target_id]
        self._chosen_solutions.pop(target_id, None)
        self._summary.setText(self._translator.t("optimize.apply.success"))
        if self._track_editions and moved:
            self._prompt_for_editions(target_name, moved)
        self.refresh_decks()
        if self._queue:
            self._recompute_queue_plans()
        else:
            self._clear_queue()
            self._summary.setText(self._translator.t("optimize.apply.success"))
        self.changed.emit()

    def _prompt_for_editions(self, deck_name: str, moved: list[MovedCopy]) -> None:
        """Offer to record set codes; skipping leaves the copies unspecified."""
        dialog = SpecifyEditionsDialog(self._translator, deck_name, moved, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        editions = dialog.editions()
        if not editions:
            return
        try:
            with get_session() as session:
                InventoryService(session).set_copy_editions(editions)
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )

    def _cancel_plan(self) -> None:
        self._clear_queue()
