"""World view: QPainter rendering of the infinite tile world.

Tiles are rendered from a per-chunk :class:`QPixmap` cache keyed by
``(cx, cy, chunk_version, tile_px)`` (LRU, about 200 chunks). Only
chunks whose version changed are rebuilt. The miner is drawn as a
simple vector robot with smooth visual interpolation between tiles.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import QPushButton, QWidget

from digscript.ui.theme import (
    BACKGROUND,
    BASE_BORDER,
    BASE_LABEL,
    FONT_FAMILY,
    GRID,
    LOCKED_MARK,
    MINER_BODY,
    MINER_DETAIL,
)

__all__ = ["CACHE_SIZE", "DEFAULT_TILE_PX", "MAX_TILE_PX", "MIN_TILE_PX", "WorldView"]

MIN_TILE_PX = 12
MAX_TILE_PX = 64
DEFAULT_TILE_PX = 24
CACHE_SIZE = 200


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _resolve(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Resolve game/world/miner/content from flexible arguments."""
    game = kwargs.pop("game", None)
    world = kwargs.pop("world", None)
    miner = kwargs.pop("miner", None)
    content = kwargs.pop("content", None)
    engine = kwargs.pop("engine", None)
    progression_view = kwargs.pop("progression_view", None) or kwargs.pop("progression", None)
    parent = kwargs.pop("parent", None)
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, "tile_at") and hasattr(arg, "generator"):
            if world is None:
                world = arg
        elif hasattr(arg, "capacity") and hasattr(arg, "inventory") and hasattr(arg, "x"):
            if miner is None:
                miner = arg
        elif hasattr(arg, "config") and hasattr(arg, "ores"):
            if content is None:
                content = arg
        elif hasattr(arg, "is_ore_unlocked"):
            if progression_view is None:
                progression_view = arg
        elif hasattr(arg, "miner") and hasattr(arg, "world"):
            if engine is None:
                engine = arg
            if game is None:
                game = arg
        elif hasattr(arg, "world") and hasattr(arg, "miner"):
            if game is None:
                game = arg
        elif hasattr(arg, "world") and hasattr(arg, "engine"):
            if game is None:
                game = arg
    if game is not None:
        if engine is None:
            engine = _get(game, "engine")
        if world is None:
            world = _get(game, "world")
        if miner is None:
            miner = _get(game, "miner")
        if content is None:
            content = _get(game, "content")
        if progression_view is None:
            progression_view = _get(game, "progression") or _get(game, "progression_view")
    if engine is not None:
        if world is None:
            world = _get(engine, "world")
        if miner is None:
            miner = _get(engine, "miner")
        if content is None:
            content = _get(engine, "content")
        if progression_view is None:
            progression_view = (
                _get(engine, "progression_view")
                or _get(engine, "progression")
                or _get(engine, "view")
            )
    if world is not None and content is None:
        content = _get(world, "content")
    if kwargs:
        raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
    return {
        "game": game,
        "world": world,
        "miner": miner,
        "content": content,
        "engine": engine,
        "progression_view": progression_view,
        "parent": parent,
    }


class WorldView(QWidget):
    """Draws the tiles around a camera center with QPainter only."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        tile_px_arg = kwargs.pop("tile_px", None)
        resolved = _resolve(*args, **kwargs)
        super().__init__(resolved["parent"])
        self.game = resolved["game"]
        self.world = resolved["world"]
        self.miner = resolved["miner"]
        self.content = resolved["content"]
        self.engine = resolved["engine"]
        self.progression_view = resolved["progression_view"]
        self.tile_px: int = int(tile_px_arg) if tile_px_arg is not None else DEFAULT_TILE_PX
        self.tile_px = max(MIN_TILE_PX, min(MAX_TILE_PX, int(self.tile_px)))
        self.follow_miner: bool = True
        self.show_grid: bool = False
        self._pixmap_cache: OrderedDict[tuple[int, int, int, int], QPixmap] = OrderedDict()
        self.pixmap_cache = self._pixmap_cache
        self.cache_size: int = CACHE_SIZE
        self.chunks_built: int = 0
        self.rebuild_count: int = 0
        self._panning: bool = False
        self._last_mouse_pos: Any = None
        miner_pos = self._miner_tile_center()
        self.camera_x: float = miner_pos[0]
        self.camera_y: float = miner_pos[1]
        self._visual_x: float = miner_pos[0]
        self._visual_y: float = miner_pos[1]
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.recenter_button = QPushButton("Recenter (C)", self)
        self.recenter_button.setVisible(False)
        self.recenter_button.clicked.connect(self.recenter)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._advance_visual)
        self._anim_timer.start()
        self._position_recenter_button()

    # -- aliases / properties ------------------------------------------------

    @property
    def tile_size(self) -> int:
        """Alias for :attr:`tile_px`."""
        return self.tile_px

    @tile_size.setter
    def tile_size(self, value: int) -> None:
        self.set_tile_px(value)

    @property
    def following(self) -> bool:
        """Alias for :attr:`follow_miner`."""
        return self.follow_miner

    @following.setter
    def following(self, value: bool) -> None:
        self.follow_miner = bool(value)

    @property
    def grid_visible(self) -> bool:
        """Alias for :attr:`show_grid`."""
        return self.show_grid

    @grid_visible.setter
    def grid_visible(self, value: bool) -> None:
        self.show_grid = bool(value)
        self.update()

    @property
    def camera(self) -> tuple[float, float]:
        """The camera center in tile coordinates."""
        return (self.camera_x, self.camera_y)

    @camera.setter
    def camera(self, value: tuple[float, float]) -> None:
        self.set_camera(value[0], value[1])

    @property
    def events(self) -> Any:
        """The game event bus, if any."""
        if self.game is not None:
            return _get(self.game, "events") or _get(self.game, "event_bus")
        if self.engine is not None:
            return _get(self.engine, "events")
        return None

    # -- helpers ---------------------------------------------------------------

    def _tick(self) -> int:
        if self.game is not None:
            tick = _get(self.game, "tick")
            if tick is not None:
                return int(tick)
        if self.engine is not None:
            return int(_get(self.engine, "tick", 0) or 0)
        return 0

    def _chunk_size(self) -> int:
        size = _get(self.world, "chunk_size")
        if size:
            return int(size)
        config = _get(self.content, "config")
        size = _get(config, "chunk_size")
        return int(size) if size else 16

    def _miner_tile_center(self) -> tuple[float, float]:
        if self.miner is None:
            return (0.5, 0.5)
        return (float(self.miner.x) + 0.5, float(self.miner.y) + 0.5)

    def _is_locked(self, ore_id: str) -> bool:
        view = self.progression_view
        if view is None and self.game is not None:
            view = _get(self.game, "progression")
        if view is None and self.engine is not None:
            view = _get(self.engine, "progression_view")
        checker = _get(view, "is_ore_unlocked")
        if callable(checker):
            return not bool(checker(ore_id))
        return False

    def _ore_color(self, ore_id: str) -> QColor:
        ore = None
        if self.content is not None:
            try:
                ore = self.content.get_ore(ore_id)
            except Exception:
                ore = None
        if ore is not None:
            return QColor(str(ore.color))
        return QColor(BACKGROUND)

    def _floor_color(self, biome_id: str) -> QColor:
        biome = None
        if self.content is not None:
            try:
                biome = self.content.get_biome(biome_id)
            except Exception:
                biome = None
        if biome is not None:
            return QColor(str(biome.floor_color))
        return QColor(BACKGROUND)

    # -- camera / zoom / grid ----------------------------------------------------

    def set_tile_px(self, value: int) -> None:
        """Set the tile size in pixels, clamped to [12, 64]."""
        self.tile_px = max(MIN_TILE_PX, min(MAX_TILE_PX, int(value)))
        self.update()

    def set_zoom(self, value: int) -> None:
        """Alias for :meth:`set_tile_px`."""
        self.set_tile_px(value)

    def zoom_by(self, steps: int) -> None:
        """Zoom by ``steps`` tile-pixel increments, clamped."""
        self.set_tile_px(self.tile_px + int(steps))

    def set_camera(self, x: float, y: float) -> None:
        """Move the camera center to tile coordinates ``(x, y)``."""
        self.camera_x = float(x)
        self.camera_y = float(y)
        self.update()

    def set_camera_center(self, x: float, y: float) -> None:
        """Alias for :meth:`set_camera`."""
        self.set_camera(x, y)

    def pan_by(self, dx_tiles: float, dy_tiles: float) -> None:
        """Pan the camera by tile offsets and stop following the miner."""
        self.follow_miner = False
        self.camera_x += float(dx_tiles)
        self.camera_y += float(dy_tiles)
        self._update_recenter_visibility()
        self.update()

    def pan(self, dx_tiles: float, dy_tiles: float) -> None:
        """Alias for :meth:`pan_by`."""
        self.pan_by(dx_tiles, dy_tiles)

    def center_on_miner(self) -> None:
        """Center the camera on the miner and resume following it."""
        self.follow_miner = True
        self.snap_visual_to_miner()
        self.camera_x, self.camera_y = self._visual_x, self._visual_y
        self._update_recenter_visibility()
        self.update()

    def recenter(self) -> None:
        """Alias for :meth:`center_on_miner`."""
        self.center_on_miner()

    def set_show_grid(self, visible: bool) -> None:
        """Show or hide the tile grid."""
        self.show_grid = bool(visible)
        self.update()

    def toggle_grid(self) -> None:
        """Toggle the tile grid."""
        self.set_show_grid(not self.show_grid)

    def snap_visual_to_miner(self) -> None:
        """Snap the interpolated miner position to the miner tile."""
        self._visual_x, self._visual_y = self._miner_tile_center()

    def miner_visual_position(self) -> tuple[float, float]:
        """Return the interpolated miner center in tile coordinates."""
        return (self._visual_x, self._visual_y)

    def visual_position(self) -> tuple[float, float]:
        """Alias for :meth:`miner_visual_position`."""
        return self.miner_visual_position()

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """Convert tile coordinates to widget pixel coordinates."""
        return (
            self.width() / 2.0 + (float(wx) - self.camera_x) * self.tile_px,
            self.height() / 2.0 + (float(wy) - self.camera_y) * self.tile_px,
        )

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Convert widget pixel coordinates to tile coordinates."""
        return (
            self.camera_x + (float(sx) - self.width() / 2.0) / self.tile_px,
            self.camera_y + (float(sy) - self.height() / 2.0) / self.tile_px,
        )

    def visible_tiles(self) -> tuple[int, int, int, int]:
        """Return ``(x0, y0, x1, y1)`` visible tile range (x1/y1 exclusive)."""
        half_w = self.width() / (2.0 * self.tile_px)
        half_h = self.height() / (2.0 * self.tile_px)
        x0 = int(self.camera_x - half_w) - 1
        y0 = int(self.camera_y - half_h) - 1
        x1 = int(self.camera_x + half_w) + 2
        y1 = int(self.camera_y + half_h) + 2
        return (x0, y0, x1, y1)

    def visible_chunk_range(self) -> tuple[int, int, int, int]:
        """Return ``(cx0, cy0, cx1, cy1)`` visible chunk range (exclusive end)."""
        x0, y0, x1, y1 = self.visible_tiles()
        size = self._chunk_size()
        return (x0 // size, y0 // size, (x1 - 1) // size + 1, (y1 - 1) // size + 1)

    # -- chunk pixmap cache -------------------------------------------------------

    def _chunk_version(self, cx: int, cy: int) -> int:
        getter = _get(self.world, "chunk_version")
        if callable(getter):
            return int(getter(cx, cy))
        return 0

    def clear_cache(self) -> None:
        """Drop all cached chunk pixmaps."""
        self._pixmap_cache.clear()

    def get_chunk_pixmap(self, cx: int, cy: int) -> QPixmap:
        """Return the cached pixmap for chunk ``(cx, cy)``, building if needed."""
        key = (cx, cy, self._chunk_version(cx, cy), self.tile_px)
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            self._pixmap_cache.move_to_end(key)
            return cached
        pixmap = self._build_chunk_pixmap(cx, cy)
        self._pixmap_cache[key] = pixmap
        self._pixmap_cache.move_to_end(key)
        while len(self._pixmap_cache) > self.cache_size:
            self._pixmap_cache.popitem(last=False)
        return pixmap

    def _build_chunk_pixmap(self, cx: int, cy: int) -> QPixmap:
        """Render one chunk into a new pixmap and count the rebuild."""
        size = self._chunk_size()
        tile_px = self.tile_px
        pixmap = QPixmap(size * tile_px, size * tile_px)
        pixmap.fill(QColor(BACKGROUND))
        painter = QPainter(pixmap)
        try:
            tick = self._tick()
            rows: Any = None
            chunk_tiles = _get(self.world, "chunk_tiles")
            if callable(chunk_tiles):
                try:
                    rows = chunk_tiles(cx, cy, tick)
                except TypeError:
                    rows = chunk_tiles(cx, cy)
            for dy in range(size):
                for dx in range(size):
                    if rows is not None:
                        tile = rows[dy][dx]
                    else:
                        tile = self.world.tile_at(cx * size + dx, cy * size + dy, tick)
                    rect_x, rect_y = dx * tile_px, dy * tile_px
                    floor = self._floor_color(tile.biome_id)
                    if tile.depleted:
                        floor = floor.darker(160)
                    if tile.ore_id is None:
                        painter.fillRect(rect_x, rect_y, tile_px, tile_px, floor)
                    elif self._is_locked(tile.ore_id):
                        painter.fillRect(rect_x, rect_y, tile_px, tile_px, floor)
                        if tile_px >= 14:
                            painter.setPen(QColor(LOCKED_MARK))
                            font = QFont(FONT_FAMILY)
                            font.setBold(True)
                            font.setPointSize(max(8, tile_px // 2))
                            painter.setFont(font)
                            painter.drawText(
                                rect_x, rect_y, tile_px, tile_px, Qt.AlignmentFlag.AlignCenter, "?"
                            )
                    else:
                        painter.fillRect(rect_x, rect_y, tile_px, tile_px, floor)
                        margin = max(1, tile_px // 8)
                        painter.fillRect(
                            rect_x + margin,
                            rect_y + margin,
                            tile_px - 2 * margin,
                            tile_px - 2 * margin,
                            self._ore_color(tile.ore_id),
                        )
        finally:
            painter.end()
        self.chunks_built += 1
        self.rebuild_count += 1
        return pixmap

    def build_chunk_pixmap(self, cx: int, cy: int) -> QPixmap:
        """Alias for :meth:`_build_chunk_pixmap`."""
        return self._build_chunk_pixmap(cx, cy)

    # -- drawing --------------------------------------------------------------------

    def _advance_visual(self) -> None:
        """Smoothly move the visual miner position toward the miner tile."""
        target_x, target_y = self._miner_tile_center()
        self._visual_x += (target_x - self._visual_x) * 0.25
        self._visual_y += (target_y - self._visual_y) * 0.25
        if abs(target_x - self._visual_x) < 0.001:
            self._visual_x = target_x
        if abs(target_y - self._visual_y) < 0.001:
            self._visual_y = target_y
        if self.follow_miner:
            self.camera_x, self.camera_y = self._visual_x, self._visual_y
        self.update()

    def _update_recenter_visibility(self) -> None:
        self.recenter_button.setVisible(not self.follow_miner)
        self._position_recenter_button()

    def _position_recenter_button(self) -> None:
        self.recenter_button.move(max(0, self.width() - self.recenter_button.width() - 8), 8)

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Reposition the Recenter button on resize."""
        super().resizeEvent(event)
        self._position_recenter_button()

    def _draw_base(self, painter: QPainter) -> None:
        config = _get(self.content, "config")
        half = int(_get(config, "base_half_size", 1) or 0)
        x0, y0 = self.world_to_screen(-half, -half)
        x1, y1 = self.world_to_screen(half + 1, half + 1)
        painter.setPen(QPen(QColor(BASE_BORDER), 2))
        painter.drawRect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
        painter.setPen(QColor(BASE_LABEL))
        font = QFont(FONT_FAMILY)
        font.setBold(True)
        font.setPointSize(max(8, self.tile_px // 2))
        painter.setFont(font)
        painter.drawText(int(x0) + 4, int(y0) + max(12, self.tile_px), "BASE")

    def _draw_miner(self, painter: QPainter) -> None:
        if self.miner is None:
            return
        sx, sy = self.world_to_screen(self._visual_x, self._visual_y)
        radius = max(4.0, self.tile_px * 0.36)
        facing = _get(self.miner, "facing")
        dx = float(_get(facing, "dx", 0) or 0)
        dy = float(_get(facing, "dy", -1) if _get(facing, "dy") is not None else -1)
        if dx == 0 and dy == 0:
            dx, dy = 0.0, -1.0
        painter.setPen(QPen(QColor(MINER_DETAIL), 2))
        painter.setBrush(QColor(MINER_BODY))
        painter.drawEllipse(int(sx - radius), int(sy - radius), int(radius * 2), int(radius * 2))
        tip_x = sx + dx * radius * 1.5
        tip_y = sy + dy * radius * 1.5
        painter.setBrush(QColor(MINER_BODY))
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(tip_x, tip_y),
                    QPointF(sx - dy * radius * 0.5, sy + dx * radius * 0.5),
                    QPointF(sx + dy * radius * 0.5, sy - dx * radius * 0.5),
                ]
            )
        )
        painter.setBrush(QColor(MINER_DETAIL))
        painter.drawEllipse(int(sx - 2), int(sy - 2), 4, 4)

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Draw visible chunk pixmaps, grid, base and the miner."""
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor(BACKGROUND))
            if self.world is not None:
                size = self._chunk_size()
                cx0, cy0, cx1, cy1 = self.visible_chunk_range()
                for cy in range(cy0, cy1):
                    for cx in range(cx0, cx1):
                        pixmap = self.get_chunk_pixmap(cx, cy)
                        sx, sy = self.world_to_screen(cx * size, cy * size)
                        painter.drawPixmap(int(sx), int(sy), pixmap)
                if self.show_grid:
                    x0, y0, x1, y1 = self.visible_tiles()
                    painter.setPen(QPen(QColor(GRID), 1))
                    for tx in range(x0, x1 + 1):
                        sx, _ = self.world_to_screen(tx, y0)
                        _, top = self.world_to_screen(tx, y0)
                        _, bottom = self.world_to_screen(tx, y1)
                        painter.drawLine(int(sx), int(top), int(sx), int(bottom))
                    for ty in range(y0, y1 + 1):
                        _, sy = self.world_to_screen(x0, ty)
                        left, _ = self.world_to_screen(x0, ty)
                        right, _ = self.world_to_screen(x1, ty)
                        painter.drawLine(int(left), int(sy), int(right), int(sy))
                self._draw_base(painter)
            self._draw_miner(painter)
        finally:
            painter.end()
        super().paintEvent(event)

    # -- input ------------------------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt override name
        """Zoom with the mouse wheel (tile size clamped to [12, 64])."""
        steps = event.angleDelta().y() // 120
        if steps == 0:
            steps = 1 if event.angleDelta().y() > 0 else -1
        self.set_tile_px(self.tile_px + int(steps) * 2)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override name
        """Start panning with the middle or right button; any click grabs focus."""
        self.setFocus()
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._panning = True
            self._last_mouse_pos = event.position()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override name
        """Pan while dragging with the middle or right button."""
        if self._panning and self._last_mouse_pos is not None:
            delta = event.position() - self._last_mouse_pos
            self._last_mouse_pos = event.position()
            self.pan_by(-delta.x() / self.tile_px, -delta.y() / self.tile_px)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override name
        """Stop panning on mouse release."""
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._panning = False
            self._last_mouse_pos = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """C recenters on the miner; G toggles the grid; other hotkeys go to MainWindow."""
        key = event.key()
        if key == Qt.Key.Key_C:
            self.recenter()
            event.accept()
        elif key == Qt.Key.Key_G:
            self.toggle_grid()
            event.accept()
        else:
            window = self.window()
            handler = getattr(window, "keyPressEvent", None)
            if window is not None and window is not self and callable(handler):
                handler(event)
            else:
                super().keyPressEvent(event)
