"""Owner of one :class:`ScriptHost` per drone.

The game process never executes player code. ``ScriptManager`` starts,
pumps and stops the subprocess hosts, validates the shared JSON store
and provides a deterministic lockstep driver for headless use.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from minesim.scripting.host import HostEvent, ScriptHost, ScriptState

__all__ = ["ScriptManager"]

logger = logging.getLogger(__name__)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class ScriptManager:
    """Own and coordinate one script subprocess per drone."""

    def __init__(
        self,
        game: Any,
        scripts_dir: Any = None,
        *,
        max_processes: int | None = None,
        hosts: dict[int, ScriptHost] | None = None,
    ) -> None:
        self.game = game
        self.engine = _get(game, "engine") or game
        self.content = _get(game, "content") or _get(self.engine, "content")
        self.progression = (
            _get(game, "progression_service")
            or _get(game, "progression")
            or _get(game, "progression_view")
            or _get(self.engine, "progression_view")
        )
        directory = (
            scripts_dir
            or _get(game, "scripts_dir")
            or _get(game, "scripts_directory")
            or Path("scripts")
        )
        self.scripts_dir = Path(directory)
        config = _get(self.content, "config")
        configured = _get(config, "max_script_processes", 8)
        self.max_processes = max(1, int(max_processes or configured or 8))
        self._hosts: dict[int, ScriptHost] = {}
        for drone_id, host in (hosts or {}).items():
            self.adopt_host(host, drone_id=drone_id)

    # -- properties -------------------------------------------------------

    @property
    def hosts(self) -> dict[int, ScriptHost]:
        """The live hosts, keyed by drone id."""
        return self._hosts

    @property
    def running_count(self) -> int:
        """The number of scripts currently running."""
        return sum(1 for host in self._hosts.values() if host.is_running)

    # -- host lifecycle ---------------------------------------------------

    def host(self, drone_id: int = 0) -> ScriptHost | None:
        """Return the host for ``drone_id`` if one was created."""
        return self._hosts.get(int(drone_id))

    def ensure_host(self, drone_id: int = 0) -> ScriptHost:
        """Return the host for ``drone_id``, creating it when needed."""
        drone_id = int(drone_id)
        host = self._hosts.get(drone_id)
        if host is not None:
            return host
        self._require_drone(drone_id)
        host = ScriptHost(
            self.engine,
            self.content,
            self.progression,
            self.scripts_dir,
            drone_id=drone_id,
            manager=self,
        )
        self._hosts[drone_id] = host
        return host

    def adopt_host(self, host: ScriptHost, drone_id: int | None = None) -> ScriptHost:
        """Register an existing host (used by the UI and tests)."""
        if drone_id is None:
            drone_id = int(getattr(host, "drone_id", 0) or 0)
        host.drone_id = int(drone_id)
        host.manager = self
        self._hosts[int(drone_id)] = host
        return host

    def start(self, drone_id: int, filename: str, source: str) -> ScriptHost:
        """Start ``source`` for ``drone_id``, respecting the process limit."""
        drone_id = int(drone_id)
        self._require_drone(drone_id)
        existing = self._hosts.get(drone_id)
        if existing is not None and existing.is_running:
            existing.stop()
        if self.running_count >= self.max_processes:
            raise RuntimeError(f"script process limit reached ({self.max_processes})")
        host = self.ensure_host(drone_id)
        host.start(str(filename), source)
        drone = self.engine.drone(drone_id)
        drone.script = Path(str(filename)).name
        return host

    def start_script(self, drone_id: int, script_name: str) -> ScriptHost:
        """Read ``scripts_dir/script_name`` and start it on ``drone_id``."""
        name, source = self.resolve_script(script_name)
        return self.start(drone_id, name, source)

    def resolve_script(self, script_name: Any) -> tuple[str, str]:
        """Return ``(file name, source)`` for a script in ``scripts_dir``."""
        raw = str(script_name or "").strip()
        if not raw:
            raise ValueError("script_name must not be empty")
        name = Path(raw).name
        if not name.endswith(".py"):
            raise ValueError("script_name must name a .py file")
        path = self.scripts_dir / name
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            raise FileNotFoundError(
                f"script {name!r} was not found in {self.scripts_dir}"
            ) from None
        return name, source

    def stop(self, drone_id: int) -> bool:
        """Stop the script of ``drone_id``; return True if a host existed."""
        host = self._hosts.get(int(drone_id))
        if host is None:
            return False
        host.stop()
        return True

    def stop_all(self) -> None:
        """Stop every running script."""
        for drone_id in sorted(self._hosts):
            self._hosts[drone_id].stop()

    def discard_host(self, drone_id: int) -> bool:
        """Stop and forget the host of ``drone_id``."""
        host = self._hosts.pop(int(drone_id), None)
        if host is None:
            return False
        host.stop()
        return True

    def assign(self, drone_id: int, script_name: str) -> ScriptHost:
        """Replace the script of ``drone_id`` with ``script_name``."""
        drone_id = int(drone_id)
        self._require_drone(drone_id)
        name, source = self.resolve_script(script_name)
        existing = self._hosts.get(drone_id)
        if existing is not None and existing.is_running:
            existing.stop()
        if self.running_count >= self.max_processes:
            raise RuntimeError(f"script process limit reached ({self.max_processes})")
        self.start(drone_id, name, source)
        return self.ensure_host(drone_id)

    # -- spawning support -------------------------------------------------

    def spawn_error(self, script_name: Any) -> dict[str, Any] | None:
        """Return a spawn error dict, or None when a spawn may proceed."""
        try:
            self.resolve_script(script_name)
        except (FileNotFoundError, ValueError):
            return {"ok": False, "reason": "unknown_script"}
        if self.running_count >= self.max_processes:
            return {"ok": False, "reason": "process_limit"}
        return None

    def start_spawned(self, drone_id: int, script_name: str) -> ScriptHost:
        """Start the script of a newly spawned drone."""
        return self.start_script(drone_id, script_name)

    # -- pumping and state ------------------------------------------------

    def pump(self) -> list[HostEvent]:
        """Pump every host in drone-id order and return the new events."""
        self._discard_removed_drones()
        events: list[HostEvent] = []
        for drone_id in sorted(self._hosts):
            host = self._hosts.get(drone_id)
            if host is None:
                continue
            try:
                new_events = host.pump()
            except Exception:
                logger.debug("script host pump failed", exc_info=True)
                continue
            for event in new_events or []:
                event.drone_id = int(drone_id)
                events.append(event)
        return events

    def _discard_removed_drones(self) -> None:
        if self.engine is None:
            return
        has_drone = getattr(self.engine, "has_drone", None)
        if not callable(has_drone):
            return
        for drone_id in list(self._hosts):
            try:
                exists = bool(has_drone(drone_id))
            except Exception:
                exists = True
            if not exists:
                self.discard_host(drone_id)

    def states(self) -> dict[int, ScriptState]:
        """Return the script state of every drone."""
        result: dict[int, ScriptState] = {}
        drones = _get(self.engine, "drones") or {}
        for drone_id in sorted(int(key) for key in drones):
            host = self._hosts.get(drone_id)
            result[drone_id] = host.state if host is not None else ScriptState.IDLE
        return result

    def console(self, drone_id: int) -> list[HostEvent]:
        """Return the console lines of ``drone_id``."""
        host = self._hosts.get(int(drone_id))
        return list(host.console_lines) if host is not None else []

    def decorate_drones(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add manager-known state/script data to ``drones()`` entries."""
        states = self.states()
        drones = _get(self.engine, "drones") or {}
        decorated: list[dict[str, Any]] = []
        for entry in entries:
            item = dict(entry)
            drone_id = int(item.get("id", 0) or 0)
            state = states.get(drone_id, ScriptState.IDLE)
            item["state"] = str(state).lower()
            drone = drones.get(drone_id)
            if drone is not None:
                item["script"] = str(getattr(drone, "script", "") or "")
                item["inventory_used"] = int(getattr(drone, "inventory_size", 0) or 0)
            decorated.append(item)
        return decorated

    # -- shared memory ----------------------------------------------------

    def _shared_store(self) -> dict[str, Any]:
        if self.engine is None:
            raise RuntimeError("no engine attached to script manager")
        store = getattr(self.engine, "shared_memory", None)
        if not isinstance(store, dict):
            store = {}
            self.engine.shared_memory = store
        return store

    def _shared_limits(self) -> tuple[int, int, int]:
        config = _get(self.content, "config")
        return (
            int(_get(config, "shared_max_keys", 64) or 64),
            int(_get(config, "shared_key_max_chars", 40) or 40),
            int(_get(config, "shared_value_max_bytes", 4096) or 4096),
        )

    def _check_key(self, key: Any) -> str:
        _max_keys, max_chars, _max_bytes = self._shared_limits()
        if not isinstance(key, str):
            raise TypeError("shared key must be a string")
        if not key:
            raise ValueError("shared key must not be empty")
        if len(key) > max_chars:
            raise ValueError(f"shared key is too long ({len(key)} characters, max {max_chars})")
        return key

    def shared_get(self, key: Any, default: Any = None) -> Any:
        """Return the JSON value stored under ``key`` or ``default``."""
        key = self._check_key(key)
        store = self._shared_store()
        if key not in store:
            return default
        return json.loads(json.dumps(store[key]))

    def shared_set(self, key: Any, value: Any) -> None:
        """Store a JSON ``value`` under ``key`` in the shared store."""
        key = self._check_key(key)
        max_keys, _max_chars, max_bytes = self._shared_limits()
        store = self._shared_store()
        if key not in store and len(store) >= max_keys:
            raise ValueError(f"shared memory already has {max_keys} keys")
        try:
            encoded = json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"shared value is not JSON serialisable: {exc}") from None
        size = len(encoded.encode("utf-8"))
        if size > max_bytes:
            raise ValueError(f"shared value is too large ({size} bytes, max {max_bytes})")
        store[key] = json.loads(encoded)

    # -- headless lockstep ------------------------------------------------

    def run_lockstep(self, max_ticks: int = 1000) -> int:
        """Advance the engine deterministically while scripts cooperate.

        The engine only steps when every running script is blocked on a
        game reply (or finished), so two identical runs give identical
        engine state.
        """
        if self.engine is None:
            return 0
        max_ticks = max(0, int(max_ticks))
        start_tick = int(_get(self.engine, "tick", 0) or 0)
        while int(_get(self.engine, "tick", 0) or 0) - start_tick < max_ticks:
            self.pump()
            running = [host for host in self._hosts.values() if host.is_running]
            if running:
                if all(host.is_blocked for host in running):
                    self.engine.step()
                else:
                    time.sleep(0.001)
                continue
            if bool(_get(self.engine, "is_idle", True)):
                break
            self.engine.step()
        return int(_get(self.engine, "tick", 0) or 0) - start_tick

    # -- game rebinding ---------------------------------------------------

    def set_game(self, game: Any) -> None:
        """Rebind the manager to ``game`` after loading or starting a game."""
        self.stop_all()
        self._hosts.clear()
        self.game = game
        self.engine = _get(game, "engine") or game
        self.content = _get(game, "content") or _get(self.engine, "content")
        self.progression = (
            _get(game, "progression_service")
            or _get(game, "progression")
            or _get(game, "progression_view")
            or _get(self.engine, "progression_view")
        )
        config = _get(self.content, "config")
        configured = _get(config, "max_script_processes", self.max_processes)
        self.max_processes = max(1, int(configured or self.max_processes))

    # -- helpers ----------------------------------------------------------

    def _require_drone(self, drone_id: int) -> Any:
        if self.engine is None:
            raise RuntimeError("no engine attached to script manager")
        try:
            return self.engine.drone(int(drone_id))
        except Exception:
            raise KeyError(f"unknown drone id {drone_id}") from None
