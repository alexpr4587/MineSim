"""Miners panel (key T): fleet rows, selection, assignment and spawning.

Each row shows one miner with its badge colour, script state, active
script, position and inventory load. Selecting a row highlights the
miner in the world view and switches the console to it. Spawning and
killing go through the same engine commands as player scripts, so the
fleet rules (slots, price and process limit) stay in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from minesim.core.commands import RemoveMiner, SpawnMiner
from minesim.core.events import (
    MinerRemoved,
    MinerSpawned,
    Moved,
    OreMined,
    ScriptFailed,
    ScriptFinished,
    ScriptStarted,
    Sold,
    Unloaded,
)
from minesim.ui.editor_panel import default_scripts_dir
from minesim.ui.floating_panel import FloatingPanel
from minesim.ui.lock_overlay import LockOverlay
from minesim.ui.theme import (
    ACCENT,
    BUTTON_BORDER,
    DISABLED_TEXT,
    ERROR,
    TEXT,
    TEXT_DIM,
    miner_badge_color,
)

__all__ = ["MinersPanel", "MinerRow", "miner_state_label"]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def miner_state_label(state: Any) -> str:
    """Map a script state to the panel's Running/Idle/Failed label."""
    text = str(state or "").upper()
    if "RUNNING" in text:
        return "Running"
    if "FAIL" in text or "ERROR" in text:
        return "Failed"
    return "Idle"


def _populate_scripts(combo: QComboBox, scripts: list[str]) -> None:
    """Fill ``combo`` with ``scripts`` while preserving the current choice."""
    current = combo.currentText()
    existing = [combo.itemText(index) for index in range(combo.count())]
    if existing == scripts:
        return
    combo.blockSignals(True)
    combo.clear()
    combo.addItems(scripts)
    index = combo.findText(current)
    if index >= 0:
        combo.setCurrentIndex(index)
    combo.blockSignals(False)


class MinerRow(QFrame):
    """One fleet row: badge, state, script, position, inventory and actions."""

    def __init__(self, miner_id: int, panel: MinersPanel) -> None:
        super().__init__(panel.rows_container)
        self.miner_id = int(miner_id)
        self.panel = panel
        self.setObjectName(f"miner_row_{self.miner_id}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"QFrame {{ border: 1px solid {BUTTON_BORDER}; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        top = QHBoxLayout()
        self.badge = QLabel(self)
        self.badge.setObjectName(f"miner_badge_{self.miner_id}")
        self.badge.setFixedSize(16, 16)
        self.id_label = QLabel(f"Miner {self.miner_id}", self)
        self.id_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        self.state_label = QLabel("Idle", self)
        self.state_label.setObjectName(f"miner_state_{self.miner_id}")
        self.select_button = QPushButton("Select", self)
        self.select_button.setObjectName(f"miner_select_{self.miner_id}")
        self.kill_button = QPushButton("Kill", self)
        self.kill_button.setObjectName(f"miner_kill_{self.miner_id}")
        self.kill_button.setEnabled(self.miner_id != 0)
        self.select_button.clicked.connect(lambda: self.panel.select_miner(self.miner_id))
        self.kill_button.clicked.connect(lambda: self.panel.kill_miner(self.miner_id))
        top.addWidget(self.badge)
        top.addWidget(self.id_label)
        top.addWidget(self.state_label)
        top.addStretch(1)
        top.addWidget(self.select_button)
        top.addWidget(self.kill_button)
        layout.addLayout(top)

        info = QHBoxLayout()
        self.script_label = QLabel("Script: —", self)
        self.script_label.setObjectName(f"miner_script_{self.miner_id}")
        self.position_label = QLabel("Pos: (0, 0)", self)
        self.layer_label = QLabel("Layer: 0", self)
        self.layer_label.setObjectName(f"miner_layer_{self.miner_id}")
        self.inventory_label = QLabel("0/10", self)
        for label in (self.script_label, self.inventory_label, self.layer_label):
            label.setStyleSheet(f"color: {TEXT_DIM};")
        info.addWidget(self.script_label, 1)
        info.addWidget(self.position_label)
        info.addWidget(self.layer_label)
        info.addWidget(self.inventory_label)
        layout.addLayout(info)

        assign = QHBoxLayout()
        assign_label = QLabel("Assign:", self)
        assign_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.assign_combo = QComboBox(self)
        self.assign_combo.setObjectName(f"miner_assign_combo_{self.miner_id}")
        self.assign_button = QPushButton("Assign", self)
        self.assign_button.setObjectName(f"miner_assign_{self.miner_id}")
        self.assign_button.clicked.connect(
            lambda: self.panel.assign_miner(self.miner_id, self.assign_combo.currentText())
        )
        assign.addWidget(assign_label)
        assign.addWidget(self.assign_combo, 1)
        assign.addWidget(self.assign_button)
        layout.addLayout(assign)

    def set_scripts(self, scripts: list[str]) -> None:
        """Refresh the assign dropdown options."""
        _populate_scripts(self.assign_combo, scripts)

    def set_selected(self, selected: bool) -> None:
        """Dim or accent the row border when it becomes (de)selected."""
        color = ACCENT if selected else BUTTON_BORDER
        width = 2 if selected else 1
        self.setStyleSheet(f"QFrame {{ border: {width}px solid {color}; }}")

    def refresh(self, miner: Any, state: Any, scripts: list[str]) -> None:
        """Update every field from the miner and its script state."""
        label = miner_state_label(state)
        self.state_label.setText(label)
        if label == "Running":
            color = ACCENT
        elif label == "Failed":
            color = ERROR
        else:
            color = TEXT_DIM
        self.state_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        script = str(_get(miner, "script", "") or "")
        self.script_label.setText(f"Script: {script or '—'}")
        script_tip = script or "No script assigned"
        self.script_label.setToolTip(script_tip)
        position = (
            int(_get(miner, "x", 0) or 0),
            int(_get(miner, "y", 0) or 0),
        )
        self.position_label.setText(f"Pos: ({position[0]}, {position[1]})")
        layer = int(_get(miner, "layer", 0) or 0)
        self.layer_label.setText(f"Layer: {layer}")
        self.layer_label.setToolTip(self.panel.layer_name(layer))
        used = int(_get(miner, "inventory_size", 0) or 0)
        capacity = int(_get(miner, "capacity", 0) or 0)
        self.inventory_label.setText(f"{used}/{capacity}")
        self.inventory_label.setToolTip("Inventory used / capacity")
        color = miner_badge_color(self.miner_id)
        self.badge.setStyleSheet(
            f"background-color: {color}; border: 1px solid {TEXT}; border-radius: 8px;"
        )
        self.badge.setToolTip(f"Badge colour of Miner {self.miner_id}")
        self.set_scripts(scripts)
        self.set_selected(self.miner_id == self.panel.selected_miner)


class MinersPanel(FloatingPanel):
    """Fleet panel: one row per miner plus spawning controls."""

    miner_selected = Signal(int)
    selection_changed = Signal(int)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Miners"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        manager = kwargs.pop("manager", None) or kwargs.pop("script_manager", None)
        scripts_dir = kwargs.pop("scripts_dir", None) or kwargs.pop("script_dir", None)
        world_view = kwargs.pop("world_view", None)
        console_panel = kwargs.pop("console_panel", None) or kwargs.pop("console", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget):
                if parent is None:
                    parent = arg
            elif hasattr(arg, "ensure_host") and hasattr(arg, "pump"):
                if manager is None:
                    manager = arg
            elif hasattr(arg, "engine") and hasattr(arg, "miner"):
                if game is None:
                    game = arg
            elif isinstance(arg, (str, Path)):
                if scripts_dir is None:
                    scripts_dir = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        self.game = game
        self.engine = _get(game, "engine") or game
        self.game_content = _get(game, "content") or _get(self.engine, "content")
        self.progression = (
            _get(game, "progression_service")
            or _get(game, "progression")
            or _get(game, "progression_view")
            or _get(self.engine, "progression_view")
        )
        self.manager = manager
        if manager is not None and getattr(manager, "scripts_dir", None) is not None:
            scripts_dir = manager.scripts_dir
        if scripts_dir is None:
            scripts_dir = _get(game, "scripts_dir") or default_scripts_dir()
        self.scripts_dir = Path(scripts_dir)
        self.world_view = world_view
        self.console_panel = console_panel
        self.selected_miner: int = 0
        self.rows: dict[int, MinerRow] = {}
        self.status_text: str = ""

        super().__init__(title, parent=parent)
        self.setWindowTitle(str(title))
        if not self._restored_geometry:
            self.resize(470, 430)
            self.move(40, 120)
        self.setMinimumSize(360, 260)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)

        controls = QHBoxLayout()
        self.spawn_script_selector = QComboBox(self.content_widget)
        self.spawn_script_selector.setObjectName("miner_spawn_script")
        self.spawn_script_selector.setToolTip("Script for the next spawned miner")
        self.spawn_button = QPushButton("Spawn", self.content_widget)
        self.spawn_button.setObjectName("miner_spawn_button")
        self.spawn_button.clicked.connect(lambda: self.spawn_miner())
        self.follow_checkbox = QCheckBox("Follow selected", self.content_widget)
        self.follow_checkbox.setObjectName("follow_selected_checkbox")
        self.follow_checkbox.setChecked(bool(_get(self.world_view, "follow_selected", True)))
        self.follow_checkbox.toggled.connect(self.set_follow_selected)
        controls.addWidget(self.spawn_script_selector, 1)
        controls.addWidget(self.spawn_button)
        controls.addWidget(self.follow_checkbox)
        body.addLayout(controls)

        self.spawn_info = QLabel("", self.content_widget)
        self.spawn_info.setObjectName("miner_spawn_info")
        self.spawn_info.setStyleSheet(f"color: {TEXT_DIM};")
        body.addWidget(self.spawn_info)

        self.status_label = QLabel("", self.content_widget)
        self.status_label.setObjectName("miner_status")
        self.status_label.setStyleSheet(f"color: {DISABLED_TEXT};")
        self.status_label.setWordWrap(True)
        body.addWidget(self.status_label)

        self.scroll = QScrollArea(self.content_widget)
        self.scroll.setObjectName("miner_rows_scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rows_container = QWidget(self.scroll)
        self.rows_container.setObjectName("miner_rows")
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(2, 2, 2, 2)
        self.rows_layout.setSpacing(4)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.rows_container)
        body.addWidget(self.scroll, 1)

        self.content_layout.addLayout(body)
        self.lock_overlay = LockOverlay(self.content_widget, "miners", self.feature_title("miners"))
        self._subscribe_events()
        self.refresh()

    # -- data helpers ----------------------------------------------------------

    def _miners(self) -> dict[int, Any]:
        miners = _get(self.engine, "miners") or {}
        return miners if isinstance(miners, dict) else {}

    def _scripts(self) -> list[str]:
        try:
            files = sorted(self.scripts_dir.glob("*.py"), key=lambda path: path.name.lower())
        except Exception:
            return []
        files.sort(key=lambda path: (0 if path.name == "main.py" else 1, path.name.lower()))
        return [path.name for path in files]

    def layer_name(self, layer: int) -> str:
        """Return the display name of ``layer`` from the content."""
        getter = _get(self.game_content, "get_layer")
        if callable(getter):
            try:
                return str(_get(getter(int(layer)), "name", f"Layer {layer}"))
            except Exception:
                pass
        layers = _get(self.game_content, "layers", None)
        if isinstance(layers, dict):
            return str(_get(layers.get(int(layer)), "name", f"Layer {layer}"))
        return f"Layer {layer}"

    def _states(self) -> dict[int, Any]:
        manager = self.manager
        if manager is not None and hasattr(manager, "states"):
            try:
                return dict(manager.states())
            except Exception:
                return {}
        return {}

    def _money(self) -> int:
        player = _get(self.game, "player_stats") or _get(self.engine, "player_stats")
        return int(_get(player, "money", 0) or 0)

    def is_feature_unlocked(self, feature_id: str) -> bool:
        """Return True when the feature is unlocked."""
        checker = getattr(self.progression, "is_feature_unlocked", None)
        if callable(checker):
            try:
                return bool(checker(str(feature_id)))
            except Exception:
                pass
        return True

    def feature_title(self, feature_id: str) -> str:
        """Return the achievement title that unlocks ``feature_id``."""
        getter = getattr(self.progression, "requirement_title", None)
        if callable(getter):
            try:
                return str(getter("feature", str(feature_id)))
            except Exception:
                pass
        features = _get(self.game_content, "features", {}) or {}
        feature = features.get(str(feature_id)) if isinstance(features, dict) else None
        return str(_get(feature, "name", feature_id))

    def next_miner_cost(self) -> int | None:
        """Return the price of the next miner, or None when no slot remains."""
        miners = self._miners()
        config = _get(self.game_content, "config")
        costs = list(_get(config, "miner_costs", []) or [])
        extra = max(0, len(miners) - 1)
        if extra >= len(costs):
            return None
        return int(costs[extra])

    def free_slots(self) -> int:
        """Return how many miners may still be spawned."""
        max_miners = int(_get(self.engine, "max_miners", 1) or 1)
        return max(0, max_miners - len(self._miners()))

    def _refresh_spawn_controls(self) -> None:
        scripts = self._scripts()
        _populate_scripts(self.spawn_script_selector, scripts)
        free = self.free_slots()
        cost = self.next_miner_cost()
        total = len(self._miners())
        max_miners = int(_get(self.engine, "max_miners", 1) or 1)
        if free <= 0:
            self.spawn_info.setText(f"Free slots: 0 · fleet full ({total}/{max_miners})")
        elif cost is None:
            self.spawn_info.setText(f"Free slots: {free} · no more miner prices")
        else:
            self.spawn_info.setText(
                f"Free slots: {free} · next miner: {cost} money (have {self._money()})"
            )
        if cost is None:
            self.spawn_button.setText("Spawn")
        else:
            self.spawn_button.setText(f"Spawn ({cost})")
        enabled = free > 0 and cost is not None and self._money() >= cost and bool(scripts)
        if enabled and self.manager is not None:
            try:
                enabled = self.manager.spawn_error(self.spawn_script_selector.currentText()) is None
            except Exception:
                enabled = False
        self.spawn_button.setEnabled(enabled)
        if not scripts:
            self.spawn_button.setToolTip("Add a .py script to the scripts folder first")
        elif free <= 0:
            self.spawn_button.setToolTip("Buy a Miner Bay upgrade for another slot")
        elif cost is not None and self._money() < cost:
            self.spawn_button.setToolTip("Not enough money for the next miner")
        else:
            self.spawn_button.setToolTip("Spawn a miner with the selected script")

    # -- refresh ---------------------------------------------------------------

    def refresh(self) -> None:
        """Rebuild rows for the current fleet and update spawn controls."""
        miners = self._miners()
        states = self._states()
        scripts = self._scripts()
        for miner_id in sorted(int(key) for key in miners):
            row = self.rows.get(miner_id)
            if row is None:
                row = MinerRow(miner_id, self)
                self.rows[miner_id] = row
                self.rows_layout.addWidget(row)
            row.refresh(miners[miner_id], states.get(miner_id), scripts)
        for miner_id in list(self.rows):
            if miner_id in miners:
                continue
            row = self.rows.pop(miner_id)
            self.rows_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        if self.selected_miner not in miners:
            self.selected_miner = 0 if 0 in miners else (min(miners) if miners else 0)
        for miner_id, row in self.rows.items():
            row.set_selected(miner_id == self.selected_miner)
        self._refresh_spawn_controls()
        self.lock_overlay.set_locked(
            not self.is_feature_unlocked("miners"), self.feature_title("miners")
        )

    # -- selection -------------------------------------------------------------

    def select_miner(self, miner_id: int) -> None:
        """Select a miner in the panel, world view and console."""
        miner_id = int(miner_id)
        if miner_id not in self._miners():
            return
        changed = miner_id != self.selected_miner
        self.selected_miner = miner_id
        for row_id, row in self.rows.items():
            row.set_selected(row_id == miner_id)
        if self.world_view is not None:
            try:
                self.world_view.select_miner(miner_id)
            except Exception:
                pass
        if self.console_panel is not None:
            try:
                self.console_panel.set_miner(miner_id)
            except Exception:
                pass
        if changed:
            self.miner_selected.emit(miner_id)
            self.selection_changed.emit(miner_id)

    def set_follow_selected(self, enabled: bool) -> None:
        """Apply the Follow selected toggle to the world view."""
        enabled = bool(enabled)
        if self.follow_checkbox.isChecked() != enabled:
            self.follow_checkbox.blockSignals(True)
            self.follow_checkbox.setChecked(enabled)
            self.follow_checkbox.blockSignals(False)
        if self.world_view is not None:
            try:
                self.world_view.set_follow_selected(enabled)
            except Exception:
                pass

    def _sync_follow_checkbox(self, enabled: bool) -> None:
        if self.follow_checkbox.isChecked() == bool(enabled):
            return
        self.follow_checkbox.blockSignals(True)
        self.follow_checkbox.setChecked(bool(enabled))
        self.follow_checkbox.blockSignals(False)

    # -- fleet actions ---------------------------------------------------------

    def kill_miner(self, miner_id: int) -> bool:
        """Kill ``miner_id`` (never miner 0) and drop its script host."""
        miner_id = int(miner_id)
        if miner_id == 0:
            return False
        if self.manager is not None:
            try:
                self.manager.discard_host(miner_id)
            except Exception:
                pass
        result = RemoveMiner(miner_id).execute(self.engine)
        if not result.get("ok"):
            self.status_text = str(result.get("reason", "kill failed"))
            self.status_label.setText(f"Kill failed: {self.status_text}")
            self.refresh()
            return False
        self.status_text = f"Miner {miner_id} killed"
        self.status_label.setText(self.status_text)
        self.refresh()
        if self.selected_miner not in self._miners():
            miners = self._miners()
            self.select_miner(0 if 0 in miners else (min(miners) if miners else 0))
        return True

    def assign_miner(self, miner_id: int, script_name: str) -> bool:
        """Assign ``script_name`` to ``miner_id`` and start it."""
        miner_id = int(miner_id)
        name = Path(str(script_name or "")).name
        if not name or miner_id not in self._miners():
            return False
        try:
            if self.manager is not None:
                self.manager.assign(miner_id, name)
            else:
                miner = self.engine.miner_by_id(miner_id)
                miner.script = name
        except Exception as exc:
            self.status_text = f"assign failed: {exc}"
            self.status_label.setText(self.status_text)
            self.refresh()
            return False
        self.status_text = f"Miner {miner_id} runs {name}"
        self.status_label.setText(self.status_text)
        self.refresh()
        return True

    def spawn_miner(self, script_name: str | None = None) -> dict[str, Any]:
        """Spawn a miner with ``script_name`` and start it."""
        name = script_name or self.spawn_script_selector.currentText()
        name = Path(str(name or "")).name
        if not name:
            return {"ok": False, "reason": "no_script"}
        if self.free_slots() <= 0:
            return {"ok": False, "reason": "no_slot"}
        if self.manager is not None:
            error = None
            try:
                error = self.manager.spawn_error(name)
            except Exception:
                error = {"ok": False, "reason": "process_limit"}
            if error is not None:
                self.status_text = str(error.get("reason", "spawn failed"))
                self.status_label.setText(f"Spawn failed: {self.status_text}")
                self._refresh_spawn_controls()
                return error
        result = SpawnMiner().execute(self.engine)
        if not result.get("ok"):
            self.status_text = str(result.get("reason", "spawn failed"))
            self.status_label.setText(f"Spawn failed: {self.status_text}")
            self._refresh_spawn_controls()
            return result
        miner_id = int(result["miner_id"])
        if self.manager is not None:
            try:
                self.manager.start_spawned(miner_id, name)
            except Exception as exc:
                self.engine.remove_miner(miner_id)
                error = {"ok": False, "reason": "process_limit", "error": str(exc)}
                self.status_text = f"spawn failed: {exc}"
                self.status_label.setText(self.status_text)
                self._refresh_spawn_controls()
                return error
        else:
            self.engine.miner_by_id(miner_id).script = name
        self.status_text = f"Miner {miner_id} spawned on {name}"
        self.status_label.setText(self.status_text)
        self.refresh()
        return result

    # -- binding and events ----------------------------------------------------

    def _subscribe_events(self) -> None:
        bus = _get(self.game, "events") or _get(self.game, "event_bus")
        if bus is None or not hasattr(bus, "subscribe"):
            return
        try:
            for event_type in (
                MinerSpawned,
                MinerRemoved,
                ScriptStarted,
                ScriptFinished,
                ScriptFailed,
                Moved,
                OreMined,
                Sold,
                Unloaded,
            ):
                bus.subscribe(event_type, lambda _event: self.refresh())
        except Exception:
            pass
        if self.world_view is not None and hasattr(self.world_view, "follow_selected_changed"):
            try:
                self.world_view.follow_selected_changed.connect(self._sync_follow_checkbox)
            except Exception:
                pass

    def set_game(self, game: Any) -> None:
        """Attach a new game, dropping the rows of the old fleet."""
        self.game = game
        self.engine = _get(game, "engine") or game
        self.game_content = _get(game, "content") or _get(self.engine, "content")
        for row in self.rows.values():
            self.rows_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self.rows.clear()
        self.selected_miner = 0
        self.status_text = ""
        self.status_label.setText("")
        self._subscribe_events()
        self.refresh()

    def set_manager(self, manager: Any) -> None:
        """Attach a ScriptManager and use its scripts folder."""
        self.manager = manager
        if manager is not None and getattr(manager, "scripts_dir", None) is not None:
            self.scripts_dir = Path(manager.scripts_dir)
        self.refresh()

    def set_world_view(self, world_view: Any) -> None:
        """Attach the world view whose selection this panel drives."""
        self.world_view = world_view
        if world_view is not None and hasattr(world_view, "follow_selected_changed"):
            try:
                world_view.follow_selected_changed.connect(self._sync_follow_checkbox)
            except Exception:
                pass

    def set_console_panel(self, console_panel: Any) -> None:
        """Attach the console that follows the selection."""
        self.console_panel = console_panel
