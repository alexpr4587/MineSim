"""Parent-side host for player scripts.

The game process never executes player code. This module starts the
child process (via ``minesim.runner.main.run``), speaks JSON over a
``multiprocessing`` pipe (``send_bytes``/``recv_bytes``; nothing from
the child is ever unpickled), submits engine commands on behalf of
player API calls and replies when the corresponding ticket is done.

``pump()`` is non-blocking and must be called repeatedly by the game
loop (which also steps the engine). Wall-clock time is used only by
the watchdog in this module.
"""

from __future__ import annotations

import ast
import json
import logging
import multiprocessing
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from minesim.core.commands import (
    Biome,
    BuyUpgrade,
    Distance,
    Inspect,
    Inventory,
    Mine,
    Move,
    OreInfo,
    Peek,
    Position,
    Scan,
    Sell,
    Stats,
    SubmitEstimate,
    Tick,
    Wait,
)
from minesim.core.direction import Direction
from minesim.core.events import ScriptFailed, ScriptFinished, ScriptStarted

__all__ = [
    "ConsoleLine",
    "HostEvent",
    "HostState",
    "NotUnlockedError",
    "ScriptHost",
    "ScriptState",
]

logger = logging.getLogger(__name__)


def analyze_features(source: str, filename: str = "<script>") -> frozenset[str]:
    """Return the script features of ``source`` using :func:`ast.parse`.

    The source is parsed, never executed. Unknown/invalid syntax yields
    an empty feature set. Features: ``defines_function``,
    ``uses_import``, ``uses_comprehension``, ``uses_class``,
    ``uses_try``, ``uses_recursion``, ``uses_lambda`` and
    ``uses_generator``.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except (SyntaxError, ValueError):
        return frozenset()
    features: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            features.add("defines_function")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            features.add("uses_import")
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            features.add("uses_comprehension")
        elif isinstance(node, ast.ClassDef):
            features.add("uses_class")
        elif isinstance(node, (ast.Try, ast.TryStar)):
            features.add("uses_try")
        elif isinstance(node, ast.Lambda):
            features.add("uses_lambda")
        elif isinstance(node, (ast.Yield, ast.YieldFrom)):
            features.add("uses_generator")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == node.name
            ):
                features.add("uses_recursion")
                break
    return frozenset(features)


class NotUnlockedError(Exception):
    """Raised in the parent when a locked function is called.

    Player scripts see this type raised inside the child process;
    the host raises the same-named class only for its own checks.
    """


class ScriptState(StrEnum):
    """Lifecycle states of a player script."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


HostState = ScriptState


@dataclass(slots=True)
class HostEvent:
    """One console/event line produced by a player script.

    ``kind`` is ``"out"``, ``"err"`` or ``"info"``.
    """

    kind: str = "out"
    text: str = ""
    message: str = ""
    error_type: str = ""
    line_number: int | None = None

    def __post_init__(self) -> None:
        if self.message and not self.text:
            self.text = self.message
        if self.text and not self.message:
            self.message = self.text

    @property
    def type(self) -> str:  # noqa: A003 - alias kept for convenience
        """Alias for :attr:`kind`."""
        return self.kind

    @property
    def stream(self) -> str:
        """Alias for :attr:`kind`."""
        return self.kind

    @property
    def line(self) -> str:
        """Alias for :attr:`text` (the console line)."""
        return self.text

    @property
    def lineno(self) -> int | None:
        """Alias for :attr:`line_number`."""
        return self.line_number

    @property
    def content(self) -> str:
        """Alias for :attr:`text`."""
        return self.text

    def __str__(self) -> str:
        return self.text


ConsoleLine = HostEvent

_ACHIEVEMENT_TITLES: dict[str, str] = {
    "hello_miner": "Hello, Miner",
    "wanderer": "Wanderer",
    "scout": "Scout",
    "data_driven": "Data Driven",
    "custom_function": "Your Own Function",
    "first_dig": "First Dig",
    "coal_miner": "Coal Miner",
    "copper_age": "Copper Age",
    "iron_will": "Iron Will",
    "silver_lining": "Silver Lining",
    "gold_rush": "Gold Rush",
    "first_sale": "First Sale",
    "pocket_change": "Pocket Change",
    "investor": "Investor",
    "tycoon": "Tycoon",
}

_DEFAULT_FUNCTIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "move",
        "signature": "move(direction)",
        "doc": "Move one tile.",
        "category": "movement",
        "unlocked_by": None,
    },
    {
        "name": "mine",
        "signature": "mine()",
        "doc": "Mine the current tile.",
        "category": "mining",
        "unlocked_by": None,
    },
    {
        "name": "peek",
        "signature": "peek()",
        "doc": "Look at the current tile.",
        "category": "mining",
        "unlocked_by": None,
    },
    {
        "name": "position",
        "signature": "position()",
        "doc": "Return (x, y).",
        "category": "movement",
        "unlocked_by": None,
    },
    {
        "name": "sell",
        "signature": "sell()",
        "doc": "Sell the inventory.",
        "category": "business",
        "unlocked_by": "first_dig",
    },
    {
        "name": "inventory",
        "signature": "inventory()",
        "doc": "Return the inventory.",
        "category": "business",
        "unlocked_by": "hello_miner",
    },
    {
        "name": "scan",
        "signature": "scan(radius)",
        "doc": "Scan for ore.",
        "category": "mining",
        "unlocked_by": "scout",
    },
    {
        "name": "stats",
        "signature": "stats()",
        "doc": "Return mining stats.",
        "category": "mining",
        "unlocked_by": "data_driven",
    },
    {
        "name": "buy_upgrade",
        "signature": "buy_upgrade(upgrade_id)",
        "doc": "Buy an upgrade level.",
        "category": "business",
        "unlocked_by": "first_sale",
    },
    {
        "name": "wait",
        "signature": "wait(ticks)",
        "doc": "Wait for ticks.",
        "category": "timing",
        "unlocked_by": None,
    },
    {
        "name": "tick",
        "signature": "tick()",
        "doc": "Return the current game tick.",
        "category": "timing",
        "unlocked_by": None,
    },
    {
        "name": "distance",
        "signature": "distance()",
        "doc": "Return the distance from the base.",
        "category": "movement",
        "unlocked_by": None,
    },
    {
        "name": "biome",
        "signature": "biome()",
        "doc": "Return the current biome id.",
        "category": "world",
        "unlocked_by": None,
    },
    {
        "name": "ore_info",
        "signature": "ore_info(ore_id)",
        "doc": "Return public ore information.",
        "category": "mining",
        "unlocked_by": None,
    },
    {
        "name": "inspect",
        "signature": "inspect()",
        "doc": "Describe the current tile.",
        "category": "mining",
        "unlocked_by": None,
    },
    {
        "name": "submit_estimate",
        "signature": "submit_estimate(ore_id, p)",
        "doc": "Submit a mining probability estimate.",
        "category": "data",
        "unlocked_by": None,
    },
)

_DEFAULT_MODULES: tuple[dict[str, Any], ...] = (
    {"name": "math", "unlocked_by": None},
    {"name": "random", "unlocked_by": "wanderer"},
    {"name": "statistics", "unlocked_by": "data_driven"},
    {"name": "collections", "unlocked_by": "custom_function"},
    {"name": "heapq", "unlocked_by": "custom_function"},
)


def _spec_entries(
    content: Any, attr: str, defaults: tuple[dict[str, Any], ...]
) -> list[dict[str, Any]]:
    """Extract spec dicts named ``attr`` from ``content``."""
    raw = getattr(content, attr, None) if content is not None else None
    items: list[Any] = []
    if isinstance(raw, dict):
        items = list(raw.values())
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    entries: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            entries.append(dict(item))
        elif hasattr(item, "name"):
            entry: dict[str, Any] = {"name": item.name}
            for key in ("signature", "doc", "category", "unlocked_by", "cost", "example"):
                if hasattr(item, key):
                    entry[key] = getattr(item, key)
            entries.append(entry)
    return entries if entries else [dict(item) for item in defaults]


def _config_value(content: Any, name: str, default: Any) -> Any:
    config = getattr(content, "config", None) if content is not None else None
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def _event_bus(engine: Any, override: Any = None) -> Any:
    if override is not None:
        return override
    for attr in ("events", "event_bus", "bus"):
        bus = getattr(engine, attr, None)
        if bus is not None:
            return bus
    try:
        from minesim.core.events import EventBus

        return EventBus()
    except Exception:
        return None


@dataclass(slots=True)
class _Pending:
    """A player API request waiting for its engine ticket."""

    request_id: Any
    name: str
    command: Any
    ticket: Any
    wait_ticket: Any = None


class ScriptHost:
    """Runs one player script in a subprocess, driving the engine."""

    def __init__(
        self,
        engine: Any = None,
        content: Any = None,
        progression_view: Any = None,
        scripts_dir: Any = None,
        **kwargs: Any,
    ) -> None:
        if engine is None:
            engine = kwargs.get("game_engine") or kwargs.get("game")
        if progression_view is None:
            progression_view = (
                kwargs.get("progression")
                or kwargs.get("progression_view")
                or kwargs.get("view")
                or kwargs.get("progression_service")
            )
        if scripts_dir is None:
            scripts_dir = (
                kwargs.get("scripts_dir")
                or kwargs.get("script_dir")
                or kwargs.get("scripts")
                or kwargs.get("directory")
            )
        if scripts_dir is None:
            scripts_dir = Path("scripts")
        self.engine = engine
        self.content = content
        self.progression_view = progression_view
        self.progression = progression_view
        self.scripts_dir = Path(scripts_dir)
        self._bus = _event_bus(
            engine, kwargs.get("events") or kwargs.get("event_bus") or kwargs.get("bus")
        )
        self._state: ScriptState = ScriptState.IDLE
        self._process: Any = None
        self._conn: Any = None
        self._pending: _Pending | None = None
        self._last_activity: float = 0.0
        self._zero_streak: int = 0
        self._console: deque[HostEvent] = deque()
        self.filename: str = ""
        self.source: str = ""
        self.defines_function: bool = False
        self.features: frozenset[str] = frozenset()
        self.last_error: dict[str, Any] | None = None
        self._functions: list[dict[str, Any]] = _spec_entries(
            content, "functions", _DEFAULT_FUNCTIONS
        )
        self._modules: list[dict[str, Any]] = _spec_entries(content, "modules", _DEFAULT_MODULES)
        self._spec_map: dict[str, dict[str, Any]] = {
            str(entry.get("name")): entry for entry in self._functions
        }
        self._saw_eof: bool = False
        self._cached_free_limit: int | None = None
        self._cached_idle_timeout: float | None = None
        self._cached_max_lines: int | None = None
        self._watchdog_lock = threading.Lock()
        self._run_id: int = 0
        self._watchdog_thread: threading.Thread | None = None

    # -- properties -------------------------------------------------------

    @property
    def state(self) -> ScriptState:
        """The current lifecycle state."""
        return self._state

    @property
    def status(self) -> ScriptState:
        """Alias for :attr:`state`."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Return True while a script is running."""
        return self._state is ScriptState.RUNNING

    @property
    def process(self) -> Any:
        """The child process, if any."""
        return self._process

    @property
    def proc(self) -> Any:
        """Alias for :attr:`process`."""
        return self._process

    @property
    def console_lines(self) -> list[HostEvent]:
        """Console lines so far (capped by ``console_max_lines``)."""
        return list(self._console)

    @property
    def console(self) -> list[HostEvent]:
        """Alias for :attr:`console_lines`."""
        return list(self._console)

    @property
    def output(self) -> list[str]:
        """Console line texts."""
        return [event.text for event in self._console]

    @property
    def error(self) -> dict[str, Any] | None:
        """Alias for :attr:`last_error`."""
        return self.last_error

    def _max_lines(self) -> int:
        if self._cached_max_lines is None:
            self._cached_max_lines = int(
                _config_value(self.content, "console_max_lines", 500) or 500
            )
        return self._cached_max_lines

    def _idle_timeout(self) -> float:
        if self._cached_idle_timeout is None:
            self._cached_idle_timeout = float(
                _config_value(self.content, "script_idle_timeout_s", 5) or 5
            )
        return self._cached_idle_timeout

    def _free_limit(self) -> int:
        if self._cached_free_limit is None:
            self._cached_free_limit = int(
                _config_value(self.content, "free_calls_before_forced_tick", 200) or 0
            )
        return self._cached_free_limit

    def _publish(self, event: Any) -> None:
        bus = self._bus
        if bus is None and self.engine is not None:
            bus = _event_bus(self.engine)
            self._bus = bus
        if bus is not None and hasattr(bus, "publish"):
            try:
                bus.publish(event)
            except Exception:
                logger.debug("event subscriber raised", exc_info=True)

    def _add_console(self, event: HostEvent, out: list[HostEvent] | None = None) -> None:
        self._console.append(event)
        limit = self._max_lines()
        while len(self._console) > max(0, limit):
            self._console.popleft()
        if out is not None:
            out.append(event)

    # -- unlock helpers ---------------------------------------------------

    def _requirement_title(self, kind: str, unlocked_by: str, name: str) -> str:
        view = self.progression_view
        for attr in ("requirement_title", "achievement_title", "title_for", "requirement"):
            method = getattr(view, attr, None) if view is not None else None
            if not callable(method):
                continue
            for args in ((kind, unlocked_by), (unlocked_by,), (kind, name), (name,)):
                try:
                    value = method(*args)
                except Exception:
                    continue
                if value:
                    return str(value)
        content = self.content
        achievements = getattr(content, "achievements", None) if content is not None else None
        if isinstance(achievements, dict):
            entry = achievements.get(unlocked_by)
            title = getattr(entry, "title", None) if entry is not None else None
            if title:
                return str(title)
            if isinstance(entry, dict) and entry.get("title"):
                return str(entry["title"])
        if unlocked_by in _ACHIEVEMENT_TITLES:
            return _ACHIEVEMENT_TITLES[unlocked_by]
        return unlocked_by.replace("_", " ").title()

    def _is_unlocked(self, kind: str, name: str, unlocked_by: Any) -> bool:
        if unlocked_by is None:
            return True
        view = self.progression_view
        if view is None:
            return True
        method_name = "is_function_unlocked" if kind == "function" else "is_module_unlocked"
        method = getattr(view, method_name, None)
        if callable(method):
            try:
                return bool(method(name))
            except Exception:
                pass
        for attr in (f"unlocked_{kind}s", f"unlocked_{kind}_ids", "unlocked"):
            value = getattr(view, attr, None)
            if isinstance(value, (set, list, tuple, dict)):
                return name in value or unlocked_by in value
        return False

    def _locked_message(self, kind: str, name: str, unlocked_by: Any) -> str:
        title = self._requirement_title(kind, str(unlocked_by), name)
        if kind == "function":
            return f"{name}() is locked. Unlock it with the achievement '{title}' ({unlocked_by})."
        return (
            f"module '{name}' is locked. Unlock it with the achievement '{title}' ({unlocked_by})."
        )

    # -- lifecycle --------------------------------------------------------

    def start(self, filename: str, source: str) -> None:
        """Start running ``source`` (named ``filename``) in a subprocess."""
        if self._state is ScriptState.RUNNING:
            self.stop()
        elif self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            self._process = None
        self.filename = str(filename)
        self.source = source
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        try:
            from minesim.scripting.stubs import write_stubs

            write_stubs(self.scripts_dir, self.content)
        except Exception:
            logger.debug("could not write minesim_api.pyi", exc_info=True)
        self.features = analyze_features(source, str(filename))
        self.defines_function = "defines_function" in self.features
        self._functions = _spec_entries(self.content, "functions", _DEFAULT_FUNCTIONS)
        self._modules = _spec_entries(self.content, "modules", _DEFAULT_MODULES)
        self._spec_map = {str(entry.get("name")): entry for entry in self._functions}
        self._saw_eof = False
        self._cached_free_limit = None
        self._cached_idle_timeout = None
        self._cached_max_lines = None
        allowed_modules: list[str] = []
        locked_modules: dict[str, str] = {}
        for entry in self._modules:
            name = str(entry.get("name") or "")
            if not name:
                continue
            unlocked_by = entry.get("unlocked_by")
            if self._is_unlocked("module", name, unlocked_by):
                allowed_modules.append(name)
            elif unlocked_by:
                locked_modules[name] = self._locked_message("module", name, unlocked_by)
            else:
                locked_modules[name] = f"module '{name}' is locked"
        spec: dict[str, Any] = {
            "functions": [dict(entry) for entry in self._functions],
            "modules": [dict(entry) for entry in self._modules],
            "locked_modules": locked_modules,
        }
        from minesim.runner.main import run as _runner_run

        ctx = multiprocessing.get_context("spawn")
        parent_conn, child_conn = ctx.Pipe(duplex=True)
        process = ctx.Process(
            target=_runner_run,
            args=(child_conn, source, self.filename, spec, allowed_modules, str(self.scripts_dir)),
            daemon=True,
        )
        process.start()
        try:
            child_conn.close()
        except Exception:
            pass
        self._conn = parent_conn
        self._process = process
        self._pending = None
        self._zero_streak = 0
        self._console.clear()
        self.last_error = None
        self._state = ScriptState.RUNNING
        self._last_activity = time.monotonic()
        self._run_id += 1
        self._publish(ScriptStarted(defines_function=self.defines_function, features=self.features))

    def stop(self) -> None:
        """Terminate the child process (always works) and mark STOPPED."""
        process = self._process
        if process is not None:
            try:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
                    if process.is_alive():
                        kill = getattr(process, "kill", None)
                        if callable(kill):
                            kill()
                        process.join(timeout=2)
                else:
                    try:
                        process.join(timeout=0)
                    except Exception:
                        pass
            except Exception:
                logger.debug("error terminating script process", exc_info=True)
        conn = self._conn
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        self._conn = None
        self._pending = None
        if self._state is ScriptState.RUNNING or process is not None:
            self._state = ScriptState.STOPPED
        elif self._state is ScriptState.IDLE:
            self._state = ScriptState.STOPPED

    # -- pipe helpers -----------------------------------------------------

    def _send(self, message: dict[str, Any]) -> bool:
        conn = self._conn
        if conn is None:
            return False
        try:
            data = json.dumps(message).encode("utf-8")
            send_bytes = getattr(conn, "send_bytes", None)
            if callable(send_bytes):
                send_bytes(data)
            else:
                conn.send(data)
            return True
        except (BrokenPipeError, OSError, EOFError, ValueError):
            return False

    def _reply(
        self, request_id: Any, result: Any = None, error: dict[str, Any] | None = None
    ) -> None:
        message: dict[str, Any] = {"kind": "reply", "id": request_id, "result": result}
        if error is not None:
            message["error"] = error
            message["result"] = None
        self._send(message)
        self._last_activity = time.monotonic()

    def _reply_error(self, request_id: Any, error_type: str, message: str) -> None:
        self._reply(request_id, error={"type": error_type, "message": message})

    # -- request translation ----------------------------------------------

    def _build_command(self, name: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        """Translate a player API call into an engine command."""
        if name == "move":
            direction = args[0] if args else kwargs.get("direction")
            if direction is None:
                raise TypeError("move() missing required argument 'direction'")
            if isinstance(direction, str):
                parsed = Direction.parse(direction)
            else:
                parsed = direction
            return Move(parsed)
        if name == "mine":
            if args or kwargs:
                raise TypeError("mine() takes no arguments")
            return Mine()
        if name == "peek":
            if args or kwargs:
                raise TypeError("peek() takes no arguments")
            return Peek()
        if name == "position":
            if args or kwargs:
                raise TypeError("position() takes no arguments")
            return Position()
        if name == "inventory":
            if args or kwargs:
                raise TypeError("inventory() takes no arguments")
            return Inventory()
        if name == "stats":
            if args or kwargs:
                raise TypeError("stats() takes no arguments")
            return Stats()
        if name == "sell":
            if args or kwargs:
                raise TypeError("sell() takes no arguments")
            return Sell()
        if name == "scan":
            radius = args[0] if args else kwargs.get("radius")
            if radius is None:
                raise TypeError("scan() missing required argument 'radius'")
            return Scan(int(radius))
        if name == "buy_upgrade":
            upgrade_id = args[0] if args else (kwargs.get("upgrade_id") or kwargs.get("id"))
            if upgrade_id is None:
                raise TypeError("buy_upgrade() missing required argument 'upgrade_id'")
            return BuyUpgrade(str(upgrade_id))
        if name == "wait":
            ticks = args[0] if args else kwargs.get("ticks")
            if ticks is None:
                raise TypeError("wait() missing required argument 'ticks'")
            ticks_int = int(ticks)
            if ticks_int < 1 or ticks_int > 600:
                raise ValueError("wait() ticks must be between 1 and 600")
            return Wait(ticks_int)
        if name == "tick":
            if args or kwargs:
                raise TypeError("tick() takes no arguments")
            return Tick()
        if name == "distance":
            if args or kwargs:
                raise TypeError("distance() takes no arguments")
            return Distance()
        if name == "biome":
            if args or kwargs:
                raise TypeError("biome() takes no arguments")
            return Biome()
        if name == "ore_info":
            ore_id = args[0] if args else (kwargs.get("ore_id") or kwargs.get("id"))
            if ore_id is None:
                raise TypeError("ore_info() missing required argument 'ore_id'")
            return OreInfo(str(ore_id))
        if name == "inspect":
            if args or kwargs:
                raise TypeError("inspect() takes no arguments")
            return Inspect()
        if name == "submit_estimate":
            ore_id = args[0] if args else (kwargs.get("ore_id") or kwargs.get("id"))
            p = args[1] if len(args) > 1 else kwargs.get("p")
            if ore_id is None:
                raise TypeError("submit_estimate() missing required argument 'ore_id'")
            if p is None:
                raise TypeError("submit_estimate() missing required argument 'p'")
            return SubmitEstimate(str(ore_id), float(p))
        raise NameError(f"unknown function '{name}'")

    def _extract_result(self, name: str, result: Any) -> Any:
        """Extract the player-facing value from an engine result dict."""
        if not isinstance(result, dict):
            return result
        if name == "move":
            return None
        if name == "mine":
            if result.get("ok"):
                return {"ok": True, "ore": result.get("ore") or result.get("ore_id")}
            cleaned: dict[str, Any] = {"ok": False}
            if result.get("reason"):
                cleaned["reason"] = result["reason"]
            if result.get("ore") or result.get("ore_id"):
                cleaned["ore"] = result.get("ore") or result.get("ore_id")
            return cleaned
        if name == "peek":
            return result.get("ore", result.get("ore_id"))
        if name == "position":
            pos = result.get("position") or [result.get("x", 0), result.get("y", 0)]
            return list(pos)
        if name == "inventory":
            return dict(result.get("inventory") or result.get("items") or {})
        if name == "scan":
            return [list(item) for item in (result.get("tiles") or result.get("results") or [])]
        if name == "stats":
            attempts = result.get("attempts") or {}
            successes = result.get("successes") or {}
            stats = result.get("stats")
            if isinstance(stats, dict):
                per_ore = {
                    ore: {
                        "attempts": int(value.get("attempts", 0)) if isinstance(value, dict) else 0,
                        "successes": int(value.get("successes", 0))
                        if isinstance(value, dict)
                        else 0,
                    }
                    for ore, value in stats.items()
                    if isinstance(value, dict) and ("attempts" in value or "successes" in value)
                }
                if per_ore:
                    return per_ore
            return {
                ore: {
                    "attempts": int(attempts.get(ore, 0)),
                    "successes": int(successes.get(ore, 0)),
                }
                for ore in sorted(set(attempts) | set(successes))
            }
        if name == "sell":
            return int(result.get("money", result.get("earned", 0)) or 0) if result.get("ok") else 0
        if name == "buy_upgrade":
            if result.get("ok"):
                return int(result.get("level", 0) or 0)
            miner = getattr(self.engine, "miner", None) if self.engine is not None else None
            upgrades = getattr(miner, "upgrades", {}) if miner is not None else {}
            upgrade_id = result.get("id") or result.get("upgrade")
            if upgrade_id and isinstance(upgrades, dict):
                return int(upgrades.get(upgrade_id, 0) or 0)
            return int(result.get("level", 0) or 0)
        if name == "wait":
            return None
        if name == "tick":
            return int(result.get("tick", 0) or 0)
        if name == "distance":
            return int(result.get("distance", 0) or 0)
        if name == "biome":
            return result.get("biome")
        if name == "ore_info":
            return result.get("info")
        if name == "inspect":
            return result.get("inspect")
        if name == "submit_estimate":
            cleaned: dict[str, Any] = {"ok": bool(result.get("ok"))}
            if result.get("reason"):
                cleaned["reason"] = result["reason"]
            if result.get("attempts") is not None:
                cleaned["attempts"] = int(result["attempts"])
            if result.get("submissions") is not None:
                cleaned["submissions"] = int(result["submissions"])
            if result.get("ok"):
                cleaned["close"] = bool(result.get("close"))
            return cleaned
        return result

    def _handle_api(self, message: dict[str, Any], out: list[HostEvent]) -> None:
        request_id = message.get("id")
        name = str(message.get("name") or "")
        args = message.get("args") or []
        kwargs = message.get("kwargs") or {}
        if not isinstance(args, list):
            self._reply_error(request_id, "TypeError", f"{name}() arguments must be a list")
            return
        if not isinstance(kwargs, dict):
            self._reply_error(request_id, "TypeError", f"{name}() keyword arguments must be a dict")
            return
        specs = self._spec_map
        if name not in specs:
            self._reply_error(request_id, "NameError", f"name '{name}' is not defined")
            return
        unlocked_by = specs[name].get("unlocked_by")
        if not self._is_unlocked("function", name, unlocked_by):
            self._reply_error(
                request_id, "NotUnlockedError", self._locked_message("function", name, unlocked_by)
            )
            return
        if self.engine is None:
            self._reply_error(request_id, "RuntimeError", "no engine attached to host")
            return
        try:
            command = self._build_command(name, args, kwargs)
        except (TypeError, ValueError, NameError) as exc:
            self._reply_error(request_id, type(exc).__name__, str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - reported to the player script
            self._reply_error(request_id, type(exc).__name__, str(exc))
            return
        try:
            cost = int(command.cost_ticks(self.engine))
        except Exception:
            cost = 0
        if cost > 0:
            self._zero_streak = 0
        else:
            self._zero_streak += 1
            limit = self._free_limit()
            if limit > 0 and self._zero_streak >= limit:
                self._zero_streak = 0
                wait_ticket = self.engine.submit(Wait(1))
                if not wait_ticket.done:
                    self._pending = _Pending(
                        request_id=request_id,
                        name=name,
                        command=command,
                        ticket=None,
                        wait_ticket=wait_ticket,
                    )
                    return
        ticket = self.engine.submit(command)
        if ticket.done:
            self._reply(request_id, result=self._extract_result(name, ticket.result))
        else:
            self._pending = _Pending(
                request_id=request_id, name=name, command=command, ticket=ticket
            )

    def _finish_pending(self) -> None:
        pending = self._pending
        if pending is None or self.engine is None:
            return
        if pending.wait_ticket is not None:
            if not pending.wait_ticket.done:
                return
            ticket = self.engine.submit(pending.command)
            if ticket.done:
                self._pending = None
                self._reply(
                    pending.request_id, result=self._extract_result(pending.name, ticket.result)
                )
            else:
                pending.wait_ticket = None
                pending.ticket = ticket
            return
        ticket = pending.ticket
        if ticket is not None and ticket.done:
            self._pending = None
            self._reply(
                pending.request_id, result=self._extract_result(pending.name, ticket.result)
            )

    def _fail(self, error: dict[str, Any], out: list[HostEvent]) -> None:
        self.last_error = dict(error)
        traceback_text = str(error.get("traceback_text") or "")
        text = traceback_text or f"{error.get('type', 'Error')}: {error.get('message', '')}"
        self._add_console(
            HostEvent(
                kind="err",
                text=text,
                error_type=str(error.get("type") or ""),
                line_number=error.get("line") if isinstance(error.get("line"), int) else None,
            ),
            out,
        )
        self._state = ScriptState.FAILED
        self._publish(ScriptFailed(error_type=str(error.get("type") or "")))
        self._pending = None

    def _succeed(self, out: list[HostEvent]) -> None:
        self._state = ScriptState.FINISHED
        self._publish(ScriptFinished())
        self._pending = None

    def _trigger_watchdog(self, out: list[HostEvent] | None = None) -> bool:
        """Kill the child for exceeding the idle timeout. Returns True if fired."""
        with self._watchdog_lock:
            if self._state is not ScriptState.RUNNING:
                return False
            process = self._process
            if process is None or not process.is_alive():
                return False
            timeout = self._idle_timeout()
            elapsed = time.monotonic() - self._last_activity
            if elapsed < timeout:
                return False
            seconds = int(timeout) if float(timeout).is_integer() else timeout
            text = f"Script ran {seconds} s without calling the game API (infinite loop?)"
            self.last_error = {
                "type": "TimeoutError",
                "message": text,
                "line": None,
                "traceback_text": text,
            }
            self._add_console(HostEvent(kind="err", text=text, error_type="TimeoutError"), out)
            self._state = ScriptState.FAILED
            self._publish(ScriptFailed(error_type="TimeoutError"))
            self._pending = None
        self.stop()
        self._state = ScriptState.FAILED
        return True

    def _watchdog_loop(self, run_id: int) -> None:
        """Background watchdog: fires even if the game loop stops pumping."""
        while self._state is ScriptState.RUNNING and self._run_id == run_id:
            time.sleep(0.05)
            if self._state is not ScriptState.RUNNING or self._run_id != run_id:
                return
            if self._pending is not None:
                self._last_activity = time.monotonic()
                continue
            self._trigger_watchdog()

    # -- main loop ----------------------------------------------------------

    def pump(self) -> list[HostEvent]:
        """Process all currently-available child messages (non-blocking).

        Replies to player API calls whose engine ticket is done,
        accumulates console lines and returns the new
        :class:`HostEvent` objects. The game loop steps the engine
        between pumps.
        """
        out: list[HostEvent] = []
        if self._state is not ScriptState.RUNNING or self._conn is None:
            return out
        self._last_activity = self._last_activity or time.monotonic()
        was_waiting = self._pending is not None
        self._finish_pending()
        conn = self._conn
        # Drain everything the child has sent so far.
        while self._state is ScriptState.RUNNING and conn is not None:
            try:
                has_data = conn.poll()
            except (OSError, EOFError, ValueError):
                break
            if not has_data:
                break
            try:
                raw = conn.recv_bytes()
            except (EOFError, BrokenPipeError, OSError, ValueError):
                self._saw_eof = True
                break
            self._last_activity = time.monotonic()
            try:
                message = json.loads(bytes(raw).decode("utf-8"))
            except Exception:
                continue
            if not isinstance(message, dict):
                continue
            kind = message.get("kind")
            if kind == "api":
                self._handle_api(message, out)
            elif kind == "console":
                stream = str(message.get("stream") or "out")
                if stream not in ("out", "err", "info"):
                    stream = "out"
                text = str(message.get("text") or "")
                self._add_console(HostEvent(kind=stream, text=text), out)
            elif kind == "error":
                error = message.get("error") or {}
                if isinstance(error, dict):
                    self._fail(error, out)
                else:
                    self._fail({"type": "RuntimeError", "message": str(error)}, out)
            elif kind == "finished":
                self._succeed(out)
            else:
                # Unknown message kinds are ignored (validated protocol).
                continue
        if self._state is not ScriptState.RUNNING:
            return out
        # Watchdog: only while the child runs player code, never while
        # it waits for the engine.
        if self._pending is not None:
            self._last_activity = time.monotonic()
        elif was_waiting and self._pending is None:
            self._last_activity = time.monotonic()
        else:
            timeout = self._idle_timeout()
            elapsed = time.monotonic() - self._last_activity
            process = self._process
            if elapsed >= timeout or self._saw_eof:
                alive = bool(process is not None and process.is_alive())
            else:
                alive = True
            if alive and elapsed >= timeout:
                if self._trigger_watchdog(out):
                    return out
            if not alive and process is not None and self._pending is None:
                # The child exited without sending finished/error.
                exitcode = getattr(process, "exitcode", None)
                try:
                    process.join(timeout=0)
                except Exception:
                    pass
                if exitcode == 0:
                    self._succeed(out)
                else:
                    text = "Script process exited unexpectedly"
                    self.last_error = {
                        "type": "RuntimeError",
                        "message": text,
                        "line": None,
                        "traceback_text": text,
                    }
                    self._add_console(
                        HostEvent(kind="err", text=text, error_type="RuntimeError"), out
                    )
                    self._state = ScriptState.FAILED
                    self._publish(ScriptFailed(error_type="RuntimeError"))
        return out

    def run_until_done(self, max_pumps: int = 100000) -> ScriptState:
        """Pump (and step the engine) until the script ends. Convenience helper."""
        for _ in range(max_pumps):
            self.pump()
            if self._state is not ScriptState.RUNNING:
                return self._state
            if self.engine is not None and hasattr(self.engine, "run_until_idle"):
                try:
                    self.engine.run_until_idle()
                except Exception:
                    pass
            time.sleep(0.001)
        return self._state


ConsoleEvent = HostEvent

__all__ = [
    "ConsoleEvent",
    "ConsoleLine",
    "HostEvent",
    "HostState",
    "NotUnlockedError",
    "ScriptHost",
    "ScriptState",
]
