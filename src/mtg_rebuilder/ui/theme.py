"""Application light / dark / system theming (Fusion + QPalette)."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from mtg_rebuilder.config import THEME_DARK, THEME_SYSTEM

_DEFAULT_STYLE_ATTR = "_mtg_rebuilder_default_style"


def _light_palette() -> QPalette:
    palette = QPalette()
    window = QColor(245, 245, 245)
    base = QColor(255, 255, 255)
    text = QColor(33, 33, 33)
    disabled = QColor(140, 140, 140)
    highlight = QColor(42, 130, 218)
    button = QColor(232, 232, 232)

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(233, 233, 233))
    palette.setColor(QPalette.ColorRole.ToolTipBase, base)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, button)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(190, 190, 190))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled
    )
    return palette


def _dark_palette() -> QPalette:
    palette = QPalette()
    window = QColor(53, 53, 53)
    base = QColor(35, 35, 35)
    text = QColor(220, 220, 220)
    disabled = QColor(127, 127, 127)
    highlight = QColor(42, 130, 218)
    button = QColor(53, 53, 53)

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.ToolTipBase, base)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, button)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))

    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(80, 80, 80))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, disabled
    )
    return palette


def _remember_default_style(app: QApplication) -> str:
    name = getattr(app, _DEFAULT_STYLE_ATTR, None)
    if isinstance(name, str) and name:
        return name
    name = app.style().objectName()
    setattr(app, _DEFAULT_STYLE_ATTR, name)
    return name


def apply_theme(app: QApplication, theme: str) -> None:
    """Apply light, dark, or platform-default appearance to ``app``."""
    default_style = _remember_default_style(app)
    app.setStyleSheet("")

    if theme == THEME_SYSTEM:
        style = QStyleFactory.create(default_style)
        if style is not None:
            app.setStyle(style)
        app.setPalette(app.style().standardPalette())
        return

    fusion = QStyleFactory.create("Fusion")
    if fusion is not None:
        app.setStyle(fusion)
    if theme == THEME_DARK:
        app.setPalette(_dark_palette())
    else:
        app.setPalette(_light_palette())
