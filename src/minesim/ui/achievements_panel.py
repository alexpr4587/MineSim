"""Achievements screen (key L): one tab per achievements.json tab.

The tree is drawn with a :class:`~PySide6.QtWidgets.QGraphicsScene` and
:class:`~PySide6.QtWidgets.QGraphicsView`: rounded square nodes with an icon
letter, lines from parent to child.

The layout is the pure function :func:`layout_tree` mapping node id to
``(col, row)`` where ``col`` is depth and rows are chosen so siblings never
overlap.

Node states: completed (filled, check mark), available (outlined, progress
ring), locked (dimmed). Tooltip shows title, description, progress such as
``7/20`` and rewards such as ``Unlocks: scan()``. Drag to pan; Esc or L closes.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from minesim.core.events import AchievementUnlocked
from minesim.ui.floating_panel import FloatingPanel
from minesim.ui.theme import ACCENT, BACKGROUND, DISABLED_TEXT, TEXT, TEXT_DIM

__all__ = ["AchievementsPanel", "layout_tree"]

NODE_SIZE = 64
COL_SPACING = 170
ROW_SPACING = 80

_TAB_LABELS = {
    "code": "Code",
    "mining": "Mining",
    "business": "Business",
    "explorer": "Explorer",
    "data": "Data",
}

_TAB_ORDER = ("code", "mining", "business", "explorer", "data")


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def layout_tree(nodes: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """Lay out a forest of achievement nodes.

    Returns ``{id: (col, row)}`` where ``col`` is the node depth (roots at 0)
    and ``row`` increases so that no two nodes share a cell and every parent is
    strictly left of its children. Siblings never overlap.

    ``nodes`` is a list of mappings with ``id`` and optional ``parent`` keys,
    in file order (used to break ties deterministically).
    """
    by_id: dict[str, dict[str, Any]] = {}
    children: dict[str, list[str]] = {}
    order: dict[str, int] = {}
    for index, node in enumerate(nodes):
        nid = str(node.get("id", ""))
        by_id[nid] = node
        children.setdefault(nid, [])
        order[nid] = index

    roots: list[str] = []
    for node in nodes:
        nid = str(node.get("id", ""))
        parent = node.get("parent")
        if parent is None:
            roots.append(nid)
        else:
            children.setdefault(str(parent), []).append(nid)

    roots.sort(key=lambda nid: order[nid])
    for nid in children:
        children[nid].sort(key=lambda c: order[c])

    # Depth (column) of every node.
    depth: dict[str, int] = {}

    def set_depth(nid: str, d: int) -> None:
        depth[nid] = d
        for child in children.get(nid, []):
            set_depth(child, d + 1)

    for root in roots:
        set_depth(root, 0)

    # Place roots depth-first; each subtree occupies a contiguous row block so
    # parents stay vertically close to their children.
    pos: dict[str, tuple[int, int]] = {}
    row = [0]

    def place(nid: str) -> None:
        pos[nid] = (depth[nid], row[0])
        row[0] += 1
        for child in children.get(nid, []):
            place(child)

    for root in roots:
        place(root)

    return pos


class _NodeItem(QGraphicsObject):
    """A single achievement node: rounded square + icon letter + state mark."""

    def __init__(
        self,
        node_id: str,
        node: dict[str, Any],
        state: str,
        progress: tuple[int, int],
        rewards_text: str,
    ) -> None:
        super().__init__()
        self.node_id = node_id
        self.node = node
        self.state = state  # "completed" | "available" | "locked"
        self.progress = progress
        self.rewards_text = rewards_text
        self.setAcceptHoverEvents(True)
        self.setToolTip(self._build_tooltip())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_tooltip(self) -> str:
        title = str(_get(self.node, "title", self.node_id))
        description = str(_get(self.node, "description", ""))
        current, target = self.progress
        progress_line = f"Progress: {current}/{target}"
        reward_line = self.rewards_text
        parts = [f"<b>{title}</b>"]
        if description:
            parts.append(description)
        parts.append(progress_line)
        if reward_line:
            parts.append(reward_line)
        return "<br/>".join(parts)

    def _icon_letter(self) -> str:
        title = str(_get(self.node, "title", self.node_id))
        for ch in title:
            if ch.isalpha():
                return ch.upper()
        return "?"

    def _state_style(self) -> tuple[QColor, QColor, str]:
        """Return (fill, border, mark) for the node state."""
        if self.state == "completed":
            return QColor(ACCENT), QColor(ACCENT), "✓"
        if self.state == "available":
            return QColor(BACKGROUND), QColor(ACCENT), ""
        # locked
        return QColor(TEXT_DIM), QColor(DISABLED_TEXT), "?"

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, NODE_SIZE, NODE_SIZE)

    def paint(self, painter: QPainter, option: Any, widget: Any) -> None:  # noqa: ARG002
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill, border, mark = self._state_style()
        rect = self.boundingRect()
        painter.setBrush(fill)
        painter.setPen(QPen(border, 2 if self.state == "locked" else 2))
        painter.drawRoundedRect(rect, 10, 10)
        # Icon letter.
        painter.setPen(QPen(TEXT if self.state != "locked" else QColor("#6a6a7d")))
        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._icon_letter())
        # State mark (completed check / locked).
        if mark:
            mark_font = painter.font()
            mark_font.setPointSize(18)
            mark_font.setBold(True)
            painter.setFont(mark_font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, mark)
        # Progress ring for available nodes.
        if self.state == "available" and self.progress[1] > 0:
            current, target = self.progress
            ratio = max(0.0, min(1.0, current / target))
            pen = QPen(QColor(ACCENT), 3)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            ring = QRectF(6, 6, NODE_SIZE - 12, NODE_SIZE - 12)
            span = -int(360 * 16 * ratio)
            painter.drawArc(ring, 90 * 16, span)


class _AchievementsView(QGraphicsView):
    """A QGraphicsView drawing one tab's achievement tree."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def wheelEvent(self, event: Any) -> None:  # noqa: N802
        # Zoom with Ctrl+wheel, scroll otherwise.
        from PySide6.QtWidgets import QApplication

        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)


class AchievementsPanel(FloatingPanel):
    """Floating achievements screen with one tab per achievements.json tab."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Achievements"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        content = kwargs.pop("content", None)
        progression = kwargs.pop("progression", None) or kwargs.pop("progression_view", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget) and parent is None:
                parent = arg
            elif hasattr(arg, "config") and hasattr(arg, "achievements"):
                if content is None:
                    content = arg
            elif hasattr(arg, "is_achievement_unlocked"):
                if progression is None:
                    progression = arg
            elif hasattr(arg, "engine") and hasattr(arg, "miner"):
                if game is None:
                    game = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        self.game = game
        if game is not None:
            if content is None:
                content = _get(game, "content")
            if progression is None:
                progression = (
                    _get(game, "progression_service")
                    or _get(game, "progression")
                    or _get(game, "progression_view")
                )
        self.progression = progression

        super().__init__(title, parent=parent)
        if not self._restored_geometry:
            self.resize(820, 620)
            self.move(100, 60)

        self.content = content

        self.tabs = QTabWidget(self.content_widget)
        self.content_layout.addWidget(self.tabs)

        self._views: dict[str, _AchievementsView] = {}
        self._node_items: dict[str, _NodeItem] = {}

        self._build_tabs()
        self.refresh()
        self._subscribe()

    # -- building -------------------------------------------------------------

    def _build_tabs(self) -> None:
        self.tabs.clear()
        self._views = {}
        for tab_id in _TAB_ORDER:
            view = _AchievementsView(self.tabs)
            self._views[tab_id] = view
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(view, 1)
            hint = QLabel(_TAB_LABELS.get(tab_id, tab_id.title()), container)
            hint.setStyleSheet(f"color: {TEXT_DIM}; padding: 4px 8px;")
            layout.insertWidget(0, hint)
            self.tabs.addTab(container, _TAB_LABELS.get(tab_id, tab_id.title()))

    def _achievements(self) -> list[dict[str, Any]]:
        if self.content is not None:
            getter = getattr(self.content, "achievement_list", None)
            if callable(getter):
                try:
                    return [dict(a.__dict__) if hasattr(a, "__dict__") else a for a in getter()]
                except Exception:
                    pass
            raw = _get(self.content, "achievements")
            if isinstance(raw, dict):
                return [dict(v.__dict__) if hasattr(v, "__dict__") else v for v in raw.values()]
            if isinstance(raw, list):
                return [dict(v) if isinstance(v, dict) else v for v in raw]
        return []

    # -- state ----------------------------------------------------------------

    def _node_state(self, achievement_id: str) -> str:
        if self.progression is None:
            return "locked"
        if self.progression.is_achievement_unlocked(achievement_id):
            return "completed"
        if self.progression.is_available(achievement_id):
            return "available"
        return "locked"

    def _progress(self, achievement_id: str) -> tuple[int, int]:
        if self.progression is None:
            return (0, 1)
        getter = getattr(self.progression, "progress", None)
        if callable(getter):
            try:
                return tuple(int(x) for x in getter(achievement_id))
            except Exception:
                pass
        return (0, 1)

    def _rewards_text(self, node: dict[str, Any]) -> str:
        rewards = _get(node, "rewards") or []
        parts: list[str] = []
        for reward in rewards:
            reward_type = _get(reward, "type")
            reward_id = _get(reward, "id")
            amount = _get(reward, "amount")
            if reward_type == "unlock_function" and reward_id:
                parts.append(f"Unlocks: {reward_id}()")
            elif reward_type == "unlock_ore" and reward_id:
                parts.append(f"Unlocks ore: {reward_id}")
            elif reward_type == "unlock_upgrade" and reward_id:
                parts.append(f"Unlocks upgrade: {reward_id}")
            elif reward_type == "unlock_module" and reward_id:
                parts.append(f"Unlocks module: {reward_id}")
            elif reward_type == "unlock_skin" and reward_id:
                parts.append(f"Unlocks skin: {reward_id}")
            elif reward_type == "unlock_example" and reward_id:
                parts.append(f"Unlocks example: {reward_id}")
            elif reward_type == "money" and amount is not None:
                parts.append(f"+{amount} money")
        return "; ".join(parts)

    def refresh(self) -> None:
        """Rebuild every tab's tree from current unlock state."""
        self._node_items.clear()
        for tab_id, view in self._views.items():
            scene = view.scene()
            scene.clear()
            nodes = [n for n in self._achievements() if str(n.get("tab")) == tab_id]
            if not nodes:
                continue
            positions = layout_tree(nodes)
            # Draw lines parent -> child first (behind nodes).
            for node in nodes:
                nid = str(node.get("id"))
                parent = node.get("parent")
                if parent is None or parent not in positions or nid not in positions:
                    continue
                x1, y1 = self._node_center(positions[str(parent)])
                x2, y2 = self._node_center(positions[nid])
                scene.addLine(QLineF(QPointF(x1, y1), QPointF(x2, y2)), QPen(QColor(TEXT_DIM), 1))
            # Draw nodes.
            for node in nodes:
                nid = str(node.get("id"))
                state = self._node_state(nid)
                progress = self._progress(nid)
                rewards_text = self._rewards_text(node)
                item = _NodeItem(nid, node, state, progress, rewards_text)
                col, row = positions[nid]
                item.setPos(QPointF(col * COL_SPACING, row * ROW_SPACING))
                scene.addItem(item)
                self._node_items[nid] = item
            scene.setSceneRect(scene.itemsBoundingRect())

    @staticmethod
    def _node_center(pos: tuple[int, int]) -> tuple[float, float]:
        col, row = pos
        return (col * COL_SPACING + NODE_SIZE / 2.0, row * ROW_SPACING + NODE_SIZE / 2.0)

    # -- events ---------------------------------------------------------------

    def _subscribe(self) -> None:
        if self.game is None:
            return
        bus = _get(self.game, "events") or _get(self.game, "event_bus")
        if bus is None or not hasattr(bus, "subscribe"):
            return
        try:
            bus.subscribe(AchievementUnlocked, lambda _e: self.refresh())
        except Exception:
            return

    def set_game(self, game: Any) -> None:
        """Attach a (new) game and refresh the tree."""
        self.game = game
        if game is not None:
            self.content = _get(game, "content")
            self.progression = (
                _get(game, "progression_service")
                or _get(game, "progression")
                or _get(game, "progression_view")
            )
        self._build_tabs()
        self.refresh()
        self._subscribe()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        self.refresh()
        super().showEvent(event)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.hide_panel()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: Any) -> None:  # noqa: N802
        super().focusOutEvent(event)
