"""Generation of ``minesim_api.pyi`` stubs for player scripts."""

from __future__ import annotations

import ast
import logging
from importlib.resources import files
from pathlib import Path
from typing import Any

__all__ = ["generate_stub_text", "generate_stubs", "write_stubs"]

logger = logging.getLogger(__name__)

_PARAM_TYPES: dict[str, str] = {
    "direction": "str",
    "radius": "int",
    "upgrade_id": "str",
    "id": "str",
    "ore_id": "str",
    "p": "float",
    "ticks": "int",
    "n": "int",
    "ore": "str",
    "max_tiles": "int",
    "success": "bool",
    "x": "int",
    "y": "int",
    "width": "int",
    "height": "int",
}

_RETURN_TYPES: dict[str, str] = {
    "move": "None",
    "mine": "dict",
    "peek": "str | None",
    "position": "tuple[int, int]",
    "sell": "int",
    "inventory": "dict",
    "scan": "list[tuple[int, int, str]]",
    "stats": "dict",
    "buy_upgrade": "int",
    "wait": "None",
    "tick": "int",
    "distance": "int",
    "biome": "str",
    "ore_info": "dict | None",
    "inspect": "dict",
    "submit_estimate": "dict",
    "goto": "None",
    "go_home": "None",
    "sweep": "Any",
    "spiral": "Any",
    "ring": "Any",
    "mine_here": "Any",
    "nearest": "tuple[int, int] | None",
    "goto_nearest": "bool",
    "mine_until": "int",
    "haul": "int",
    "farm": "int",
}


def _function_entries(content: Any) -> list[dict[str, Any]]:
    """Return function spec dicts from ``content`` (or defaults)."""
    entries: list[dict[str, Any]] = []
    raw = getattr(content, "functions", None) if content is not None else None
    if isinstance(raw, dict):
        items = list(raw.values())
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        items = []
    for item in items:
        if isinstance(item, dict):
            entries.append(dict(item))
        elif hasattr(item, "name"):
            entries.append(
                {
                    "name": item.name,
                    "signature": getattr(item, "signature", "") or "",
                    "doc": getattr(item, "doc", "") or "",
                    "category": getattr(item, "category", "") or "",
                    "unlocked_by": getattr(item, "unlocked_by", None),
                }
            )
    if entries:
        return entries
    try:
        from minesim.core.content import load_content

        loaded = load_content()
        return _function_entries(loaded)
    except Exception:
        logger.debug("could not load content for stubs; using defaults", exc_info=True)
    return [
        {"name": "move", "signature": "move(direction)", "doc": "Move one tile."},
        {"name": "mine", "signature": "mine()", "doc": "Mine the current tile."},
        {"name": "peek", "signature": "peek()", "doc": "Look at the current tile."},
        {"name": "position", "signature": "position()", "doc": "Return (x, y)."},
        {"name": "sell", "signature": "sell()", "doc": "Sell the inventory."},
        {"name": "inventory", "signature": "inventory()", "doc": "Return the inventory."},
        {"name": "scan", "signature": "scan(radius)", "doc": "Scan for ore."},
        {"name": "stats", "signature": "stats()", "doc": "Return mining stats."},
        {"name": "buy_upgrade", "signature": "buy_upgrade(upgrade_id)", "doc": "Buy an upgrade."},
        {"name": "wait", "signature": "wait(ticks)", "doc": "Wait for ticks."},
        {"name": "tick", "signature": "tick()", "doc": "Return the current tick."},
        {"name": "distance", "signature": "distance()", "doc": "Distance from the base."},
        {"name": "biome", "signature": "biome()", "doc": "Current biome id."},
        {"name": "ore_info", "signature": "ore_info(ore_id)", "doc": "Public ore info."},
        {"name": "inspect", "signature": "inspect()", "doc": "Describe the current tile."},
        {
            "name": "submit_estimate",
            "signature": "submit_estimate(ore_id, p)",
            "doc": "Submit a probability estimate.",
        },
    ]


def _signature_params(signature: str, name: str) -> list[str]:
    """Extract parameter names from a ``name(a, b)`` signature string."""
    text = (signature or "").strip()
    if "(" in text and ")" in text:
        inner = text[text.index("(") + 1 : text.rindex(")")]
    else:
        inner = ""
    params: list[str] = []
    for part in inner.split(","):
        part = part.strip()
        if not part:
            continue
        part = part.split("=")[0].split(":")[0].strip().lstrip("*")
        if part:
            params.append(part)
    return params


def _minerlib_entries() -> list[dict[str, Any]]:
    """Return minerlib function entries parsed from its source (no import)."""
    entries: list[dict[str, Any]] = []
    try:
        path = files("minesim.runner").joinpath("minerlib.py")
        text = path.read_text(encoding="utf-8")
    except Exception:
        logger.debug("could not read minerlib source for stubs", exc_info=True)
        return [
            {"name": "goto", "signature": "goto(x, y)", "doc": "Move to (x, y)."},
            {"name": "go_home", "signature": "go_home()", "doc": "Move to (0, 0)."},
            {"name": "sweep", "signature": "sweep(width, height)", "doc": "Serpentine positions."},
            {"name": "spiral", "signature": "spiral()", "doc": "Spiral positions."},
            {"name": "mine_here", "signature": "mine_here()", "doc": "Mine here if possible."},
        ]
    tree = ast.parse(text)
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


def _format_entry(entry: dict[str, Any]) -> str:
    """Format one stub function definition."""
    name = str(entry.get("name") or "")
    signature = str(entry.get("signature") or f"{name}()")
    params = _signature_params(signature, name)
    typed = ", ".join(f"{param}: {_PARAM_TYPES.get(param, 'Any')}" for param in params)
    return_type = _RETURN_TYPES.get(name, "Any")
    doc = str(entry.get("doc") or "").strip()
    if doc:
        doc_repr = repr(doc)
        return "\n".join(
            [
                f"def {name}({typed}) -> {return_type}:",
                f"    {doc_repr}",
                "    ...",
            ]
        )
    return f"def {name}({typed}) -> {return_type}: ..."


def generate_stub_text(content: Any = None) -> str:
    """Generate the text of ``minesim_api.pyi``.

    Built from the function specs in ``functions.json`` (via
    ``content``) and the documented functions of ``minerlib``.
    """
    lines: list[str] = [
        "# Generated by MineSim from functions.json and minerlib. Do not edit.",
        "from typing import Any",
        "",
        'North: str = "north"',
        'East: str = "east"',
        'South: str = "south"',
        'West: str = "west"',
        "",
    ]
    for entry in _function_entries(content):
        lines.append(_format_entry(entry))
    lines.append("")
    lines.append("class NotUnlockedError(Exception): ...")
    lines.append("")
    lines.append("# --- minerlib ---")
    for entry in _minerlib_entries():
        lines.append(_format_entry(entry))
    lines.append("")
    lines.append("class Samples:")
    lines.append("    def __init__(self) -> None: ...")
    lines.append("    def add(self, ore: str, success: bool) -> None: ...")
    lines.append("    def count(self, ore: str) -> int: ...")
    lines.append("    def rate(self, ore: str) -> float: ...")
    lines.append("    def summary(self) -> dict[str, dict[str, float | int]]: ...")
    lines.append("")
    return "\n".join(lines)


def write_stubs(scripts_dir: Any, content: Any = None) -> Path:
    """Write ``minesim_api.pyi`` into ``scripts_dir`` and return its path."""
    directory = Path(scripts_dir)
    directory.mkdir(parents=True, exist_ok=True)
    out = directory / "minesim_api.pyi"
    out.write_text(generate_stub_text(content), encoding="utf-8")
    return out


generate_stubs = write_stubs
