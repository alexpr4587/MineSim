"""Engine commands (miner actions with tick costs)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from digscript.core.direction import Direction
from digscript.core.events import MineAttempted, Moved, OreMined, Sold, UpgradeBought
from digscript.core.rng import mix64, unit

__all__ = [
    "BuyUpgrade",
    "Inventory",
    "Mine",
    "Move",
    "Peek",
    "Position",
    "Scan",
    "Sell",
    "Stats",
    "Wait",
]

_ZERO_COST_NAMES = {"Peek", "Position", "Inventory", "Stats"}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _resolve_context(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Resolve engine/miner/content/world from flexible cost arguments."""
    engine = kwargs.get("engine")
    miner = kwargs.get("miner")
    content = kwargs.get("content")
    world = kwargs.get("world")
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, "miner") and hasattr(arg, "world"):
            engine = arg
        elif hasattr(arg, "capacity") and hasattr(arg, "inventory"):
            miner = arg
        elif hasattr(arg, "config") and hasattr(arg, "ores"):
            content = arg
        elif hasattr(arg, "tile_at") and hasattr(arg, "generator"):
            world = arg
    if engine is not None:
        if miner is None:
            miner = _get(engine, "miner")
        if world is None:
            world = _get(engine, "world")
        if content is None:
            content = _get(engine, "content")
    if content is not None and miner is None and hasattr(content, "config"):
        miner = None
    return {"engine": engine, "miner": miner, "content": content, "world": world}


def _publish(engine: Any, event: Any) -> None:
    bus = _get(engine, "events") or _get(engine, "event_bus") or _get(engine, "bus")
    if bus is not None and hasattr(bus, "publish"):
        bus.publish(event)


def _tick(engine: Any) -> int:
    return int(_get(engine, "tick", 0) or 0)


def _seed(engine: Any, content: Any, world: Any) -> int:
    seed = _get(engine, "seed")
    if seed is not None:
        return int(seed)
    seed = _get(world, "seed")
    if seed is not None:
        return int(seed)
    generator = _get(world, "generator")
    seed = _get(generator, "seed")
    if seed is not None:
        return int(seed)
    config = _get(content, "config")
    seed = _get(config, "seed_default")
    if seed is not None:
        return int(seed)
    return 0


def _is_unlocked(engine: Any, content: Any, ore_id: str) -> bool:
    view = _get(engine, "progression_view") or _get(engine, "progression") or _get(engine, "view")
    checker = _get(view, "is_ore_unlocked")
    if callable(checker):
        return bool(checker(ore_id))
    ore = None
    if content is not None:
        try:
            ore = content.get_ore(ore_id)
        except Exception:
            ore = None
    if ore is None:
        return True
    return ore.unlocked_by is None


def _is_upgrade_unlocked(engine: Any, content: Any, upgrade_id: str) -> bool:
    view = _get(engine, "progression_view") or _get(engine, "progression") or _get(engine, "view")
    checker = _get(view, "is_upgrade_unlocked")
    if callable(checker):
        return bool(checker(upgrade_id))
    upgrade = None
    if content is not None:
        try:
            upgrade = content.get_upgrade(upgrade_id)
        except Exception:
            upgrade = None
    if upgrade is None:
        return True
    return upgrade.unlocked_by is None


def _get_ore(content: Any, ore_id: str) -> Any:
    return content.get_ore(ore_id)


def _mine_failure(engine: Any) -> dict[str, Any] | None:
    """Return a failure result for Mine, or None if the mine can proceed."""
    ctx = _resolve_context(engine)
    miner = ctx["miner"]
    world = ctx["world"]
    content = ctx["content"]
    if miner is None or world is None or content is None:
        return {"ok": False, "reason": "nothing_to_mine"}
    tile = world.tile_at(miner.x, miner.y, _tick(engine))
    if tile.is_base or tile.depleted or tile.ore_id is None:
        return {"ok": False, "reason": "nothing_to_mine"}
    ore_id = tile.ore_id
    if not _is_unlocked(engine, content, ore_id):
        return {"ok": False, "reason": "locked_ore"}
    ore = _get_ore(content, ore_id)
    if miner.tool_tier < ore.tier:
        return {"ok": False, "reason": "tool_too_weak"}
    inventory_size = getattr(miner, "inventory_size", None)
    if inventory_size is None:
        inventory_size = sum(miner.inventory.values())
    if inventory_size >= miner.capacity:
        return {"ok": False, "reason": "inventory_full"}
    return None


@dataclass(frozen=True, slots=True)
class Move:
    """Move one tile in ``direction``."""

    direction: Direction = Direction.NORTH

    def __post_init__(self) -> None:
        object.__setattr__(self, "direction", Direction.parse(self.direction))

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        if miner is not None:
            return int(miner.move_ticks)
        content = ctx["content"]
        if content is not None:
            return int(content.config.move_ticks)
        return 4

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        miner.x += self.direction.dx
        miner.y += self.direction.dy
        miner.facing = self.direction
        miner.stats.tiles_moved += 1
        _publish(engine, Moved(x=miner.x, y=miner.y, direction=self.direction.name.lower()))
        return {
            "ok": True,
            "x": miner.x,
            "y": miner.y,
            "position": [miner.x, miner.y],
            "direction": self.direction.name.lower(),
            "facing": self.direction.name.lower(),
        }


@dataclass(frozen=True, slots=True)
class Mine:
    """Mine the tile the miner stands on."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        engine = ctx["engine"]
        miner = ctx["miner"]
        content = ctx["content"]
        world = ctx["world"]
        if miner is None or world is None or content is None:
            return 0
        if _mine_failure(engine) is not None:
            return 0
        ore = _get_ore(content, world.tile_at(miner.x, miner.y, _tick(engine)).ore_id)
        power = max(1, int(miner.tool_power))
        return int(math.ceil(ore.hardness * content.config.mine_tick_base / power))

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        world = engine.world
        content = engine.content
        failure = _mine_failure(engine)
        if failure is not None:
            return failure
        ore_id = world.tile_at(miner.x, miner.y, _tick(engine)).ore_id
        ore = _get_ore(content, ore_id)
        attempt_counter = int(_get(engine, "attempt_counter", 0) or 0)
        seed = _seed(engine, content, world)
        roll = unit(mix64(seed, _tick(engine), miner.x, miner.y, attempt_counter))
        try:
            engine.attempt_counter = attempt_counter + 1
        except Exception:
            pass
        success = roll < ore.mine_probability
        stats = miner.stats
        record = getattr(stats, "record_attempt", None)
        if callable(record):
            record(ore_id, success)
        else:
            stats.attempts[ore_id] = stats.attempts.get(ore_id, 0) + 1
            if success:
                stats.successes[ore_id] = stats.successes.get(ore_id, 0) + 1
                stats.total_mined += 1
        _publish(engine, MineAttempted(ore_id=ore_id, success=success))
        if not success:
            return {
                "ok": False,
                "reason": "miss",
                "ore": ore_id,
                "ore_id": ore_id,
                "success": False,
            }
        miner.add_item(ore_id, 1)
        world.mine_tile(miner.x, miner.y, _tick(engine))
        _publish(engine, OreMined(ore_id=ore_id, amount=1))
        return {
            "ok": True,
            "ore": ore_id,
            "ore_id": ore_id,
            "amount": 1,
            "success": True,
        }


@dataclass(frozen=True, slots=True)
class Peek:
    """Look at the tile the miner stands on."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        tile = engine.world.tile_at(miner.x, miner.y, _tick(engine))
        if tile.is_base or tile.depleted or tile.ore_id is None:
            value: str | None = None
        elif not _is_unlocked(engine, engine.content, tile.ore_id):
            value = "unknown"
        else:
            value = tile.ore_id
        return {"ok": True, "ore": value, "ore_id": value}


@dataclass(frozen=True, slots=True)
class Scan:
    """Scan for ore within ``radius`` tiles (capped by the miner)."""

    radius: int = 0

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        content = ctx["content"]
        effective = int(self.radius)
        if miner is not None:
            effective = min(effective, int(miner.scan_radius))
        effective = max(0, effective)
        per_radius = int(content.config.scan_ticks_per_radius) if content is not None else 1
        return 1 + per_radius * effective

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        effective = min(max(0, int(self.radius)), max(0, int(miner.scan_radius)))
        tiles: list[list[Any]] = []
        for dy in range(-effective, effective + 1):
            for dx in range(-effective, effective + 1):
                tile = engine.world.tile_at(miner.x + dx, miner.y + dy, _tick(engine))
                if tile.ore_id is None:
                    continue
                label = (
                    tile.ore_id if _is_unlocked(engine, engine.content, tile.ore_id) else "unknown"
                )
                tiles.append([dx, dy, label])
        return {
            "ok": True,
            "radius": effective,
            "requested_radius": int(self.radius),
            "tiles": tiles,
            "results": tiles,
            "scan": tiles,
        }


@dataclass(frozen=True, slots=True)
class Sell:
    """Sell the whole inventory at the base."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        world = ctx["world"]
        content = ctx["content"]
        if miner is not None and world is not None:
            tile = world.tile_at(miner.x, miner.y, _tick(ctx["engine"]))
            if not tile.is_base:
                return 0
        if content is not None:
            return int(content.config.sell_ticks)
        return 2

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        tile = engine.world.tile_at(miner.x, miner.y, _tick(engine))
        if not tile.is_base:
            return {"ok": False, "reason": "not_on_base"}
        items = dict(miner.inventory)
        gained = 0
        for ore_id, count in items.items():
            gained += engine.content.get_ore(ore_id).base_value * count
        miner.money += gained
        miner.inventory.clear()
        if gained > 0:
            miner.stats.total_earned += gained
            miner.stats.sales += 1
            _publish(engine, Sold(money=gained, items=dict(items)))
        return {
            "ok": True,
            "money": gained,
            "earned": gained,
            "money_earned": gained,
            "items": items,
            "sold": dict(items),
            "total_money": miner.money,
            "balance": miner.money,
        }


@dataclass(frozen=True, slots=True)
class BuyUpgrade:
    """Buy the next level of upgrade ``id``."""

    id: str = ""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        content = engine.content
        upgrades = getattr(miner, "upgrades", None)
        if upgrades is None:
            upgrades = {}
            try:
                miner.upgrades = upgrades
            except Exception:
                pass
        level = int(upgrades.get(self.id, 0))
        try:
            upgrade = content.get_upgrade(self.id)
        except Exception:
            return {"ok": False, "reason": "unknown_upgrade", "id": self.id, "upgrade": self.id}
        if not _is_upgrade_unlocked(engine, content, self.id):
            return {"ok": False, "reason": "locked_upgrade", "id": self.id, "upgrade": self.id}
        if level >= upgrade.max_level:
            return {
                "ok": False,
                "reason": "max_level",
                "id": self.id,
                "upgrade": self.id,
                "level": level,
            }
        if level >= len(upgrade.costs):
            return {
                "ok": False,
                "reason": "max_level",
                "id": self.id,
                "upgrade": self.id,
                "level": level,
            }
        cost = int(upgrade.costs[level])
        if miner.money < cost:
            return {
                "ok": False,
                "reason": "insufficient_funds",
                "id": self.id,
                "upgrade": self.id,
                "level": level,
                "cost": cost,
                "money": miner.money,
            }
        miner.money -= cost
        new_level = level + 1
        upgrades[self.id] = new_level
        for stat, delta in upgrade.stat_changes().items():
            if stat == "move_ticks":
                miner.move_ticks = max(1, int(miner.move_ticks) + int(delta))
            elif stat == "capacity":
                miner.capacity = max(0, int(miner.capacity) + int(delta))
            elif stat == "tool_power":
                miner.tool_power = max(1, int(miner.tool_power) + int(delta))
            elif stat == "tool_tier":
                miner.tool_tier = max(0, int(miner.tool_tier) + int(delta))
            elif stat == "scan_radius":
                miner.scan_radius = max(0, int(miner.scan_radius) + int(delta))
            elif hasattr(miner, stat):
                setattr(miner, stat, int(getattr(miner, stat)) + int(delta))
        _publish(engine, UpgradeBought(id=self.id, level=new_level))
        return {
            "ok": True,
            "id": self.id,
            "upgrade": self.id,
            "level": new_level,
            "cost": cost,
            "money": miner.money,
            "total_money": miner.money,
            "balance": miner.money,
        }


@dataclass(frozen=True, slots=True)
class Wait:
    """Wait for ``ticks`` ticks."""

    ticks: int = 0

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return max(0, int(self.ticks))

    def execute(self, engine: Any) -> dict[str, Any]:
        return {"ok": True, "ticks": int(self.ticks), "waited": int(self.ticks)}


@dataclass(frozen=True, slots=True)
class Position:
    """Return the miner position."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        return {
            "ok": True,
            "x": miner.x,
            "y": miner.y,
            "position": [miner.x, miner.y],
        }


@dataclass(frozen=True, slots=True)
class Inventory:
    """Return the miner inventory."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any) -> dict[str, Any]:
        miner = engine.miner
        inventory = dict(miner.inventory)
        return {
            "ok": True,
            "inventory": inventory,
            "items": dict(inventory),
            "money": miner.money,
        }


@dataclass(frozen=True, slots=True)
class Stats:
    """Return mining stats."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any) -> dict[str, Any]:
        stats = engine.miner.stats
        attempts = dict(getattr(stats, "attempts", {}) or {})
        successes = dict(getattr(stats, "successes", {}) or {})
        per_ore: dict[str, Any] = {}
        for ore_id in sorted(set(attempts) | set(successes)):
            per_ore[ore_id] = {
                "attempts": attempts.get(ore_id, 0),
                "successes": successes.get(ore_id, 0),
            }
        hybrid: dict[str, Any] = dict(per_ore)
        hybrid["attempts"] = attempts
        hybrid["successes"] = successes
        hybrid["total_mined"] = int(getattr(stats, "total_mined", 0))
        hybrid["total_earned"] = int(getattr(stats, "total_earned", 0))
        hybrid["tiles_moved"] = int(getattr(stats, "tiles_moved", 0))
        hybrid["sales"] = int(getattr(stats, "sales", 0))
        return {
            "ok": True,
            "stats": hybrid,
            "attempts": attempts,
            "successes": successes,
            "total_mined": hybrid["total_mined"],
            "total_earned": hybrid["total_earned"],
            "tiles_moved": hybrid["tiles_moved"],
            "sales": hybrid["sales"],
        }
