from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import DeckService, OptimizationService
from mtg_sorter.services.optimization_service import AssemblyPlan


class OptimizerWidget(QWidget):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._current_plan: AssemblyPlan | None = None
        self._build_ui()
        self.refresh_decks()

    def retranslate(self) -> None:
        self._target_label.setText(self._translator.t("optimize.target"))
        self._run_button.setText(self._translator.t("optimize.run"))
        line_edit = self._deck_combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText(
                self._translator.t("optimize.target.search")
            )
        self._apply_section_titles_from_plan()
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
        layout.addWidget(self._summary)

        self._inventory_group = QGroupBox()
        inventory_layout = QVBoxLayout(self._inventory_group)
        self._inventory_list = QListWidget()
        inventory_layout.addWidget(self._inventory_list)
        layout.addWidget(self._inventory_group)

        self._solution_group = QGroupBox()
        solution_layout = QVBoxLayout(self._solution_group)
        self._solution_combo = QComboBox()
        solution_layout.addWidget(self._solution_combo)
        self._solution_list = QListWidget()
        solution_layout.addWidget(self._solution_list)
        layout.addWidget(self._solution_group)

        self._missing_group = QGroupBox()
        missing_layout = QVBoxLayout(self._missing_group)
        self._missing_list = QListWidget()
        missing_layout.addWidget(self._missing_list)
        layout.addWidget(self._missing_group)

        self._set_section_titles(0, 0, 0)

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

    def _run_optimization(self) -> None:
        deck_id = self._selected_deck_id()
        if deck_id is None:
            return

        self._inventory_list.clear()
        self._solution_list.clear()
        self._solution_combo.clear()
        self._missing_list.clear()
        self._current_plan = None
        self._set_section_titles(0, 0, 0)

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
        self._apply_section_titles_from_plan()

        if plan.already_armed:
            self._summary.setText(self._translator.t("optimize.already_armed"))
            self._inventory_list.addItem("—")
            return

        if plan.free_inventory_used:
            for card_id, qty in sorted(
                plan.free_inventory_used.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                name = plan.card_names.get(card_id, card_id)
                self._inventory_list.addItem(f"{name}: {qty}")
        else:
            self._inventory_list.addItem("—")

        if plan.still_missing:
            self._summary.setText(self._translator.t("optimize.no_solutions"))
            for card_id, qty in sorted(
                plan.still_missing.items(),
                key=lambda item: plan.card_names.get(item[0], item[0]).lower(),
            ):
                name = plan.card_names.get(card_id, card_id)
                self._missing_list.addItem(f"{name}: {qty}")
            return

        result = plan.result
        if not result.solutions:
            self._summary.setText(self._translator.t("optimize.no_solutions"))
            return

        self._summary.setText(
            f"{self._translator.t('optimize.decks_to_dismantle')}: "
            f"{result.minimum_decks_to_dismantle}"
        )

        if len(result.solutions) > 1:
            self._summary.setText(
                self._summary.text()
                + f"\n{self._translator.t('optimize.multiple')}"
            )

        try:
            self._solution_combo.currentIndexChanged.disconnect(self._show_selected_solution)
        except TypeError:
            pass

        for solution in result.solutions:
            label = plan.solution_labels.get(solution, ", ".join(sorted(solution)))
            self._solution_combo.addItem(label, solution)

        self._solution_combo.currentIndexChanged.connect(self._show_selected_solution)
        self._show_selected_solution()

    def _show_selected_solution(self) -> None:
        solution = self._solution_combo.currentData()
        self._solution_list.clear()
        if not solution:
            return
        deck_names = self._current_plan.deck_names if self._current_plan else {}
        for deck_id in sorted(
            solution,
            key=lambda item: deck_names.get(item, item).lower(),
        ):
            self._solution_list.addItem(deck_names.get(deck_id, deck_id))
