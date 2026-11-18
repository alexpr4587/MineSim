"""Prompt 28: underground layers, shaft travel and per-layer persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from minesim.core.commands import (
    Ascend,
    Contracts,
    Deliver,
    Descend,
    Layer,
    Layers,
    Mine,
    Move,
    Price,
    PriceHistory,
    Prices,
    Refine,
    Sell,
    SellStock,
    Stock,
    Unload,
    Wait,
)
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.events import LayerChanged
from minesim.core.game import Game
from minesim.core.save import CURRENT_VERSION, SaveGame, migrate
from minesim.core.world import World, WorldGenerator
from minesim.core.worldevents import WorldEvents

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "golden_layer0.json"
SAVE_V9 = FIXTURES / "save_v9.json"


@pytest.fixture(scope="module")
def content():
    return load_content()


def _session() -> list[object]:
    return [
        Move(Direction.EAST),
        Move(Direction.EAST),
        Mine(),
        Move(Direction.EAST),
        Mine(),
        Wait(5),
        Move(Direction.WEST),
        Move(Direction.WEST),
        Move(Direction.WEST),
        Sell(),
    ]


def _run_golden_session() -> dict[str, object]:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    game = Game.new(seed=int(expected["seed"]))
    results = []
    for command in _session():
        ticket = game.submit(command)
        game.run_until_idle()
        assert ticket.done
        results.append(ticket.result)
    assert results == expected["session"]
    assert game.tick == expected["tick"]
    assert game.miner.x == expected["miner"]["x"]
    assert game.miner.y == expected["miner"]["y"]
    assert dict(game.miner.inventory) == expected["miner"]["inventory"]
    assert game.player_stats.money == expected["miner"]["money"]
    return expected


def test_golden_layer_zero_is_unchanged(content) -> None:
    expected = _run_golden_session()
    generator = WorldGenerator(int(expected["seed"]), content)
    world = World(generator, content)
    tiles = []
    for cx, cy in expected["chunks"]:
        for row in world.chunk_tiles(int(cx), int(cy), 0):
            for tile in row:
                tiles.append(
                    [
                        tile.ore_id,
                        tile.biome_id,
                        tile.is_base,
                        tile.depleted,
                    ]
                )
    recorded = [
        [x, y, *entry]
        for (x, y), entry in zip(
            [(x, y) for x, y, *_ in expected["tiles"]],
            (entry[2:] for entry in expected["tiles"]),
            strict=True,
        )
    ]
    assert len(recorded) == len(expected["tiles"])
    assert [[entry[2], entry[3], entry[4], entry[5]] for entry in expected["tiles"]] == tiles
    # The fixed session ends with the same layer-0 delta as before layers existed.
    session_game = Game.new(seed=int(expected["seed"]))
    for command in _session():
        session_game.submit(command)
        session_game.run_until_idle()
    assert session_game.world.to_dict() == expected["world_delta"]


def _find_ore(world: World, layer: int, ore_id: str | None = None) -> tuple[int, int]:
    for y in range(0, 40):
        for x in range(3, 40):
            tile = world.tile_at(x, y, 0, layer=layer)
            if tile.ore_id is not None and (ore_id is None or tile.ore_id == ore_id):
                return x, y
    raise AssertionError(f"no ore on layer {layer}")


def test_layers_differ_are_deterministic_and_isolated(content) -> None:
    first = World(WorldGenerator(12345, content), content)
    second = World(WorldGenerator(12345, content), content)
    coords = [(x, y) for x in range(3, 20) for y in range(-3, 4)]
    ids = {
        layer: [first.tile_at(x, y, 0, layer=layer).ore_id for x, y in coords]
        for layer in (0, 1, 2, 3)
    }
    for layer in (0, 1, 2, 3):
        assert ids[layer] == [second.tile_at(x, y, 0, layer=layer).ore_id for x, y in coords]
    assert ids[0] != ids[1]
    assert ids[1] != ids[2]
    assert ids[2] != ids[3]

    x, y = _find_ore(first, 1)
    surface_before = first.tile_at(x, y, 0, layer=0)
    mined = first.mine_tile(x, y, 0, layer=1)
    assert mined is not None
    assert first.tile_at(x, y, 0, layer=1).depleted
    assert first.tile_at(x, y, 0, layer=0) == surface_before
    assert first.chunk_version(x // first.chunk_size, y // first.chunk_size, 1) > 0
    assert first.chunk_version(x // first.chunk_size, y // first.chunk_size, 0) == 0
    data = first.to_dict()
    assert str(1) in data["layer_deltas"]
    assert data["delta"] == {}
    reloaded = World.from_dict(WorldGenerator(12345, content), content, data=data)
    assert reloaded.tile_at(x, y, 0, layer=1).depleted
    assert not reloaded.tile_at(x, y, 0, layer=0).depleted


def _game_with_shaft(level: int = 1) -> Game:
    game = Game.new(seed=12345)
    game.progression_state.unlock_upgrade("shaft")
    game.player_stats.upgrades["shaft"] = level
    return game


def test_descend_and_ascend_rules() -> None:
    game = _game_with_shaft(1)
    game.miner.x = 5
    game.miner.y = 0
    result = game.submit(Descend())
    game.run_until_idle()
    assert result.result == {
        "ok": False,
        "layer": 0,
        "reason": "not_on_station",
    }

    game.miner.x = 0
    baseline = game.tick
    result = game.submit(Descend())
    game.run_until_idle()
    assert result.result == {"ok": True, "layer": 1, "reason": None}
    assert game.tick == baseline + 20
    assert (game.miner.x, game.miner.y, game.miner.layer) == (0, 0, 1)
    assert game.submit(Layer()).result == {"ok": True, "layer": 1}

    game.miner.x = 4
    result = game.submit(Ascend())
    game.run_until_idle()
    assert result.result == {
        "ok": False,
        "layer": 1,
        "reason": "not_on_station",
    }
    game.miner.x = 0
    result = game.submit(Ascend())
    game.run_until_idle()
    assert result.result == {"ok": True, "layer": 0, "reason": None}
    assert (game.miner.x, game.miner.y, game.miner.layer) == (0, 0, 0)
    result = game.submit(Ascend())
    game.run_until_idle()
    assert result.result == {
        "ok": False,
        "layer": 0,
        "reason": "already_surface",
    }


def test_descend_needs_shaft_and_layer() -> None:
    game = Game.new(seed=12345)
    result = game.submit(Descend())
    game.run_until_idle()
    assert result.result == {
        "ok": False,
        "layer": 0,
        "reason": "shaft_too_shallow",
    }
    game = _game_with_shaft(1)
    game.miner.layer = 1
    result = game.submit(Descend())
    game.run_until_idle()
    assert result.result == {
        "ok": False,
        "layer": 1,
        "reason": "shaft_too_shallow",
    }
    layers = game.submit(Layers()).result
    assert [entry["index"] for entry in layers["layers"]] == [0, 1, 2, 3]
    assert [entry["accessible"] for entry in layers["layers"]] == [
        True,
        True,
        False,
        False,
    ]
    assert layers["layers"][1]["name"] == "Old Galleries"


def test_layer_changed_event() -> None:
    game = _game_with_shaft(1)
    seen: list[LayerChanged] = []
    game.events.subscribe(LayerChanged, seen.append)
    game.submit(Descend())
    game.run_until_idle()
    game.submit(Ascend())
    game.run_until_idle()
    assert seen == [
        LayerChanged(miner_id=0, from_layer=0, to_layer=1),
        LayerChanged(miner_id=0, from_layer=1, to_layer=0),
    ]


@pytest.mark.parametrize(
    "make",
    [
        lambda: Unload(),
        lambda: Sell(),
        lambda: SellStock("stone"),
        lambda: Refine("stone_brick"),
        lambda: Deliver(1),
        lambda: Contracts(),
        lambda: Price("stone"),
        lambda: Prices(),
        lambda: PriceHistory("stone"),
        lambda: Stock(),
    ],
)
def test_surface_only_commands_refuse_underground(make) -> None:
    game = _game_with_shaft(1)
    game.submit(Descend())
    game.run_until_idle()
    assert game.miner.layer == 1
    game.miner.inventory = {"stone": 1}
    result = game.submit(make())
    game.run_until_idle()
    assert result.result == {"ok": False, "reason": "not_on_surface_base"}


def test_world_events_are_surface_only(content) -> None:
    definition = SimpleNamespace(
        kind="rich_vein",
        radius=100,
        duration=100000,
        yield_multiplier=3,
        move_cost_multiplier=3,
        min_distance=0,
        max_distance=0,
        factor_choices=[1.5],
    )
    config = SimpleNamespace(
        world_event_interval_ticks=2500,
        world_event_chance=1.0,
        seed_default=12345,
    )
    events = WorldEvents(424242, config, {"rich_vein": definition}, item_ids=("stone",))
    neutral = {"yield_multiplier": 1, "move_multiplier": 1}
    for tick in range(0, 60000, 100):
        active = events.active_at(tick)
        if active:
            event = active[0]
            assert events.modifiers_at(event.x, event.y, tick, layer=1) == neutral
            assert events.modifiers_at(event.x, event.y, tick)["yield_multiplier"] > 1
            return
    raise AssertionError("no world event found")


def test_v9_save_fixture_migrates_miner_layers() -> None:
    data = json.loads(SAVE_V9.read_text(encoding="utf-8"))
    assert data["version"] == 9
    migrated = migrate(data)
    assert migrated["version"] == CURRENT_VERSION == 10
    assert migrated["fleet"][0]["layer"] == 0
    savegame = SaveGame.from_dict(data)
    assert savegame.version == 10
    game = Game.load_data(savegame) if hasattr(Game, "load_data") else None
    if game is not None:
        assert game.miner.layer == 0


def test_headless_trip_down_mine_and_return_to_sell() -> None:
    game = _game_with_shaft(1)
    game.submit(Descend())
    game.run_until_idle()
    for _ in range(5):
        game.submit(Move(Direction.EAST))
        game.run_until_idle()
    assert game.miner.layer == 1
    assert game.world.tile_at(5, 0, game.tick, layer=1).ore_id == "stone"
    mined = game.submit(Mine())
    game.run_until_idle()
    assert mined.result["ok"] is True
    assert game.miner.inventory.get("stone", 0) == 1
    for _ in range(5):
        game.submit(Move(Direction.WEST))
        game.run_until_idle()
    game.submit(Ascend())
    game.run_until_idle()
    before = game.player_stats.money
    sold = game.submit(Sell())
    game.run_until_idle()
    assert sold.result["ok"] is True
    assert game.player_stats.money > before
    assert game.miner.inventory == {}
