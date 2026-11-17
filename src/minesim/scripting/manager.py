"""Owner of one :class:`ScriptHost` per miner.

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

from minesim.core.events import ApiCalled
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
    """Own and coordinate one script subprocess per miner."""

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
        for miner_id, host in (hosts or {}).items():
            self.adopt_host(host, miner_id=miner_id)

    # -- properties -------------------------------------------------------

    @property
    def hosts(self) -> dict[int, ScriptHost]:
        """The live hosts, keyed by miner id."""
        return self._hosts

    @property
    def running_count(self) -> int:
        """The number of scripts currently running."""
        return sum(1 for host in self._hosts.values() if host.is_running)

    # -- host lifecycle ---------------------------------------------------

    def host(self, miner_id: int = 0) -> ScriptHost | None:
        """Return the host for ``miner_id`` if one was created."""
        return self._hosts.get(int(miner_id))

    def ensure_host(self, miner_id: int = 0) -> ScriptHost:
        """Return the host for ``miner_id``, creating it when needed."""
        miner_id = int(miner_id)
        host = self._hosts.get(miner_id)
        if host is not None:
            return host
        self._require_miner(miner_id)
        host = ScriptHost(
            self.engine,
            self.content,
            self.progression,
            self.scripts_dir,
            miner_id=miner_id,
            manager=self,
        )
        self._hosts[miner_id] = host
        return host

    def adopt_host(self, host: ScriptHost, miner_id: int | None = None) -> ScriptHost:
        """Register an existing host (used by the UI and tests)."""
        if miner_id is None:
            miner_id = int(getattr(host, "miner_id", 0) or 0)
        host.miner_id = int(miner_id)
        host.manager = self
        self._hosts[int(miner_id)] = host
        return host

    def start(self, miner_id: int, filename: str, source: str) -> ScriptHost:
        """Start ``source`` for ``miner_id``, respecting the process limit."""
        miner_id = int(miner_id)
        self._require_miner(miner_id)
        existing = self._hosts.get(miner_id)
        if existing is not None and existing.is_running:
            existing.stop()
        if self.running_count >= self.max_processes:
            raise RuntimeError(f"script process limit reached ({self.max_processes})")
        host = self.ensure_host(miner_id)
        host.start(str(filename), source)
        miner = self.engine.miner_by_id(miner_id)
        miner.script = Path(str(filename)).name
        return host

    def start_script(self, miner_id: int, script_name: str) -> ScriptHost:
        """Read ``scripts_dir/script_name`` and start it on ``miner_id``."""
        name, source = self.resolve_script(script_name)
        return self.start(miner_id, name, source)

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

    def stop(self, miner_id: int) -> bool:
        """Stop the script of ``miner_id``; return True if a host existed."""
        host = self._hosts.get(int(miner_id))
        if host is None:
            return False
        host.stop()
        return True

    def stop_all(self) -> None:
        """Stop every running script."""
        for miner_id in sorted(self._hosts):
            self._hosts[miner_id].stop()

    def discard_host(self, miner_id: int) -> bool:
        """Stop and forget the host of ``miner_id``."""
        host = self._hosts.pop(int(miner_id), None)
        if host is None:
            return False
        host.stop()
        return True

    def assign(self, miner_id: int, script_name: str) -> ScriptHost:
        """Replace the script of ``miner_id`` with ``script_name``."""
        miner_id = int(miner_id)
        self._require_miner(miner_id)
        name, source = self.resolve_script(script_name)
        existing = self._hosts.get(miner_id)
        if existing is not None and existing.is_running:
            existing.stop()
        if self.running_count >= self.max_processes:
            raise RuntimeError(f"script process limit reached ({self.max_processes})")
        self.start(miner_id, name, source)
        return self.ensure_host(miner_id)

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

    def start_spawned(self, miner_id: int, script_name: str) -> ScriptHost:
        """Start the script of a newly spawned miner."""
        return self.start_script(miner_id, script_name)

    # -- pumping and state ------------------------------------------------

    def pump(self) -> list[HostEvent]:
        """Pump every host in miner-id order and return the new events."""
        self._discard_removed_miners()
        events: list[HostEvent] = []
        for miner_id in sorted(self._hosts):
            host = self._hosts.get(miner_id)
            if host is None:
                continue
            try:
                new_events = host.pump()
            except Exception:
                logger.debug("script host pump failed", exc_info=True)
                continue
            for event in new_events or []:
                event.miner_id = int(miner_id)
                events.append(event)
        return events

    def _discard_removed_miners(self) -> None:
        if self.engine is None:
            return
        has_miner = getattr(self.engine, "has_miner", None)
        if not callable(has_miner):
            return
        for miner_id in list(self._hosts):
            try:
                exists = bool(has_miner(miner_id))
            except Exception:
                exists = True
            if not exists:
                self.discard_host(miner_id)

    def states(self) -> dict[int, ScriptState]:
        """Return the script state of every miner."""
        result: dict[int, ScriptState] = {}
        miners = _get(self.engine, "miners") or {}
        for miner_id in sorted(int(key) for key in miners):
            host = self._hosts.get(miner_id)
            result[miner_id] = host.state if host is not None else ScriptState.IDLE
        return result

    def console(self, miner_id: int) -> list[HostEvent]:
        """Return the console lines of ``miner_id``."""
        host = self._hosts.get(int(miner_id))
        return list(host.console_lines) if host is not None else []

    def decorate_miners(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add manager-known state/script data to ``miners()`` entries."""
        states = self.states()
        miners = _get(self.engine, "miners") or {}
        decorated: list[dict[str, Any]] = []
        for entry in entries:
            item = dict(entry)
            miner_id = int(item.get("id", 0) or 0)
            state = states.get(miner_id, ScriptState.IDLE)
            item["state"] = str(state).lower()
            miner = miners.get(miner_id)
            if miner is not None:
                item["script"] = str(getattr(miner, "script", "") or "")
                item["inventory_used"] = int(getattr(miner, "inventory_size", 0) or 0)
            decorated.append(item)
        return decorated

    # -- API events -------------------------------------------------------

    def publish_api_called(self, function: str, miner_id: int = 0) -> None:
        """Publish :class:`ApiCalled` for a successful script API call."""
        bus = (
            _get(self.game, "events")
            or _get(self.game, "event_bus")
            or _get(self.engine, "events")
            or _get(self.engine, "event_bus")
        )
        if bus is None or not hasattr(bus, "publish"):
            return
        bus.publish(ApiCalled(function=str(function), miner_id=int(miner_id)))

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

    def _require_miner(self, miner_id: int) -> Any:
        if self.engine is None:
            raise RuntimeError("no engine attached to script manager")
        try:
            return self.engine.miner_by_id(int(miner_id))
        except Exception:
            raise KeyError(f"unknown miner id {miner_id}") from None
