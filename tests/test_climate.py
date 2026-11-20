"""Tests for temperature, overheating and fleet airflow (prompt 31)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from minesim.core.commands import BuyUpgrade, Climate, Cool, Mine, Move, Temperature, Wait
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.engine import AllUnlocked, GameEngine
from minesim.core.events import EventBus, MinerOverheated, MinerRecovered
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


def _deep(engine, miner):
    miner.layer = 2
    miner.x, miner.y = 5, 5


def _submit(engine, command, miner_id=0):
    ticket = engine.submit(command, miner_id=miner_id)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


def _first_overheat_tick(engine, ticks=1500):
    for tick in range(1, ticks + 1):
        engine.step()
        if any(miner.cooldown_remaining for miner in engine.miners.values()):
            return tick
    raise AssertionError("no miner overheated")


def test_config_upgrades_and_functions(content):
    config = content.config
    assert config.heat_gain_per_level == pytest.approx(0.12)
    assert config.cool_rate == pytest.approx(2.0)
    assert config.overheat_at == 100
    assert config.cooldown_ticks == 300
    assert config.cooldown_temperature == 50
    assert config.airflow_start == 4
    assert config.overload_penalty == pytest.approx(0.5)
    assert config.hot_layer_min_heat == 1
    cooling = content.get_upgrade("cooling")
    assert cooling.max_level == 4
    assert cooling.costs == [400, 1200, 3000, 7000]
    assert cooling.stat_changes() == {"heat_gain_reduction_percent": 15}
    ventilation = content.get_upgrade("ventilation")
    assert ventilation.max_level == 5
    assert ventilation.costs == [500, 1500, 3500, 8000, 16000]
    assert ventilation.stat_changes() == {"airflow_bonus": 2}
    for name in ("temperature", "cool", "climate"):
        function = content.functions[name]
        assert function.unlocked_by is None


def test_hot_layers_heat_only_while_working(content):
    engine, _world, miner, _bus = _engine(content)
    _deep(engine, miner)
    engine.submit(Wait(100))
    for _ in range(100):
        engine.step()
    assert miner.temperature == pytest.approx(12.0)

    idle, _world, idle_miner, _bus = _engine(content)
    _deep(idle, idle_miner)
    for _ in range(20):
        idle.step()
    assert idle_miner.temperature == 0.0


def test_stations_and_the_surface_cool_the_miner(content):
    engine, _world, miner, _bus = _engine(content)
    miner.layer = 2
    miner.x, miner.y = 0, 0
    miner.temperature = 40.0
    engine.submit(Wait(2))
    engine.run_until_idle()
    assert miner.temperature == pytest.approx(36.0)

    surface, _world, surface_miner, _bus = _engine(content)
    surface_miner.temperature = 10.0
    for _ in range(5):
        surface.step()
    assert surface_miner.temperature == 0.0


def test_abyss_heats_twice_as_fast(content):
    engine, _world, miner, _bus = _engine(content)
    miner.layer = 3
    miner.x, miner.y = 5, 5
    engine.submit(Wait(50))
    for _ in range(50):
        engine.step()
    assert miner.temperature == pytest.approx(12.0)


def test_overheat_shutdown_recovery_and_refusals(content):
    engine, _world, miner, bus = _engine(
        content,
        heat_gain_per_level=10.0,
        cooldown_ticks=5,
        cooldown_temperature=50,
    )
    _deep(engine, miner)
    miner.temperature = 90.0
    overheated = []
    recovered = []
    bus.subscribe(MinerOverheated, overheated.append)
    bus.subscribe(MinerRecovered, recovered.append)
    ticket = engine.submit(Wait(100))
    engine.step()
    assert ticket.done is True
    assert ticket.result["ok"] is False
    assert ticket.result["reason"] == "overheated"
    assert miner.temperature == 100.0
    assert miner.cooldown_remaining == 5
    assert overheated and overheated[0].miner_id == 0

    move = engine.submit(Move(Direction.EAST))
    assert move.done is True
    assert move.result == {
        "ok": False,
        "reason": "overheated",
        "cost": 0,
        "energy": miner.energy,
    }
    mine = engine.submit(Mine())
    assert mine.done is True
    assert mine.result["reason"] == "overheated"
    assert engine.submit(Temperature()).result["overheated"] is True
    assert engine.submit(Climate()).result["layer"] == 2

    for _ in range(4):
        engine.step()
    assert miner.cooldown_remaining == 1
    assert miner.temperature == 100.0
    engine.step()
    assert miner.cooldown_remaining == 0
    assert miner.temperature == 50.0
    assert recovered and recovered[0].miner_id == 0


def test_cool_command_costs_the_cool_rate_time(content):
    engine, _world, miner, _bus = _engine(content)
    miner.layer = 2
    miner.x, miner.y = 0, 0
    miner.temperature = 80.0
    ticket = engine.submit(Cool(30))
    assert ticket.done is False
    for _ in range(24):
        engine.step()
    assert ticket.done is False
    assert miner.temperature == pytest.approx(32.0)
    engine.step()
    assert ticket.done is True
    assert ticket.result["ok"] is True
    assert ticket.result["temperature"] == pytest.approx(30.0)

    off_station, _world, away, _bus = _engine(content)
    _deep(off_station, away)
    result = _submit(off_station, Cool(30))
    assert result["ok"] is False
    assert result["reason"] == "not_on_station"


def test_climate_reports_airflow_load_and_overload(content):
    engine, _world, _miner, _bus = _engine(content)
    for _ in range(5):
        engine.spawn_miner()
    for miner in engine.miners.values():
        _deep(engine, miner)
    state = _submit(engine, Climate())
    assert state == {
        "layer": 2,
        "heat": 1,
        "airflow": 4,
        "miners_in_hot_layers": 6,
        "overload": pytest.approx(1.0),
    }
    assert _submit(engine, Temperature())["heat"] == 1


def test_ventilation_prevents_overload_and_delays_overheating(content):
    def first(level):
        engine, _world, _miner, _bus = _engine(content)
        engine.player_stats.upgrades["ventilation"] = int(level)
        for _ in range(5):
            engine.spawn_miner()
        for miner in engine.miners.values():
            _deep(engine, miner)
            miner.temperature = 0.0
            engine.submit(Wait(2000), miner_id=miner.id)
        assert engine.airflow() == 4 + int(level) * 2
        return _first_overheat_tick(engine)

    without = first(0)
    with_vent = first(5)
    assert without < with_vent
    assert with_vent > without * 1.5


def test_cooling_upgrade_reduces_heat_gain(content):
    def temperature_after_100(level):
        engine, _world, miner, _bus = _engine(content)
        engine.player_stats.upgrades["cooling"] = int(level)
        _deep(engine, miner)
        engine.submit(Wait(100))
        for _ in range(100):
            engine.step()
        return miner.temperature

    assert temperature_after_100(0) == pytest.approx(12.0)
    assert temperature_after_100(1) == pytest.approx(10.2)


def test_climate_upgrades_can_be_bought(content):
    engine, _world, miner, _bus = _engine(content)
    miner.money = 100_000
    assert _submit(engine, BuyUpgrade("cooling"))["level"] == 1
    assert _submit(engine, BuyUpgrade("ventilation"))["level"] == 1
    assert engine.airflow() == 6


def test_v11_save_fixture_migrates_temperature():
    path = FIXTURES / "save_v11.json"
    savegame = SaveGame.load(path)
    assert savegame.version == CURRENT_VERSION == 12
    assert savegame.fleet[0]["temperature"] == 0.0
    assert savegame.fleet[0]["cooldown_remaining"] == 0
    assert savegame.player_stats["money"] == 43


def test_temperature_and_cooldown_survive_a_save_round_trip(tmp_path):
    game = Game.new(seed=31)
    game.miner.temperature = 78.5
    game.miner.cooldown_remaining = 12
    path = game.save(tmp_path / "slot.json")
    loaded = Game.load(path)
    assert loaded.miner.temperature == pytest.approx(78.5)
    assert loaded.miner.cooldown_remaining == 12
