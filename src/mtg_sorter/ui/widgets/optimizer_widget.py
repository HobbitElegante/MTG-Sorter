from PySide6.QtWidgets import (
    QComboBox,
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
        self._inventory_group.setTitle(self._translator.t("optimize.from_inventory"))
        self._solution_group.setTitle(self._translator.t("optimize.decks_to_dismantle"))
        self._missing_group.setTitle(self._translator.t("optimize.missing"))
        self.refresh_decks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._deck_combo = QComboBox()
        self._target_label = QLabel(self._translator.t("optimize.target"))
        form.addRow(self._target_label, self._deck_combo)
        layout.addLayout(form)

        self._run_button = QPushButton(self._translator.t("optimize.run"))
        self._run_button.clicked.connect(self._run_optimization)
        layout.addWidget(self._run_button)

        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._inventory_group = QGroupBox(self._translator.t("optimize.from_inventory"))
        inventory_layout = QVBoxLayout(self._inventory_group)
        self._inventory_list = QListWidget()
        inventory_layout.addWidget(self._inventory_list)
        layout.addWidget(self._inventory_group)

        self._solution_group = QGroupBox(self._translator.t("optimize.decks_to_dismantle"))
        solution_layout = QVBoxLayout(self._solution_group)
        self._solution_combo = QComboBox()
        solution_layout.addWidget(self._solution_combo)
        self._solution_list = QListWidget()
        solution_layout.addWidget(self._solution_list)
        layout.addWidget(self._solution_group)

        self._missing_group = QGroupBox(self._translator.t("optimize.missing"))
        missing_layout = QVBoxLayout(self._missing_group)
        self._missing_list = QListWidget()
        missing_layout.addWidget(self._missing_list)
        layout.addWidget(self._missing_group)

    def refresh_decks(self) -> None:
        current = self._deck_combo.currentData()
        self._deck_combo.clear()
        with get_session() as session:
            for deck in DeckService(session).list_decks():
                self._deck_combo.addItem(deck.name, deck.id)
        if current is not None:
            index = self._deck_combo.findData(current)
            if index >= 0:
                self._deck_combo.setCurrentIndex(index)

    def _run_optimization(self) -> None:
        deck_id = self._deck_combo.currentData()
        if deck_id is None:
            return

        self._inventory_list.clear()
        self._solution_list.clear()
        self._solution_combo.clear()
        self._missing_list.clear()
        self._current_plan = None

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
