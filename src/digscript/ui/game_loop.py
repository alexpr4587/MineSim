"""Game loop: converts real elapsed time into engine ticks.

A :class:`QTimer` fires every 16 ms; each frame converts the real
elapsed time into ``tick_hz * speed`` engine steps (at most 200 per
frame). Space toggles pause; keys 1 to 5 set the speed.
"""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer

__all__ = ["FRAME_MS", "GameLoop", "MAX_TICKS_PER_FRAME", "SPEED_KEYS", "SPEEDS"]

FRAME_MS = 16
MAX_TICKS_PER_FRAME = 200
SPEEDS: tuple[int, ...] = (0, 1, 2, 5, 20)
SPEED_KEYS: dict[int, int] = {1: 0, 2: 1, 3: 2, 4: 5, 5: 20}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class GameLoop(QObject):
    """Drives :meth:`engine.step` from a 16 ms QTimer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        game = kwargs.pop("game", None)
        engine = kwargs.pop("engine", None)
        hud = kwargs.pop("hud", None)
        world_view = kwargs.pop("world_view", None)
        tick_hz = kwargs.pop("tick_hz", None)
        parent = kwargs.pop("parent", None)
        for arg in args:
            if arg is None:
                continue
            if hasattr(arg, "money_label") or hasattr(arg, "refresh") and not hasattr(arg, "step"):
                if hud is None:
                    hud = arg
            elif hasattr(arg, "paintEvent") or hasattr(arg, "tile_px"):
                if world_view is None:
                    world_view = arg
            elif hasattr(arg, "step") and hasattr(arg, "tick"):
                if engine is None:
                    engine = arg
            elif game is None:
                game = arg
        super().__init__(parent)
        self.game = game
        if engine is None and game is not None:
            engine = _get(game, "engine")
        self.engine = engine
        self.hud = hud
        self.world_view = world_view
        if tick_hz is None:
            content = _get(game, "content")
            config = _get(content, "config")
            tick_hz = _get(config, "tick_hz", 10)
        self.tick_hz: int = int(tick_hz or 10)
        self.speed: int = 1
        self.paused: bool = False
        self._accumulator: float = 0.0
        self._last_time: float | None = None
        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self._on_timeout)

    # -- control -------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """Return True when the timer is active."""
        return self.timer.isActive()

    def start(self) -> None:
        """Start the 16 ms timer."""
        self._last_time = time.monotonic()
        self.timer.start(FRAME_MS)

    def stop(self) -> None:
        """Stop the timer."""
        self.timer.stop()

    def set_speed(self, speed: int) -> None:
        """Set the speed multiplier (0 pauses)."""
        self.speed = int(speed)
        self.paused = self.speed == 0
        if self.hud is not None:
            hud_speed = _get(self.hud, "speed")
            if hud_speed is not None and int(hud_speed) != self.speed:
                try:
                    self.hud.speed = self.speed
                    self.hud.paused = self.paused
                except Exception:
                    pass

    def set_paused(self, paused: bool) -> None:
        """Pause or resume (resuming restores 1x)."""
        if paused:
            self.set_speed(0)
        elif self.speed == 0:
            self.set_speed(1)
        else:
            self.paused = False

    def toggle_pause(self) -> None:
        """Toggle pause (Space)."""
        self.set_paused(not (self.paused or self.speed == 0))

    def pause(self) -> None:
        """Pause the game."""
        self.set_speed(0)

    def resume(self) -> None:
        """Resume the game at 1x."""
        if self.speed == 0:
            self.set_speed(1)

    def set_speed_index(self, index: int) -> None:
        """Set the speed by index into :data:`SPEEDS`."""
        index = max(0, min(len(SPEEDS) - 1, int(index)))
        self.set_speed(SPEEDS[index])

    # -- speed math --------------------------------------------------------------------

    def ticks_for_elapsed(self, elapsed_seconds: float) -> int:
        """Return engine ticks for ``elapsed_seconds`` of real time.

        ``ticks = elapsed * tick_hz * speed``, capped at 200 per frame
        and zero while paused.
        """
        if self.paused or self.speed == 0:
            return 0
        ticks = int(float(elapsed_seconds) * self.tick_hz * self.speed)
        return max(0, min(MAX_TICKS_PER_FRAME, ticks))

    def compute_ticks(self, elapsed_ms: float) -> int:
        """Return engine ticks for ``elapsed_ms`` milliseconds of real time."""
        return self.ticks_for_elapsed(float(elapsed_ms) / 1000.0)

    def ticks_to_run(self, elapsed_ms: float) -> int:
        """Alias for :meth:`compute_ticks`."""
        return self.compute_ticks(elapsed_ms)

    # -- stepping -------------------------------------------------------------------------

    def _step_engine(self, ticks: int) -> None:
        if self.engine is None or ticks <= 0:
            return
        for _ in range(int(ticks)):
            step = _get(self.engine, "step")
            if callable(step):
                step()

    def advance(self, elapsed_ms: float) -> int:
        """Step the engine for ``elapsed_ms`` of real time.

        Returns the number of ticks stepped. Fractional ticks are
        carried in an accumulator so slow speeds still advance.
        """
        self._accumulator += float(elapsed_ms) / 1000.0 * self.tick_hz * self.speed
        if self.paused or self.speed == 0:
            self._accumulator = 0.0
            return 0
        ticks = min(MAX_TICKS_PER_FRAME, int(self._accumulator))
        self._accumulator -= ticks
        if ticks > 0:
            self._step_engine(ticks)
            self._refresh_ui()
        return ticks

    def step_frame(self, elapsed_ms: float = FRAME_MS) -> int:
        """Alias for :meth:`advance`."""
        return self.advance(elapsed_ms)

    def _refresh_ui(self) -> None:
        if self.hud is not None:
            refresh = _get(self.hud, "refresh")
            if callable(refresh):
                refresh()
            else:
                update = _get(self.hud, "update_display")
                if callable(update):
                    update()
        if self.world_view is not None:
            update = _get(self.world_view, "update")
            if callable(update):
                update()

    def _on_timeout(self) -> None:
        now = time.monotonic()
        if self._last_time is None:
            self._last_time = now
            return
        elapsed_ms = (now - self._last_time) * 1000.0
        self._last_time = now
        self.advance(elapsed_ms)

    # -- keyboard ---------------------------------------------------------------------------

    def handle_key(self, key: Any) -> bool:
        """Handle a key press; return True when consumed.

        Space toggles pause; keys 1 to 5 select Pause/1x/2x/5x/20x.
        """
        if isinstance(key, str):
            if key == " " or key.lower() == "space":
                self.toggle_pause()
                return True
            try:
                number = int(key)
            except ValueError:
                return False
            if number in SPEED_KEYS:
                self.set_speed(SPEED_KEYS[number])
                return True
            return False
        if isinstance(key, int):
            qt_value = int(key)
            if qt_value == int(Qt.Key.Key_Space):
                self.toggle_pause()
                return True
            key_map = {
                int(Qt.Key.Key_1): 0,
                int(Qt.Key.Key_2): 1,
                int(Qt.Key.Key_3): 2,
                int(Qt.Key.Key_4): 5,
                int(Qt.Key.Key_5): 20,
            }
            if qt_value in key_map:
                self.set_speed(key_map[qt_value])
                return True
        return False

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Forward key presses to :meth:`handle_key`."""
        if self.handle_key(event.key()):
            event.accept()
