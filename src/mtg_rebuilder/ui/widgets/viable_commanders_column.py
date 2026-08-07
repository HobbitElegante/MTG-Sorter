"""Commander card images for Planes viables (side grid + inline wrap strip)."""

from __future__ import annotations

from itertools import count

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from mtg_rebuilder.i18n import Translator
from mtg_rebuilder.ui.widgets.card_preview import PREVIEW_ASPECT, image_loader

# Side panel: up to three faces per row.
GRID_COLUMNS = 3
THUMB_WIDTH = 120
THUMB_HEIGHT = int(THUMB_WIDTH * PREVIEW_ASPECT)
GRID_SPACING = 8
STRIP_SPACING = 6

_slot_owner_ids = count(10_000)


class FlowLayout(QLayout):
    """Left-to-right wrapping layout (Qt cookbook style)."""

    def __init__(self, parent: QWidget | None = None, *, spacing: int = -1) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._spacing = spacing

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )
        return size

    def spacing(self) -> int:
        if self._spacing >= 0:
            return self._spacing
        return super().spacing()

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        x = effective.x()
        y = effective.y()
        line_height = 0
        space = self.spacing()

        for item in self._items:
            widget = item.widget()
            space_x = space
            space_y = space
            if widget is not None:
                space_x = space
                space_y = space
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + margins.bottom()


class CommanderThumb(QLabel):
    """Fixed-size card face using the shared preview image loader."""

    def __init__(
        self, translator: Translator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._owner = next(_slot_owner_ids)
        self._oracle_id: str | None = None
        self._card_name = ""
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setFixedSize(THUMB_WIDTH, THUMB_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        image_loader().resolved.connect(self._on_resolved)
        self.clear_card()

    def set_card(self, oracle_id: str | None, name: str = "") -> None:
        if oracle_id == self._oracle_id and name == self._card_name:
            return
        self._oracle_id = oracle_id or None
        self._card_name = name
        self._pixmap = None
        if self._oracle_id is None:
            image_loader().cancel(self._owner)
            self.clear_card()
            return
        self.setToolTip(name)
        self.setText(self._translator.t("preview.loading"))
        image_loader().request(self._owner, self._oracle_id, False)

    def clear_card(self) -> None:
        self._oracle_id = None
        self._card_name = ""
        self._pixmap = None
        image_loader().cancel(self._owner)
        self.setPixmap(QPixmap())
        self.setToolTip("")
        self.setText("")

    def _on_resolved(
        self,
        oracle_id: str,
        back: bool,
        image: object,
        _has_back: bool,
    ) -> None:
        if back or oracle_id != self._oracle_id:
            return
        if not isinstance(image, QImage) or image.isNull():
            self.setPixmap(QPixmap())
            self.setText(self._translator.t("preview.missing"))
            return
        self._pixmap = QPixmap.fromImage(image)
        self.setText("")
        self.setPixmap(
            self._pixmap.scaled(
                QSize(THUMB_WIDTH, THUMB_HEIGHT),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


class ViableCommandersStrip(QWidget):
    """Inline commanders with ``·`` separators, wrapping to the available width."""

    def __init__(
        self, translator: Translator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._flow = FlowLayout(self, spacing=STRIP_SPACING)
        self._flow.setContentsMargins(0, 2, 0, 2)
        self.setLayout(self._flow)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

    def set_commanders(self, cards: list[tuple[str, str]]) -> None:
        while self._flow.count():
            item = self._flow.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for index, (oracle_id, name) in enumerate(cards):
            if index > 0:
                sep = QLabel("·")
                sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
                font = sep.font()
                font.setPointSize(max(12, font.pointSize() + 2))
                sep.setFont(font)
                self._flow.addWidget(sep)
            thumb = CommanderThumb(self._translator, self)
            thumb.set_card(oracle_id, name)
            self._flow.addWidget(thumb)

        self.updateGeometry()

    def clear(self) -> None:
        self.set_commanders([])

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._flow.heightForWidth(width)

    def sizeHint(self) -> QSize:
        width = max(self.width(), THUMB_WIDTH * 3)
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        return QSize(THUMB_WIDTH, THUMB_HEIGHT + 4)


class ViableCommandersColumn(QScrollArea):
    """Commander images for the selected set, laid out in rows of three."""

    def __init__(
        self, translator: Translator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._slots: list[CommanderThumb] = []
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._inner = QWidget()
        self._grid = QGridLayout(self._inner)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(GRID_SPACING)
        self._grid.setVerticalSpacing(GRID_SPACING)
        self._grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.setWidget(self._inner)

        panel_width = GRID_COLUMNS * THUMB_WIDTH + (GRID_COLUMNS - 1) * GRID_SPACING
        self.setFixedWidth(panel_width + 4)
        self.setMinimumHeight(THUMB_HEIGHT)

    def set_commanders(self, cards: list[tuple[str, str]]) -> None:
        """Bind one ``(oracle_id, name)`` per deck; wrap every ``GRID_COLUMNS``."""
        while len(self._slots) < len(cards):
            self._slots.append(CommanderThumb(self._translator, self._inner))

        for slot in self._slots:
            self._grid.removeWidget(slot)
            slot.hide()

        for index, (oracle_id, name) in enumerate(cards):
            slot = self._slots[index]
            row, col = divmod(index, GRID_COLUMNS)
            self._grid.addWidget(slot, row, col)
            slot.show()
            slot.set_card(oracle_id, name)

        for slot in self._slots[len(cards) :]:
            slot.clear_card()

    def clear(self) -> None:
        self.set_commanders([])
