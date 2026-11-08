"""HUD top bar: money, inventory, tick, position and speed buttons."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from digscript.ui.theme import FONT_FAMILY, HUD_BACKGROUND

__all__ = ["HUD", "SPEEDS", "SPEED_BUTTONS"]

SPEEDS: tuple[int, ...] = (0, 1, 2, 5, 20)
SPEED_BUTTONS: tuple[tuple[str, int], ...] = (
    ("Pause", 0),
    ("1x", 1),
    ("2x", 2),
    ("5x", 5),
    ("20x", 20),
)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class HUD(QWidget):
    """Top bar reading game state through Game getters and EventBus events."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        game = kwargs.pop("game", None)
        game_loop = kwargs.pop("game_loop", None) or kwargs.pop("loop", None)
        parent = kwargs.pop("parent", None)
        for arg in args:
            if arg is None:
                continue
            if hasattr(arg, "set_speed") and hasattr(arg, "toggle_pause"):
                if game_loop is None:
                    game_loop = arg
            elif game is None:
                game = arg
        super().__init__(parent)
        self.game = game
        self.game_loop = game_loop
        self.speed: int = 1
        self.paused: bool = False
        self.setStyleSheet(f"background-color: {HUD_BACKGROUND};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self.money_label = QLabel("Money: 0", self)
        self.inventory_label = QLabel("Inventory: 0/10", self)
        self.tick_label = QLabel("Tick: 0", self)
        self.position_label = QLabel("Pos: (0, 0)", self)
        for label in (
            self.money_label,
            self.inventory_label,
            self.tick_label,
            self.position_label,
        ):
            label.setFont(QFont(FONT_FAMILY))
            layout.addWidget(label)
        layout.addStretch(1)
        self.speed_buttons: dict[int, QPushButton] = {}
        self.buttons: list[QPushButton] = []
        for text, speed in SPEED_BUTTONS:
            button = QPushButton(text, self)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, s=speed: self.set_speed(s))
            layout.addWidget(button)
            self.speed_buttons[speed] = button
            self.buttons.append(button)
        self._subscribe_events()
        self._sync_buttons()
        self.refresh()

    # -- game loop wiring --------------------------------------------------------

    def set_game_loop(self, game_loop: Any) -> None:
        """Attach the game loop that speed buttons control."""
        self.game_loop = game_loop

    def attach(self, game_loop: Any) -> None:
        """Alias for :meth:`set_game_loop`."""
        self.set_game_loop(game_loop)

    def set_game(self, game: Any) -> None:
        """Attach a new game and re-subscribe to its events."""
        self.game = game
        self._subscribe_events()
        self.refresh()

    # -- speed control -------------------------------------------------------------

    def set_speed(self, speed: int) -> None:
        """Set the game speed (0 pauses)."""
        self.speed = int(speed)
        self.paused = self.speed == 0
        if self.game_loop is not None:
            setter = _get(self.game_loop, "set_speed")
            if callable(setter):
                setter(self.speed)
        self._sync_buttons()

    def set_paused(self, paused: bool) -> None:
        """Pause or resume the game."""
        if paused:
            self.set_speed(0)
        elif self.speed == 0:
            self.set_speed(1)
        else:
            self.paused = False
            self._sync_buttons()

    def toggle_pause(self) -> None:
        """Toggle pause."""
        if self.paused or self.speed == 0:
            self.set_speed(1)
        else:
            self.set_speed(0)

    def pause(self) -> None:
        """Pause the game."""
        self.set_speed(0)

    def resume(self) -> None:
        """Resume the game at 1x."""
        if self.speed == 0:
            self.set_speed(1)

    def _sync_buttons(self) -> None:
        for speed, button in self.speed_buttons.items():
            button.setChecked(speed == self.speed)

    # -- display ---------------------------------------------------------------------

    def _subscribe_events(self) -> None:
        if self.game is None:
            return
        bus = _get(self.game, "events") or _get(self.game, "event_bus")
        if bus is None or not hasattr(bus, "subscribe"):
            return
        try:
            from digscript.core.events import MineAttempted, Moved, OreMined, Sold, TickAdvanced

            bus.subscribe(TickAdvanced, lambda _event: self.refresh())
            bus.subscribe(Moved, lambda _event: self.refresh())
            bus.subscribe(OreMined, lambda _event: self.refresh())
            bus.subscribe(MineAttempted, lambda _event: self.refresh())
            bus.subscribe(Sold, lambda _event: self.refresh())
        except Exception:
            pass

    def refresh(self) -> None:
        """Re-read money, inventory, tick and position from the game."""
        game = self.game
        if game is None:
            return
        miner = _get(game, "miner")
        money = _get(miner, "money", 0) or 0
        used = _get(miner, "inventory_size")
        if used is None:
            inventory = _get(miner, "inventory") or {}
            used = sum(inventory.values()) if isinstance(inventory, dict) else 0
        capacity = _get(miner, "capacity", 0) or 0
        tick = _get(game, "tick")
        if tick is None:
            engine = _get(game, "engine")
            tick = _get(engine, "tick", 0) or 0
        position = _get(miner, "position")
        if position is None:
            position = (_get(miner, "x", 0) or 0, _get(miner, "y", 0) or 0)
        self.money_label.setText(f"Money: {int(money)}")
        self.inventory_label.setText(f"Inventory: {int(used)}/{int(capacity)}")
        self.tick_label.setText(f"Tick: {int(tick)}")
        self.position_label.setText(f"Pos: ({int(position[0])}, {int(position[1])})")
        if self.game_loop is not None:
            speed = _get(self.game_loop, "speed")
            if speed is not None and int(speed) != self.speed:
                self.speed = int(speed)
                self.paused = self.speed == 0
                self._sync_buttons()

    def update_display(self) -> None:
        """Alias for :meth:`refresh`."""
        self.refresh()

    def update_hud(self) -> None:
        """Alias for :meth:`refresh`."""
        self.refresh()
