from PySide6.QtWidgets import QMainWindow, QTabWidget

from mtg_sorter.database import get_session
from mtg_sorter.i18n import Translator
from mtg_sorter.services import SettingsService
from mtg_sorter.ui.widgets.browse_widget import BrowseWidget
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
        self._browse = BrowseWidget(self._translator)

        self._tab_widgets = (
            self._browse,
            self._decks,
            self._inventory,
            self._optimizer,
        )
        self._tab_keys = (
            "tab.browse",
            "tab.decks",
            "tab.inventory",
            "tab.optimize",
        )

        for widget, key in zip(self._tab_widgets, self._tab_keys, strict=True):
            self._tabs.addTab(widget, self._translator.t(key))

        self._inventory.changed.connect(self._optimizer.refresh_decks)
        self._decks.changed.connect(self._on_collection_changed)
        self._optimizer.changed.connect(self._on_optimizer_applied)
        self._browse.changed.connect(self._refresh_from_browse)
        self._browse.locale_changed.connect(self.set_locale)

    def _refresh_from_browse(self) -> None:
        self._inventory.refresh()
        self._decks.refresh()
        self._optimizer.refresh_decks()

    def _on_collection_changed(self) -> None:
        self._inventory.refresh()
        self._browse.refresh_collection_stats()
        self._optimizer.refresh_decks()

    def _on_optimizer_applied(self) -> None:
        self._decks.refresh()
        self._inventory.refresh()
        self._browse.refresh_collection_stats()
        self._optimizer.refresh_decks()

    def set_locale(self, locale: str) -> None:
        self._translator.set_locale(locale)
        with get_session() as session:
            SettingsService(session).set_ui_locale(locale)
        self.setWindowTitle(self._translator.t("app.title"))
        for index, key in enumerate(self._tab_keys):
            self._tabs.setTabText(index, self._translator.t(key))
        self._browse.retranslate()
        self._decks.retranslate()
        self._inventory.retranslate()
        self._optimizer.retranslate()
