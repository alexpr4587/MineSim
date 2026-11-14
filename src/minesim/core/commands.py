"""Engine commands (miner actions with tick costs)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from minesim.core.direction import Direction
from minesim.core.events import (
    ContractDelivered,
    EstimateSubmitted,
    MineAttempted,
    Moved,
    OreMined,
    RefineStarted,
    Sold,
    StockSold,
    Unloaded,
    UpgradeBought,
)
from minesim.core.rng import mix64, unit

__all__ = [
    "Biome",
    "BuyUpgrade",
    "Distance",
    "Inspect",
    "Inventory",
    "Mine",
    "Move",
    "OreInfo",
    "Peek",
    "Position",
    "Price",
    "PriceHistory",
    "Prices",
    "Recipes",
    "Refine",
    "RefineryStatus",
    "Contracts",
    "Deliver",
    "RemoveDrone",
    "Scan",
    "Sell",
    "SellStock",
    "SpawnDrone",
    "Stats",
    "Stock",
    "SubmitEstimate",
    "Tick",
    "Unload",
    "Wait",
]

_ZERO_COST_NAMES = {
    "Biome",
    "Distance",
    "Inspect",
    "Inventory",
    "OreInfo",
    "Peek",
    "Position",
    "Price",
    "PriceHistory",
    "Prices",
    "Recipes",
    "Refine",
    "RefineryStatus",
    "Contracts",
    "Deliver",
    "Stats",
    "Stock",
    "SubmitEstimate",
    "Tick",
}


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


def _drone(engine: Any, drone: Any = None) -> Any:
    """Return the acting drone (or drone 0 for legacy direct calls)."""
    if drone is not None:
        return drone
    return _get(engine, "miner")


def _drone_id(drone: Any) -> int:
    return int(_get(drone, "id", 0) or 0)


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


def _warehouse(engine: Any) -> Any:
    return _get(engine, "warehouse")


def _market(engine: Any) -> Any:
    return _get(engine, "market")


def _catalog(engine: Any) -> Any:
    return _get(engine, "catalog")


def _on_base(engine: Any, miner: Any) -> bool:
    world = _get(engine, "world")
    if miner is None or world is None:
        return False
    try:
        return bool(world.tile_at(miner.x, miner.y, _tick(engine)).is_base)
    except Exception:
        return False


def _item_unlocked(engine: Any, item_id: str) -> bool:
    catalog = _catalog(engine)
    if catalog is None:
        return False
    try:
        item = catalog.get(item_id)
    except Exception:
        return False
    if item.kind == "ore":
        return _is_unlocked(engine, _get(engine, "content"), item_id)
    if item.unlocked_by is None:
        return True
    view = _get(engine, "progression_view") or _get(engine, "progression")
    checker = _get(view, "is_product_unlocked")
    if callable(checker):
        return bool(checker(item_id))
    return False


def _market_price(engine: Any, item_id: str) -> float | None:
    market = _market(engine)
    catalog = _catalog(engine)
    if market is None or catalog is None:
        return None
    try:
        return float(market.price(item_id))
    except Exception:
        return None


def _round_price(value: float | None) -> float | None:
    return None if value is None else round(float(value), 2)


def _mine_failure(engine: Any, drone: Any = None) -> dict[str, Any] | None:
    """Return a failure result for Mine, or None if the mine can proceed."""
    ctx = _resolve_context(engine)
    miner = _drone(engine, drone) if drone is not None else ctx["miner"]
    world = ctx["world"]
    content = ctx["content"]
    if miner is None or world is None or content is None:
        return {"ok": False, "reason": "nothing_to_mine", "ore_id": None}
    tile = world.tile_at(miner.x, miner.y, _tick(engine))
    if tile.is_base or tile.depleted or tile.ore_id is None:
        return {"ok": False, "reason": "nothing_to_mine", "ore_id": None}
    ore_id = tile.ore_id
    if not _is_unlocked(engine, content, ore_id):
        return {"ok": False, "reason": "locked_ore", "ore_id": ore_id}
    ore = _get_ore(content, ore_id)
    if miner.tool_tier < ore.tier:
        return {"ok": False, "reason": "tool_too_weak", "ore_id": ore_id}
    inventory_size = getattr(miner, "inventory_size", None)
    if inventory_size is None:
        inventory_size = sum(miner.inventory.values())
    if inventory_size >= miner.capacity:
        return {"ok": False, "reason": "inventory_full", "ore_id": ore_id}
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

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        miner.x += self.direction.dx
        miner.y += self.direction.dy
        miner.facing = self.direction
        miner.stats.tiles_moved += 1
        _publish(
            engine,
            Moved(
                drone_id=_drone_id(miner),
                x=miner.x,
                y=miner.y,
                direction=self.direction.name.lower(),
            ),
        )
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
        if _mine_failure(engine, miner) is not None:
            return 0
        ore = _get_ore(content, world.tile_at(miner.x, miner.y, _tick(engine)).ore_id)
        power = max(1, int(miner.tool_power))
        return int(math.ceil(ore.hardness * content.config.mine_tick_base / power))

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        world = engine.world
        content = engine.content
        failure = _mine_failure(engine, miner)
        if failure is not None:
            _publish(
                engine,
                MineAttempted(
                    drone_id=_drone_id(miner),
                    ore_id=failure.get("ore_id"),
                    success=False,
                    reason=str(failure.get("reason")),
                ),
            )
            return failure
        ore_id = world.tile_at(miner.x, miner.y, _tick(engine)).ore_id
        ore = _get_ore(content, ore_id)
        attempt_counter = int(_get(engine, "attempt_counter", 0) or 0)
        seed = _seed(engine, content, world)
        dice = (seed, _tick(engine), miner.x, miner.y, attempt_counter)
        drone_id = _drone_id(miner)
        if drone_id != 0:
            dice = (*dice, drone_id)
        roll = unit(mix64(*dice))
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
        _publish(
            engine,
            MineAttempted(
                drone_id=drone_id,
                ore_id=ore_id,
                success=success,
                reason=None if success else "miss",
            ),
        )
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
        _publish(engine, OreMined(drone_id=drone_id, ore_id=ore_id, amount=1))
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

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
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

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
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

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        if not _on_base(engine, miner):
            return {"ok": False, "reason": "not_on_base"}
        items = {item_id: int(count) for item_id, count in miner.inventory.items() if count > 0}
        market = _market(engine)
        catalog = _catalog(engine)
        gained = 0
        units = 0
        weighted_index = 0.0
        for item_id, count in sorted(items.items()):
            if market is not None:
                weighted_index += float(market.index(item_id)) * count
                gained += int(market.sell(item_id, count))
            elif catalog is not None:
                gained += int(catalog.base_value(item_id)) * count
            units += count
        avg_index = weighted_index / units if units else 1.0
        miner.money += gained
        miner.inventory.clear()
        if gained > 0:
            miner.stats.total_earned += gained
            miner.stats.sales += 1
            _publish(
                engine,
                Sold(
                    drone_id=_drone_id(miner),
                    money=gained,
                    items=dict(items),
                    avg_index=avg_index,
                ),
            )
        return {
            "ok": True,
            "money": gained,
            "earned": gained,
            "money_earned": gained,
            "items": items,
            "sold": dict(items),
            "avg_index": avg_index,
            "total_money": miner.money,
            "balance": miner.money,
        }


@dataclass(frozen=True, slots=True)
class Unload:
    """Move the drone inventory into the base warehouse."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        if miner is not None and _on_base(ctx["engine"], miner):
            return 1
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        if not _on_base(engine, miner):
            return {"ok": False, "reason": "not_on_base"}
        warehouse = _warehouse(engine)
        if warehouse is None:
            return {"ok": False, "reason": "no_warehouse"}
        moved: dict[str, int] = {}
        for item_id, count in sorted(dict(miner.inventory).items()):
            count = int(count)
            if count <= 0:
                continue
            accepted = int(warehouse.add(item_id, count))
            if accepted <= 0:
                continue
            moved[item_id] = accepted
            remaining = count - accepted
            if remaining > 0:
                miner.inventory[item_id] = remaining
            else:
                miner.inventory.pop(item_id, None)
        if moved:
            _publish(engine, Unloaded(items=dict(moved)))
        return {
            "ok": True,
            "moved": dict(moved),
            "left": dict(miner.inventory),
            "capacity": int(getattr(warehouse, "capacity", 0)),
            "total": int(warehouse.total()),
        }


@dataclass(frozen=True, slots=True)
class SellStock:
    """Sell items from the warehouse at market prices."""

    item: str = ""
    amount: int | None = None

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        content = ctx["content"]
        if miner is None or not _on_base(ctx["engine"], miner):
            return 0
        if content is not None:
            return int(content.config.sell_ticks)
        return 2

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        if not _on_base(engine, miner):
            return {"ok": False, "reason": "not_on_base"}
        warehouse = _warehouse(engine)
        if warehouse is None:
            return {"ok": False, "reason": "no_warehouse"}
        catalog = _catalog(engine)
        if catalog is None:
            return {"ok": False, "reason": "no_catalog"}
        try:
            catalog.get(self.item)
        except Exception:
            return {"ok": False, "reason": "unknown_item", "item": self.item}
        stock = int(warehouse.count(self.item))
        requested = stock if self.amount is None else max(0, int(self.amount))
        quantity = min(requested, stock)
        market = _market(engine)
        index = float(market.index(self.item)) if market is not None else 1.0
        if quantity <= 0:
            return {
                "ok": True,
                "item": self.item,
                "amount": 0,
                "money": 0,
                "avg_index": index,
                "stock": stock,
                "total_money": miner.money,
                "balance": miner.money,
            }
        if market is not None:
            money = int(market.sell(self.item, quantity))
        else:
            money = int(catalog.base_value(self.item)) * quantity
        warehouse.remove(self.item, quantity)
        miner.money += money
        if money > 0:
            miner.stats.total_earned += money
            miner.stats.sales += 1
            _publish(
                engine,
                StockSold(item=self.item, amount=quantity, money=money),
            )
        return {
            "ok": True,
            "item": self.item,
            "amount": quantity,
            "money": money,
            "earned": money,
            "avg_index": index,
            "stock": int(warehouse.count(self.item)),
            "total_money": miner.money,
            "balance": miner.money,
        }


@dataclass(frozen=True, slots=True)
class Recipes:
    """Return every refinery recipe and its unlock state."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        content = _get(engine, "content")
        recipes = getattr(content, "recipes", {}) if content is not None else {}
        view = _get(engine, "progression_view") or _get(engine, "progression")
        checker = _get(view, "is_recipe_unlocked")
        result: dict[str, Any] = {}
        for recipe_id, recipe in recipes.items():
            unlocked = recipe.unlocked_by is None
            if callable(checker):
                try:
                    unlocked = bool(checker(str(recipe_id)))
                except Exception:
                    pass
            result[str(recipe_id)] = {
                "id": str(recipe_id),
                "name": str(getattr(recipe, "name", recipe_id)),
                "inputs": dict(getattr(recipe, "inputs", {}) or {}),
                "outputs": dict(getattr(recipe, "outputs", {}) or {}),
                "ticks": int(getattr(recipe, "ticks", 0)),
                "unlocked": bool(unlocked),
                "unlocked_by": getattr(recipe, "unlocked_by", None),
            }
        return {"ok": True, "recipes": result}


@dataclass(frozen=True, slots=True)
class Refine:
    """Start ``times`` runs of refinery recipe ``recipe_id`` at the base."""

    recipe_id: str = ""
    times: int = 1

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        content = ctx["content"]
        if miner is None or not _on_base(ctx["engine"], miner):
            return 0
        if content is not None:
            return int(getattr(content.config, "refine_ticks", 2))
        return 2

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        if not _on_base(engine, miner):
            return {"ok": False, "reason": "not_on_base"}
        refinery = _get(engine, "refinery")
        if refinery is None:
            return {"ok": False, "reason": "no_refinery"}
        warehouse = _warehouse(engine)
        if warehouse is None:
            return {"ok": False, "reason": "no_warehouse"}
        try:
            job = refinery.start(self.recipe_id, self.times, warehouse, _tick(engine))
        except KeyError:
            return {"ok": False, "reason": "unknown_recipe", "recipe": self.recipe_id}
        except ValueError as exc:
            return {"ok": False, "reason": str(exc), "recipe": self.recipe_id}
        _publish(
            engine,
            RefineStarted(recipe=str(self.recipe_id), times=int(job.times)),
        )
        return {
            "ok": True,
            "recipe": str(self.recipe_id),
            "times": int(job.times),
            "duration": int(job.duration),
            "finish_tick": int(job.finish_tick),
            "inputs": dict(job.inputs),
            "outputs": dict(job.outputs),
        }


@dataclass(frozen=True, slots=True)
class RefineryStatus:
    """Return every running refinery job."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        refinery = _get(engine, "refinery")
        if refinery is None:
            return {"ok": True, "jobs": [], "slots": 0}
        return {
            "ok": True,
            "jobs": refinery.status(),
            "slots": int(getattr(refinery, "slots", 0)),
            "job_count": len(getattr(refinery, "jobs", [])),
        }


@dataclass(frozen=True, slots=True)
class Contracts:
    """Return every open delivery contract."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        board = _get(engine, "contracts")
        if board is None:
            return {"ok": True, "contracts": [], "slots": 0}
        return {
            "ok": True,
            "contracts": board.status(),
            "slots": int(getattr(board, "slots", 0)),
            "count": len(getattr(board, "contracts", [])),
        }


@dataclass(frozen=True, slots=True)
class Deliver:
    """Deliver contract ``contract_id`` at the base and collect the reward."""

    contract_id: int = 0

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        content = ctx["content"]
        if miner is None or not _on_base(ctx["engine"], miner):
            return 0
        if content is not None:
            return int(getattr(content.config, "deliver_ticks", 2))
        return 2

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        if not _on_base(engine, miner):
            return {"ok": False, "reason": "not_on_base"}
        board = _get(engine, "contracts")
        if board is None:
            return {"ok": False, "reason": "no_contracts"}
        warehouse = _warehouse(engine)
        if warehouse is None:
            return {"ok": False, "reason": "no_warehouse"}
        try:
            reward = board.deliver(self.contract_id, warehouse)
        except KeyError:
            return {"ok": False, "reason": "unknown_contract", "id": int(self.contract_id)}
        except ValueError as exc:
            return {"ok": False, "reason": str(exc), "id": int(self.contract_id)}
        miner.money += int(reward)
        miner.stats.total_earned += int(reward)
        _publish(
            engine,
            ContractDelivered(id=int(self.contract_id), reward=int(reward)),
        )
        return {
            "ok": True,
            "id": int(self.contract_id),
            "reward": int(reward),
            "money": int(miner.money),
            "total_money": int(miner.money),
            "balance": int(miner.money),
        }


@dataclass(frozen=True, slots=True)
class Stock:
    """Return the contents and capacity of the warehouse."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        warehouse = _warehouse(engine)
        if warehouse is None:
            return {"ok": False, "reason": "no_warehouse"}
        items = {
            str(item_id): int(count)
            for item_id, count in sorted(dict(warehouse.items).items())
            if int(count) > 0
        }
        return {
            "ok": True,
            "items": items,
            "stock": dict(items),
            "capacity": int(getattr(warehouse, "capacity", 0)),
            "used": int(warehouse.total()),
            "total": int(warehouse.total()),
            "free": int(getattr(warehouse, "free", 0)),
        }


@dataclass(frozen=True, slots=True)
class Price:
    """Return the current market price of ``item``."""

    item: str = ""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        if not _item_unlocked(engine, self.item):
            return {"ok": True, "item": self.item, "price": None}
        price = _market_price(engine, self.item)
        return {"ok": True, "item": self.item, "price": _round_price(price)}


@dataclass(frozen=True, slots=True)
class Prices:
    """Return the current market prices of every unlocked item."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        catalog = _catalog(engine)
        prices: dict[str, float | None] = {}
        if catalog is not None:
            for item_id in catalog.ids:
                if not _item_unlocked(engine, item_id):
                    continue
                prices[item_id] = _round_price(_market_price(engine, item_id))
        return {"ok": True, "prices": prices}


@dataclass(frozen=True, slots=True)
class PriceHistory:
    """Return the recent price samples of ``item``."""

    item: str = ""
    n: int = 50

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        if not _item_unlocked(engine, self.item):
            return {"ok": True, "item": self.item, "history": None}
        market = _market(engine)
        if market is None:
            return {"ok": True, "item": self.item, "history": []}
        try:
            samples = market.history(self.item, self.n)
        except Exception:
            return {"ok": True, "item": self.item, "history": None}
        return {
            "ok": True,
            "item": self.item,
            "history": [_round_price(float(value)) for value in samples],
        }


@dataclass(frozen=True, slots=True)
class BuyUpgrade:
    """Buy the next level of upgrade ``id``."""

    id: str = ""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
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
            elif stat == "warehouse_capacity":
                warehouse = _warehouse(engine)
                if warehouse is not None:
                    warehouse.capacity = max(0, int(warehouse.capacity) + int(delta))
            elif stat == "furnace_slots":
                refinery = _get(engine, "refinery")
                if refinery is not None:
                    refinery.slots = max(1, int(refinery.slots) + int(delta))
            elif stat == "contract_slots":
                board = _get(engine, "contracts")
                if board is not None:
                    board.slots = max(1, int(board.slots) + int(delta))
            elif hasattr(miner, stat):
                setattr(miner, stat, int(getattr(miner, stat)) + int(delta))
        _publish(
            engine,
            UpgradeBought(
                drone_id=_drone_id(miner) if drone is not None else 0,
                id=self.id,
                level=new_level,
            ),
        )
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

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        return {"ok": True, "ticks": int(self.ticks), "waited": int(self.ticks)}


@dataclass(frozen=True, slots=True)
class SpawnDrone:
    """Buy a new drone; costs ``drone_costs`` for the next extra drone."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        drones = _get(engine, "drones") or {}
        max_drones = int(_get(engine, "max_drones", 1) or 1)
        if len(drones) >= max_drones:
            return {"ok": False, "reason": "no_slot"}
        content = _get(engine, "content")
        config = _get(content, "config")
        costs = list(_get(config, "drone_costs", []) or [])
        extra = max(0, len(drones) - 1)
        if extra >= len(costs):
            return {"ok": False, "reason": "no_slot"}
        cost = int(costs[extra])
        player = _get(engine, "player_stats")
        money = int(_get(player, "money", 0) or 0)
        if money < cost:
            return {
                "ok": False,
                "reason": "not_enough_money",
                "cost": cost,
                "money": money,
            }
        try:
            player.money = money - cost
        except Exception:
            pass
        new_drone = engine.spawn_drone()
        return {"ok": True, "drone_id": int(new_drone.id), "cost": cost}


@dataclass(frozen=True, slots=True)
class RemoveDrone:
    """Remove drone ``id`` from the fleet (never drone 0)."""

    id: int = 0

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        target = int(self.id)
        if target == 0:
            return {"ok": False, "reason": "cannot_remove_main", "drone_id": target}
        removed = engine.remove_drone(target)
        if not removed:
            return {"ok": False, "reason": "unknown_drone", "drone_id": target}
        return {"ok": True, "drone_id": target}


@dataclass(frozen=True, slots=True)
class Position:
    """Return the miner position."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
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

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
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

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        stats = _drone(engine, drone).stats
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


@dataclass(frozen=True, slots=True)
class Tick:
    """Return the current game tick."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        return {"ok": True, "tick": _tick(engine)}


@dataclass(frozen=True, slots=True)
class Distance:
    """Return the Chebyshev distance from the base at ``(0, 0)``."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        distance = max(abs(int(miner.x)), abs(int(miner.y)))
        return {"ok": True, "distance": distance}


@dataclass(frozen=True, slots=True)
class Biome:
    """Return the id of the biome under the miner."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        tile = engine.world.tile_at(miner.x, miner.y, _tick(engine))
        return {"ok": True, "biome": tile.biome_id}


@dataclass(frozen=True, slots=True)
class OreInfo:
    """Return public information about ore ``ore_id`` (never its probability)."""

    ore_id: str = ""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        content = engine.content
        try:
            ore = _get_ore(content, self.ore_id)
        except Exception:
            return {"ok": True, "ore_id": self.ore_id, "info": None}
        if not _is_unlocked(engine, content, self.ore_id):
            return {"ok": True, "ore_id": self.ore_id, "info": None}
        info = {
            "id": ore.id,
            "name": ore.name,
            "tier": int(ore.tier),
            "hardness": int(ore.hardness),
            "base_value": int(ore.base_value),
            "regen_ticks": int(ore.regen_ticks),
        }
        return {"ok": True, "ore_id": self.ore_id, "info": info}


@dataclass(frozen=True, slots=True)
class Inspect:
    """Describe whether the current tile can be mined and when it regrows."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        world = engine.world
        content = engine.content
        tick = _tick(engine)
        tile = world.tile_at(miner.x, miner.y, tick)
        if tile.ore_id is None:
            ore = None
        elif _is_unlocked(engine, content, tile.ore_id):
            ore = tile.ore_id
        else:
            ore = "unknown"
        regrows_in: int | None = None
        if tile.depleted:
            delta = getattr(world, "delta", None)
            entry = delta.get((miner.x, miner.y)) if isinstance(delta, dict) else None
            if entry is not None and entry[1] is not None:
                regrows_in = max(0, int(entry[1]) - tick)
        failure = _mine_failure(engine, miner)
        return {
            "ok": True,
            "inspect": {
                "ore": ore,
                "mineable": failure is None,
                "reason": failure.get("reason") if failure is not None else None,
                "regrows_in": regrows_in,
            },
        }


@dataclass(frozen=True, slots=True)
class SubmitEstimate:
    """Submit an estimate for the mining probability of ``ore_id``."""

    ore_id: str = ""
    p: float = 0.0

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, drone: Any = None) -> dict[str, Any]:
        miner = _drone(engine, drone)
        content = engine.content
        try:
            ore = _get_ore(content, self.ore_id)
        except Exception:
            return {
                "ok": False,
                "reason": "unknown_ore",
                "ore_id": self.ore_id,
                "attempts": 0,
            }
        stats = getattr(miner, "stats", None)
        attempts_by_ore = getattr(stats, "attempts", {}) if stats is not None else {}
        attempts = int(attempts_by_ore.get(self.ore_id, 0))
        if attempts < 100:
            return {
                "ok": False,
                "reason": "not_enough_data",
                "ore_id": self.ore_id,
                "attempts": attempts,
            }
        estimates = getattr(miner, "estimates", None)
        if not isinstance(estimates, dict):
            estimates = {}
            try:
                miner.estimates = estimates
            except Exception:
                pass
        used = int(estimates.get(self.ore_id, 0))
        if used >= 3:
            return {
                "ok": False,
                "reason": "limit_reached",
                "ore_id": self.ore_id,
                "attempts": attempts,
                "submissions": used,
            }
        estimates[self.ore_id] = used + 1
        p = float(self.p)
        error = abs(p - float(ore.mine_probability))
        close = error <= 0.05
        _publish(
            engine,
            EstimateSubmitted(
                ore_id=self.ore_id,
                p=p,
                error=error,
                attempts=attempts,
                good=close,
            ),
        )
        return {"ok": True, "close": close}
