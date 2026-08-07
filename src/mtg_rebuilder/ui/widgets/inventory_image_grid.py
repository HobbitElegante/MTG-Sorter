"""Scrollable inventory image grid (local cache only; no network downloads).

Uses viewport virtualization: only tiles near the visible scroll window exist as
widgets, so switching into Image view and scrolling stay responsive with ~1k+ cards.

Layout math lives in ``ui.inventory_image_layout`` (Qt-free) for headless tests.
"""

from collections import OrderedDict
from itertools import count
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from mtg_rebuilder.i18n import Translator
from mtg_rebuilder.services.browse_service import InventorySummaryRow
from mtg_rebuilder.ui.inventory_image_layout import (
    CAPTION_EXTRA,
    THUMB_MIN_WIDTH,
    TILE_PADDING,
    content_height,
    local_front_image_path,
    thumb_height_for_width,
    thumb_width_for_viewport,
    tile_top_left,
    visible_index_range,
)
from mtg_rebuilder.ui.widgets.card_preview import image_loader

_PIXMAP_CACHE_SIZE = 160
_SYNC_DEBOUNCE_MS = 16

_tile_owner_ids = count(1)

# oracle_id -> QPixmap (hit) or None (ensure failed / unreadable). Disk misses
# that have not been ensured yet are *not* stored, so scroll can still download.
_pixmap_cache: OrderedDict[str, QPixmap | None] = OrderedDict()


def _cached_pixmap(oracle_id: str) -> tuple[bool, QPixmap | None]:
    """Return (known, pixmap). known=False means not yet looked up."""
    if oracle_id not in _pixmap_cache:
        return False, None
    _pixmap_cache.move_to_end(oracle_id)
    return True, _pixmap_cache[oracle_id]


def _store_pixmap(oracle_id: str, pixmap: QPixmap | None) -> None:
    _pixmap_cache[oracle_id] = pixmap
    _pixmap_cache.move_to_end(oracle_id)
    while len(_pixmap_cache) > _PIXMAP_CACHE_SIZE:
        _pixmap_cache.popitem(last=False)


def load_local_pixmap(oracle_id: str, images_dir: Path | None = None) -> QPixmap | None:
    """Return a cached/on-disk pixmap, or None if not available yet.

    Successful loads and permanent failures (after ensure) are cached. A plain
    disk miss is *not* cached so the caller can still request an on-demand
    download when the tile becomes visible.
    """
    known, cached = _cached_pixmap(oracle_id)
    if known:
        return cached
    path = local_front_image_path(oracle_id, images_dir)
    if path is None:
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        _store_pixmap(oracle_id, None)
        return None
    _store_pixmap(oracle_id, pixmap)
    return pixmap


def mark_image_unavailable(oracle_id: str) -> None:
    """Remember that ensure_image failed so we do not retry in a tight loop."""
    _store_pixmap(oracle_id, None)


class _CardTile(QFrame):
    clicked = Signal(str)

    def __init__(
        self,
        translator: Translator,
        parent: QWidget | None = None,
        *,
        thumb_width: int = THUMB_MIN_WIDTH,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._owner = next(_tile_owner_ids)
        self._oracle_id = ""
        self._card_name = ""
        self._selected = False
        self._source_pixmap: QPixmap | None = None
        self._thumb_width = thumb_width
        self.setObjectName("inventoryCardTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setWordWrap(True)
        self._image.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self._image, 0, Qt.AlignmentFlag.AlignHCenter)

        self._caption = QLabel()
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setWordWrap(True)
        caption_font = self._caption.font()
        caption_font.setPointSize(max(8, caption_font.pointSize() - 2))
        self._caption.setFont(caption_font)
        layout.addWidget(self._caption)

        self._apply_thumb_size(thumb_width)
        self._apply_style()

    def oracle_id(self) -> str:
        return self._oracle_id

    def owner_id(self) -> int:
        return self._owner

    def cancel_pending(self) -> None:
        image_loader().cancel(self._owner)

    def bind(self, row: InventorySummaryRow, *, selected: bool) -> None:
        same_card = row.oracle_id == self._oracle_id
        if not same_card:
            self.cancel_pending()
        self._oracle_id = row.oracle_id
        self._card_name = row.card_name
        self._caption.setText(row.card_name)
        self.set_selected(selected)
        if same_card and self._source_pixmap is not None:
            self._rescale()
            return
        self._source_pixmap = None
        self._show_placeholder()
        self.load_image_if_needed()

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._apply_style()

    def retranslate(self) -> None:
        if self._source_pixmap is None and self._oracle_id:
            self._show_placeholder()

    def set_thumb_width(self, width: int) -> None:
        if width == self._thumb_width:
            return
        self._apply_thumb_size(width)
        self._rescale()

    def load_image_if_needed(self) -> None:
        if not self._oracle_id:
            return
        if self._source_pixmap is not None:
            self._rescale()
            return

        known, cached = _cached_pixmap(self._oracle_id)
        if known:
            if cached is not None:
                self._source_pixmap = cached
                self._rescale()
            else:
                self._show_placeholder()
            return

        pixmap = load_local_pixmap(self._oracle_id)
        if pixmap is not None:
            self._source_pixmap = pixmap
            self._rescale()
            return

        # Not on disk yet — empty slot, then ensure_image in the background.
        self._show_placeholder()
        image_loader().request(self._owner, self._oracle_id, False)

    def apply_resolved(self, oracle_id: str, pixmap: QPixmap | None) -> None:
        if oracle_id != self._oracle_id:
            return
        if pixmap is None or pixmap.isNull():
            mark_image_unavailable(oracle_id)
            self._source_pixmap = None
            self._show_placeholder()
            return
        _store_pixmap(oracle_id, pixmap)
        self._source_pixmap = pixmap
        self._rescale()

    def _apply_thumb_size(self, width: int) -> None:
        self._thumb_width = width
        height = thumb_height_for_width(width)
        self._image.setFixedSize(width, height)
        self.setFixedSize(width + TILE_PADDING, height + CAPTION_EXTRA)

    def _rescale(self) -> None:
        if self._source_pixmap is None:
            if self._oracle_id:
                self._show_placeholder()
            return
        self._image.setText("")
        self._image.setToolTip("")
        self._image.setPixmap(
            self._source_pixmap.scaled(
                QSize(self._thumb_width, thumb_height_for_width(self._thumb_width)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        )

    def _show_placeholder(self) -> None:
        """Empty card-shaped slot while the image loads (or if ensure fails)."""
        self._image.setPixmap(QPixmap())
        self._image.setText("")
        self._image.setToolTip(self._translator.t("inventory.view.missing_image"))

    def _apply_style(self) -> None:
        border = "#4a90d9" if self._selected else "palette(mid)"
        width = 2 if self._selected else 1
        self.setStyleSheet(
            f"#inventoryCardTile {{"
            f" border: {width}px solid {border};"
            f" border-radius: 4px;"
            f" background: palette(base);"
            f"}}"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton and self._oracle_id:
            self.clicked.emit(self._oracle_id)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if (
            self._oracle_id
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
        ):
            self.clicked.emit(self._oracle_id)
            return
        super().keyPressEvent(event)


class InventoryImageGrid(QScrollArea):
    """Virtualized grid of card faces from the local image cache (max 5 per row)."""

    card_selected = Signal(str)

    def __init__(
        self,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._rows: list[InventorySummaryRow] = []
        self._tiles: dict[int, _CardTile] = {}
        self._pool: list[_CardTile] = []
        self._selected_oracle_id: str | None = None
        self._thumb_width = THUMB_MIN_WIDTH
        self._pending_rows: list[InventorySummaryRow] | None = None

        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(_SYNC_DEBOUNCE_MS)
        self._sync_timer.timeout.connect(self._sync_visible_tiles)

        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(50)
        self._resize_timer.timeout.connect(self._apply_responsive_size)

        self._populate_timer = QTimer(self)
        self._populate_timer.setSingleShot(True)
        self._populate_timer.setInterval(0)
        self._populate_timer.timeout.connect(self._flush_pending_rows)

        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self._container = QWidget()
        self._container.setMinimumWidth(1)
        self.setWidget(self._container)
        image_loader().resolved.connect(self._on_image_resolved)

    def set_rows(self, rows: list[InventorySummaryRow]) -> None:
        # Defer so the stacked-widget switch can paint before we mount tiles.
        self._pending_rows = list(rows)
        self._populate_timer.start()

    def ensure_layout_sync(self) -> None:
        """Re-run geometry + visible tiles after the stacked view is laid out."""
        if self._pending_rows is not None:
            self._flush_pending_rows()
        else:
            self._thumb_width = self._compute_thumb_width()
            self._update_container_geometry()
            self._sync_visible_tiles()

    def selected_oracle_id(self) -> str | None:
        return self._selected_oracle_id

    def select_oracle_id(self, oracle_id: str | None) -> None:
        self._selected_oracle_id = oracle_id
        for index, tile in self._tiles.items():
            row = self._rows[index] if 0 <= index < len(self._rows) else None
            tile.set_selected(
                row is not None and row.oracle_id == oracle_id
            )

    def retranslate(self) -> None:
        for tile in self._tiles.values():
            tile.retranslate()
        for tile in self._pool:
            tile.retranslate()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._resize_timer.start()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        if self._pending_rows is not None:
            self._flush_pending_rows()
        self._schedule_sync()

    def _flush_pending_rows(self) -> None:
        if self._pending_rows is None:
            return
        rows = self._pending_rows
        self._pending_rows = None
        self._rows = rows
        self._thumb_width = self._compute_thumb_width()
        self._update_container_geometry()
        self._recycle_all_tiles()
        self._sync_visible_tiles()

    def _compute_thumb_width(self) -> int:
        return thumb_width_for_viewport(max(self.viewport().width(), 1))

    def _update_container_geometry(self) -> None:
        width = max(self.viewport().width(), 1)
        height = content_height(len(self._rows), self._thumb_width)
        self._container.setFixedSize(width, height)

    def _apply_responsive_size(self) -> None:
        width = self._compute_thumb_width()
        size_changed = width != self._thumb_width
        self._thumb_width = width
        self._update_container_geometry()
        if size_changed:
            for tile in self._tiles.values():
                tile.set_thumb_width(width)
            for tile in self._pool:
                tile.set_thumb_width(width)
            # Positions depend on thumb size — remount.
            self._recycle_all_tiles()
        self._sync_visible_tiles()

    def _on_scroll(self, _value: int) -> None:
        self._schedule_sync()

    def _schedule_sync(self) -> None:
        self._sync_timer.start()

    def _recycle_all_tiles(self) -> None:
        for tile in self._tiles.values():
            tile.cancel_pending()
            tile.hide()
            self._pool.append(tile)
        self._tiles.clear()

    def _acquire_tile(self) -> _CardTile:
        if self._pool:
            tile = self._pool.pop()
            tile.set_thumb_width(self._thumb_width)
            tile.show()
            return tile
        tile = _CardTile(
            self._translator,
            self._container,
            thumb_width=self._thumb_width,
        )
        tile.clicked.connect(self._on_tile_clicked)
        return tile

    def _sync_visible_tiles(self) -> None:
        start, end = visible_index_range(
            self.verticalScrollBar().value(),
            self.viewport().height(),
            self._thumb_width,
            len(self._rows),
        )
        needed = set(range(start, end))
        for index in list(self._tiles):
            if index not in needed:
                tile = self._tiles.pop(index)
                tile.cancel_pending()
                tile.hide()
                self._pool.append(tile)

        for index in range(start, end):
            row = self._rows[index]
            selected = row.oracle_id == self._selected_oracle_id
            tile = self._tiles.get(index)
            if tile is None:
                tile = self._acquire_tile()
                self._tiles[index] = tile
            tile.bind(row, selected=selected)
            x, y = tile_top_left(index, self._thumb_width)
            tile.move(x, y)
            tile.raise_()

    def _on_image_resolved(
        self,
        oracle_id: str,
        back: bool,
        image: object,
        _has_back: bool,
    ) -> None:
        if back:
            return
        pixmap: QPixmap | None = None
        if isinstance(image, QImage) and not image.isNull():
            pixmap = QPixmap.fromImage(image)
        elif isinstance(image, QPixmap) and not image.isNull():
            pixmap = image
        for tile in self._tiles.values():
            if tile.oracle_id() == oracle_id:
                tile.apply_resolved(oracle_id, pixmap)
        # Cache failure even if no tile still shows this card.
        if pixmap is None or pixmap.isNull():
            mark_image_unavailable(oracle_id)

    def _on_tile_clicked(self, oracle_id: str) -> None:
        self.select_oracle_id(oracle_id)
        self.card_selected.emit(oracle_id)
