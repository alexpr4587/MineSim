"""Tests for the v0.4 progression counters (prompt 34)."""

from __future__ import annotations

import pytest

from minesim.core.commands import Charge, Descend, Mine, Move, Unload, Wait
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.events import (
    Charged,
    DockServed,
    EnergySpent,
    LayerChanged,
    MineAttempted,
    MinerOverheated,
    MinerRescued,
    MinerStranded,
    MoveRefused,
    OreMined,
    TemperatureChanged,
)
from minesim.core.game import Game
from minesim.core.progression.state import ProgressionState
from minesim.core.save import CURRENT_VERSION, migrate


@pytest.fixture(scope="module")
def content():
    return load_content()


def _submit(game, command, miner_id=0):
    ticket = game.submit(command, miner_id=miner_id)
    game.run_until_idle()
    assert ticket.done
    return ticket.result


def _find_layer_tile(game, layer: int, start: int = 2) -> tuple[int, int, str]:
    for y in range(start, start + 60):
        for x in range(start, start + 60):
            tile = game.world.tile_at(x, y, 0, layer=layer)
            if tile.ore_id is not None:
                return x, y, str(tile.ore_id)
    raise AssertionError(f"no ore on layer {layer}")


def test_each_new_counter_from_synthetic_events():
    game = Game.new(seed=21)
    bus = game.events
    state = game.progression_state

    bus.publish(LayerChanged(miner_id=0, from_layer=0, to_layer=2))
    bus.publish(LayerChanged(miner_id=1, from_layer=0, to_layer=3))
    bus.publish(LayerChanged(miner_id=0, from_layer=2, to_layer=1))
    assert state.get_counter("max_layer") == 3
    assert state.get_counter("descents") == 2

    bus.publish(OreMined(ore_id="stone", amount=3, layer=1))
    bus.publish(OreMined(ore_id="stone", amount=2, layer=2))
    assert state.get_counter("mined_layer:1") == 3
    assert state.get_counter("mined_layer:2") == 2

    bus.publish(EnergySpent(miner_id=0, amount=7))
    bus.publish(EnergySpent(miner_id=1, amount=5))
    assert state.get_counter("energy_used") == 12

    bus.publish(Charged(miner_id=0, amount=100))
    bus.publish(Charged(miner_id=0, amount=50))
    assert state.get_counter("charges") == 2

    bus.publish(MinerStranded(miner_id=0))
    bus.publish(MinerRescued(miner_id=0))
    bus.publish(MinerOverheated(miner_id=0))
    assert state.get_counter("strandings") == 1
    assert state.get_counter("rescues") == 1
    assert state.get_counter("overheats") == 1

    bus.publish(TemperatureChanged(miner_id=0, temperature=62.0))
    bus.publish(TemperatureChanged(miner_id=0, temperature=84.9))
    bus.publish(TemperatureChanged(miner_id=0, temperature=40.0))
    assert state.get_counter("peak_temp") == 84

    bus.publish(DockServed(miner_id=0, units=6, waited_ticks=3))
    bus.publish(DockServed(miner_id=1, units=4, waited_ticks=7))
    assert state.get_counter("dock_wait_ticks") == 10
    assert state.get_counter("dock_units") == 10

    bus.publish(MineAttempted(ore_id="stone", success=False, reason="low_energy"))
    bus.publish(MineAttempted(ore_id="stone", success=False, reason="overheated"))
    bus.publish(MoveRefused(miner_id=0, reason="low_energy"))
    bus.publish(MoveRefused(miner_id=0, reason="overheated"))
    assert state.get_counter("fail:low_energy") == 2
    assert state.get_counter("fail:overheated") == 2
    assert state.get_counter("attempts:any") == 0

    bus.publish(LayerChanged(miner_id=1, from_layer=0, to_layer=2))
    bus.publish(LayerChanged(miner_id=2, from_layer=0, to_layer=2))
    assert state.get_counter("peak_deep_miners") == 2
    bus.publish(LayerChanged(miner_id=1, from_layer=2, to_layer=0))
    assert state.get_counter("peak_deep_miners") == 2


def test_move_refused_events_from_the_engine():
    game = Game.new(seed=22)
    refused: list[MoveRefused] = []
    game.events.subscribe(MoveRefused, refused.append)
    game.miner.x, game.miner.y = 5, 5
    game.miner.energy = 0

    result = _submit(game, Move(Direction.EAST))
    assert result["reason"] == "low_energy"
    assert refused[-1] == MoveRefused(miner_id=0, reason="low_energy")
    assert game.progression_state.get_counter("fail:low_energy") == 1

    overheated = Game.new(seed=23)
    refused = []
    overheated.events.subscribe(MoveRefused, refused.append)
    overheated.miner.cooldown_remaining = 5
    result = _submit(overheated, Move(Direction.WEST))
    assert result["reason"] == "overheated"
    assert refused[-1] == MoveRefused(miner_id=0, reason="overheated")
    assert overheated.progression_state.get_counter("fail:overheated") == 1


def test_temperature_changes_move_peak_temp_and_overheats():
    game = Game.new(seed=24)
    state = game.progression_state
    changes: list[TemperatureChanged] = []
    overheated: list[MinerOverheated] = []
    game.events.subscribe(TemperatureChanged, changes.append)
    game.events.subscribe(MinerOverheated, overheated.append)
    game.miner.layer = 2
    game.miner.x, game.miner.y = 5, 5
    game.miner.temperature = 79.0
    game.miner.energy = 10**9

    game.submit(Wait(10))
    for _ in range(10):
        game.step()
    assert changes and changes[-1].miner_id == 0
    assert state.get_counter("peak_temp") >= 80

    game.miner.temperature = 99.9
    game.submit(Wait(10))
    game.step()
    assert overheated and overheated[-1].miner_id == 0
    assert state.get_counter("overheats") == 1


def test_layers_dock_and_charge_counters_from_the_engine():
    game = Game.new(seed=25)
    state = game.progression_state
    state.unlocked_features.add("warehouse")
    game.player_stats.upgrades["shaft"] = 2
    game.miner.energy = 10**9

    assert _submit(game, Descend())["ok"]
    assert _submit(game, Descend())["ok"]
    assert state.get_counter("max_layer") == 2
    assert state.get_counter("descents") == 2

    x, y, ore_id = _find_layer_tile(game, 2)
    state.unlock_ore(ore_id)
    game.miner.x, game.miner.y = x, y
    game.miner.tool_tier = 10
    game.miner.capacity = 10**6
    for _ in range(500):
        game.world.delta.clear()
        if _submit(game, Mine()).get("ok"):
            break
    assert state.get_counter("mined_layer:2") >= 1

    game.player_stats.battery_capacity = 10
    game.miner.energy = 0
    game.miner.x, game.miner.y, game.miner.layer = 0, 0, 0
    assert _submit(game, Charge())["ok"]
    assert state.get_counter("charges") == 1
    game.player_stats.battery_capacity = 10**9
    game.miner.energy = 10**9

    first = game.engine.spawn_miner()
    second = game.engine.spawn_miner()
    first.inventory = {"stone": 1}
    second.inventory = {"stone": 1}
    game.submit(Unload(), miner_id=first.id)
    game.submit(Unload(), miner_id=second.id)
    game.run_until_idle()
    assert state.get_counter("dock_units") == 2
    assert state.get_counter("dock_wait_ticks") >= 1


def test_v12_save_migrates_with_new_counters_at_zero(content):
    data = {"version": 12, "seed": 1, "progression": {"counters": {"tiles_moved": 5}}}
    migrated = migrate(data)
    assert migrated["version"] == CURRENT_VERSION == 13
    state = ProgressionState.from_dict(migrated["progression"], content=content)
    assert state.get_counter("tiles_moved") == 5
    for name in (
        "max_layer",
        "descents",
        "energy_used",
        "charges",
        "strandings",
        "rescues",
        "overheats",
        "peak_temp",
        "dock_wait_ticks",
        "dock_units",
        "peak_deep_miners",
        "fail:low_energy",
        "fail:overheated",
    ):
        assert state.get_counter(name) == 0


def test_save_version_is_thirteen():
    assert CURRENT_VERSION == 13
