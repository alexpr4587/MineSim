"""Non-blocking toast notifications for achievement unlocks.

A :class:`ToastManager` subscribes to :class:`~digscript.core.events.AchievementUnlocked`
and shows a short-lived toast in the top-right corner of the main window.
Several toasts are queued and shown one after another (each for 4 s).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from digscript.core.events import AchievementUnlocked
from digscript.ui.theme import BACKGROUND, BUTTON_BORDER, TEXT


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class Toast(QLabel):
    """A single toast: title + message, closes itself after ``duration_ms``."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
        duration_ms: int = 4000,
    ) -> None:
        super().__init__(parent)
        text = f"<b>{title}</b><br/>{message}"
        self.setText(text)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet(
            f"QLabel {{ background-color: {BACKGROUND}; color: {TEXT}; "
            f"border: 1px solid {BUTTON_BORDER}; border-radius: 6px; "
            f"padding: 8px 12px; font-size: 11px; }}"
        )
        self.setMinimumWidth(260)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close)
        self._timer.start(int(duration_ms))
        self.adjustSize()

    def show_at_top_right(self, window: QWidget) -> None:
        """Position the toast near the top-right of ``window`` and show it."""
        margin = 12
        tw = self.width()
        ww = window.width()
        x = max(0, ww - tw - margin)
        y = max(0, 8)
        self.move(x, y)
        self.show()
        self.raise_()


class ToastManager(QObject):
    """Show achievement-unlock toasts, one at a time, in a queue."""

    def __init__(self, window: QWidget, game: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.window = window
        self.game = game
        self._queue: list[tuple[str, str]] = []
        self._current: Toast | None = None
        self._active = True
        self._chain_timer = QTimer(self)
        self._chain_timer.setSingleShot(True)
        self._chain_timer.timeout.connect(self._on_chain)
        self._subscribe()

    # -- subscription ---------------------------------------------------------

    def _bus(self) -> Any:
        return _get(self.game, "events") or _get(self.game, "event_bus")

    def set_game(self, game: Any) -> None:
        """Attach a (new) game and re-subscribe to its event bus."""
        self.game = game
        self._subscribe()

    def _subscribe(self) -> None:
        bus = self._bus()
        if bus is None or not hasattr(bus, "subscribe"):
            return
        try:
            bus.subscribe(AchievementUnlocked, self._on_achievement_unlocked)
        except Exception:
            return

    def _on_achievement_unlocked(self, event: Any) -> None:
        achievement_id = _get(event, "id", "")
        if not achievement_id:
            return
        content = _get(self.game, "content")
        achievement = None
        if content is not None:
            getter = getattr(content, "get_achievement", None)
            if callable(getter):
                try:
                    achievement = getter(str(achievement_id))
                except Exception:
                    achievement = None
        title = str(_get(achievement, "title", achievement_id))
        message = self._reward_message(achievement)
        self._queue.append((title, message))
        self._show_next()

    # -- queue ----------------------------------------------------------------

    def _show_next(self) -> None:
        if not self._active:
            return
        if self._current is not None:
            return
        if not self._queue:
            return
        try:
            window = self.window
        except RuntimeError:
            self._active = False
            return
        title, message = self._queue.pop(0)
        toast = Toast(title, message, window)
        self._current = toast
        self._chain_timer.start(4000)
        toast.show_at_top_right(window)

    def _on_chain(self) -> None:
        self._current = None
        self._show_next()

    # -- rewards --------------------------------------------------------------

    @staticmethod
    def _reward_message(achievement: Any) -> str:
        rewards = _get(achievement, "rewards") or []
        if not rewards:
            return "Achievement unlocked."
        lines: list[str] = []
        for reward in rewards:
            reward_type = _get(reward, "type")
            reward_id = _get(reward, "id")
            amount = _get(reward, "amount")
            if reward_type == "unlock_function" and reward_id:
                lines.append(f"Unlocks: {reward_id}()")
            elif reward_type == "unlock_ore" and reward_id:
                lines.append(f"Unlocks ore: {reward_id}")
            elif reward_type == "unlock_upgrade" and reward_id:
                lines.append(f"Unlocks upgrade: {reward_id}")
            elif reward_type == "unlock_module" and reward_id:
                lines.append(f"Unlocks module: {reward_id}")
            elif reward_type == "money" and amount is not None:
                lines.append(f"+{amount} money")
        return "; ".join(lines) if lines else "Achievement unlocked."


__all__ = ["Toast", "ToastManager"]
