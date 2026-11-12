"""Headless balance report for the v0.2 achievement chain.

Runs two simple strategies for 200,000 ticks on the default seed and writes
``docs/BALANCE.md`` with the tick at which every achievement completes (or
``never``). This is a reporting tool only: it never changes gameplay numbers.

Usage: ``python tools/balance_sim.py``
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

# Make the src layout importable when run as a plain script.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from digscript.core.commands import BuyUpgrade, Mine, Move, Sell  # noqa: E402
from digscript.core.direction import Direction  # noqa: E402
from digscript.core.game import Game  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
_DOCS = _ROOT / "docs"

__all__ = [
    "DEFAULT_TICKS",
    "RandomWalker",
    "SerpentineSweeper",
    "build_report",
    "main",
    "run_strategy",
]

DEFAULT_TICKS = 200_000
DEFAULT_SEED = 12345
_DIRECTIONS = (Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST)
_UPGRADE_ORDER = ("backpack", "pickaxe", "motor", "scanner")
_TAB_ORDER = ("code", "mining", "business", "explorer", "data")


def _mineable(game: Game, tile: Any) -> bool:
    """Return True when the miner can mine the tile right now."""
    if tile.is_base or tile.depleted or tile.ore_id is None:
        return False
    miner = game.miner
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


def run_strategy(strategy: Any, ticks: int = DEFAULT_TICKS, seed: int = DEFAULT_SEED) -> Game:
    """Run ``strategy`` headlessly for ``ticks`` engine ticks and return the game."""
    game = Game.new(seed=seed)
    while game.tick < ticks:
        if game.engine.is_idle:
            for _ in range(100):
                command = strategy.next_command(game)
                if command is None:
                    break
                ticket = game.submit(command)
                if not ticket.done:
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
        f"of two simple strategies on seed {seed}. This is a report only; no gameplay "
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
        for strategy in (RandomWalker(), SerpentineSweeper())
    ]
    report = build_report(results, ticks, seed)
    print(report)
    _DOCS.mkdir(parents=True, exist_ok=True)
    (_DOCS / "BALANCE.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
