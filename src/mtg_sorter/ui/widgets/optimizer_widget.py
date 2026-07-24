from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import DeckService, OptimizationService
from mtg_sorter.services.optimization_service import AssemblyPlan


class OptimizerWidget(QWidget):
    changed = Signal()

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._current_plan: AssemblyPlan | None = None
        self._build_ui()
        self.refresh_decks()

    def retranslate(self) -> None:
        self._target_label.setText(self._translator.t("optimize.target"))
        self._run_button.setText(self._translator.t("optimize.run"))
        self._confirm_button.setText(self._translator.t("optimize.confirm"))
        self._cancel_button.setText(self._translator.t("optimize.cancel"))
        line_edit = self._deck_combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(
                self._translator.t("optimize.target.search")
            )
        self._apply_section_titles_from_plan()
        if self._current_plan is not None:
            self._refresh_plan_display()
        else:
            self.refresh_decks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
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
        completer = QCompleter(self._deck_combo.model(), self._deck_combo)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._deck_combo.setCompleter(completer)
        self._target_label = QLabel(self._translator.t("optimize.target"))
        form.addRow(self._target_label, self._deck_combo)
        layout.addLayout(form)

        self._run_button = QPushButton(self._translator.t("optimize.run"))
        self._run_button.clicked.connect(self._run_optimization)
        layout.addWidget(self._run_button)

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
        self._missing_list = QListWidget()
        missing_layout.addWidget(self._missing_list)
        layout.addWidget(self._missing_group)
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

    def refresh_decks(self) -> None:
        current = self._deck_combo.currentData()
        self._deck_combo.blockSignals(True)
        self._deck_combo.clear()
        with get_session() as session:
            service = DeckService(session)
            for deck in service.list_decks():
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
        self._deck_combo.blockSignals(False)

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

    def _clear_plan_ui(self) -> None:
        self._inventory_list.clear()
        self._solution_tree.clear()
        self._solution_combo.clear()
        self._missing_list.clear()
        self._summary.setText("")
        self._current_plan = None
        self._set_section_titles(0, 0, 0)
        self._missing_group.setVisible(False)
        self._set_plan_actions_visible(False)
        self._inventory_group.setVisible(True)
        self._solution_group.setVisible(True)

    def _run_optimization(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return

        self._clear_plan_ui()

        try:
            with get_session() as session:
                plan = OptimizationService(session).plan_assembly(deck_id)
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        self._current_plan = plan
        self._refresh_plan_display()

    def _refresh_plan_display(self) -> None:
        plan = self._current_plan
        if plan is None:
            return

        self._inventory_list.clear()
        self._solution_tree.clear()
        self._solution_combo.clear()
        self._missing_list.clear()
        self._apply_section_titles_from_plan()

        try:
            self._solution_combo.currentIndexChanged.disconnect(
                self._show_selected_solution
            )
        except TypeError:
            pass

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
            for card_id, qty in sorted(
                plan.still_missing.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                self._missing_list.addItem(self._card_qty_label(card_id, qty))
            return

        self._missing_group.setVisible(False)
        result = plan.result
        if not result.solutions:
            self._summary.setText(self._translator.t("optimize.no_solutions"))
            self._solution_group.setVisible(False)
            self._set_plan_actions_visible(False)
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

        for solution in result.solutions:
            label = plan.solution_labels.get(solution, ", ".join(sorted(solution)))
            self._solution_combo.addItem(label, solution)

        self._solution_combo.setVisible(len(result.solutions) > 1)
        self._solution_combo.currentIndexChanged.connect(self._show_selected_solution)
        self._show_selected_solution()

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
        try:
            with get_session() as session:
                OptimizationService(session).apply_assembly_plan(target_id, solution)
        except Exception as exc:
            QMessageBox.critical(
                self,
                self._translator.t("common.error"),
                str(exc),
            )
            return

        self._clear_plan_ui()
        self._summary.setText(self._translator.t("optimize.apply.success"))
        self.refresh_decks()
        self.changed.emit()

    def _cancel_plan(self) -> None:
        self._clear_plan_ui()
