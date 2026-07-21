import sys

from PySide6.QtWidgets import QApplication

from mtg_sorter.config import DEFAULT_LOCALE
from mtg_sorter.database import init_db
from mtg_sorter.i18n import Translator
from mtg_sorter.ui import MainWindow


def main() -> None:
    init_db()
    app = QApplication(sys.argv)
    translator = Translator(DEFAULT_LOCALE)
    window = MainWindow(translator)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
