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


class OptimizerWidget(QWidget):
    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = translator
        self._build_ui()
        self.refresh_decks()

    def retranslate(self) -> None:
        self._run_button.setText(self._translator.t("optimize.run"))
        self.refresh_decks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._deck_combo = QComboBox()
        form.addRow(self._translator.t("optimize.target"), self._deck_combo)
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

        if plan.free_inventory_used:
            for card_id, qty in sorted(
                plan.free_inventory_used.items(),
                key=lambda item: item[0],
            ):
                self._inventory_list.addItem(f"{card_id}: {qty}")
        else:
            self._inventory_list.addItem("—")

        if plan.still_missing:
            self._summary.setText(self._translator.t("optimize.no_solutions"))
            for card_id, qty in plan.still_missing.items():
                self._missing_list.addItem(f"{card_id}: {qty}")
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
        for deck_id in sorted(solution):
            self._solution_list.addItem(deck_id)
