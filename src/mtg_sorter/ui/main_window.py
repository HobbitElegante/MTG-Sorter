from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QTabWidget

from mtg_sorter.i18n import Translator
from mtg_sorter.ui.widgets.decks_widget import DecksWidget
from mtg_sorter.ui.widgets.inventory_widget import InventoryWidget
from mtg_sorter.ui.widgets.optimizer_widget import OptimizerWidget


class MainWindow(QMainWindow):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self._translator = translator
        self.setWindowTitle(self._translator.t("app.title"))
        self.resize(960, 720)

        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._inventory = InventoryWidget(self._translator)
        self._decks = DecksWidget(self._translator)
        self._optimizer = OptimizerWidget(self._translator)

        self._tabs.addTab(self._inventory, self._translator.t("tab.inventory"))
        self._tabs.addTab(self._decks, self._translator.t("tab.decks"))
        self._tabs.addTab(self._optimizer, self._translator.t("tab.optimize"))

        self._inventory.changed.connect(self._optimizer.refresh_decks)
        self._decks.changed.connect(self._optimizer.refresh_decks)

        self._build_menu()

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu(self._translator.t("menu.language"))
        for locale, label_key in (("en", "language.en"), ("es", "language.es")):
            action = QAction(self._translator.t(label_key), self)
            action.triggered.connect(lambda _checked=False, loc=locale: self.set_locale(loc))
            menu.addAction(action)

    def set_locale(self, locale: str) -> None:
        self._translator.set_locale(locale)
        self.setWindowTitle(self._translator.t("app.title"))
        self._tabs.setTabText(0, self._translator.t("tab.inventory"))
        self._tabs.setTabText(1, self._translator.t("tab.decks"))
        self._tabs.setTabText(2, self._translator.t("tab.optimize"))
        self._inventory.retranslate()
        self._decks.retranslate()
        self._optimizer.retranslate()
