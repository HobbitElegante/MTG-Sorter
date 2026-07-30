import sys

from PySide6.QtWidgets import QApplication

from mtg_sorter.database import get_session, init_db
from mtg_sorter.i18n import Translator
from mtg_sorter.services import SettingsService
from mtg_sorter.ui import MainWindow
from mtg_sorter.ui.theme import apply_theme


def main() -> None:
    init_db()
    with get_session() as session:
        settings = SettingsService(session)
        locale = settings.get_ui_locale()
        theme = settings.get_ui_theme()
    app = QApplication(sys.argv)
    apply_theme(app, theme)
    translator = Translator(locale)
    window = MainWindow(translator)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
