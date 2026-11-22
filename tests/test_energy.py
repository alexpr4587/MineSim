"""Tests for batteries, energy costs, charging and rescue (prompt 30)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from minesim.core.commands import (
    Ascend,
    Battery,
    BuyUpgrade,
    Charge,
    Descend,
    EnergyCost,
    Mine,
    Move,
)
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.engine import AllUnlocked, GameEngine
from minesim.core.events import (
    Charged,
    EnergySpent,
    EventBus,
    MinerRescued,
    MinerStranded,
)
from minesim.core.game import Game
from minesim.core.miner import Miner
from minesim.core.save import CURRENT_VERSION, SaveGame
from minesim.core.world import World, WorldGenerator

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def content():
    return load_content()


def _content_with(content, **config_updates):
    config = content.config.model_copy(update=config_updates)
    return replace(content, config=config)


def _engine(content, **config_updates):
    if config_updates:
        content = _content_with(content, **config_updates)
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    bus = EventBus()
    engine = GameEngine(world, miner, content, bus, AllUnlocked())
    return engine, world, miner, bus


def _find_tile(world, ore_id: str, layer: int = 0, start: int = 2) -> tuple[int, int]:
    for y in range(start, start + 40):
        for x in range(start, start + 40):
            if world.tile_at(x, y, 0, layer=layer).ore_id == ore_id:
                return x, y
    raise AssertionError(f"no tile with {ore_id} on layer {layer}")


def _submit(engine, command):
    ticket = engine.submit(command)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


def test_config_and_upgrades(content):
    config = content.config
    assert config.battery_start == 300
    assert config.energy_move == 1
    assert config.energy_mine_base == 1
    assert config.energy_scan_per_radius == 1
    assert config.energy_shaft == 15
    assert config.charge_rate == 10
    assert config.rescue_ticks == 600
    assert config.rescue_energy_fraction == 0.25
    assert config.rescue_loses_inventory is True
    battery = content.get_upgrade("battery")
    assert battery.max_level == 5
    assert battery.costs == [200, 600, 1500, 4000, 9000]
    assert battery.stat_changes() == {"battery_capacity": 100}
    charger = content.get_upgrade("charger")
    assert charger.max_level == 3
    assert charger.costs == [300, 900, 2500]
    assert charger.stat_changes() == {"charge_rate": 10}


def test_battery_starts_full_and_move_spends_energy(content):
    engine, _world, miner, bus = _engine(content)
    spent = []
    bus.subscribe(EnergySpent, spent.append)
    assert miner.energy == 300
    assert miner.battery_capacity == 300
    assert engine.submit(Battery()).result == {
        "ok": True,
        "energy": 300,
        "capacity": 300,
        "charge_rate": 10,
    }
    ticket = engine.submit(Move(Direction.EAST))
    assert ticket.done is False
    assert miner.energy == 299
    assert spent and spent[0].amount == 1
    engine.run_until_idle()
    assert (miner.x, miner.y) == (1, 0)


def test_energy_costs_use_the_layer_multiplier(content):
    engine, _world, miner, _bus = _engine(content)
    assert _submit(engine, EnergyCost("move"))["cost"] == 1
    miner.scan_radius = 2
    assert _submit(engine, EnergyCost("scan", 2))["cost"] == 2
    assert _submit(engine, EnergyCost("scan", 9))["cost"] == 2
    miner.x, miner.y = _find_tile(engine.world, "stone")
    assert _submit(engine, EnergyCost("mine"))["cost"] == 1
    miner.layer = 1
    miner.x = miner.y = 0
    miner.scan_radius = 5
    assert _submit(engine, EnergyCost("move"))["cost"] == 2
    assert _submit(engine, EnergyCost("scan", 5))["cost"] == 6
    assert _submit(engine, EnergyCost("ascend"))["cost"] == 18
    assert Ascend().energy_cost(engine, miner) == 18
    miner.layer = 0
    miner.x = miner.y = 0
    miner.upgrades["shaft"] = 1
    assert _submit(engine, EnergyCost("descend"))["cost"] == 15
    assert Descend().energy_cost(engine, miner) == 15
    assert _submit(engine, EnergyCost("nonsense"))["ok"] is False


def test_mine_energy_depends_on_hardness(content):
    engine, _world, miner, _bus = _engine(content)
    miner.x, miner.y = _find_tile(engine.world, "stone")
    assert _submit(engine, EnergyCost("mine"))["cost"] == 1
    miner.x, miner.y = _find_tile(engine.world, "coal")
    assert _submit(engine, EnergyCost("mine"))["cost"] == 2
    ticket = engine.submit(Mine())
    assert ticket.done is False
    assert miner.energy == 298


def test_low_energy_refuses_after_one_tick_without_spending(content):
    engine, _world, miner, _bus = _engine(content)
    miner.x, miner.y = 5, 5
    miner.energy = 0
    ticket = engine.submit(Move(Direction.EAST))
    assert ticket.done is False
    assert miner.active is not None
    engine.step()
    assert ticket.done is True
    assert ticket.result["ok"] is False
    assert ticket.result["reason"] == "low_energy"
    assert miner.energy == 0
    assert (miner.x, miner.y) == (5, 5)
    assert miner.stranded_since == 1


def test_charge_restores_the_missing_energy(content):
    engine, _world, miner, bus = _engine(content)
    charged = []
    bus.subscribe(Charged, charged.append)
    miner.battery_capacity = 37
    miner.energy = 12
    ticket = engine.submit(Charge())
    assert ticket.done is False
    engine.step()
    engine.step()
    assert miner.energy == 12
    assert ticket.done is False
    engine.step()
    assert ticket.done is True
    assert miner.energy == 37
    assert ticket.result["charged"] == 25
    assert charged and charged[0].amount == 25


def test_charge_requires_a_base_or_station(content):
    engine, _world, miner, _bus = _engine(content)
    miner.x, miner.y = 5, 5
    miner.energy = 0
    ticket = engine.submit(Charge())
    assert ticket.done is True
    assert ticket.result["ok"] is False
    assert ticket.result["reason"] == "not_on_station"


def test_battery_and_charger_upgrades(content):
    engine, _world, miner, _bus = _engine(content)
    miner.money = 100_000
    assert _submit(engine, BuyUpgrade("battery"))["level"] == 1
    assert miner.battery_capacity == 400
    assert _submit(engine, BuyUpgrade("charger"))["level"] == 1
    assert miner.charge_rate == 20
    assert _submit(engine, Battery())["capacity"] == 400


def test_stranded_miner_is_rescued_and_loses_the_inventory(content):
    engine, _world, miner, bus = _engine(
        content,
        rescue_ticks=3,
        rescue_energy_fraction=0.5,
        rescue_loses_inventory=True,
    )
    stranded = []
    rescued = []
    bus.subscribe(MinerStranded, stranded.append)
    bus.subscribe(MinerRescued, rescued.append)
    miner.x, miner.y = 5, 5
    miner.energy = 0
    miner.inventory = {"stone": 2}
    for _ in range(4):
        engine.step()
    assert stranded and stranded[0].miner_id == 0
    assert rescued and rescued[0].lost_items == {"stone": 2}
    assert (miner.x, miner.y) == (0, 0)
    assert miner.energy == 150
    assert miner.inventory == {}
    assert miner.stranded_since is None


def test_rescue_can_keep_the_inventory(content):
    engine, _world, miner, _bus = _engine(
        content,
        rescue_ticks=1,
        rescue_energy_fraction=0.25,
        rescue_loses_inventory=False,
    )
    miner.x, miner.y = 5, 5
    miner.energy = 0
    miner.inventory = {"coal": 1}
    engine.step()
    engine.step()
    assert (miner.x, miner.y) == (0, 0)
    assert miner.energy == 75
    assert miner.inventory == {"coal": 1}


def test_miner_on_the_base_is_never_stranded(content):
    engine, _world, miner, _bus = _engine(content, rescue_ticks=1)
    stranded = []
    engine.events.subscribe(MinerStranded, stranded.append)
    miner.energy = 0
    for _ in range(5):
        engine.step()
    assert not stranded
    assert miner.stranded_since is None
    assert (miner.x, miner.y) == (0, 0)


def test_energy_and_capacity_survive_a_save_round_trip(content, tmp_path):
    game = Game(content, seed=7)
    game.miner.energy = 123
    game.miner.battery_capacity = 500
    game.miner.charge_rate = 20
    path = game.save(tmp_path / "slot.json")
    loaded = Game.load(path, content)
    assert loaded.miner.energy == 123
    assert loaded.miner.battery_capacity == 500
    assert loaded.miner.charge_rate == 20


def test_v10_save_fixture_migrates_to_full_battery(content):
    raw = json.loads((FIXTURES / "save_v10.json").read_text(encoding="utf-8"))
    assert raw["version"] == 10
    savegame = SaveGame.load(FIXTURES / "save_v10.json")
    assert savegame.version == CURRENT_VERSION == 13
    assert savegame.fleet[0]["energy"] == 300
    game = Game.load(FIXTURES / "save_v10.json", content)
    assert game.miner.energy == 300
    assert game.miner.battery_capacity == 300
