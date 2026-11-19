"""Generation of ``minesim_api.pyi`` stubs for player scripts."""

from __future__ import annotations

import ast
import logging
from importlib.resources import files
from pathlib import Path
from typing import Any

from minesim.runner.aliases import DEPRECATED_ALIASES

__all__ = ["generate_stub_text", "generate_stubs", "write_stubs"]

logger = logging.getLogger(__name__)

_PRIMITIVE_NAMES: frozenset[str] = frozenset(
    {
        "move",
        "mine",
        "peek",
        "position",
        "battery",
        "charge",
        "energy_cost",
        "sell",
        "unload",
        "stock",
        "sell_stock",
        "price",
        "prices",
        "price_history",
        "inventory",
        "scan",
        "stats",
        "buy_upgrade",
        "wait",
        "tick",
        "events",
        "distance",
        "biome",
        "layer",
        "layers",
        "descend",
        "ascend",
        "ore_info",
        "inspect",
        "submit_estimate",
        "recipes",
        "refine",
        "refinery",
        "contracts",
        "deliver",
        "miner_id",
        "miners",
        "spawn_miner",
        "kill_miner",
        "assign",
        "shared_get",
        "shared_set",
    }
)

_PARAM_TYPES: dict[str, str] = {
    "direction": "str",
    "action": "str",
    "arg": "int | None",
    "alpha": "float",
    "min_index": "float",
    "values": "list[float]",
    "xs": "list[float]",
    "ys": "list[float]",
    "radius": "int",
    "upgrade_id": "str",
    "id": "str",
    "ore_id": "str",
    "item": "str",
    "amount": "int | None",
    "recipe_id": "str",
    "times": "int",
    "contract_id": "int",
    "contract": "int",
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
    "script_name": "str",
    "miner_id": "int",
    "key": "str",
    "value": "Any",
    "default": "Any",
}

_RETURN_TYPES: dict[str, str] = {
    "move": "bool",
    "battery": "tuple[int, int]",
    "charge": "dict",
    "energy_cost": "int",
    "mine": "dict",
    "peek": "str | None",
    "position": "tuple[int, int]",
    "sell": "int",
    "unload": "dict",
    "stock": "dict",
    "sell_stock": "int",
    "recipes": "dict",
    "refine": "dict",
    "refinery": "list[dict]",
    "contracts": "list[dict]",
    "deliver": "int",
    "price": "float | None",
    "prices": "dict",
    "price_history": "list[float] | None",
    "inventory": "dict",
    "scan": "list[tuple[int, int, str]]",
    "stats": "dict",
    "buy_upgrade": "int",
    "wait": "None",
    "tick": "int",
    "events": "list[dict]",
    "distance": "int",
    "biome": "str",
    "ore_info": "dict | None",
    "inspect": "dict",
    "submit_estimate": "dict",
    "miner_id": "int",
    "miners": "list[dict]",
    "spawn_miner": "int | dict",
    "kill_miner": "bool",
    "assign": "None",
    "shared_get": "Any",
    "shared_set": "None",
    "goto": "None",
    "go_home": "None",
    "sweep": "Any",
    "spiral": "Any",
    "ring": "Any",
    "mine_here": "Any",
    "nearest": "tuple[int, int] | None",
    "goto_nearest": "bool",
    "route": "list[str]",
    "goto_route": "None",
    "ore_map": "dict[tuple[int, int], str]",
    "sma": "float",
    "trend": "float",
    "sell_if": "int",
    "best_item_to_sell": "str | None",
    "moving_average": "list[float]",
    "linear_fit": "tuple[float, float]",
    "refine_all": "int",
    "wait_for_refinery": "None",
    "best_contract": "dict | None",
    "fulfill": "int",
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
        {"name": "battery", "signature": "battery()", "doc": "Return (energy, capacity)."},
        {"name": "charge", "signature": "charge()", "doc": "Recharge on a base or station."},
        {
            "name": "energy_cost",
            "signature": "energy_cost(action, arg=None)",
            "doc": "Return an action's energy cost.",
        },
        {"name": "sell", "signature": "sell()", "doc": "Sell the inventory."},
        {"name": "unload", "signature": "unload()", "doc": "Unload into the warehouse."},
        {"name": "stock", "signature": "stock()", "doc": "Return the warehouse stock."},
        {
            "name": "sell_stock",
            "signature": "sell_stock(item, amount=None)",
            "doc": "Sell warehouse items.",
        },
        {"name": "recipes", "signature": "recipes()", "doc": "Return refinery recipes."},
        {
            "name": "refine",
            "signature": "refine(recipe_id, times=1)",
            "doc": "Start a refinery job.",
        },
        {"name": "refinery", "signature": "refinery()", "doc": "Return running jobs."},
        {"name": "contracts", "signature": "contracts()", "doc": "Return open contracts."},
        {
            "name": "deliver",
            "signature": "deliver(contract_id)",
            "doc": "Deliver a contract.",
        },
        {"name": "price", "signature": "price(item)", "doc": "Return an item price."},
        {"name": "prices", "signature": "prices()", "doc": "Return all item prices."},
        {
            "name": "price_history",
            "signature": "price_history(item, n=50)",
            "doc": "Return recent price samples.",
        },
        {"name": "inventory", "signature": "inventory()", "doc": "Return the inventory."},
        {"name": "scan", "signature": "scan(radius)", "doc": "Scan for ore."},
        {"name": "stats", "signature": "stats()", "doc": "Return mining stats."},
        {"name": "buy_upgrade", "signature": "buy_upgrade(upgrade_id)", "doc": "Buy an upgrade."},
        {"name": "wait", "signature": "wait(ticks)", "doc": "Wait for ticks."},
        {"name": "tick", "signature": "tick()", "doc": "Return the current tick."},
        {"name": "events", "signature": "events()", "doc": "Return active world events."},
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


def _signature_params(signature: str, name: str) -> list[tuple[str, str | None]]:
    """Extract parameter names and defaults from a signature string."""
    text = (signature or "").strip()
    if "(" in text and ")" in text:
        inner = text[text.index("(") + 1 : text.rindex(")")]
    else:
        inner = ""
    params: list[tuple[str, str | None]] = []
    for part in inner.split(","):
        part = part.strip()
        if not part:
            continue
        default: str | None = None
        if "=" in part:
            part, default = part.split("=", 1)
            default = default.strip()
        part = part.split(":")[0].strip().lstrip("*")
        if part:
            params.append((part, default))
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
        if node.name in _PRIMITIVE_NAMES or node.name.startswith("_"):
            continue
        params = ast.unparse(node.args)
        doc = ast.get_docstring(node) or ""
        entries.append({"name": node.name, "signature": f"{node.name}({params})", "doc": doc})
    return entries


def _format_entry(entry: dict[str, Any]) -> str:
    """Format one stub function definition."""
    name = str(entry.get("name") or "")
    signature = str(entry.get("signature") or f"{name}()")
    params = _signature_params(signature, name)
    typed = ", ".join(
        f"{param}: {_PARAM_TYPES.get(param, 'Any')}" + (f" = {default}" if default else "")
        for param, default in params
    )
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
    lines.append("# --- deprecated aliases ---")
    for old_name, new_name in DEPRECATED_ALIASES.items():
        lines.append(f"def {old_name}(*args: Any, **kwargs: Any) -> Any: ...")
        lines.append(f'    """Deprecated alias for {new_name}()."""')
    lines.append("")
    lines.append("# --- minerlib ---")
    for entry in _minerlib_entries():
        lines.append(_format_entry(entry))
    lines.append("")
    lines.append("class Forecast:")
    lines.append("    def __init__(self, alpha: float = 0.3) -> None: ...")
    lines.append("    def update(self, x: float) -> float: ...")
    lines.append("    def predict(self) -> float: ...")
    lines.append("")
    lines.append("class Worker:")
    lines.append('    def __init__(self, name: str = "worker") -> None: ...')
    lines.append("    def goto(self, x: int, y: int) -> None: ...")
    lines.append("    def haul(self) -> int: ...")
    lines.append("    def step(self) -> bool: ...")
    lines.append("    def run(self, steps: int = 100) -> int: ...")
    lines.append("")
    lines.append("class MinerWorker(Worker):")
    lines.append('    def __init__(self, name: str = "miner", ore: str = "stone") -> None: ...')
    lines.append("    def step(self) -> bool: ...")
    lines.append("")
    lines.append("class HaulerWorker(Worker):")
    lines.append('    def __init__(self, name: str = "hauler", key: str = "work") -> None: ...')
    lines.append("    def step(self) -> bool: ...")
    lines.append("")
    lines.append("class Fleet:")
    lines.append("    def spawn(self, script: str) -> Any: ...")
    lines.append("    def kill_all(self) -> list[int]: ...")
    lines.append("    def broadcast(self, key: str, value: Any) -> None: ...")
    lines.append("    def gather(self, key: str) -> Any: ...")
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
