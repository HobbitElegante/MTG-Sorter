"""Scryfall logo icon — painted with QPainter (no QtSvg).

The original brand path is extremely dense; rendering it via QSvgRenderer on
toggle was freezing the UI on some systems. A simplified seal is enough to
read as “Scryfall” and swaps instantly between muted / active.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_COLOR_INACTIVE = QColor("#94a3b8")
_COLOR_ACTIVE = QColor("#0f766e")
_CHIP_ACTIVE = QColor("#ccfbf1")
_CHIP_BORDER = QColor("#5eead4")

_ICON_CACHE: dict[tuple[int, bool], QIcon] = {}


def _draw_seal(painter: QPainter, bound: QRectF, color: QColor) -> None:
    """Simplified circular seal inspired by the Scryfall mark."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawEllipse(bound)

    # Inner crescent / spiral hint (light cutouts).
    inset = bound.adjusted(
        bound.width() * 0.18,
        bound.height() * 0.18,
        -bound.width() * 0.18,
        -bound.height() * 0.18,
    )
    painter.setBrush(QColor(255, 255, 255, 230))
    path = QPainterPath()
    path.moveTo(QPointF(inset.center().x(), inset.top()))
    path.quadTo(
        QPointF(inset.left(), inset.center().y()),
        QPointF(inset.center().x(), inset.bottom()),
    )
    path.quadTo(
        QPointF(inset.left() + inset.width() * 0.35, inset.center().y()),
        QPointF(inset.center().x(), inset.top()),
    )
    painter.drawPath(path)

    # Small accent dots along the right (reads as the nested arcs).
    painter.setBrush(QColor(255, 255, 255, 220))
    cx = bound.center().x() + bound.width() * 0.18
    for factor in (0.28, 0.42, 0.56, 0.70):
        y = bound.top() + bound.height() * factor
        r = bound.width() * 0.045
        painter.drawEllipse(QPointF(cx, y), r, r)


def scryfall_icon(size: int = 22, *, active: bool = False) -> QIcon:
    key = (size, active)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached

    # Slightly larger canvas when active so the chip reads clearly.
    canvas = size + (6 if active else 0)
    pixmap = QPixmap(QSize(canvas, canvas))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if active:
        painter.setPen(QPen(_CHIP_BORDER, 1.0))
        painter.setBrush(_CHIP_ACTIVE)
        painter.drawRoundedRect(QRectF(0.5, 0.5, canvas - 1, canvas - 1), 5, 5)
        margin = 4.0
        color = _COLOR_ACTIVE
    else:
        margin = 1.0
        color = _COLOR_INACTIVE

    seal = QRectF(margin, margin, canvas - 2 * margin, canvas - 2 * margin)
    _draw_seal(painter, seal, color)
    painter.end()

    icon = QIcon(pixmap)
    _ICON_CACHE[key] = icon
    return icon
