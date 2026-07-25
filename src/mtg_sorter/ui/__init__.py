"""UI package.

Keep this module free of PySide6 imports so pure helpers like
``inventory_display`` can be imported from tests without loading Qt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mtg_sorter.ui.main_window import MainWindow as MainWindow

__all__ = ["MainWindow"]


def __getattr__(name: str) -> Any:
    if name == "MainWindow":
        from mtg_sorter.ui.main_window import MainWindow

        return MainWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
