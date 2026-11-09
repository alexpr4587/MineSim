"""Tests for the miner, tick engine and economy (prompt 02)."""

from __future__ import annotations

import math

import pytest

from digscript.core.commands import (
    BuyUpgrade,
    Inventory,
    Mine,
    Move,
    Peek,
    Position,
    Scan,
    Sell,
    Stats,
    Wait,
)
from digscript.core.content import load_content
from digscript.core.direction import Direction
from digscript.core.engine import AllUnlocked, GameEngine
from digscript.core.events import (
    EventBus,
    MineAttempted,
    Moved,
    OreMined,
    Sold,
    TickAdvanced,
    UpgradeBought,
)
from digscript.core.miner import Miner
from digscript.core.world import World, WorldGenerator


@pytest.fixture(scope="module")
def content():
    return load_content()


def _engine(content, *, miner=None, progression=None, seed=None):
    generator = WorldGenerator(content.config.seed_default if seed is None else seed, content)
    world = World(generator, content)
    if miner is None:
        miner = Miner.from_config(content)
    bus = EventBus()
    engine = GameEngine(world, miner, content, bus, progression or AllUnlocked())
    return engine, world, miner, bus


def _find_tile(world, ore_id, start=2):
    for y in range(start, start + 40):
        for x in range(start, start + 40):
            if world.tile_at(x, y, 0).ore_id == ore_id:
                return x, y
    raise AssertionError(f"no tile with {ore_id}")


def _submit(engine, command):
    ticket = engine.submit(command)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


class _LockedCoal:
    def is_ore_unlocked(self, ore_id):
        return ore_id == "stone"

    def is_function_unlocked(self, name):
        return True

    def is_upgrade_unlocked(self, upgrade_id):
        return True

    def is_module_unlocked(self, name):
        return True


# -- content -----------------------------------------------------------------


def test_config_and_upgrades(content):
    config = content.config
    assert config.move_ticks == 4
    assert config.mine_tick_base == 3
    assert config.sell_ticks == 2
    assert config.scan_ticks_per_radius == 1
    assert config.start_capacity == 10
    assert config.start_tool_power == 1
    assert config.start_tool_tier == 0
    assert config.start_scan_radius == 2
    assert config.free_calls_before_forced_tick == 200
    assert config.script_idle_timeout_s == 5
    assert config.console_max_lines == 500
    backpack = content.get_upgrade("backpack")
    assert backpack.max_level == 5
    assert backpack.costs == [25, 60, 140, 300, 700]
    assert backpack.unlocked_by == "first_sale"
    pickaxe = content.get_upgrade("pickaxe")
    assert pickaxe.costs == [50, 150, 400, 1000, 2500]
    assert pickaxe.unlocked_by == "pocket_change"
    motor = content.get_upgrade("motor")
    assert motor.max_level == 3
    assert motor.costs == [100, 400, 1500]
    scanner = content.get_upgrade("scanner")
    assert scanner.max_level == 4
    assert scanner.costs == [150, 500, 1500, 4000]
    assert motor.unlocked_by == scanner.unlocked_by == "investor"


# -- direction / events --------------------------------------------------------


def test_direction_parse_and_deltas():
    assert Direction.parse("north") is Direction.NORTH
    assert Direction.parse("n") is Direction.NORTH
    assert Direction.parse("EAST") is Direction.EAST
    assert Direction.parse("w") is Direction.WEST
    assert (Direction.NORTH.dx, Direction.NORTH.dy) == (0, -1)
    assert (Direction.SOUTH.dx, Direction.SOUTH.dy) == (0, 1)
    with pytest.raises(ValueError):
        Direction.parse("up")


def test_event_bus_subscribe_and_publish():
    bus = EventBus()
    seen = []
    bus.subscribe(Moved, seen.append)
    event = Moved(x=1, y=2, direction="east")
    bus.publish(event)
    assert seen == [event]


def test_all_unlocked():
    view = AllUnlocked()
    assert view.is_ore_unlocked("ruby")
    assert view.is_function_unlocked("sell")
    assert view.is_upgrade_unlocked("backpack")
    assert view.is_module_unlocked("random")


# -- acceptance ---------------------------------------------------------------


def test_headless_move_mine_sell(content):
    engine, world, miner, _ = _engine(content)
    result = _submit(engine, Move(Direction.EAST))
    assert result["ok"] and (miner.x, miner.y) == (1, 0)
    _submit(engine, Move(Direction.EAST))
    assert (miner.x, miner.y) == (2, 0)
    mine_result = _submit(engine, Mine())
    if mine_result["ok"]:
        assert miner.inventory_size == 1
    _submit(engine, Move(Direction.WEST))
    _submit(engine, Move(Direction.WEST))
    sell_result = _submit(engine, Sell())
    assert sell_result["ok"]
    assert miner.inventory == {}


# -- tick costs -----------------------------------------------------------------


def test_tick_costs(content):
    engine, world, miner, _ = _engine(content)
    assert Move(Direction.EAST).cost_ticks(engine) == content.config.move_ticks
    assert Peek().cost_ticks(engine) == 0
    assert Position().cost_ticks(engine) == 0
    assert Inventory().cost_ticks(engine) == 0
    assert Stats().cost_ticks(engine) == 0
    assert Wait(3).cost_ticks(engine) == 3
    assert Sell().cost_ticks(engine) == content.config.sell_ticks
    # Stone at (2, 0): hardness 1, mine_tick_base 3, tool_power 1.
    miner.x, miner.y = _find_tile(world, "stone")
    assert world.tile_at(miner.x, miner.y, 0).ore_id == "stone"
    assert Mine().cost_ticks(engine) == 3
    miner.scan_radius = 2
    assert Scan(5).cost_ticks(engine) == 1 + 2
    assert Scan(1).cost_ticks(engine) == 2

    tick0 = engine.tick
    ticket = engine.submit(Position())
    assert ticket.done and engine.tick == tick0
    ticket = engine.submit(Wait(3))
    assert not ticket.done
    engine.step()
    engine.step()
    assert not ticket.done
    engine.step()
    assert ticket.done and engine.tick == tick0 + 3


def test_fifo_queue(content):
    engine, world, miner, _ = _engine(content)
    tickets = [
        engine.submit(Move(Direction.EAST)),
        engine.submit(Move(Direction.EAST)),
        engine.submit(Mine()),
    ]
    assert not any(ticket.done for ticket in tickets)
    engine.run_until_idle()
    assert all(ticket.done for ticket in tickets)
    assert (miner.x, miner.y) == (2, 0)
    # The queued Mine was costed at the tile reached by the Moves.
    assert engine.tick == 4 + 4 + 3


# -- determinism ---------------------------------------------------------------


def test_same_seed_same_commands_same_state_and_events(content):
    def run():
        engine, world, miner, bus = _engine(content)
        log = []
        for event_type in (Moved, MineAttempted, OreMined, Sold, UpgradeBought, TickAdvanced):
            bus.subscribe(event_type, lambda e, log=log: log.append(repr(e)))
        for command in (
            Move(Direction.EAST),
            Move(Direction.EAST),
            Mine(),
            Mine(),
            Wait(2),
            Position(),
        ):
            _submit(engine, command)
        return engine, world, miner, log

    engine_a, world_a, miner_a, log_a = run()
    engine_b, world_b, miner_b, log_b = run()
    assert miner_a.to_dict() == miner_b.to_dict()
    assert world_a.to_dict() == world_b.to_dict()
    assert engine_a.tick == engine_b.tick
    assert log_a == log_b


# -- mining rules ---------------------------------------------------------------


def test_capacity_limit(content):
    engine, world, miner, _ = _engine(content)
    miner.x, miner.y = _find_tile(world, "stone")
    miner.capacity = 1
    miner.inventory = {"stone": 1}
    tick0 = engine.tick
    result = _submit(engine, Mine())
    assert result == result  # result is present
    assert result["ok"] is False
    assert result["reason"] == "inventory_full"
    assert engine.tick == tick0
    assert miner.inventory == {"stone": 1}


def test_nothing_to_mine_on_base(content):
    engine, world, miner, _ = _engine(content)
    result = _submit(engine, Mine())
    assert result["ok"] is False
    assert result["reason"] == "nothing_to_mine"


def test_locked_ore_and_peek_unknown(content):
    engine, world, miner, _ = _engine(content, progression=_LockedCoal())
    miner.x, miner.y = _find_tile(world, "coal")
    assert _submit(engine, Peek())["ore"] == "unknown"
    result = _submit(engine, Mine())
    assert result["ok"] is False
    assert result["reason"] == "locked_ore"


def test_tool_too_weak(content):
    engine, world, miner, _ = _engine(content)
    miner.x, miner.y = _find_tile(world, "copper")
    miner.tool_tier = 0
    result = _submit(engine, Mine())
    assert result["ok"] is False
    assert result["reason"] == "tool_too_weak"
    miner.tool_tier = 1
    assert Mine().cost_ticks(engine) == math.ceil(3 * 3 / 1)


def test_peek_and_scan(content):
    engine, world, miner, _ = _engine(content)
    assert _submit(engine, Peek())["ore"] is None
    miner.x, miner.y = _find_tile(world, "stone")
    assert _submit(engine, Peek())["ore"] == "stone"
    miner.scan_radius = 1
    result = _submit(engine, Scan(1))
    assert result["ok"]
    assert [0, 0, "stone"] in result["tiles"]


def test_scan_locked_is_unknown(content):
    engine, world, miner, _ = _engine(content, progression=_LockedCoal())
    miner.x, miner.y = _find_tile(world, "coal")
    miner.scan_radius = 0
    result = _submit(engine, Scan(0))
    assert [0, 0, "unknown"] in result["tiles"]


@pytest.mark.parametrize("ore_id", ["stone", "coal"])
def test_mining_probability_within_3_sigma(content, ore_id):
    engine, world, miner, _ = _engine(content)
    miner.x, miner.y = _find_tile(world, ore_id)
    ore = content.get_ore(ore_id)
    miner.capacity = 10**9
    attempts = 5000
    successes = 0
    for _ in range(attempts):
        world.delta.clear()
        miner.inventory.clear()
        result = _submit(engine, Mine())
        if result["ok"]:
            successes += 1
    p = ore.mine_probability
    sigma = math.sqrt(attempts * p * (1 - p))
    assert abs(successes - attempts * p) <= 3 * sigma


# -- economy ---------------------------------------------------------------------


def test_sell_only_on_base_and_money(content):
    engine, world, miner, _ = _engine(content)
    miner.x, miner.y = _find_tile(world, "stone")
    miner.inventory = {"stone": 3, "coal": 2}
    tick0 = engine.tick
    result = _submit(engine, Sell())
    assert result["ok"] is False
    assert engine.tick == tick0
    assert miner.money == 0
    # Move onto the base (miner starts there in a fresh engine).
    engine2, _, miner2, _ = _engine(content)
    miner2.inventory = {"stone": 3, "coal": 2}
    sold = _submit(engine2, Sell())
    assert sold["ok"]
    expected = 3 * content.get_ore("stone").base_value + 2 * content.get_ore("coal").base_value
    assert sold["money"] == expected
    assert miner2.money == expected
    assert miner2.stats.total_earned == expected
    assert miner2.stats.sales == 1
    assert miner2.inventory == {}


def test_sold_event(content):
    engine, _, miner, bus = _engine(content)
    seen = []
    bus.subscribe(Sold, seen.append)
    miner.inventory = {"stone": 2}
    _submit(engine, Sell())
    assert seen and seen[0].money == 2 and seen[0].items == {"stone": 2}


def test_upgrades_apply_and_respect_cost_and_max_level(content):
    engine, _, miner, bus = _engine(content)
    seen = []
    bus.subscribe(UpgradeBought, seen.append)
    miner.money = 100
    result = _submit(engine, BuyUpgrade("backpack"))
    assert result["ok"] and result["level"] == 1
    assert miner.capacity == 20
    assert miner.money == 100 - 25
    assert seen[0].id == "backpack" and seen[0].level == 1
    # Insufficient funds.
    miner.money = 0
    result = _submit(engine, BuyUpgrade("backpack"))
    assert result["ok"] is False
    assert miner.capacity == 20
    # Pickaxe raises power and tier.
    miner.money = 1000
    assert _submit(engine, BuyUpgrade("pickaxe"))["ok"]
    assert miner.tool_power == 2 and miner.tool_tier == 1
    # Motor never drops move_ticks below 1.
    miner.money = 10000
    for _ in range(3):
        assert _submit(engine, BuyUpgrade("motor"))["ok"]
    assert miner.move_ticks == 1
    result = _submit(engine, BuyUpgrade("motor"))
    assert result["ok"] is False
    assert miner.move_ticks == 1
    # Scanner.
    assert _submit(engine, BuyUpgrade("scanner"))["ok"]
    assert miner.scan_radius == 3


def test_buy_upgrade_after_sell_fifo(content):
    engine, _, miner, _ = _engine(content)
    miner.inventory = {"stone": 30}
    sell_ticket = engine.submit(Sell())
    buy_ticket = engine.submit(BuyUpgrade("backpack"))
    engine.run_until_idle()
    assert sell_ticket.done and buy_ticket.done
    assert buy_ticket.result["ok"]
    assert miner.capacity == 20


def test_mine_events_and_stats(content):
    engine, world, miner, bus = _engine(content)
    attempted, mined = [], []
    bus.subscribe(MineAttempted, attempted.append)
    bus.subscribe(OreMined, mined.append)
    miner.x, miner.y = _find_tile(world, "stone")
    result = _submit(engine, Mine())
    assert attempted and attempted[0].ore_id == "stone"
    assert attempted[0].success == result["ok"]
    if result["ok"]:
        assert mined and mined[0].amount == 1
        assert world.tile_at(miner.x, miner.y, engine.tick).depleted
    stats = _submit(engine, Stats())
    assert stats["stats"]["stone"]["attempts"] == 1
    assert stats["stats"]["stone"]["successes"] == (1 if result["ok"] else 0)
