"""Engine commands (miner actions with tick costs)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from minesim.core.direction import Direction
from minesim.core.events import (
    Charged,
    ContractDelivered,
    EstimateSubmitted,
    LayerChanged,
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
    "Ascend",
    "Battery",
    "Biome",
    "BuyUpgrade",
    "Charge",
    "Descend",
    "Distance",
    "EnergyCost",
    "Events",
    "Inspect",
    "Inventory",
    "Layer",
    "Layers",
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
    "MinerId",
    "Miners",
    "RemoveMiner",
    "Scan",
    "Sell",
    "SellStock",
    "SpawnMiner",
    "Stats",
    "Stock",
    "SubmitEstimate",
    "Tick",
    "Unload",
    "Wait",
]

_ZERO_COST_NAMES = {
    "Battery",
    "Biome",
    "Distance",
    "EnergyCost",
    "Layer",
    "Layers",
    "Events",
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
    "MinerId",
    "Miners",
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


def _miner(engine: Any, miner: Any = None) -> Any:
    """Return the acting miner (or miner 0 for legacy direct calls)."""
    if miner is not None:
        return miner
    return _get(engine, "miner")


def _miner_id(miner: Any) -> int:
    return int(_get(miner, "id", 0) or 0)


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


def _is_feature_unlocked(engine: Any, feature_id: str) -> bool:
    view = _get(engine, "progression_view") or _get(engine, "progression") or _get(engine, "view")
    checker = _get(view, "is_feature_unlocked")
    if callable(checker):
        try:
            return bool(checker(str(feature_id)))
        except Exception:
            return True
    return True


def _locked_feature(feature_id: str) -> dict[str, Any]:
    return {"ok": False, "reason": "locked_feature", "feature": str(feature_id)}


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


def _world_events(engine: Any) -> Any:
    return _get(engine, "world_events")


def _catalog(engine: Any) -> Any:
    return _get(engine, "catalog")


def _miner_layer(miner: Any) -> int:
    """Return the layer of ``miner`` (0 when it has no layer)."""
    return int(_get(miner, "layer", 0) or 0)


def _is_surface_base(engine: Any, miner: Any) -> bool:
    """Return True when ``miner`` stands on the surface base."""
    world = _get(engine, "world")
    if miner is None or world is None or _miner_layer(miner) != 0:
        return False
    try:
        return bool(world.tile_at(miner.x, miner.y, _tick(engine), layer=0).is_base)
    except Exception:
        return False


def _on_base(engine: Any, miner: Any) -> bool:
    """Backwards-compatible alias for :func:`_is_surface_base`."""
    return _is_surface_base(engine, miner)


def _is_station(engine: Any, miner: Any) -> bool:
    """Return True when ``miner`` stands on a station of its layer."""
    world = _get(engine, "world")
    if miner is None or world is None:
        return False
    try:
        tile = world.tile_at(miner.x, miner.y, _tick(engine), layer=_miner_layer(miner))
    except Exception:
        return False
    return bool(tile.is_base)


def _shaft_level(engine: Any) -> int:
    """Return the bought shaft upgrade level (the deepest reachable layer)."""
    levels = _get(engine, "upgrade_levels")
    if isinstance(levels, dict):
        return int(levels.get("shaft", 0) or 0)
    player = _get(engine, "player_stats")
    levels = _get(player, "upgrades", {})
    if isinstance(levels, dict):
        return int(levels.get("shaft", 0) or 0)
    return 0


def _has_layer(engine: Any, layer: int) -> bool:
    content = _get(engine, "content")
    layers = _get(content, "layers", None)
    return not layers or int(layer) in layers


def _delta_for(world: Any, layer: int) -> Any:
    deltas = _get(world, "deltas", None)
    if isinstance(deltas, dict):
        return deltas.get(int(layer), {})
    delta = _get(world, "delta", None)
    return delta if int(layer) == 0 and isinstance(delta, dict) else {}


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


def _mine_failure(engine: Any, miner: Any = None) -> dict[str, Any] | None:
    """Return a failure result for Mine, or None if the mine can proceed."""
    ctx = _resolve_context(engine)
    miner = _miner(engine, miner) if miner is not None else ctx["miner"]
    world = ctx["world"]
    content = ctx["content"]
    if miner is None or world is None or content is None:
        return {"ok": False, "reason": "nothing_to_mine", "ore_id": None}
    layer = _miner_layer(miner)
    tile = world.tile_at(miner.x, miner.y, _tick(engine), layer=layer)
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


def _energy_config(engine: Any) -> Any:
    content = _get(engine, "content")
    return _get(content, "config")


def _energy_multiplier(engine: Any, miner: Any) -> float:
    """Return the current layer's energy multiplier (1.0 when unknown)."""
    content = _get(engine, "content")
    layer = _miner_layer(miner)
    layers = _get(content, "layers", None)
    definition = None
    if isinstance(layers, dict):
        definition = layers.get(layer)
    if definition is None:
        getter = _get(content, "get_layer")
        if callable(getter):
            try:
                definition = getter(layer)
            except Exception:
                definition = None
    return float(_get(definition, "energy_multiplier", 1.0) or 1.0)


def _scale_energy(base: int, multiplier: float) -> int:
    """Scale ``base`` energy by ``multiplier`` and round up."""
    if int(base) <= 0:
        return 0
    return int(math.ceil(float(base) * float(multiplier)))


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
            base = int(miner.move_ticks)
        else:
            content = ctx["content"]
            base = int(content.config.move_ticks) if content is not None else 4
        events = _world_events(ctx["engine"])
        if events is not None and miner is not None:
            tick = _tick(ctx["engine"])
            layer = _miner_layer(miner)
            multiplier = int(
                events.modifiers_at(miner.x, miner.y, tick, layer).get("move_multiplier", 1) or 1
            )
            destination = events.modifiers_at(
                miner.x + self.direction.dx,
                miner.y + self.direction.dy,
                tick,
                layer,
            )
            multiplier = max(multiplier, int(destination.get("move_multiplier", 1) or 1))
            if multiplier > 1:
                return int(math.ceil(base * multiplier))
        return base

    def energy_cost(self, engine: Any, miner: Any = None) -> int:
        """Return the energy needed to start this move."""
        miner = _miner(engine, miner)
        config = _energy_config(engine)
        base = int(_get(config, "energy_move", 1) or 0)
        return _scale_energy(base, _energy_multiplier(engine, miner))

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        events = _world_events(engine)
        in_slow_zone = False
        layer = _miner_layer(miner)
        if events is not None:
            tick = _tick(engine)
            current = events.modifiers_at(miner.x, miner.y, tick, layer)
            destination = events.modifiers_at(
                miner.x + self.direction.dx,
                miner.y + self.direction.dy,
                tick,
                layer,
            )
            in_slow_zone = (
                int(current.get("move_multiplier", 1) or 1) > 1
                or int(destination.get("move_multiplier", 1) or 1) > 1
            )
        miner.x += self.direction.dx
        miner.y += self.direction.dy
        miner.facing = self.direction
        miner.stats.tiles_moved += 1
        _publish(
            engine,
            Moved(
                miner_id=_miner_id(miner),
                x=miner.x,
                y=miner.y,
                layer=layer,
                direction=self.direction.name.lower(),
                in_slow_zone=in_slow_zone,
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


def _shaft_target(engine: Any, miner: Any) -> int | None:
    """Return the shaft target layer of a descend, or None if not allowed."""
    layer = _miner_layer(miner)
    target = layer + 1
    if target > _shaft_level(engine) or not _has_layer(engine, target):
        return None
    return target


def _change_layer(engine: Any, miner: Any, target: int, from_layer: int) -> dict[str, Any]:
    miner.layer = int(target)
    miner.x = 0
    miner.y = 0
    _publish(
        engine,
        LayerChanged(
            miner_id=_miner_id(miner),
            from_layer=int(from_layer),
            to_layer=int(target),
        ),
    )
    return {"ok": True, "layer": int(target), "reason": None}


@dataclass(frozen=True, slots=True)
class Descend:
    """Use a shaft station to travel one layer deeper."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        engine = ctx["engine"]
        miner = ctx["miner"]
        if miner is None or not _is_station(engine, miner):
            return 0
        if _shaft_target(engine, miner) is None:
            return 0
        content = ctx["content"]
        return int(getattr(content.config, "shaft_ticks", 20))

    def energy_cost(self, engine: Any, miner: Any = None) -> int:
        """Return the energy needed to start a descent."""
        miner = _miner(engine, miner)
        if miner is None or not _is_station(engine, miner):
            return 0
        if _shaft_target(engine, miner) is None:
            return 0
        config = _energy_config(engine)
        base = int(_get(config, "energy_shaft", 15) or 0)
        return _scale_energy(base, _energy_multiplier(engine, miner))

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        layer = _miner_layer(miner)
        if not _is_station(engine, miner):
            return {"ok": False, "layer": layer, "reason": "not_on_station"}
        target = _shaft_target(engine, miner)
        if target is None:
            return {"ok": False, "layer": layer, "reason": "shaft_too_shallow"}
        return _change_layer(engine, miner, target, layer)


@dataclass(frozen=True, slots=True)
class Ascend:
    """Use a shaft station to travel one layer towards the surface."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        engine = ctx["engine"]
        miner = ctx["miner"]
        if miner is None or not _is_station(engine, miner):
            return 0
        if _miner_layer(miner) == 0:
            return 0
        content = ctx["content"]
        return int(getattr(content.config, "shaft_ticks", 20))

    def energy_cost(self, engine: Any, miner: Any = None) -> int:
        """Return the energy needed to start an ascent."""
        miner = _miner(engine, miner)
        if miner is None or not _is_station(engine, miner) or _miner_layer(miner) == 0:
            return 0
        config = _energy_config(engine)
        base = int(_get(config, "energy_shaft", 15) or 0)
        return _scale_energy(base, _energy_multiplier(engine, miner))

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        layer = _miner_layer(miner)
        if not _is_station(engine, miner):
            return {"ok": False, "layer": layer, "reason": "not_on_station"}
        if layer == 0:
            return {"ok": False, "layer": 0, "reason": "already_surface"}
        target = layer - 1
        if not _has_layer(engine, target):
            return {"ok": False, "layer": layer, "reason": "unknown_layer"}
        return _change_layer(engine, miner, target, layer)


def _battery_state(miner: Any) -> tuple[int, int, int]:
    """Return ``(energy, capacity, charge_rate)`` for ``miner``."""
    capacity = max(0, int(_get(miner, "battery_capacity", 0) or 0))
    energy = max(0, min(int(_get(miner, "energy", capacity) or 0), capacity))
    rate = max(1, int(_get(miner, "charge_rate", 1) or 1))
    return energy, capacity, rate


def _charge_ticks(miner: Any) -> int:
    energy, capacity, rate = _battery_state(miner)
    missing = max(0, capacity - energy)
    return max(1, int(math.ceil(missing / rate)))


@dataclass(frozen=True, slots=True)
class Charge:
    """Recharge the battery while standing on a base or station."""

    def cost_ticks(self, engine: Any, miner: Any = None) -> int:
        miner = _miner(engine, miner)
        if miner is None or not _is_station(engine, miner):
            return 0
        return _charge_ticks(miner)

    def energy_cost(self, engine: Any, miner: Any = None) -> int:
        """Charging never costs energy."""
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        energy, capacity, rate = _battery_state(miner)
        if not _is_station(engine, miner):
            return {
                "ok": False,
                "reason": "not_on_station",
                "energy": energy,
                "capacity": capacity,
                "charge_rate": rate,
                "charged": 0,
            }
        missing = max(0, capacity - energy)
        amount = missing
        if amount > 0:
            try:
                miner.energy = energy + amount
            except Exception:
                pass
            _publish(engine, Charged(miner_id=_miner_id(miner), amount=amount))
        return {
            "ok": True,
            "energy": int(_get(miner, "energy", energy + amount) or 0),
            "capacity": capacity,
            "charge_rate": rate,
            "charged": amount,
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
        layer = _miner_layer(miner)
        ore = _get_ore(content, world.tile_at(miner.x, miner.y, _tick(engine), layer=layer).ore_id)
        power = max(1, int(miner.tool_power))
        return int(math.ceil(ore.hardness * content.config.mine_tick_base / power))

    def energy_cost(self, engine: Any, miner: Any = None) -> int:
        """Return the energy needed to start mining the current tile."""
        miner = _miner(engine, miner)
        if miner is None or _mine_failure(engine, miner) is not None:
            return 0
        world = _get(engine, "world")
        content = _get(engine, "content")
        if world is None or content is None:
            return 0
        tile = world.tile_at(miner.x, miner.y, _tick(engine), layer=_miner_layer(miner))
        try:
            ore = _get_ore(content, tile.ore_id)
        except Exception:
            return 0
        config = _energy_config(engine)
        base = int(_get(config, "energy_mine_base", 1) or 0) + int(ore.hardness) // 2
        return _scale_energy(base, _energy_multiplier(engine, miner))

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        world = engine.world
        content = engine.content
        failure = _mine_failure(engine, miner)
        if failure is not None:
            _publish(
                engine,
                MineAttempted(
                    miner_id=_miner_id(miner),
                    ore_id=failure.get("ore_id"),
                    layer=_miner_layer(miner),
                    success=False,
                    reason=str(failure.get("reason")),
                ),
            )
            return failure
        layer = _miner_layer(miner)
        ore_id = world.tile_at(miner.x, miner.y, _tick(engine), layer=layer).ore_id
        ore = _get_ore(content, ore_id)
        attempt_counter = int(_get(engine, "attempt_counter", 0) or 0)
        seed = _seed(engine, content, world)
        dice = (seed, _tick(engine), miner.x, miner.y, attempt_counter)
        if layer != 0:
            dice = (*dice, layer)
        miner_id = _miner_id(miner)
        if miner_id != 0:
            dice = (*dice, miner_id)
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
                miner_id=miner_id,
                ore_id=ore_id,
                layer=layer,
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
        events = _world_events(engine)
        yield_multiplier = 1
        if events is not None:
            modifiers = events.modifiers_at(miner.x, miner.y, _tick(engine), layer)
            yield_multiplier = max(1, int(modifiers.get("yield_multiplier", 1) or 1))
        free = max(0, int(miner.capacity) - int(miner.inventory_size))
        amount = max(1, min(yield_multiplier, free))
        in_rich_vein = yield_multiplier > 1
        miner.add_item(ore_id, amount)
        world.mine_tile(miner.x, miner.y, _tick(engine), layer=layer)
        _publish(
            engine,
            OreMined(
                miner_id=miner_id,
                ore_id=ore_id,
                amount=amount,
                layer=layer,
                in_rich_vein=in_rich_vein,
            ),
        )
        return {
            "ok": True,
            "ore": ore_id,
            "ore_id": ore_id,
            "amount": amount,
            "success": True,
            "in_rich_vein": in_rich_vein,
        }


@dataclass(frozen=True, slots=True)
class Battery:
    """Return the battery energy and capacity of the acting miner."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        energy, capacity, rate = _battery_state(miner)
        return {
            "ok": True,
            "energy": energy,
            "capacity": capacity,
            "charge_rate": rate,
        }


@dataclass(frozen=True, slots=True)
class EnergyCost:
    """Return the energy an action would cost right now."""

    action: str = ""
    arg: int | None = None

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def _command_for(self) -> Any | None:
        action = str(self.action or "").strip().lower()
        if action == "move":
            return Move()
        if action == "mine":
            return Mine()
        if action == "scan":
            return Scan(0 if self.arg is None else int(self.arg))
        if action == "descend":
            return Descend()
        if action == "ascend":
            return Ascend()
        if action == "charge":
            return Charge()
        return None

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        action = str(self.action or "").strip().lower()
        command = self._command_for()
        if command is None:
            return {
                "ok": False,
                "reason": "unknown_action",
                "action": action,
                "cost": 0,
            }
        method = getattr(command, "energy_cost", None)
        cost = int(method(engine, miner)) if callable(method) else 0
        return {
            "ok": True,
            "action": action,
            "cost": max(0, cost),
            "energy": int(_get(miner, "energy", 0) or 0),
        }


@dataclass(frozen=True, slots=True)
class Peek:
    """Look at the tile the miner stands on."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        layer = _miner_layer(miner)
        tile = engine.world.tile_at(miner.x, miner.y, _tick(engine), layer=layer)
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

    def energy_cost(self, engine: Any, miner: Any = None) -> int:
        """Return the energy needed to start a scan of ``radius`` tiles."""
        miner = _miner(engine, miner)
        effective = max(0, int(self.radius))
        if miner is not None:
            effective = min(effective, max(0, int(miner.scan_radius)))
        config = _energy_config(engine)
        base = int(_get(config, "energy_scan_per_radius", 1) or 0) * effective
        return _scale_energy(base, _energy_multiplier(engine, miner))

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        effective = min(max(0, int(self.radius)), max(0, int(miner.scan_radius)))
        layer = _miner_layer(miner)
        tiles: list[list[Any]] = []
        for dy in range(-effective, effective + 1):
            for dx in range(-effective, effective + 1):
                tile = engine.world.tile_at(miner.x + dx, miner.y + dy, _tick(engine), layer=layer)
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
            if not _is_surface_base(ctx["engine"], miner):
                return 0
        if content is not None:
            return int(content.config.sell_ticks)
        return 2

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        if not _is_surface_base(engine, miner):
            return {"ok": False, "reason": "not_on_surface_base"}
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
                    miner_id=_miner_id(miner),
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
    """Move the miner inventory into the base warehouse."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        miner = ctx["miner"]
        if miner is not None and _is_surface_base(ctx["engine"], miner):
            return 1
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        if not _is_surface_base(engine, miner):
            return {"ok": False, "reason": "not_on_surface_base"}
        if not _is_feature_unlocked(engine, "warehouse"):
            return _locked_feature("warehouse")
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
        if miner is None or not _is_surface_base(ctx["engine"], miner):
            return 0
        if content is not None:
            return int(content.config.sell_ticks)
        return 2

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        if not _is_surface_base(engine, miner):
            return {"ok": False, "reason": "not_on_surface_base"}
        if not _is_feature_unlocked(engine, "market"):
            return _locked_feature("market")
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
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
        if miner is None or not _is_surface_base(ctx["engine"], miner):
            return 0
        if content is not None:
            return int(getattr(content.config, "refine_ticks", 2))
        return 2

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        if not _is_surface_base(engine, miner):
            return {"ok": False, "reason": "not_on_surface_base"}
        if not _is_feature_unlocked(engine, "refinery"):
            return _locked_feature("refinery")
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        if not _is_surface_base(engine, _miner(engine, miner)):
            return {"ok": False, "reason": "not_on_surface_base"}
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
        if miner is None or not _is_surface_base(ctx["engine"], miner):
            return 0
        if content is not None:
            return int(getattr(content.config, "deliver_ticks", 2))
        return 2

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        if not _is_surface_base(engine, miner):
            return {"ok": False, "reason": "not_on_surface_base"}
        if not _is_feature_unlocked(engine, "contracts"):
            return _locked_feature("contracts")
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        if not _is_surface_base(engine, _miner(engine, miner)):
            return {"ok": False, "reason": "not_on_surface_base"}
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        if not _is_surface_base(engine, _miner(engine, miner)):
            return {"ok": False, "reason": "not_on_surface_base"}
        if not _item_unlocked(engine, self.item):
            return {"ok": True, "item": self.item, "price": None}
        price = _market_price(engine, self.item)
        return {"ok": True, "item": self.item, "price": _round_price(price)}


@dataclass(frozen=True, slots=True)
class Prices:
    """Return the current market prices of every unlocked item."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        if not _is_surface_base(engine, _miner(engine, miner)):
            return {"ok": False, "reason": "not_on_surface_base"}
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        if not _is_surface_base(engine, _miner(engine, miner)):
            return {"ok": False, "reason": "not_on_surface_base"}
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
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
                miner_id=_miner_id(miner) if miner is not None else 0,
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        return {"ok": True, "ticks": int(self.ticks), "waited": int(self.ticks)}


@dataclass(frozen=True, slots=True)
class SpawnMiner:
    """Buy a new miner; costs ``miner_costs`` for the next extra miner."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        ctx = _resolve_context(*args, **kwargs)
        content = ctx["content"]
        config = _get(content, "config")
        return int(_get(config, "spawn_ticks", 5) or 5)

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        if not _is_feature_unlocked(engine, "miners"):
            return _locked_feature("miners")
        miners = _get(engine, "miners") or {}
        max_miners = int(_get(engine, "max_miners", 1) or 1)
        if len(miners) >= max_miners:
            return {"ok": False, "reason": "no_slot"}
        content = _get(engine, "content")
        config = _get(content, "config")
        costs = list(_get(config, "miner_costs", []) or [])
        extra = max(0, len(miners) - 1)
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
        new_miner = engine.spawn_miner()
        return {"ok": True, "miner_id": int(new_miner.id), "cost": cost}


@dataclass(frozen=True, slots=True)
class RemoveMiner:
    """Remove miner ``id`` from the fleet (never miner 0)."""

    id: int = 0

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        if not _is_feature_unlocked(engine, "miners"):
            return _locked_feature("miners")
        target = int(self.id)
        if target == 0:
            return {"ok": False, "reason": "cannot_remove_main", "miner_id": target}
        removed = engine.remove_miner(target)
        if not removed:
            return {"ok": False, "reason": "unknown_miner", "miner_id": target}
        return {"ok": True, "miner_id": target}


@dataclass(frozen=True, slots=True)
class MinerId:
    """Return the id of the acting miner."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        return {"ok": True, "id": _miner_id(_miner(engine, miner))}


@dataclass(frozen=True, slots=True)
class Miners:
    """Return the fleet as a list of miner summaries."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miners = _get(engine, "miners") or {}
        entries: list[dict[str, Any]] = []
        for miner_id in sorted(int(key) for key in miners):
            item = miners[miner_id]
            entries.append(
                {
                    "id": miner_id,
                    "x": int(_get(item, "x", 0) or 0),
                    "y": int(_get(item, "y", 0) or 0),
                    "layer": _miner_layer(item),
                    "state": "idle",
                    "script": str(_get(item, "script", "") or ""),
                    "inventory_used": int(
                        _get(item, "inventory_size", sum(_get(item, "inventory", {}).values())) or 0
                    ),
                }
            )
        return {"ok": True, "miners": entries}


@dataclass(frozen=True, slots=True)
class Position:
    """Return the miner position."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        stats = _miner(engine, miner).stats
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        return {"ok": True, "tick": _tick(engine)}


@dataclass(frozen=True, slots=True)
class Events:
    """Return the random world events active right now."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        events = _world_events(engine)
        tick = _tick(engine)
        active: list[dict[str, Any]] = []
        if events is not None:
            for event in events.active_at(tick):
                if event.kind == "market_news":
                    if event.item is None or not _item_unlocked(engine, str(event.item)):
                        continue
                    direction = "shortage" if float(event.factor) > 1.0 else "glut"
                else:
                    direction = None
                active.append(
                    {
                        "kind": event.kind,
                        "x": event.x,
                        "y": event.y,
                        "radius": event.radius,
                        "ends_in": max(0, int(event.ends) - tick),
                        "item": event.item,
                        "direction": direction,
                    }
                )
        return {"ok": True, "events": active, "active": list(active)}


@dataclass(frozen=True, slots=True)
class Distance:
    """Return the Chebyshev distance from the base at ``(0, 0)``."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        distance = max(abs(int(miner.x)), abs(int(miner.y)))
        return {"ok": True, "distance": distance}


@dataclass(frozen=True, slots=True)
class Layer:
    """Return the index of the layer the miner is on."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        return {"ok": True, "layer": _miner_layer(_miner(engine, miner))}


@dataclass(frozen=True, slots=True)
class Layers:
    """List every layer and whether the shaft reaches it."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        content = engine.content
        layers = getattr(content, "layers", None) or {}
        max_layer = _shaft_level(engine)
        entries = [
            {
                "index": int(index),
                "name": str(getattr(layer, "name", index)),
                "accessible": int(index) <= max_layer,
            }
            for index, layer in sorted(layers.items())
        ]
        return {"ok": True, "layers": entries}


@dataclass(frozen=True, slots=True)
class Biome:
    """Return the id of the biome under the miner."""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        layer = _miner_layer(miner)
        tile = engine.world.tile_at(miner.x, miner.y, _tick(engine), layer=layer)
        return {"ok": True, "biome": tile.biome_id}


@dataclass(frozen=True, slots=True)
class OreInfo:
    """Return public information about ore ``ore_id`` (never its probability)."""

    ore_id: str = ""

    def cost_ticks(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
        world = engine.world
        content = engine.content
        tick = _tick(engine)
        layer = _miner_layer(miner)
        tile = world.tile_at(miner.x, miner.y, tick, layer=layer)
        if tile.ore_id is None:
            ore = None
        elif _is_unlocked(engine, content, tile.ore_id):
            ore = tile.ore_id
        else:
            ore = "unknown"
        regrows_in: int | None = None
        if tile.depleted:
            delta = _delta_for(world, layer)
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

    def execute(self, engine: Any, miner: Any = None) -> dict[str, Any]:
        miner = _miner(engine, miner)
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
