"""API reference panel: functions, modules and minerlib helpers."""

from __future__ import annotations

import ast
from typing import Any

from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from digscript.ui.floating_panel import FloatingPanel
from digscript.ui.theme import DISABLED_TEXT, SYNTAX_API, TEXT, TEXT_DIM

__all__ = [
    "ApiPanel",
    "ApiReferencePanel",
    "FunctionReferencePanel",
    "FunctionsPanel",
    "ReferencePanel",
]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _entries(content: Any, attr: str) -> list[dict[str, Any]]:
    if content is None:
        return []
    raw = _get(content, attr)
    items: list[Any] = []
    if isinstance(raw, dict):
        items = list(raw.values())
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    result: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            result.append(dict(item))
        elif hasattr(item, "name"):
            entry: dict[str, Any] = {"name": item.name}
            for key in ("signature", "doc", "category", "unlocked_by", "cost", "example"):
                if hasattr(item, key):
                    entry[key] = getattr(item, key)
            result.append(entry)
    return result


def _minerlib_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    try:
        from importlib.resources import files

        text = files("digscript.runner").joinpath("minerlib.py").read_text(encoding="utf-8")
    except Exception:
        return [
            {"name": "goto", "signature": "goto(x, y)", "doc": "Move the miner to (x, y)."},
            {"name": "go_home", "signature": "go_home()", "doc": "Move the miner back to (0, 0)."},
            {
                "name": "sweep",
                "signature": "sweep(width, height)",
                "doc": "Yield positions in serpentine order.",
            },
            {
                "name": "spiral",
                "signature": "spiral()",
                "doc": "Yield positions in an infinite spiral.",
            },
            {
                "name": "mine_here",
                "signature": "mine_here()",
                "doc": "Mine the current tile if it holds ore.",
            },
        ]
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return entries
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in {
            "move",
            "mine",
            "peek",
            "position",
            "scan",
            "inventory",
            "sell",
        }:
            continue
        params = [arg.arg for arg in node.args.args]
        doc = ast.get_docstring(node) or ""
        entries.append(
            {"name": node.name, "signature": f"{node.name}({', '.join(params)})", "doc": doc}
        )
    return entries


class ApiPanel(FloatingPanel):
    """Floating panel listing every API function, module and helper."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Functions"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        content = kwargs.pop("content", None)
        progression = kwargs.pop("progression", None) or kwargs.pop("progression_view", None)
        host = kwargs.pop("host", None) or kwargs.pop("script_host", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, str):
                title = arg
            elif isinstance(arg, QWidget):
                if parent is None:
                    parent = arg
            elif hasattr(arg, "engine") and hasattr(arg, "miner"):
                if game is None:
                    game = arg
            elif hasattr(arg, "start") and hasattr(arg, "pump"):
                if host is None:
                    host = arg
            elif hasattr(arg, "config") and hasattr(arg, "ores"):
                if content is None:
                    content = arg
            elif hasattr(arg, "is_function_unlocked"):
                if progression is None:
                    progression = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        self.game = game
        if game is not None:
            if content is None:
                content = _get(game, "content")
            if progression is None:
                progression = _get(game, "progression_service") or _get(game, "progression")
        if host is not None and content is None:
            content = _get(host, "content")
            if progression is None:
                progression = _get(host, "progression_view") or _get(host, "progression")
        self.content = content
        self.api_content = content
        self.progression = progression
        self.progression_view = progression
        self.host = host
        self.function_entries: list[dict[str, Any]] = []
        self.module_entries: list[dict[str, Any]] = []
        self.minerlib_entries: list[dict[str, Any]] = []
        self.entries: list[dict[str, Any]] = []

        super().__init__(title, parent=parent)
        if not self._restored_geometry:
            self.resize(520, 480)
            self.move(420, 60)
        self.text_edit = QTextEdit(self.content_widget)
        self.text_edit.setObjectName("api_reference")
        self.text_edit.setReadOnly(True)
        self.view = self.text_edit
        self.reference = self.text_edit
        self.reference_text_widget = self.text_edit
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_edit)
        self.content_layout.addLayout(layout)
        self._subscribe()
        self.refresh()

    # -- unlock helpers ---------------------------------------------------------

    def _is_unlocked(self, kind: str, name: str, unlocked_by: Any) -> bool:
        if unlocked_by is None:
            return True
        view = self.progression
        if view is None:
            return False
        method = getattr(
            view, "is_function_unlocked" if kind == "function" else "is_module_unlocked", None
        )
        if callable(method):
            try:
                return bool(method(name))
            except Exception:
                pass
        for attr in (f"unlocked_{kind}s", "unlocked"):
            value = getattr(view, attr, None)
            if isinstance(value, (set, list, tuple, dict)):
                return name in value or unlocked_by in value
        return False

    def _achievement_title(self, unlocked_by: Any) -> str:
        if not unlocked_by:
            return ""
        view = self.progression
        for attr in ("requirement_title", "achievement_title", "title_for"):
            method = getattr(view, attr, None) if view is not None else None
            if callable(method):
                for args in (("function", str(unlocked_by)), (str(unlocked_by),)):
                    try:
                        value = method(*args)
                    except Exception:
                        continue
                    if value:
                        return str(value)
        content = self.api_content
        achievements = _get(content, "achievements") if content is not None else None
        if isinstance(achievements, dict):
            entry = achievements.get(str(unlocked_by))
            title = _get(entry, "title")
            if title:
                return str(title)
        elif isinstance(achievements, (list, tuple)):
            for entry in achievements:
                if _get(entry, "id") == str(unlocked_by):
                    title = _get(entry, "title")
                    if title:
                        return str(title)
        return str(unlocked_by).replace("_", " ").title()

    def locked_text(self, kind: str, name: str, unlocked_by: Any) -> str:
        """Return the locked message for an entry."""
        return f"Locked, unlock with the achievement {self._achievement_title(unlocked_by)}"

    # -- building -----------------------------------------------------------------

    def _build_entries(self) -> None:
        content = self.api_content
        if content is None and self.game is not None:
            content = _get(self.game, "content")
            self.content = content
            self.api_content = content
        functions = _entries(content, "functions")
        if not functions:
            try:
                from digscript.core.content import load_content

                loaded = load_content()
                functions = _entries(loaded, "functions")
                if content is None:
                    content = loaded
                    self.content = loaded
                    self.api_content = loaded
            except Exception:
                functions = [
                    {"name": "move", "signature": "move(direction)", "doc": "Move one tile."},
                    {"name": "mine", "signature": "mine()", "doc": "Mine the current tile."},
                    {"name": "peek", "signature": "peek()", "doc": "Look at the current tile."},
                    {"name": "position", "signature": "position()", "doc": "Return (x, y)."},
                ]
        modules = _entries(content, "modules")
        if not modules:
            modules = [
                {"name": "math", "unlocked_by": None},
                {"name": "random", "unlocked_by": "wanderer"},
            ]
        self.function_entries = []
        for entry in functions:
            name = str(entry.get("name") or "")
            unlocked_by = entry.get("unlocked_by")
            unlocked = self._is_unlocked("function", name, unlocked_by)
            self.function_entries.append(
                {
                    "name": name,
                    "signature": str(entry.get("signature") or f"{name}()"),
                    "doc": str(entry.get("doc") or ""),
                    "category": str(entry.get("category") or ""),
                    "cost": str(entry.get("cost") or ""),
                    "example": str(entry.get("example") or ""),
                    "unlocked_by": unlocked_by,
                    "unlocked": unlocked,
                    "locked": not unlocked,
                    "achievement_title": self._achievement_title(unlocked_by)
                    if not unlocked
                    else "",
                    "kind": "function",
                }
            )
        self.module_entries = []
        for entry in modules:
            name = str(entry.get("name") or "")
            unlocked_by = entry.get("unlocked_by")
            unlocked = self._is_unlocked("module", name, unlocked_by)
            self.module_entries.append(
                {
                    "name": name,
                    "signature": f"import {name}",
                    "doc": str(entry.get("doc") or ""),
                    "unlocked_by": unlocked_by,
                    "unlocked": unlocked,
                    "locked": not unlocked,
                    "achievement_title": self._achievement_title(unlocked_by)
                    if not unlocked
                    else "",
                    "kind": "module",
                }
            )
        self.minerlib_entries = []
        for entry in _minerlib_entries():
            self.minerlib_entries.append(
                {
                    "name": str(entry.get("name") or ""),
                    "signature": str(entry.get("signature") or ""),
                    "doc": str(entry.get("doc") or ""),
                    "unlocked_by": None,
                    "unlocked": True,
                    "locked": False,
                    "achievement_title": "",
                    "kind": "minerlib",
                }
            )
        self.entries = [*self.function_entries, *self.module_entries, *self.minerlib_entries]

    @staticmethod
    def _escape(text: str) -> str:
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def refresh(self) -> None:
        """Rebuild the reference from current unlock state."""
        self._build_entries()
        parts: list[str] = [
            f"<h2 style='color:{SYNTAX_API}'>API Reference</h2>",
            "<h3>Functions</h3>",
        ]
        for entry in self.function_entries:
            signature = self._escape(entry["signature"])
            doc = self._escape(entry["doc"])
            detail = ""
            if entry["cost"]:
                detail += (
                    f"<br/><span style='color:{TEXT_DIM}'>Cost: "
                    f"{self._escape(entry['cost'])}</span>"
                )
            if entry["example"]:
                detail += (
                    f"<br/><code style='color:{TEXT_DIM}'>{self._escape(entry['example'])}</code>"
                )
            if entry["locked"]:
                locked = self.locked_text("function", entry["name"], entry["unlocked_by"])
                parts.append(
                    f"<p style='color:{DISABLED_TEXT}'><b>{signature}</b> — {doc}{detail}</p>"
                    f"<p style='color:{DISABLED_TEXT}'>{self._escape(locked)}</p>"
                )
            else:
                parts.append(
                    f"<p style='color:{TEXT}'>"
                    f"<b style='color:{SYNTAX_API}'>{signature}</b> — {doc}{detail}</p>"
                )
        parts.append("<h3>Constants</h3><p>North, East, South, West — directions for move().</p>")
        parts.append("<h3>Modules</h3>")
        for entry in self.module_entries:
            signature = self._escape(entry["signature"])
            if entry["locked"]:
                locked = self.locked_text("module", entry["name"], entry["unlocked_by"])
                parts.append(
                    f"<p style='color:{DISABLED_TEXT}'><b>{signature}</b><br/>"
                    f"{self._escape(locked)}</p>"
                )
            else:
                parts.append(f"<p style='color:{TEXT}'><b>{signature}</b></p>")
        parts.append("<h3>minerlib helpers</h3>")
        for entry in self.minerlib_entries:
            signature = self._escape(entry["signature"])
            doc = self._escape(entry["doc"]).replace("\n", "<br/>")
            parts.append(f"<p style='color:{TEXT_DIM}'><b>{signature}</b> — {doc}</p>")
        self.text_edit.setHtml("".join(parts))

    def rebuild(self) -> None:
        """Alias for :meth:`refresh`."""
        self.refresh()

    def populate(self) -> None:
        """Alias for :meth:`refresh`."""
        self.refresh()

    def update_reference(self) -> None:
        """Alias for :meth:`refresh`."""
        self.refresh()

    def plain_text(self) -> str:
        """Return the reference as plain text."""
        return self.text_edit.toPlainText()

    def get_text(self) -> str:
        """Alias for :meth:`plain_text`."""
        return self.plain_text()

    def set_game(self, game: Any) -> None:
        """Attach a new game and refresh."""
        self.game = game
        self.content = _get(game, "content")
        self.api_content = self.content
        self.progression = _get(game, "progression_service") or _get(game, "progression")
        self.progression_view = self.progression
        self._subscribe()
        self.refresh()

    def _subscribe(self) -> None:
        if self.game is None:
            return
        bus = _get(self.game, "events") or _get(self.game, "event_bus")
        if bus is None or not hasattr(bus, "subscribe"):
            return
        try:
            from digscript.core.events import AchievementUnlocked

            bus.subscribe(AchievementUnlocked, lambda _e: self.refresh())
        except Exception:
            pass

    def showEvent(self, event: Any) -> None:  # noqa: N802
        self.refresh()
        super().showEvent(event)


FunctionsPanel = ApiPanel
ApiReferencePanel = ApiPanel
FunctionReferencePanel = ApiPanel
ReferencePanel = ApiPanel
