"""Child-side runner: executes player code in a restricted namespace.

This module runs inside the subprocess started by
``minesim.scripting.host``. It imports only the standard library.
Player code is never executed in the game process.
"""

from __future__ import annotations

import builtins as _builtins
import importlib
import json
import traceback
import types
from pathlib import Path
from typing import Any

__all__ = ["NotUnlockedError", "run"]


class NotUnlockedError(Exception):
    """Raised when a player calls a locked API function."""


_KEEP_BUILTINS = (
    "print",
    "range",
    "len",
    "min",
    "max",
    "sum",
    "abs",
    "round",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sorted",
    "reversed",
    "list",
    "dict",
    "set",
    "tuple",
    "str",
    "int",
    "float",
    "bool",
    "isinstance",
    "any",
    "all",
    "divmod",
    "pow",
    "repr",
    "True",
    "False",
    "None",
)

_DEFAULT_FUNCTIONS: tuple[dict[str, Any], ...] = (
    {"name": "move", "signature": "move(direction)", "doc": "Move one tile.", "category": ""},
    {"name": "mine", "signature": "mine()", "doc": "Mine the current tile.", "category": ""},
    {"name": "peek", "signature": "peek()", "doc": "Look at the current tile.", "category": ""},
    {"name": "position", "signature": "position()", "doc": "Return (x, y).", "category": ""},
    {"name": "sell", "signature": "sell()", "doc": "Sell the inventory.", "category": ""},
    {
        "name": "inventory",
        "signature": "inventory()",
        "doc": "Return the inventory.",
        "category": "",
    },
    {"name": "scan", "signature": "scan(radius)", "doc": "Scan for ore.", "category": ""},
    {"name": "stats", "signature": "stats()", "doc": "Return mining stats.", "category": ""},
    {
        "name": "buy_upgrade",
        "signature": "buy_upgrade(upgrade_id)",
        "doc": "Buy an upgrade level.",
        "category": "",
    },
    {"name": "wait", "signature": "wait(ticks)", "doc": "Wait for ticks.", "category": ""},
    {"name": "tick", "signature": "tick()", "doc": "Return the current tick.", "category": ""},
    {
        "name": "distance",
        "signature": "distance()",
        "doc": "Return the distance from the base.",
        "category": "",
    },
    {"name": "biome", "signature": "biome()", "doc": "Return the current biome.", "category": ""},
    {
        "name": "ore_info",
        "signature": "ore_info(ore_id)",
        "doc": "Return public ore information.",
        "category": "",
    },
    {
        "name": "inspect",
        "signature": "inspect()",
        "doc": "Describe the current tile.",
        "category": "",
    },
    {
        "name": "submit_estimate",
        "signature": "submit_estimate(ore_id, p)",
        "doc": "Submit a mining probability estimate.",
        "category": "",
    },
)

_CONSTANTS: dict[str, str] = {
    "North": "north",
    "East": "east",
    "South": "south",
    "West": "west",
}


def _send(conn: Any, message: dict[str, Any]) -> None:
    """Send ``message`` as JSON bytes over ``conn``."""
    data = json.dumps(message).encode("utf-8")
    send_bytes = getattr(conn, "send_bytes", None)
    if callable(send_bytes):
        send_bytes(data)
        return
    send = getattr(conn, "send", None)
    if callable(send):
        try:
            send(data)
        except TypeError:
            send(message)
        return
    raise EOFError("connection closed")


def _recv(conn: Any) -> dict[str, Any]:
    """Receive one JSON message from ``conn``."""
    recv_bytes = getattr(conn, "recv_bytes", None)
    if callable(recv_bytes):
        data = recv_bytes()
    else:
        recv = getattr(conn, "recv", None)
        if not callable(recv):
            raise EOFError("connection closed")
        data = recv()
    if isinstance(data, (bytes, bytearray)):
        return json.loads(bytes(data).decode("utf-8"))
    if isinstance(data, str):
        return json.loads(data)
    return data  # type: ignore[return-value]


def _function_specs(spec: Any) -> list[dict[str, Any]]:
    """Normalise ``spec`` into a list of function dicts."""
    raw: Any = None
    if isinstance(spec, dict):
        raw = spec.get("functions", spec.get("api", raw))
        if raw is None and "name" in spec:
            raw = [spec]
    elif isinstance(spec, (list, tuple)):
        raw = list(spec)
    if raw is None:
        return [dict(item) for item in _DEFAULT_FUNCTIONS]
    specs: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        for name, value in raw.items():
            if isinstance(value, dict):
                entry = dict(value)
                entry.setdefault("name", name)
                specs.append(entry)
            else:
                specs.append({"name": str(name)})
    elif isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, dict):
                specs.append(dict(item))
            elif isinstance(item, str):
                specs.append({"name": item})
            elif hasattr(item, "name"):
                specs.append(
                    {
                        "name": item.name,
                        "signature": getattr(item, "signature", ""),
                        "doc": getattr(item, "doc", ""),
                        "category": getattr(item, "category", ""),
                        "unlocked_by": getattr(item, "unlocked_by", None),
                    }
                )
    if not specs:
        return [dict(item) for item in _DEFAULT_FUNCTIONS]
    return specs


def _module_specs(spec: Any) -> list[dict[str, Any]]:
    """Normalise module specs from ``spec`` (may be empty)."""
    raw: Any = None
    if isinstance(spec, dict):
        raw = spec.get("modules")
    if not isinstance(raw, (list, tuple)):
        return []
    specs: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            specs.append(dict(item))
        elif isinstance(item, str):
            specs.append({"name": item})
        elif hasattr(item, "name"):
            specs.append({"name": item.name, "unlocked_by": getattr(item, "unlocked_by", None)})
    return specs


def _locked_module_messages(spec: Any) -> dict[str, str]:
    """Map locked module name -> explanatory message."""
    messages: dict[str, str] = {}
    if isinstance(spec, dict):
        raw = spec.get("locked_modules") or spec.get("locked_module_messages") or {}
        if isinstance(raw, dict):
            for name, value in raw.items():
                messages[str(name)] = str(value)
        elif isinstance(raw, (list, tuple)):
            for name in raw:
                messages[str(name)] = f"module '{name}' is locked"
    return messages


def _exception_classes() -> dict[str, Any]:
    """All builtin exception classes, by name."""
    result: dict[str, Any] = {}
    for name in dir(_builtins):
        try:
            obj = getattr(_builtins, name)
        except Exception:
            continue
        if isinstance(obj, type) and issubclass(obj, BaseException):
            result[name] = obj
    return result


_EXCEPTION_CLASSES = _exception_classes()


def _raise_from_error(error: dict[str, Any]) -> None:
    """Raise the exception described by ``error``."""
    error_type = str(error.get("type") or "RuntimeError")
    message = str(error.get("message") or "")
    if error_type == "NotUnlockedError":
        raise NotUnlockedError(message)
    cls = _EXCEPTION_CLASSES.get(error_type)
    if cls is not None:
        raise cls(message)
    raise RuntimeError(message)


def _convert_result(name: str, result: Any) -> Any:
    """Convert a JSON result back to player-facing Python values."""
    if name == "position" and isinstance(result, list):
        return tuple(result)
    if name == "scan" and isinstance(result, list):
        return [tuple(item) if isinstance(item, list) else item for item in result]
    return result


def _format_error(exc: BaseException, filename: str) -> dict[str, Any]:
    """Build the error dict reported to the host.

    Internal runner frames are stripped; player frames (the player
    file and helper modules in the scripts directory) are kept, so
    the traceback shows the player's line.
    """
    error_type = type(exc).__name__
    message = str(exc)
    line: int | None = None
    frames: list[Any] = []
    tb = exc.__traceback__
    is_syntax = isinstance(exc, SyntaxError)
    if is_syntax:
        syntax_exc = exc  # type: ignore[assignment]
        line = getattr(syntax_exc, "lineno", None)
        text = getattr(syntax_exc, "text", None)
        traceback_text = f'  File "{filename}", line {line}\n'
        if text:
            traceback_text += f"    {text.rstrip()}\n"
        traceback_text += f"SyntaxError: {message}\n"
    else:
        raw_frames = traceback.extract_tb(tb) if tb is not None else []
        this_file = __file__
        runner_dir = str(Path(this_file).resolve().parent)
        kept: list[Any] = []
        for frame in raw_frames:
            frame_path = str(Path(frame.filename).resolve()) if frame.filename else ""
            if frame_path.startswith(runner_dir):
                continue
            kept.append(frame)
        frames = kept if kept else list(raw_frames)
        if frames:
            line = frames[-1].lineno
        parts = ["Traceback (most recent call last):\n"]
        for frame in frames:
            parts.append(f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}\n')
            if frame.line:
                parts.append(f"    {frame.line.strip()}\n")
        parts.append(f"{error_type}: {message}\n")
        traceback_text = "".join(parts)
    return {
        "type": error_type,
        "message": message,
        "line": line,
        "traceback_text": traceback_text,
        "filename": filename,
    }


def run(
    conn: Any,
    source: str,
    filename: str,
    spec: Any = None,
    allowed_modules: Any = None,
    scripts_dir: Any = None,
) -> None:
    """Execute ``source`` as a player script, talking to the host over ``conn``.

    ``spec`` describes the API functions (and modules); the proxies
    for those functions are generated from it. ``allowed_modules``
    lists the importable standard-library modules and ``scripts_dir``
    is the directory whose ``.py`` files may also be imported.
    """
    if filename is None:
        filename = "script.py"
    filename = str(filename)
    scripts_path = Path(scripts_dir) if scripts_dir is not None else Path.cwd()
    allowed: set[str] = set()
    if allowed_modules is not None:
        if isinstance(allowed_modules, str):
            allowed.add(allowed_modules)
        else:
            allowed.update(str(name) for name in allowed_modules)
    function_specs = _function_specs(spec)
    module_specs = _module_specs(spec)
    known_modules = {str(entry.get("name")) for entry in module_specs if entry.get("name")}
    locked_messages = _locked_module_messages(spec)
    for entry in module_specs:
        name = str(entry.get("name") or "")
        if name and name not in allowed and name not in locked_messages:
            unlocked_by = entry.get("unlocked_by")
            if unlocked_by:
                locked_messages[name] = (
                    f"module '{name}' is locked. Unlock it with the achievement '{unlocked_by}'."
                )
            else:
                locked_messages[name] = f"module '{name}' is not allowed"

    request_id = [0]

    def send_message(message: dict[str, Any]) -> None:
        _send(conn, message)

    def call_api(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        request_id[0] += 1
        current = request_id[0]
        send_message(
            {
                "kind": "api",
                "id": current,
                "name": name,
                "args": list(args),
                "kwargs": dict(kwargs),
            }
        )
        while True:
            reply = _recv(conn)
            if not isinstance(reply, dict):
                continue
            if reply.get("kind") not in ("reply", "result"):
                continue
            if reply.get("id") not in (None, current):
                continue
            break
        error = reply.get("error")
        if error:
            _raise_from_error(error)
        return _convert_result(name, reply.get("result"))

    def make_proxy(entry: dict[str, Any]) -> Any:
        name = str(entry.get("name"))

        def proxy(*args: Any, **kwargs: Any) -> Any:
            return call_api(name, args, kwargs)

        proxy.__name__ = name
        proxy.__doc__ = str(entry.get("doc") or "")
        proxy.__module__ = "minesim_api"
        return proxy

    proxies: dict[str, Any] = {}
    for entry in function_specs:
        name = str(entry.get("name") or "")
        if name:
            proxies[name] = make_proxy(entry)

    def player_print(*args: Any, **kwargs: Any) -> None:
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        file_arg = kwargs.get("file", None)
        stream = "out"
        if file_arg is not None:
            file_name = getattr(file_arg, "name", "") or str(file_arg)
            if "err" in str(file_name):
                stream = "err"
        if sep is None:
            sep = " "
        if end is None:
            end = ""
        text = str(sep).join(str(arg) for arg in args) + str(end)
        if text.endswith("\n"):
            text = text[:-1]
        try:
            send_message({"kind": "console", "text": text, "stream": stream})
        except (EOFError, BrokenPipeError, OSError):
            pass
        return None

    # Restricted builtins.
    player_builtins: dict[str, Any] = {}
    for name in _KEEP_BUILTINS:
        if name in ("True", "False", "None"):
            continue
        value = getattr(_builtins, name, None)
        if value is not None:
            player_builtins[name] = value
    player_builtins["print"] = player_print
    player_builtins.update(_EXCEPTION_CLASSES)
    player_builtins["NotUnlockedError"] = NotUnlockedError
    player_builtins["BaseException"] = BaseException

    # minerlib, with the API injected.
    try:
        import minesim.runner.minerlib as minerlib
    except Exception:
        minerlib = types.ModuleType("minerlib")  # pragma: no cover
    for api_name, api_fn in proxies.items():
        setattr(minerlib, api_name, api_fn)
    minerlib.__dict__["NotUnlockedError"] = NotUnlockedError
    minerlib.__dict__["print"] = player_print

    loaded: dict[str, Any] = {"minerlib": minerlib}

    def load_script_module(top: str) -> Any:
        path = scripts_path / f"{top}.py"
        module = types.ModuleType(top)
        module.__dict__["__builtins__"] = player_builtins
        module.__dict__["__name__"] = top
        module.__dict__["__file__"] = str(path)
        module.__dict__["__package__"] = ""
        module.__dict__.update(proxies)
        module.__dict__.update(_CONSTANTS)
        module.__dict__["NotUnlockedError"] = NotUnlockedError
        module.__dict__["print"] = player_print
        source_text = path.read_text(encoding="utf-8")
        code = compile(source_text, str(path), "exec")
        exec(code, module.__dict__)  # noqa: S102 - runner executing player helper code
        return module

    def restricted_import(
        name: Any,
        globals_arg: Any = None,
        locals_arg: Any = None,
        fromlist: Any = (),
        level: Any = 0,
    ) -> Any:
        if not isinstance(name, str) or not name:
            raise ImportError(f"cannot import {name!r}")
        top = name.split(".")[0]
        if level:
            raise ImportError(f"relative import of {name!r} is not allowed")
        if top in loaded:
            return loaded[top]
        if top == "minerlib":
            loaded[top] = minerlib
            return minerlib
        if top in allowed:
            if "." in name:
                importlib.import_module(name)
                module = importlib.import_module(top)
            else:
                module = importlib.import_module(top)
            loaded[top] = module
            return module
        script_path = scripts_path / f"{top}.py"
        try:
            is_script = script_path.is_file()
        except OSError:
            is_script = False
        if is_script:
            module = load_script_module(top)
            loaded[top] = module
            if "." in name:
                current: Any = module
                for part in name.split(".")[1:]:
                    current = getattr(current, part)
                return current
            return module
        if top in locked_messages or top in known_modules:
            raise ImportError(locked_messages.get(top) or f"module '{top}' is locked")
        raise ImportError(f"module '{top}' is not allowed")

    player_builtins["__import__"] = restricted_import
    player_builtins["__build_class__"] = getattr(_builtins, "__build_class__", None)

    namespace: dict[str, Any] = {
        "__builtins__": player_builtins,
        "__name__": "__main__",
        "__file__": filename,
        "__package__": "",
    }
    namespace.update(proxies)
    namespace.update(_CONSTANTS)
    namespace["NotUnlockedError"] = NotUnlockedError

    try:
        code = compile(source, filename, "exec")
    except BaseException as exc:  # noqa: BLE001 - reported to the host, not raised
        error = _format_error(exc, filename)
        try:
            send_message({"kind": "error", "error": error})
        except (EOFError, BrokenPipeError, OSError):
            pass
        return

    try:
        exec(code, namespace)  # noqa: S102 - runner executing player code
    except EOFError:
        return
    except BaseException as exc:  # noqa: BLE001 - reported to the host, not raised
        error = _format_error(exc, filename)
        try:
            send_message({"kind": "error", "error": error})
        except (EOFError, BrokenPipeError, OSError):
            pass
        return

    try:
        send_message({"kind": "finished"})
    except (EOFError, BrokenPipeError, OSError):
        pass


main = run
