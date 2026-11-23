"""Headless balance report for the v0.4 achievement chain.

Runs four strategies for 400,000 ticks on the default seed and writes
``docs/BALANCE.md`` with the tick at which every achievement completes (or
``never``). The last strategy exercises the warehouse, the dynamic market,
the refinery, a deep shaft, the climate system and a four-miner fleet driven in
lockstep. This is a reporting tool only: it never changes gameplay numbers.

Usage: ``python tools/balance_sim.py``
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Any

# Make the src layout importable when run as a plain script.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from minesim.core.commands import (  # noqa: E402
    Ascend,
    BuyUpgrade,
    Charge,
    Cool,
    Deliver,
    Descend,
    Mine,
    Move,
    Refine,
    Sell,
    SellStock,
    SpawnMiner,
    Unload,
)
from minesim.core.direction import Direction  # noqa: E402
from minesim.core.game import Game  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs"

__all__ = [
    "DEFAULT_TICKS",
    "DeepFleet",
    "FleetTrader",
    "RandomWalker",
    "SerpentineSweeper",
    "build_report",
    "main",
    "run_strategy",
]

DEFAULT_TICKS = 400_000
DEFAULT_SEED = 12345
_DIRECTIONS = (Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST)
_UPGRADE_ORDER = ("backpack", "pickaxe", "motor", "scanner")
_TAB_ORDER = (
    "code",
    "mining",
    "business",
    "trading",
    "industry",
    "fleet",
    "explorer",
    "data",
    "engineering",
    "depths",
)


def _mineable(game: Game, tile: Any, miner: Any = None) -> bool:
    """Return True when ``miner`` (miner 0 by default) can mine the tile."""
    if tile.is_base or tile.depleted or tile.ore_id is None:
        return False
    miner = game.miner if miner is None else miner
    if miner.inventory_size >= miner.capacity:
        return False
    ore = game.content.get_ore(tile.ore_id)
    return game.progression.is_ore_unlocked(tile.ore_id) and miner.tool_tier >= ore.tier


def _step_towards(x: int, y: int, target_x: int, target_y: int) -> Move | None:
    """Return one move that reduces the distance to the target."""
    if x < target_x:
        return Move(Direction.EAST)
    if x > target_x:
        return Move(Direction.WEST)
    if y < target_y:
        return Move(Direction.SOUTH)
    if y > target_y:
        return Move(Direction.NORTH)
    return None


def _serpentine_path(radius: int) -> list[tuple[int, int]]:
    """Return an outward serpentine path over a square of the given radius."""
    rows = [0]
    for distance in range(1, radius + 1):
        rows.extend((distance, -distance))
    path: list[tuple[int, int]] = []
    for index, y in enumerate(rows):
        if index == 0:
            xs = range(0, radius + 1)
        elif index % 2 == 1:
            xs = range(radius, -radius - 1, -1)
        else:
            xs = range(-radius, radius + 1)
        path.extend((x, y) for x in xs)
    return path


class RandomWalker:
    """Walk randomly, mine any mineable tile and sell if standing on the base."""

    name = "Random walker"

    def __init__(self, seed: int = 7) -> None:
        self._rng = random.Random(seed)

    def next_command(self, game: Game) -> Any:
        """Return the next command for the random walker."""
        miner = game.miner
        tile = game.world.tile_at(miner.x, miner.y, game.tick)
        if tile.is_base and miner.inventory:
            return Sell()
        if _mineable(game, tile):
            return Mine()
        return Move(self._rng.choice(_DIRECTIONS))


class SerpentineSweeper:
    """Sweep a square in serpentine order, hauling and upgrading greedily."""

    name = "Serpentine sweeper"

    def __init__(self, radius: int = 120) -> None:
        self._path = _serpentine_path(radius)
        self._index = 0
        self._selling = False

    def next_command(self, game: Game) -> Any:
        """Return the next command for the serpentine sweeper."""
        while True:
            miner = game.miner
            if self._selling:
                if (miner.x, miner.y) != (0, 0):
                    return _step_towards(miner.x, miner.y, 0, 0)
                if miner.inventory:
                    return Sell()
                upgrade = self._next_upgrade(game)
                if upgrade is not None:
                    return upgrade
                self._selling = False
                continue
            if miner.inventory_size >= miner.capacity:
                self._selling = True
                continue
            target = self._path[self._index % len(self._path)]
            if (miner.x, miner.y) != target:
                return _step_towards(miner.x, miner.y, target[0], target[1])
            tile = game.world.tile_at(miner.x, miner.y, game.tick)
            if _mineable(game, tile):
                return Mine()
            self._index = (self._index + 1) % len(self._path)

    def _next_upgrade(self, game: Game) -> BuyUpgrade | None:
        """Return the cheapest affordable upgrade level, if any."""
        best: BuyUpgrade | None = None
        best_key: tuple[int, int] | None = None
        for order, upgrade_id in enumerate(_UPGRADE_ORDER):
            if not game.progression.is_upgrade_unlocked(upgrade_id):
                continue
            upgrade = game.content.get_upgrade(upgrade_id)
            level = int(game.miner.upgrades.get(upgrade_id, 0))
            if level >= upgrade.max_level or level >= len(upgrade.costs):
                continue
            cost = int(upgrade.costs[level])
            if game.miner.money < cost:
                continue
            key = (cost, order)
            if best_key is None or key < best_key:
                best_key = key
                best = BuyUpgrade(upgrade_id)
        return best


class FleetTrader:
    """Mine, haul into the warehouse, trade on the market, refine and spawn a miner.

    The strategy only sells warehouse stock when the market index of an item
    is at least ``sell_index`` (it sells the best item when the warehouse is
    full so the fleet never stalls). It refines every unlocked recipe the stock
    allows, delivers contracts, buys upgrades and drives a second miner in the
    same lockstep as miner 0.
    """

    name = "Warehouse trader"

    def __init__(self, radius: int = 90, sell_index: float = 1.1) -> None:
        self._path = _serpentine_path(radius)
        self._index: dict[int, int] = {}
        self._selling: dict[int, bool] = {}
        self._sell_index = float(sell_index)
        self._upgrade_order = (
            "pickaxe",
            "miner_bay",
            "backpack",
            "furnace",
            "motor",
            "scanner",
            "contract_board",
            "warehouse",
        )
        self._refine_items = {"coal", "copper", "iron", "silver", "gold", "ruby"}
        self._refine_order = (
            "cut_ruby",
            "gold_bar",
            "steel_bar",
            "silver_bar",
            "iron_bar",
            "copper_bar",
        )

    # -- driver ---------------------------------------------------------------

    def next_commands(self, game: Game) -> list[tuple[int, Any]]:
        """Return one command per idle miner (lockstep across the fleet)."""
        commands: list[tuple[int, Any]] = []
        for miner_id in sorted(game.engine.miners):
            miner = game.engine.miner_by_id(miner_id)
            self._index.setdefault(miner_id, miner_id * len(self._path) // 2)
            self._selling.setdefault(miner_id, False)
            commands.append((miner_id, self._command_for(game, miner)))
        return commands

    def next_command(self, game: Game) -> Any:
        """Return miner 0's next command (single-miner compatibility)."""
        commands = self.next_commands(game)
        return commands[0][1] if commands else None

    # -- decisions ------------------------------------------------------------

    def _command_for(self, game: Game, miner: Any) -> Any:
        on_base = bool(game.world.tile_at(miner.x, miner.y, game.tick).is_base)
        if on_base:
            command = self._base_command(game, miner)
            if command is not None:
                return command
        return self._field_command(game, miner)

    def _base_command(self, game: Game, miner: Any) -> Any:
        warehouse = game.engine.warehouse
        if game.is_feature_unlocked("market"):
            item = self._best_stock_item(game)
            if item is not None:
                return SellStock(item)
        if game.is_feature_unlocked("contracts"):
            command = self._deliver_command(game)
            if command is not None:
                return command
        if game.is_feature_unlocked("refinery"):
            command = self._refine_command(game)
            if command is not None:
                return command
        if miner.inventory:
            if (
                game.is_feature_unlocked("warehouse")
                and warehouse.free > 0
                and self._wants_unload(game, miner)
            ):
                return Unload()
            return Sell()
        spawn = self._spawn_command(game)
        if spawn is not None:
            return spawn
        return self._next_upgrade(game)

    def _wants_unload(self, game: Game, miner: Any) -> bool:
        state = game.progression_state
        if state.get_counter("unloads") < 3:
            return True
        if state.get_counter("money_earned") < 3500:
            return False
        return True

    def _field_command(self, game: Game, miner: Any) -> Any:
        if miner.inventory_size >= miner.capacity:
            if (miner.x, miner.y) == (0, 0):
                return None
            return _step_towards(miner.x, miner.y, 0, 0)
        for _ in range(len(self._path) + 1):
            target = self._path[self._index[int(miner.id)] % len(self._path)]
            if (miner.x, miner.y) != target:
                return _step_towards(miner.x, miner.y, target[0], target[1])
            tile = game.world.tile_at(miner.x, miner.y, game.tick)
            if _mineable(game, tile, miner):
                return Mine()
            self._index[int(miner.id)] += 1
        return None

    def _best_stock_item(self, game: Game) -> str | None:
        market = game.engine.market
        warehouse = game.engine.warehouse
        if market is None:
            return None
        best_item: str | None = None
        best_index = self._sell_index
        for item, count in warehouse.items.items():
            if int(count) <= 0 or item in self._refine_items:
                continue
            index = float(market.index(item))
            if index >= self._sell_index and index > best_index:
                best_index = index
                best_item = item
        if best_item is None and warehouse.free <= 0:
            fallback_index = -1.0
            for item, count in warehouse.items.items():
                if int(count) <= 0:
                    continue
                index = float(market.index(item))
                if best_item is None or index > fallback_index:
                    fallback_index = index
                    best_item = item
        return best_item

    def _deliver_command(self, game: Game) -> Deliver | None:
        board = game.engine.contracts
        warehouse = game.engine.warehouse
        for contract in list(board.contracts):
            if warehouse.count(contract.item) >= contract.quantity:
                return Deliver(contract.id)
        return None

    def _refine_command(self, game: Game) -> Refine | None:
        refinery = game.engine.refinery
        if len(refinery.jobs) >= refinery.slots:
            return None
        warehouse = game.engine.warehouse
        for recipe_id in self._refine_order:
            recipe = game.content.recipes.get(recipe_id)
            if recipe is None or not game.progression.is_recipe_unlocked(recipe_id):
                continue
            if all(warehouse.count(item) >= count for item, count in recipe.inputs.items()):
                return Refine(recipe_id, 1)
        return None

    def _spawn_command(self, game: Game) -> SpawnMiner | None:
        if not game.is_feature_unlocked("miners"):
            return None
        if 1 in game.engine.miners or game.engine.max_miners < 2:
            return None
        cost = int(game.content.config.miner_costs[0])
        if game.player_stats.money < cost:
            return None
        return SpawnMiner()

    def _next_upgrade(self, game: Game) -> BuyUpgrade | None:
        if (
            game.is_feature_unlocked("miners")
            and 1 not in game.engine.miners
            and game.engine.max_miners >= 2
            and game.player_stats.money < int(game.content.config.miner_costs[0])
        ):
            return None
        for upgrade_id in self._upgrade_order:
            if not game.progression.is_upgrade_unlocked(upgrade_id):
                continue
            upgrade = game.content.upgrades.get(upgrade_id)
            if upgrade is None:
                continue
            level = int(game.player_stats.upgrades.get(upgrade_id, 0))
            if level >= upgrade.max_level or level >= len(upgrade.costs):
                continue
            cost = int(upgrade.costs[level])
            if game.player_stats.money >= cost:
                return BuyUpgrade(upgrade_id)
            if cost <= 1000:
                return None
        return None


class DeepFleet(FleetTrader):
    """Run a five-miner fleet across the surface and the underground layers.

    Miner 0 keeps the surface economy running. The other miners descend once
    the shaft is available, mine layer quotas, charge and cool at stations, and
    unload at the surface dock. Miner 3 is deliberately reckless until it has
    overheated once and reached the temperature achievement, which exercises
    stranding, rescue and the climate counters.
    """

    name = "Deep fleet"

    def __init__(self, radius: int = 70, sell_index: float = 1.05) -> None:
        super().__init__(radius=radius, sell_index=sell_index)
        self._target_fleet = 5
        self._upgrade_order = (
            "pickaxe",
            "miner_bay",
            "backpack",
            "shaft",
            "charger",
            "battery",
            "cooling",
            "ventilation",
            "dock",
            "furnace",
            "motor",
            "scanner",
            "contract_board",
            "warehouse",
        )

    def _is_reckless(self, game: Game, miner: Any) -> bool:
        if int(getattr(miner, "id", 0)) != 3:
            return False
        state = game.progression_state
        return state.get_counter("overheats") < 1 or state.get_counter("peak_temp") < 80

    def _layer_multiplier(self, game: Game, layer: int) -> float:
        entry = game.content.layers.get(int(layer))
        return max(0.01, float(getattr(entry, "energy_multiplier", 1.0) or 1.0))

    def _shaft_cost(self, game: Game, miner: Any) -> int:
        base = int(getattr(game.content.config, "energy_shaft", 15) or 15)
        return int(math.ceil(base * self._layer_multiplier(game, int(miner.layer))))

    def _needs_charge(self, game: Game, miner: Any) -> bool:
        if self._is_reckless(game, miner):
            return False
        capacity = max(1, int(getattr(miner, "battery_capacity", 0) or 0))
        energy = int(getattr(miner, "energy", 0) or 0)
        layer = int(getattr(miner, "layer", 0) or 0)
        move = max(1, int(getattr(game.content.config, "energy_move", 1) or 1))
        distance = abs(int(miner.x)) + abs(int(miner.y))
        reserve = (
            int(math.ceil(distance * move * self._layer_multiplier(game, layer)))
            + 2 * self._shaft_cost(game, miner)
            + 20
        )
        return energy < max(50, int(math.ceil(capacity * 0.15)), reserve)

    def _needs_cool(self, game: Game, miner: Any) -> bool:
        if self._is_reckless(game, miner):
            return False
        return float(getattr(miner, "temperature", 0.0) or 0.0) >= 70.0

    def _target_layer(self, game: Game, miner_id: int) -> int:
        shaft = int(game.player_stats.upgrades.get("shaft", 0) or 0)
        if int(miner_id) == 0 or shaft <= 0:
            return 0
        if shaft == 1:
            return 1
        if int(miner_id) == 1 and game.progression_state.get_counter("mined_layer:1") < 120:
            return 1
        if shaft == 2:
            return 2
        if int(miner_id) in (3, 4):
            return 3
        return 2

    def _command_for(self, game: Game, miner: Any) -> Any:
        if int(getattr(miner, "cooldown_remaining", 0) or 0) > 0:
            return None
        layer = int(getattr(miner, "layer", 0) or 0)
        tile = game.world.tile_at(miner.x, miner.y, game.tick, layer=layer)
        on_station = bool(tile.is_base)
        target = self._target_layer(game, int(miner.id))
        full = miner.inventory_size >= miner.capacity
        energy = int(getattr(miner, "energy", 0) or 0)
        capacity = max(1, int(getattr(miner, "battery_capacity", 0) or 0))

        if on_station and layer == 0:
            if miner.inventory:
                return self._sell_or_unload(game, miner)
            if int(miner.id) == 0:
                command = super()._base_command(game, miner)
                if command is not None:
                    return command
            if self._needs_charge(game, miner) or energy < capacity * 0.8:
                return Charge()
            if target > 0:
                return Descend()
            return self._field_command(game, miner)

        if on_station:
            if full:
                if self._needs_charge(game, miner) or energy < self._shaft_cost(game, miner):
                    return Charge()
                return Ascend()
            if target != layer:
                if self._needs_charge(game, miner) or energy < self._shaft_cost(game, miner):
                    return Charge()
                return Descend() if target > layer else Ascend()
            if self._needs_charge(game, miner):
                return Charge()
            if self._needs_cool(game, miner):
                return Cool(30.0)
            return self._field_command(game, miner)

        if (
            full
            or target != layer
            or self._needs_charge(game, miner)
            or self._needs_cool(game, miner)
        ):
            return _step_towards(miner.x, miner.y, 0, 0)
        return self._field_command(game, miner)

    def _sell_or_unload(self, game: Game, miner: Any) -> Any:
        if not self._wants_unload(game, miner):
            return Sell()
        warehouse = game.engine.warehouse
        if game.is_feature_unlocked("warehouse") and warehouse is not None and warehouse.free > 0:
            return Unload()
        return Sell()

    def _wants_unload(self, game: Game, miner: Any) -> bool:
        return game.progression_state.get_counter("money_earned") >= 9000

    def _spawn_command(self, game: Game) -> SpawnMiner | None:
        if not game.is_feature_unlocked("miners"):
            return None
        miners = game.engine.miners
        if len(miners) >= self._target_fleet or game.engine.max_miners <= len(miners):
            return None
        costs = list(game.content.config.miner_costs)
        extra = max(0, len(miners) - 1)
        if extra >= len(costs):
            return None
        if game.player_stats.money < int(costs[extra]):
            return None
        return SpawnMiner()


def _next_commands(strategy: Any, game: Game) -> list[tuple[int, Any]]:
    producer = getattr(strategy, "next_commands", None)
    if callable(producer):
        raw = producer(game) or []
    else:
        command = strategy.next_command(game)
        raw = [(0, command)] if command is not None else []
    return [(int(miner_id), command) for miner_id, command in raw if command is not None]


def run_strategy(strategy: Any, ticks: int = DEFAULT_TICKS, seed: int = DEFAULT_SEED) -> Game:
    """Run ``strategy`` headlessly for ``ticks`` engine ticks and return the game."""
    game = Game.new(seed=seed)
    while game.tick < ticks:
        if game.engine.is_idle:
            for _ in range(100):
                commands = _next_commands(strategy, game)
                if not commands:
                    break
                waiting = False
                for miner_id, command in commands:
                    ticket = game.submit(command, miner_id=miner_id)
                    if not ticket.done:
                        waiting = True
                if waiting:
                    break
        game.step()
    return game


def _tick_text(completed: dict[str, int], achievement_id: str) -> str:
    value = completed.get(achievement_id)
    return "never" if value is None else str(int(value))


def build_report(results: list[tuple[str, Game]], ticks: int, seed: int) -> str:
    """Return the Markdown balance report for ``results``."""
    content = results[0][1].content
    achievements = sorted(
        content.achievement_list,
        key=lambda entry: (
            _TAB_ORDER.index(entry.tab) if entry.tab in _TAB_ORDER else len(_TAB_ORDER),
            entry.id,
        ),
    )

    lines: list[str] = []
    lines.append("# Balance report")
    lines.append("")
    lines.append(
        f"Generated by `tools/balance_sim.py` from a headless {ticks:,}-tick simulation "
        f"of four strategies on seed {seed}. This is a report only; no gameplay "
        "numbers were tuned."
    )
    lines.append("")
    lines.append(
        "- **Random walker**: walks randomly, mines any unlocked ore it can and sells "
        "only when it happens to stand on the base."
    )
    lines.append(
        "- **Serpentine sweeper**: follows an outward serpentine path, returns home to "
        "sell when the inventory is full and buys the cheapest available upgrade level "
        "before resuming."
    )
    lines.append(
        "- **Warehouse trader**: mines and unloads into the warehouse, sells stock only "
        "when the market index is at least 1.1, refines every unlocked recipe it can, "
        "delivers contracts, buys upgrades and spawns a second miner. Both miners run "
        "in lockstep."
    )
    lines.append(
        "- **Deep fleet**: keeps the warehouse trader economy, expands to five miners, "
        "buys the shaft and climate upgrades, sends miners to layer quotas, charges and "
        "cools at stations, and deliberately lets one miner overheat and run dry."
    )
    lines.append("")
    lines.append("## Strategy totals")
    lines.append("")
    lines.append("| Metric | " + " | ".join(name for name, _game in results) + " |")
    lines.append("|---|" + "---|" * len(results))
    metrics = (
        ("Achievements completed", lambda game: len(game.progression_state.completed)),
        ("Money", lambda game: game.miner.money),
        ("Tiles moved", lambda game: game.progression_state.get_counter("tiles_moved")),
        ("Mining attempts", lambda game: game.progression_state.get_counter("attempts:any")),
        ("Ore mined", lambda game: game.progression_state.get_counter("mined:any")),
        ("Unique ores mined", lambda game: game.progression_state.get_counter("unique_ores_mined")),
        ("Biomes visited", lambda game: game.progression_state.get_counter("biomes_visited")),
        ("Max distance", lambda game: game.progression_state.get_counter("max_distance")),
    )
    for label, getter in metrics:
        values = " | ".join(str(getter(game)) for _name, game in results)
        lines.append(f"| {label} | {values} |")
    lines.append("")
    lines.append("## Achievement completion ticks")
    lines.append("")
    lines.append("| Achievement | Tab | " + " | ".join(name for name, _game in results) + " |")
    lines.append("|---|---|" + "---|" * len(results))
    for achievement in achievements:
        cells = " | ".join(
            _tick_text(game.progression_state.completed, achievement.id) for _name, game in results
        )
        lines.append(f"| {achievement.title} (`{achievement.id}`) | {achievement.tab} | {cells} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the simulation, print the report and write ``docs/BALANCE.md``."""
    args = list(sys.argv[1:] if argv is None else argv)
    ticks = int(args[0]) if args else DEFAULT_TICKS
    seed = int(args[1]) if len(args) > 1 else DEFAULT_SEED
    results = [
        (strategy.name, run_strategy(strategy, ticks=ticks, seed=seed))
        for strategy in (RandomWalker(), SerpentineSweeper(), FleetTrader(), DeepFleet())
    ]
    report = build_report(results, ticks, seed)
    print(report)
    _DOCS.mkdir(parents=True, exist_ok=True)
    (_DOCS / "BALANCE.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
