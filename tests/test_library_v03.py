"""Tests for the v0.3 library helpers, modules and examples (prompt 22)."""

from __future__ import annotations

from pathlib import Path

import pytest

from minesim.core.commands import (
    Contracts,
    Deliver,
    Events,
    Inventory,
    Mine,
    Move,
    OreInfo,
    Peek,
    Price,
    PriceHistory,
    Prices,
    Recipes,
    Refine,
    RefineryStatus,
    Scan,
    Sell,
    SellStock,
    Stock,
    Unload,
    Wait,
)
from minesim.core.content import load_content
from minesim.core.contracts import Contract
from minesim.core.direction import Direction
from minesim.core.engine import AllUnlocked, GameEngine
from minesim.core.events import EventBus
from minesim.core.miner import Miner
from minesim.core.world import World, WorldGenerator
from minesim.runner import minerlib
from minesim.scripting.host import ScriptState
from minesim.scripting.manager import ScriptManager

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def content():
    return load_content()


def _engine(content):
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    engine = GameEngine(world, miner, content, EventBus(), AllUnlocked())
    return engine, world, miner


def _submit(engine, command):
    ticket = engine.submit(command)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


def _inject(monkeypatch, engine, miner):
    def move(direction):
        return _submit(engine, Move(Direction.parse(direction)))

    def position():
        return (miner.x, miner.y)

    def peek():
        return _submit(engine, Peek())["ore"]

    def mine():
        return _submit(engine, Mine())

    def scan(radius):
        result = _submit(engine, Scan(int(radius)))
        return [tuple(tile) for tile in result["tiles"]]

    def inventory():
        return _submit(engine, Inventory())["inventory"]

    def sell():
        return _submit(engine, Sell())["money"]

    def unload():
        return _submit(engine, Unload())

    def stock():
        return _submit(engine, Stock())

    def sell_stock(item, amount=None):
        return _submit(engine, SellStock(str(item), amount))["money"]

    def price(item):
        return _submit(engine, Price(str(item)))["price"]

    def prices():
        return _submit(engine, Prices())["prices"]

    def price_history(item, n=50):
        return _submit(engine, PriceHistory(str(item), int(n)))["history"]

    def recipes():
        return _submit(engine, Recipes())["recipes"]

    def refine(recipe_id, times=1):
        return _submit(engine, Refine(str(recipe_id), int(times)))

    def refinery():
        return _submit(engine, RefineryStatus())["jobs"]

    def contracts():
        return _submit(engine, Contracts())["contracts"]

    def deliver(contract_id):
        return _submit(engine, Deliver(int(contract_id)))["reward"]

    def events():
        return _submit(engine, Events())["events"]

    def ore_info(ore_id):
        return _submit(engine, OreInfo(str(ore_id)))["info"]

    def wait(ticks):
        return _submit(engine, Wait(int(ticks)))

    for name, value in {
        "move": move,
        "position": position,
        "peek": peek,
        "mine": mine,
        "scan": scan,
        "inventory": inventory,
        "sell": sell,
        "unload": unload,
        "stock": stock,
        "sell_stock": sell_stock,
        "price": price,
        "prices": prices,
        "price_history": price_history,
        "recipes": recipes,
        "refine": refine,
        "refinery": refinery,
        "contracts": contracts,
        "deliver": deliver,
        "events": events,
        "ore_info": ore_info,
        "wait": wait,
    }.items():
        monkeypatch.setattr(minerlib, name, value)


def _position_after(start, directions):
    x, y = start
    for direction in directions:
        if direction == "north":
            y -= 1
        elif direction == "south":
            y += 1
        elif direction == "east":
            x += 1
        elif direction == "west":
            x -= 1
    return (x, y)


def test_route_avoids_a_slow_zone(content, monkeypatch):
    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine, miner)
    miner.x, miner.y = 0, 0
    monkeypatch.setattr(
        minerlib,
        "events",
        lambda: [{"kind": "slow_zone", "x": 0, "y": 1, "radius": 1, "ends_in": 100}],
    )
    directions = minerlib.route(0, 3)
    assert directions
    assert _position_after((0, 0), directions) == (0, 3)
    x, y = 0, 0
    for direction in directions:
        x, y = _position_after((x, y), [direction])
        assert (x, y) != (0, 1)
        assert (x, y) != (1, 1)
        assert (x, y) != (-1, 1)
    assert len(directions) > 3

    miner.x, miner.y = 0, 0
    minerlib.goto_route(0, 3)
    assert (miner.x, miner.y) == (0, 3)


def test_ore_map_reads_the_scanner(content, monkeypatch):
    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine, miner)
    miner.scan_radius = 6
    miner.x, miner.y = 0, 0
    mapping = minerlib.ore_map(6)
    assert isinstance(mapping, dict)
    assert all(isinstance(key, tuple) and len(key) == 2 for key in mapping)
    assert all(isinstance(value, str) for value in mapping.values())


def test_moving_average_linear_fit_trend_and_forecast(monkeypatch):
    assert minerlib.moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]
    assert minerlib.moving_average([1, 2], 5) == []
    assert minerlib.linear_fit([0, 1, 2, 3], [1, 3, 5, 7]) == (2.0, 1.0)
    assert minerlib.linear_fit([1], [2]) == (0.0, 0.0)
    assert minerlib.linear_fit([2, 2, 2], [1, 2, 3]) == (0.0, 0.0)

    history = [100.0, 102.0, 104.0, 106.0]
    monkeypatch.setattr(minerlib, "price_history", lambda item, n=50: history[-n:])
    assert minerlib.sma("stone", 2) == pytest.approx(105.0)
    assert minerlib.trend("stone", 4) == pytest.approx(2.0)

    forecast = minerlib.Forecast(0.5)
    assert forecast.predict() == 0.0
    assert forecast.update(2.0) == 2.0
    assert forecast.update(4.0) == 3.0
    assert forecast.predict() == 3.0
    with pytest.raises(ValueError):
        minerlib.Forecast(0.0)


def test_sell_if_thresholds_and_best_item(content, monkeypatch):
    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine, miner)
    miner.x, miner.y = 0, 0
    engine.warehouse.add("stone", 5)
    engine.market._states["stone"].index = 1.5
    engine.market._states["stone"].impact = 0.0
    engine.market._states["stone"].shock = 1.0

    assert minerlib.sell_if("stone", 2.0) == 0
    assert engine.warehouse.count("stone") == 5
    earned = minerlib.sell_if("stone", 1.0)
    assert earned > 0
    assert engine.warehouse.count("stone") == 0
    assert minerlib.sell_if("stone", 1.0) == 0

    engine.warehouse.add("stone", 4)
    engine.warehouse.add("coal", 4)
    engine.market._states["stone"].index = 2.0
    engine.market._states["coal"].index = 1.2
    assert minerlib.best_item_to_sell() == "stone"
    assert (engine.warehouse.count("stone"), engine.warehouse.count("coal")) == (4, 4)


def test_refine_all_uses_limited_stock(content, monkeypatch):
    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine, miner)
    miner.x, miner.y = 0, 0
    engine.warehouse.add("copper", 5)
    assert minerlib.refine_all("copper_bar") == 1
    assert engine.warehouse.count("copper") == 2
    assert len(engine.refinery.jobs) == 1
    assert engine.refinery.jobs[0].times == 1
    assert minerlib.refine_all("copper_bar") == 0

    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine, miner)
    miner.x, miner.y = 0, 0
    engine.warehouse.add("copper", 9)
    assert minerlib.refine_all("copper_bar") == 3
    assert engine.warehouse.count("copper") == 0
    assert engine.refinery.jobs[0].times == 3


def test_best_contract_and_fulfill(content, monkeypatch):
    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine, miner)
    miner.x, miner.y = 0, 0
    contract = Contract(
        id=7,
        item="stone",
        quantity=5,
        reward=100,
        created=0,
        deadline=10000,
        slot=0,
    )
    engine.contracts.contracts.append(contract)
    assert minerlib.best_contract() is None

    engine.warehouse.add("stone", 10)
    best = minerlib.best_contract()
    assert best is not None
    assert best["id"] == 7
    assert minerlib.fulfill(7) == 100
    assert engine.warehouse.count("stone") == 5
    assert engine.contracts.contracts == []


def test_worker_subclasses_and_fleet(monkeypatch):
    monkeypatch.setattr(minerlib, "peek", lambda: "stone")
    monkeypatch.setattr(minerlib, "nearest", lambda ore: (0, 0))
    monkeypatch.setattr(minerlib, "position", lambda: (0, 0))
    monkeypatch.setattr(minerlib, "goto", lambda x, y: None)
    monkeypatch.setattr(minerlib, "haul", lambda: 5)
    monkeypatch.setattr(minerlib, "mine", lambda: {"ok": True, "amount": 1})

    digger = minerlib.MinerWorker("digger", "stone")
    assert digger.run(3) == 3
    assert digger.mined == 3
    assert digger.hauls == 0

    calls = {"count": 0}

    def sometimes_full():
        calls["count"] += 1
        if calls["count"] == 2:
            return {"ok": False, "reason": "inventory_full"}
        return {"ok": True, "amount": 1}

    monkeypatch.setattr(minerlib, "mine", sometimes_full)
    refilling = minerlib.MinerWorker("refilling", "stone")
    refilling.run(3)
    assert refilling.hauls == 1
    assert refilling.earned == 5

    work = {"work": {"x": 2, "y": 2, "item": "stone", "haul": True}}
    visited: list[tuple[int, int]] = []
    monkeypatch.setattr(minerlib, "shared_get", lambda key, default=None: work.get(key, default))
    monkeypatch.setattr(minerlib, "shared_set", lambda key, value: work.__setitem__(key, value))
    monkeypatch.setattr(minerlib, "wait", lambda ticks: None)
    monkeypatch.setattr(minerlib, "goto", lambda x, y: visited.append((x, y)))
    hauler = minerlib.HaulerWorker("hauler")
    assert hauler.run(2) == 2
    assert (2, 2) in visited
    assert hauler.carried == 10

    monkeypatch.setattr(minerlib, "drone_id", lambda: 0)
    monkeypatch.setattr(minerlib, "drones", lambda: [{"id": 0}, {"id": 1}, {"id": 2}])
    monkeypatch.setattr(minerlib, "kill_drone", lambda drone_id: drone_id == 1)
    monkeypatch.setattr(minerlib, "spawn_drone", lambda script: 9)
    shared: dict[str, object] = {}
    monkeypatch.setattr(minerlib, "shared_set", lambda key, value: shared.__setitem__(key, value))
    monkeypatch.setattr(minerlib, "shared_get", lambda key, default=None: shared.get(key, default))
    fleet = minerlib.Fleet()
    assert fleet.spawn("worker.py") == 9
    assert fleet.kill_all() == [1]
    fleet.broadcast("goal", 4)
    assert fleet.gather("goal") == 4


def test_v03_examples_are_listed_and_compile(content):
    expected = {
        "09_market_watcher",
        "10_refine_everything",
        "11_contract_runner",
        "12_two_drones",
        "13_worker_classes",
        "14_event_hunter",
        "15_price_forecast",
        "16_fleet_manager",
    }
    assert expected <= set(content.examples)
    examples_dir = ROOT / "src" / "minesim" / "examples"
    for example_id in expected:
        example = content.examples[example_id]
        path = examples_dir / example.file
        assert path.is_file()
        source = path.read_text(encoding="utf-8")
        assert source.startswith("# ")
        assert "# Unlocks needed:" in source
        compile(source, str(path), "exec")


def test_new_modules_are_available(content):
    expected = {
        "abc": "inheritance",
        "enum": "inheritance",
        "bisect": "chartist",
        "operator": "trend_follower",
    }
    for name, unlocked_by in expected.items():
        assert name in content.modules
        assert content.modules[name].unlocked_by == unlocked_by


@pytest.mark.integration
@pytest.mark.parametrize(
    "example_id",
    [
        "09_market_watcher",
        "10_refine_everything",
        "11_contract_runner",
        "12_two_drones",
        "13_worker_classes",
        "14_event_hunter",
        "15_price_forecast",
        "16_fleet_manager",
    ],
)
def test_v03_examples_run_through_subprocess(example_id, content, tmp_path):
    example = content.examples[example_id]
    source = (ROOT / "src" / "minesim" / "examples" / example.file).read_text(encoding="utf-8")
    (tmp_path / example.file).write_text(source, encoding="utf-8")
    engine, _world, _miner = _engine(content)
    manager = ScriptManager(engine, tmp_path)
    manager.start_script(0, example.file)
    try:
        manager.run_lockstep(3000)
        host = manager.host(0)
        assert host is not None
        assert host.state is not ScriptState.FAILED, host.last_error
        assert host.last_error is None
    finally:
        manager.stop_all()
