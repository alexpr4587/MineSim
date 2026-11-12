"""Tests for achievements, unlocks and saves (prompt 04)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from digscript.core.commands import Mine, Move, Sell, Wait
from digscript.core.content import load_content
from digscript.core.direction import Direction
from digscript.core.events import (
    AchievementUnlocked,
    MineAttempted,
    Moved,
    OreMined,
    ScriptFinished,
    ScriptStarted,
    Sold,
)
from digscript.core.game import Game
from digscript.core.progression.state import ProgressionState
from digscript.core.save import SaveError, SaveGame, default_save_path, migrate
from digscript.core.schemas import ContentError


@pytest.fixture(scope="module")
def content():
    return load_content()


def _submit(game, command):
    ticket = game.submit(command)
    game.run_until_idle()
    assert ticket.done
    return ticket.result


def _find_tile(game, ore_id):
    for y in range(2, 60):
        for x in range(2, 60):
            if game.world.tile_at(x, y, 0).ore_id == ore_id:
                return x, y
    raise AssertionError(f"no tile with {ore_id}")


def _mine_one(game):
    for _ in range(50):
        result = _submit(game, Mine())
        if result.get("ok"):
            return result
        if result.get("reason") not in (None,):
            # Misses are the only expected non-ok reason while on an ore tile.
            assert result["reason"] == "miss"
    raise AssertionError("mining never succeeded")


def test_initial_unlocks(content):
    state = ProgressionState(content)
    assert state.is_ore_unlocked("stone")
    assert not state.is_ore_unlocked("coal")
    for name in ("move", "mine", "peek", "position"):
        assert state.is_function_unlocked(name)
    for name in ("sell", "inventory", "scan", "stats", "buy_upgrade"):
        assert not state.is_function_unlocked(name)
    assert state.is_module_unlocked("math")
    for name in ("random", "statistics", "collections", "heapq"):
        assert not state.is_module_unlocked(name)
    for upgrade_id in ("backpack", "pickaxe", "motor", "scanner"):
        assert not state.is_upgrade_unlocked(upgrade_id)


def test_acceptance_mine_then_sell():
    game = Game.new(seed=12345)
    unlocked = []
    game.events.subscribe(AchievementUnlocked, unlocked.append)
    game.miner.x, game.miner.y = _find_tile(game, "stone")
    _mine_one(game)
    assert "first_dig" in game.progression_state.completed
    assert game.progression.is_ore_unlocked("coal")
    assert game.progression.is_function_unlocked("sell")
    assert [event.id for event in unlocked] == ["first_dig"]
    game.miner.x, game.miner.y = 0, 0
    result = _submit(game, Sell())
    assert result["ok"]
    assert "first_sale" in game.progression_state.completed
    assert game.progression.is_function_unlocked("buy_upgrade")
    assert game.progression.is_upgrade_unlocked("backpack")


def test_mined_specific_ore_and_parent_gating():
    game = Game.new(seed=1)
    bus = game.events
    assert game.progression.is_available("coal_miner") is False
    assert game.progression.is_available("first_dig") is True
    game.progression_state.counters["mined:coal"] = 20
    game.progression.check_achievements()
    assert "coal_miner" not in game.progression_state.completed
    assert not game.progression.is_ore_unlocked("copper")
    bus.publish(OreMined(ore_id="stone", amount=1))
    assert "first_dig" in game.progression_state.completed
    assert "coal_miner" in game.progression_state.completed
    assert game.progression.is_ore_unlocked("copper")
    assert game.progression.progress("coal_miner") == (20, 20)
    for _ in range(20):
        bus.publish(OreMined(ore_id="copper", amount=1))
    assert "copper_age" in game.progression_state.completed
    assert game.progression.is_ore_unlocked("iron")


def test_code_chain_tiles_attempts_and_rewards():
    game = Game.new(seed=2)
    bus = game.events
    assert game.progression.is_available("wanderer") is False
    bus.publish(ScriptFinished())
    assert "hello_miner" in game.progression_state.completed
    assert game.progression.is_function_unlocked("inventory")
    assert game.progression.progress("hello_miner") == (1, 1)
    assert game.progression.is_available("wanderer") is True
    for _ in range(10):
        bus.publish(Moved(x=0, y=0, direction="east"))
    assert game.progression.progress("wanderer") == (10, 200)
    for _ in range(190):
        bus.publish(Moved(x=0, y=0, direction="east"))
    assert "wanderer" in game.progression_state.completed
    assert game.progression.is_module_unlocked("random")
    for _ in range(50):
        bus.publish(MineAttempted(ore_id="stone", success=False))
    assert "scout" in game.progression_state.completed
    assert game.progression.is_function_unlocked("scan")
    for _ in range(150):
        bus.publish(MineAttempted(ore_id="stone", success=False))
    assert "data_driven" in game.progression_state.completed
    assert game.progression.is_function_unlocked("stats")
    assert game.progression.is_module_unlocked("statistics")


def test_script_defines_function():
    game = Game.new(seed=3)
    bus = game.events
    bus.publish(ScriptStarted(defines_function=False))
    assert "custom_function" not in game.progression_state.completed
    bus.publish(ScriptFinished())
    assert "hello_miner" in game.progression_state.completed
    bus.publish(ScriptStarted(defines_function=True))
    assert "custom_function" in game.progression_state.completed
    assert game.progression.is_module_unlocked("collections")
    assert game.progression.is_module_unlocked("heapq")
    assert game.progression.progress("custom_function") == (1, 1)


def test_sales_and_money_chain_and_money_reward():
    game = Game.new(seed=4)
    bus = game.events
    bus.publish(Sold(money=0, items={}))
    assert "first_sale" not in game.progression_state.completed
    assert game.progression_state.counters.get("sales", 0) == 0
    bus.publish(Sold(money=10, items={"stone": 10}))
    assert "first_sale" in game.progression_state.completed
    assert game.progression.is_function_unlocked("buy_upgrade")
    assert game.progression.is_upgrade_unlocked("backpack")
    bus.publish(Sold(money=90, items={"stone": 90}))
    assert "pocket_change" in game.progression_state.completed
    assert game.progression.is_upgrade_unlocked("pickaxe")
    bus.publish(Sold(money=900, items={"stone": 900}))
    assert "investor" in game.progression_state.completed
    assert game.progression.is_upgrade_unlocked("motor")
    assert game.progression.is_upgrade_unlocked("scanner")
    game.miner.money = 7
    bus.publish(Sold(money=9000, items={"stone": 9000}))
    assert "tycoon" in game.progression_state.completed
    assert game.miner.money == 507
    assert game.progression_state.counters["money_earned"] == 10000


def test_requirement_title():
    game = Game.new(seed=5)
    service = game.progression
    assert service.requirement_title("ore", "coal") == "First Dig"
    assert service.requirement_title("function", "sell") == "First Dig"
    assert service.requirement_title("function", "inventory") == "Hello, Miner"
    assert service.requirement_title("module", "random") == "Wanderer"
    assert service.requirement_title("upgrade", "backpack") == "First Sale"
    assert service.requirement_title("ore", "copper") == "Coal Miner"
    assert service.requirement_title("function", "first_dig") == "First Dig"


def test_save_load_round_trip_and_next_500_ticks(tmp_path):
    game = Game.new(seed=99)
    _submit(game, Move(Direction.EAST))
    _submit(game, Move(Direction.EAST))
    game.miner.x, game.miner.y = _find_tile(game, "stone")
    _mine_one(game)
    path = tmp_path / "nested" / "slot1.json"
    saved_path = game.save(path)
    assert saved_path == path
    assert path.is_file()
    assert not list(path.parent.glob("*.tmp"))
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert set(raw) == {
        "version",
        "seed",
        "tick",
        "selected_skin",
        "miner",
        "world_delta",
        "progression",
    }
    assert raw["version"] == 3
    assert raw["selected_skin"] == "rusty_bot"
    loaded = Game.load(path)
    assert loaded.seed == game.seed
    assert loaded.tick == game.tick
    assert loaded.miner.to_dict() == game.miner.to_dict()
    assert loaded.world.to_dict() == game.world.to_dict()
    assert loaded.progression_state.to_dict() == game.progression_state.to_dict()

    def run_500_ticks(active):
        target = active.tick + 500
        commands = [Move(Direction.EAST), Mine(), Move(Direction.WEST), Wait(2)]
        index = 0
        while active.tick < target:
            if active.engine.is_idle:
                active.submit(commands[index % len(commands)])
                index += 1
            active.engine.step()

    run_500_ticks(game)
    run_500_ticks(loaded)
    assert game.tick == loaded.tick
    assert game.miner.to_dict() == loaded.miner.to_dict()
    assert game.world.to_dict() == loaded.world.to_dict()
    assert game.progression_state.to_dict() == loaded.progression_state.to_dict()
    assert game.engine.attempt_counter == loaded.engine.attempt_counter


def test_corrupted_and_wrong_version_saves(tmp_path):
    corrupted = tmp_path / "bad.json"
    corrupted.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SaveError):
        SaveGame.load(corrupted)
    with pytest.raises(SaveError):
        Game.load(corrupted)
    newer = tmp_path / "newer.json"
    newer.write_text(
        json.dumps(
            {
                "version": 999,
                "seed": 1,
                "tick": 0,
                "miner": {},
                "world_delta": {},
                "progression": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SaveError):
        SaveGame.load(newer)
    with pytest.raises(SaveError):
        Game.load(newer)
    with pytest.raises(SaveError):
        migrate({"version": 999, "seed": 1})
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"version": 1}), encoding="utf-8")
    with pytest.raises(SaveError):
        SaveGame.load(invalid)
    assert migrate({"version": 1, "seed": 1})["seed"] == 1


def test_default_save_path():
    path = default_save_path()
    assert path.name == "slot1.json"
    assert path.parent.name == "saves"
    assert "DigScript" in path.parts


def _copy_content(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "src" / "digscript" / "content"
    destination = tmp_path / "content"
    destination.mkdir()
    for item in source.iterdir():
        shutil.copy(item, destination / item.name)
    return destination


@pytest.mark.parametrize(
    ("filename", "key"),
    [
        ("ores.json", "id"),
        ("functions.json", "name"),
        ("modules.json", "name"),
        ("upgrades.json", "id"),
    ],
)
def test_content_validation_unknown_unlocked_by(tmp_path, filename, key):
    content_dir = _copy_content(tmp_path)
    data = json.loads((content_dir / filename).read_text(encoding="utf-8"))
    data[0]["unlocked_by"] = "no_such_achievement"
    (content_dir / filename).write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_content(content_dir)
    assert filename in str(excinfo.value)
    assert "no_such_achievement" in str(excinfo.value)


def test_content_validation_unknown_reward_id(tmp_path):
    content_dir = _copy_content(tmp_path)
    data = json.loads((content_dir / "achievements.json").read_text(encoding="utf-8"))
    data[0]["rewards"] = [{"type": "unlock_ore", "id": "no_such_ore"}]
    (content_dir / "achievements.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_content(content_dir)
    assert "achievements.json" in str(excinfo.value)
    assert "no_such_ore" in str(excinfo.value)
