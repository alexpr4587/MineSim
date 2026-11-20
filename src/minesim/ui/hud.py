"""HUD top bar: money, inventory, tick, position, layer and speed buttons."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from minesim.ui.theme import (
    ACCENT,
    ERROR,
    FONT_FAMILY,
    HUD_BACKGROUND,
    HUD_SELECTED_BACKGROUND,
    HUD_SELECTED_TEXT,
    TEXT,
    TEXT_DIM,
    temperature_color,
)

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
        world_view = kwargs.pop("world_view", None)
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
        self.world_view = world_view
        self.speed: int = 1
        self.paused: bool = False
        self.setObjectName("hud")
        self.setStyleSheet(
            "QWidget#hud {"
            f" background-color: {HUD_BACKGROUND};"
            " }"
            " QPushButton:checked {"
            f" background-color: {HUD_SELECTED_BACKGROUND};"
            f" color: {HUD_SELECTED_TEXT};"
            f" border: 2px solid {TEXT};"
            " font-weight: bold;"
            " }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        self.money_label = QLabel("Money: 0", self)
        self.inventory_label = QLabel("Inventory: 0/10", self)
        self.energy_label = QLabel("Energy: 0/0", self)
        self.energy_label.setObjectName("hud_energy_label")
        self.energy_bar = QProgressBar(self)
        self.energy_bar.setObjectName("hud_energy_bar")
        self.energy_bar.setTextVisible(False)
        self.energy_bar.setFixedWidth(80)
        self.energy_bar.setFixedHeight(10)
        self.temperature_label = QLabel("Temp: 0/100", self)
        self.temperature_label.setObjectName("hud_temperature_label")
        self.temperature_bar = QProgressBar(self)
        self.temperature_bar.setObjectName("hud_temperature_bar")
        self.temperature_bar.setTextVisible(False)
        self.temperature_bar.setFixedWidth(80)
        self.temperature_bar.setFixedHeight(10)
        self.temperature_bar.setRange(0, 100)
        self.airflow_label = QLabel("Air 4 / load 0", self)
        self.airflow_label.setObjectName("hud_airflow_label")
        self.warehouse_label = QLabel("Warehouse: 0/100", self)
        self.miners_label = QLabel("Miners: 1/0", self)
        self.miners_label.setToolTip("Miners alive / free slots")
        self.tick_label = QLabel("Tick: 0", self)
        self.position_label = QLabel("Pos: (0, 0)", self)
        self.layer_label = QLabel("Layer: Surface (0)", self)
        self.layer_label.setObjectName("hud_layer")
        self.events_label = QLabel("", self)
        self.events_label.setStyleSheet(f"color: {TEXT_DIM};")
        for label in (
            self.money_label,
            self.inventory_label,
            self.energy_label,
            self.temperature_label,
            self.airflow_label,
            self.warehouse_label,
            self.miners_label,
            self.tick_label,
            self.position_label,
            self.layer_label,
            self.events_label,
        ):
            label.setFont(QFont(FONT_FAMILY))
            layout.addWidget(label)
            if label is self.energy_label:
                layout.addWidget(self.energy_bar)
            elif label is self.temperature_label:
                layout.addWidget(self.temperature_bar)
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
        if self.world_view is not None:
            self._watch_world_view()
        self.refresh()

    # -- game loop wiring --------------------------------------------------------

    def set_game_loop(self, game_loop: Any) -> None:
        """Attach the game loop that speed buttons control."""
        self.game_loop = game_loop

    def attach(self, game_loop: Any) -> None:
        """Alias for :meth:`set_game_loop`."""
        self.set_game_loop(game_loop)

    def set_world_view(self, world_view: Any) -> None:
        """Attach the world view whose viewed layer the HUD reports."""
        self.world_view = world_view
        self._watch_world_view()
        self.refresh()

    def _watch_world_view(self) -> None:
        view = self.world_view
        signal = getattr(view, "viewed_layer_changed", None)
        if signal is None:
            return
        try:
            signal.connect(lambda _layer: self.refresh())
        except Exception:
            pass

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
            from minesim.core.events import (
                Charged,
                ContractDelivered,
                EnergySpent,
                MineAttempted,
                MinerOverheated,
                MinerRecovered,
                MinerRemoved,
                MinerSpawned,
                Moved,
                OreMined,
                RefineFinished,
                Sold,
                StockSold,
                TickAdvanced,
                Unloaded,
                WorldEventEnded,
                WorldEventStarted,
            )

            bus.subscribe(TickAdvanced, lambda _event: self.refresh())
            bus.subscribe(MinerSpawned, lambda _event: self.refresh())
            bus.subscribe(MinerRemoved, lambda _event: self.refresh())
            bus.subscribe(WorldEventStarted, lambda _event: self.refresh())
            bus.subscribe(WorldEventEnded, lambda _event: self.refresh())
            bus.subscribe(Moved, lambda _event: self.refresh())
            bus.subscribe(OreMined, lambda _event: self.refresh())
            bus.subscribe(MineAttempted, lambda _event: self.refresh())
            bus.subscribe(Sold, lambda _event: self.refresh())
            bus.subscribe(StockSold, lambda _event: self.refresh())
            bus.subscribe(Unloaded, lambda _event: self.refresh())
            bus.subscribe(RefineFinished, lambda _event: self.refresh())
            bus.subscribe(ContractDelivered, lambda _event: self.refresh())
            bus.subscribe(EnergySpent, lambda _event: self.refresh())
            bus.subscribe(Charged, lambda _event: self.refresh())
            bus.subscribe(MinerOverheated, lambda _event: self.refresh())
            bus.subscribe(MinerRecovered, lambda _event: self.refresh())
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
        engine = _get(game, "engine")
        miners = _get(game, "miners")
        if not isinstance(miners, dict):
            miners = _get(engine, "miners")
        miner_count = len(miners) if isinstance(miners, dict) else 1
        max_miners = int(_get(engine, "max_miners", 1) or 1)
        free_slots = max(0, max_miners - miner_count)
        warehouse = _get(engine, "warehouse") or _get(game, "warehouse")
        warehouse_used = _get(warehouse, "used", None)
        if warehouse_used is None:
            warehouse_used = _get(warehouse, "total", None)
        if warehouse_used is None:
            warehouse_used = 0
        warehouse_capacity = _get(warehouse, "capacity", 0) or 0
        energy = int(_get(miner, "energy", 0) or 0)
        battery_capacity = int(_get(miner, "battery_capacity", 0) or 0)
        self.money_label.setText(f"Money: {int(money)}")
        self.inventory_label.setText(f"Inventory: {int(used)}/{int(capacity)}")
        self.energy_label.setText(f"Energy: {energy}/{battery_capacity}")
        self.energy_bar.setRange(0, max(1, battery_capacity))
        self.energy_bar.setValue(max(0, min(energy, max(1, battery_capacity))))
        bar_color = ERROR if battery_capacity and energy * 4 < battery_capacity else ACCENT
        self.energy_bar.setStyleSheet(
            "QProgressBar { border: 1px solid "
            f"{TEXT_DIM}; border-radius: 3px; background: transparent; }}"
            f" QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 2px; }}"
        )
        climate = self._climate_state(engine, miner)
        temperature = float(_get(miner, "temperature", 0.0) or 0.0)
        overheated = int(_get(miner, "cooldown_remaining", 0) or 0) > 0
        config = _get(_get(game, "content"), "config")
        heat_limit = int(_get(config, "overheat_at", 100) or 100)
        self.temperature_bar.setRange(0, max(1, heat_limit))
        self.temperature_bar.setValue(max(0, min(int(temperature), max(1, heat_limit))))
        self.temperature_label.setText(f"Temp: {int(round(temperature))}/{heat_limit}")
        temp_color = ERROR if overheated else temperature_color(temperature)
        self.temperature_label.setStyleSheet(
            f"color: {temp_color};" + (" font-weight: bold;" if overheated else "")
        )
        self.temperature_bar.setStyleSheet(
            "QProgressBar { border: 1px solid "
            f"{TEXT_DIM}; border-radius: 3px; background: transparent; }}"
            f" QProgressBar::chunk {{ background-color: {temp_color}; border-radius: 2px; }}"
        )
        airflow = int(climate.get("airflow", 0) or 0)
        load = int(climate.get("miners_in_hot_layers", 0) or 0)
        overload = float(climate.get("overload", 0.0) or 0.0)
        self.airflow_label.setText(f"Air {airflow} / load {load}")
        self.airflow_label.setStyleSheet(
            f"color: {ERROR}; font-weight: bold;" if overload > 0 else f"color: {TEXT_DIM};"
        )
        self.airflow_label.setToolTip("Miners in hot layers / airflow. Overload raises heat gain.")
        self.warehouse_label.setText(f"Warehouse: {int(warehouse_used)}/{int(warehouse_capacity)}")
        self.miners_label.setText(f"Miners: {int(miner_count)}/{free_slots}")
        self.tick_label.setText(f"Tick: {int(tick)}")
        self.position_label.setText(f"Pos: ({int(position[0])}, {int(position[1])})")
        self.layer_label.setText(self._layer_text(miner))
        self.events_label.setText(self._event_ticker(int(tick)))
        if self.game_loop is not None:
            speed = _get(self.game_loop, "speed")
            if speed is not None and int(speed) != self.speed:
                self.speed = int(speed)
                self.paused = self.speed == 0
                self._sync_buttons()

    def _climate_state(self, engine: Any, miner: Any) -> dict[str, Any]:
        getter = _get(engine, "climate_state")
        if callable(getter):
            try:
                state = getter(miner)
                if isinstance(state, dict):
                    return state
            except Exception:
                pass
        return {
            "layer": int(_get(miner, "layer", 0) or 0),
            "heat": 0,
            "airflow": 0,
            "miners_in_hot_layers": 0,
            "overload": 0.0,
        }

    def _layer_text(self, miner: Any) -> str:
        layer = _get(self.world_view, "viewed_layer")
        if layer is None:
            layer = _get(miner, "layer", 0) or 0
        layer = int(layer)
        name = None
        content = _get(self.game, "content")
        getter = _get(content, "get_layer")
        if callable(getter):
            try:
                name = _get(getter(layer), "name")
            except Exception:
                name = None
        if name is None:
            layers = _get(content, "layers", None)
            if isinstance(layers, dict):
                name = _get(layers.get(layer), "name")
        return f"Layer: {name or f'Layer {layer}'} ({layer})"

    def _event_ticker(self, tick: int) -> str:
        """Return a compact ticker of every active world event."""
        engine = _get(self.game, "engine")
        events = _get(engine, "world_events")
        if events is None or not hasattr(events, "active_at"):
            return "Events: none"
        content = _get(self.game, "content")
        config = _get(content, "config")
        tick_hz = max(1, int(_get(config, "tick_hz", 10) or 10))
        parts: list[str] = []
        for event in events.active_at(tick):
            kind = str(_get(event, "kind", ""))
            seconds = int(round(max(0, int(_get(event, "ends", tick) or tick) - tick) / tick_hz))
            if kind == "rich_vein":
                parts.append(f"◆ rich vein {seconds}s")
            elif kind == "slow_zone":
                parts.append(f"▤ slow zone {seconds}s")
            elif kind == "market_news":
                item = str(_get(event, "item", "") or "item")
                shortage = float(_get(event, "factor", 1.0) or 1.0) > 1.0
                arrow = "▲" if shortage else "▼"
                direction = "shortage" if shortage else "glut"
                parts.append(f"{arrow} {item} {direction} {seconds}s")
        return "Events: " + (" | ".join(parts) if parts else "none")

    def update_display(self) -> None:
        """Alias for :meth:`refresh`."""
        self.refresh()

    def update_hud(self) -> None:
        """Alias for :meth:`refresh`."""
        self.refresh()
