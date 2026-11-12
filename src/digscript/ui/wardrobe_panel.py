"""Wardrobe panel (key K): pick the miner skin.

Each skin is shown as a card with an animated pixel-art preview. Locked
skins are dimmed and name the achievement that unlocks them. Selecting a
skin calls :meth:`digscript.core.game.Game.select_skin`.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from digscript.ui.floating_panel import FloatingPanel
from digscript.ui.sprites import SpriteBook
from digscript.ui.theme import (
    ACCENT,
    BACKGROUND,
    BUTTON_BORDER,
    DISABLED_TEXT,
    TEXT,
    TEXT_DIM,
)

__all__ = ["WardrobePanel"]

PREVIEW_TILE_PX = 64
PREVIEW_INTERVAL_MS = 180


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class _SkinCard(QFrame):
    """One skin card: animated preview, name, description and lock state."""

    def __init__(self, skin_id: str, panel: WardrobePanel) -> None:
        super().__init__(panel.content_widget)
        self.skin_id = skin_id
        self.panel = panel
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.preview = QLabel(self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(PREVIEW_TILE_PX)
        layout.addWidget(self.preview)

        self.name_label = QLabel(self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        layout.addWidget(self.name_label)

        self.description_label = QLabel(self)
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setStyleSheet(f"color: {TEXT_DIM};")
        layout.addWidget(self.description_label, 1)

        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.refresh()

    def skin(self) -> Any:
        return self.panel.sprite_book.skin(self.skin_id) if self.panel.sprite_book else None

    def is_unlocked(self) -> bool:
        game = self.panel.game
        checker = getattr(game, "is_skin_unlocked", None)
        if callable(checker):
            return bool(checker(self.skin_id))
        return _get(self.skin(), "unlocked_by") is None

    def requirement_text(self) -> str:
        unlocked_by = _get(self.skin(), "unlocked_by")
        if not unlocked_by:
            return ""
        progression = self.panel.progression
        title_getter = getattr(progression, "requirement_title", None)
        title = ""
        if callable(title_getter):
            try:
                title = title_getter("achievement", str(unlocked_by))
            except Exception:
                title = ""
        return str(title or unlocked_by)

    def refresh(self) -> None:
        skin = self.skin()
        if skin is None:
            self.name_label.setText(self.skin_id.replace("_", " ").title())
            self.description_label.setText("")
            self.status_label.setText("Skin data unavailable")
            self.status_label.setStyleSheet(f"color: {DISABLED_TEXT};")
            return
        self.name_label.setText(str(_get(skin, "name", self.skin_id)))
        self.description_label.setText(str(_get(skin, "description", "")))
        unlocked = self.is_unlocked()
        selected = self.panel.game is not None and (
            str(_get(self.panel.game, "selected_skin")) == self.skin_id
        )
        if not unlocked:
            self.status_label.setText(f"Unlocked by: {self.requirement_text()}")
            self.status_label.setStyleSheet(f"color: {DISABLED_TEXT};")
            self.name_label.setStyleSheet(f"color: {DISABLED_TEXT}; font-weight: bold;")
            self.setStyleSheet(
                f"_SkinCard {{ background-color: {BACKGROUND}; "
                f"border: 1px solid {BUTTON_BORDER}; }}"
            )
        elif selected:
            self.status_label.setText("Selected")
            self.status_label.setStyleSheet(f"color: {ACCENT};")
            self.name_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
            self.setStyleSheet(
                f"_SkinCard {{ background-color: {BACKGROUND}; border: 2px solid {ACCENT}; }}"
            )
        else:
            self.status_label.setText("Click to select")
            self.status_label.setStyleSheet(f"color: {TEXT_DIM};")
            self.name_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
            self.setStyleSheet(
                f"_SkinCard {{ background-color: {BACKGROUND}; "
                f"border: 1px solid {BUTTON_BORDER}; }}"
            )
        self._update_preview(unlocked)

    def _update_preview(self, unlocked: bool) -> None:
        book = self.panel.sprite_book
        if book is None:
            return
        pixmap = book.miner_pixmap(
            self.skin_id,
            "down",
            "walk",
            self.panel.preview_frame,
            PREVIEW_TILE_PX,
        )
        if not unlocked:
            dimmed = QPixmap(pixmap.size())
            dimmed.fill(Qt.GlobalColor.transparent)
            painter = QPainter(dimmed)
            try:
                painter.setOpacity(0.35)
                painter.drawPixmap(0, 0, pixmap)
            finally:
                painter.end()
            pixmap = dimmed
        self.preview.setPixmap(pixmap)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        if event.button() == Qt.MouseButton.LeftButton and self.is_unlocked():
            self.panel.select(self.skin_id)
            event.accept()
            return
        super().mousePressEvent(event)


class WardrobePanel(FloatingPanel):
    """Floating panel listing every skin with an animated preview."""

    skin_selected = Signal(str)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Wardrobe"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        content = kwargs.pop("content", None)
        progression = kwargs.pop("progression", None) or kwargs.pop("progression_view", None)
        sprite_book = kwargs.pop("sprite_book", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget) and parent is None:
                parent = arg
            elif hasattr(arg, "config") and hasattr(arg, "skins"):
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
        self.content = content
        self.progression = progression
        self.sprite_book = sprite_book
        if self.sprite_book is None and content is not None:
            self.sprite_book = SpriteBook(content)

        super().__init__(title, parent=parent)
        if not self._restored_geometry:
            self.resize(820, 380)
            self.move(80, 220)

        self.preview_frame = 0
        self.cards: dict[str, _SkinCard] = {}
        self.cards_container = QWidget(self.content_widget)
        self.cards_layout = QHBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.content_layout.addWidget(self.cards_container, 1)
        hint = QLabel(
            "Pick a miner skin. Locked skins unlock through achievements.", self.content_widget
        )
        hint.setStyleSheet(f"color: {TEXT_DIM};")
        self.content_layout.addWidget(hint)
        self._build_cards()
        self.refresh()

        self._timer = QTimer(self)
        self._timer.setInterval(PREVIEW_INTERVAL_MS)
        self._timer.timeout.connect(self._advance_preview)
        self._timer.start()

    # -- cards ---------------------------------------------------------------

    def skins(self) -> list[Any]:
        """Return the skin entries in file order."""
        if self.content is None:
            return []
        getter = getattr(self.content, "skin_list", None)
        if callable(getter):
            return list(getter())
        raw = _get(self.content, "skins")
        if isinstance(raw, dict):
            return list(raw.values())
        if isinstance(raw, (list, tuple)):
            return list(raw)
        return []

    def _build_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self.cards = {}
        for skin in self.skins():
            skin_id = str(_get(skin, "id", ""))
            if not skin_id:
                continue
            card = _SkinCard(skin_id, self)
            self.cards_layout.addWidget(card, 1)
            self.cards[skin_id] = card
        self.cards_layout.addStretch(1)

    def refresh(self) -> None:
        """Refresh every card (selection, lock state and preview)."""
        for card in self.cards.values():
            card.refresh()

    def select(self, skin_id: str) -> None:
        """Select ``skin_id`` through the game and refresh the cards."""
        game = self.game
        if game is None:
            return
        try:
            game.select_skin(skin_id)
        except ValueError:
            return
        self.refresh()
        self.skin_selected.emit(skin_id)

    def set_game(self, game: Any) -> None:
        """Attach a (new) game, content and progression service."""
        self.game = game
        if game is not None:
            self.content = _get(game, "content")
            self.progression = (
                _get(game, "progression_service")
                or _get(game, "progression")
                or _get(game, "progression_view")
            )
            self.sprite_book = SpriteBook(self.content) if self.content is not None else None
        self._build_cards()
        self.refresh()

    # -- animation -----------------------------------------------------------

    def _advance_preview(self) -> None:
        self.preview_frame = 1 - self.preview_frame
        for card in self.cards.values():
            card._update_preview(card.is_unlocked())

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        self.refresh()
        super().showEvent(event)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        if event.key() == Qt.Key.Key_Escape:
            self.hide_panel()
            event.accept()
            return
        super().keyPressEvent(event)
