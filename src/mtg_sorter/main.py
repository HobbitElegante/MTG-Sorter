import sys

from PySide6.QtWidgets import QApplication

from mtg_sorter.database import get_session, init_db
from mtg_sorter.i18n import Translator
from mtg_sorter.services import SettingsService
from mtg_sorter.ui import MainWindow


def main() -> None:
    init_db()
    with get_session() as session:
        locale = SettingsService(session).get_ui_locale()
    app = QApplication(sys.argv)
    translator = Translator(locale)
    window = MainWindow(translator)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
