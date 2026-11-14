"""Tests for the progression engine extension (prompt 11)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from minesim.core.commands import BuyUpgrade, Mine, Move, Sell
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.events import (
    EstimateSubmitted,
    MineAttempted,
    Moved,
    OreMined,
    ScriptFinished,
    ScriptStarted,
    Sold,
    TileRegenerated,
    UpgradeBought,
)
from minesim.core.game import Game
from minesim.core.progression.state import ProgressionState
from minesim.core.save import DEFAULT_SKIN, SaveGame, migrate
from minesim.core.schemas import (
    Achievement,
    ContentError,
    CounterCriteria,
    Reward,
    ScriptFeatureCriteria,
)
from minesim.scripting.host import analyze_features

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FEATURES = (
    "defines_function",
    "uses_import",
    "uses_comprehension",
    "uses_class",
    "uses_try",
    "uses_recursion",
    "uses_lambda",
    "uses_generator",
)


@pytest.fixture(scope="module")
def content():
    return load_content()


def _find_tile(game, ore_id, start=2):
    for y in range(start, start + 80):
        for x in range(start, start + 80):
            if game.world.tile_at(x, y, 0).ore_id == ore_id:
                return x, y
    raise AssertionError(f"no tile with {ore_id}")


def _submit(game, command):
    ticket = game.submit(command)
    game.run_until_idle()
    assert ticket.done
    return ticket.result


def _mine_success(game, ore_id):
    game.state.unlock_ore(ore_id)
    game.miner.x, game.miner.y = _find_tile(game, ore_id)
    game.miner.tool_tier = 10
    game.miner.capacity = 10**6
    for _ in range(500):
        game.world.delta.clear()
        result = _submit(game, Mine())
        if result.get("ok"):
            return
    raise AssertionError(f"could not mine {ore_id}")


def test_initial_unlock_sets_include_null_skins_and_examples(content):
    state = ProgressionState(content)
    for skin in content.skins.values():
        assert state.is_skin_unlocked(skin.id) is (skin.unlocked_by is None)
    fake = SimpleNamespace(
        examples={
            "free": SimpleNamespace(id="free", unlocked_by=None),
            "locked": SimpleNamespace(id="locked", unlocked_by="first_dig"),
        }
    )
    state = ProgressionState(fake)
    assert state.is_example_unlocked("free")
    assert not state.is_example_unlocked("locked")


def test_mine_attempt_boundary_and_fail_reasons():
    game = Game.new(seed=11)
    events = []
    game.events.subscribe(MineAttempted, events.append)

    # Rule failure: not an attempt, but a failure.
    result = _submit(game, Mine())
    assert result["reason"] == "nothing_to_mine"
    assert events[-1].reason == "nothing_to_mine"
    assert game.progression_state.get_counter("attempts:any") == 0
    assert game.progression_state.get_counter("fail:nothing_to_mine") == 1

    # Locked ore is a rule failure, not an attempt.
    game.miner.x, game.miner.y = _find_tile(game, "coal")
    result = _submit(game, Mine())
    assert result["reason"] == "locked_ore"
    assert game.progression_state.get_counter("attempts:any") == 0
    assert game.progression_state.get_counter("fail:locked_ore") == 1

    # Tool too weak is a rule failure.
    game.progression_state.unlock_ore("copper")
    game.miner.x, game.miner.y = _find_tile(game, "copper")
    game.miner.tool_tier = 0
    result = _submit(game, Mine())
    assert result["reason"] == "tool_too_weak"
    assert game.progression_state.get_counter("attempts:any") == 0
    assert game.progression_state.get_counter("fail:tool_too_weak") == 1

    # Inventory full is a rule failure.
    game.miner.x, game.miner.y = _find_tile(game, "stone")
    game.miner.tool_tier = 10
    game.miner.capacity = 0
    result = _submit(game, Mine())
    assert result["reason"] == "inventory_full"
    assert game.progression_state.get_counter("attempts:any") == 0
    assert game.progression_state.get_counter("fail:inventory_full") == 1

    # A miss is an attempt.
    game.miner.capacity = 10**6
    for _ in range(500):
        game.world.delta.clear()
        _submit(game, Mine())
        if any(event.reason == "miss" for event in events):
            break
    assert game.progression_state.get_counter("fail:miss") >= 1
    assert game.progression_state.get_counter("attempts:any") >= 1
    assert game.progression_state.get_counter("attempts:stone") >= 1


def test_every_new_counter_from_synthetic_events():
    game = Game.new(seed=12)
    bus = game.events
    state = game.progression_state

    bus.publish(Moved(x=3, y=4))
    bus.publish(Moved(x=-5, y=2))
    assert state.get_counter("tiles_moved") == 2
    assert state.get_counter("max_distance") == 5

    bus.publish(MineAttempted(ore_id="stone", success=True, reason=None))
    bus.publish(MineAttempted(ore_id="stone", success=True, reason=None))
    assert state.get_counter("streak") == 2
    bus.publish(MineAttempted(ore_id="stone", success=False, reason="miss"))
    bus.publish(MineAttempted(ore_id="stone", success=False, reason="miss"))
    assert state.get_counter("fail_streak") == 2
    assert state.get_counter("streak") == 2
    assert state.get_counter("fail:miss") == 2
    assert state.get_counter("attempts:any") == 4
    assert state.get_counter("attempts:stone") == 4

    # A rule failure increments fail:<reason> but is not an attempt and
    # does not break either streak.
    bus.publish(MineAttempted(ore_id="stone", success=False, reason="locked_ore"))
    assert state.get_counter("fail:locked_ore") == 1
    assert state.get_counter("attempts:any") == 4
    assert state.get_counter("fail_streak") == 2

    bus.publish(OreMined(ore_id="stone", amount=1))
    bus.publish(OreMined(ore_id="coal", amount=1))
    bus.publish(OreMined(ore_id="stone", amount=1))
    assert state.get_counter("mined:any") == 3
    assert state.get_counter("unique_ores_mined") == 2

    bus.publish(Sold(money=10, items={"stone": 5}))
    bus.publish(Sold(money=50, items={"stone": 1, "coal": 2}))
    bus.publish(Sold(money=5, items={"stone": 1}))
    assert state.get_counter("largest_sale") == 50
    assert state.get_counter("ores_in_one_sale") == 2

    bus.publish(UpgradeBought(id="backpack", level=1))
    assert state.get_counter("upgrades_bought") == 1
    bus.publish(TileRegenerated(x=2, y=3))
    assert state.get_counter("regens") == 1

    bus.publish(ScriptStarted(defines_function=False, features=frozenset({"uses_import"})))
    bus.publish(ScriptStarted(defines_function=True))
    assert state.get_counter("scripts_run") == 2
    assert state.get_counter("script_feature:uses_import") == 1
    assert state.get_counter("script_feature:defines_function") == 1
    bus.publish(ScriptFinished())
    assert state.get_counter("scripts_finished") == 1

    bus.publish(EstimateSubmitted(ore_id="stone", p=0.9, error=0.01, attempts=120, good=True))
    bus.publish(EstimateSubmitted(ore_id="stone", p=0.1, error=0.8, attempts=120, good=False))
    assert state.get_counter("good_estimates") == 1


def test_biome_visit_counters():
    game = Game.new(seed=12345)
    bus = game.events
    state = game.progression_state
    bus.publish(Moved(x=0, y=0))
    assert state.get_counter("biome:quarry") == 1
    assert state.get_counter("biomes_visited") == 1
    bus.publish(Moved(x=0, y=0))
    assert state.get_counter("biomes_visited") == 1

    target = None
    for radius in range(1, 12):
        for dx, dy in ((radius, 0), (0, radius), (-radius, 0), (0, -radius)):
            x, y = dx * 32, dy * 32
            biome_id = game.world.generator.biome_id_at(x, y)
            if biome_id != "quarry":
                target = (x, y, biome_id)
                break
        if target is not None:
            break
    assert target is not None
    x, y, biome_id = target
    bus.publish(Moved(x=x, y=y))
    assert state.get_counter(f"biome:{biome_id}") == 1
    assert state.get_counter("biomes_visited") == 2


def test_script_feature_criteria_and_legacy_alias():
    game = Game.new(seed=13)
    achievement = Achievement(
        id="uses_lambda_test",
        tab="code",
        parent=None,
        title="Lambda Test",
        criteria=ScriptFeatureCriteria(feature="uses_lambda"),
        rewards=[],
    )
    game.content.achievements["uses_lambda_test"] = achievement
    game.events.publish(ScriptStarted(features=frozenset({"uses_lambda"})))
    assert game.progression_state.is_completed("uses_lambda_test")
    assert game.progression.progress("uses_lambda_test") == (1, 1)

    # The old criteria type is an alias of the defines_function feature.
    game.events.publish(ScriptFinished())
    game.events.publish(ScriptStarted(defines_function=True))
    assert game.progression_state.is_completed("custom_function")


@pytest.mark.parametrize(
    ("feature", "positive", "negative"),
    [
        ("defines_function", "def f():\n    pass\n", "x = 1\n"),
        ("uses_import", "import math\n", "x = 1\n"),
        ("uses_comprehension", "xs = [i for i in range(3)]\n", "xs = list(range(3))\n"),
        ("uses_class", "class A:\n    pass\n", "x = 1\n"),
        ("uses_try", "try:\n    x = 1\nexcept Exception:\n    pass\n", "x = 1\n"),
        ("uses_recursion", "def f(n):\n    return f(n - 1)\n", "def f(n):\n    return n\n"),
        ("uses_lambda", "f = lambda x: x\n", "def f(x):\n    return x\n"),
        ("uses_generator", "def g():\n    yield 1\n", "def g():\n    return 1\n"),
    ],
)
def test_ast_feature_table(feature, positive, negative):
    assert feature in analyze_features(positive)
    assert feature not in analyze_features(negative)


def test_analyze_features_invalid_source_is_empty():
    assert analyze_features("x = (\n") == frozenset()


def test_reward_types_unlock_skin_and_example():
    game = Game.new(seed=14)
    achievement = Achievement(
        id="reward_test",
        tab="business",
        parent=None,
        title="Reward Test",
        criteria=CounterCriteria(counter="sales", target=1),
        rewards=[
            Reward(type="unlock_skin", id="locked_test_skin"),
            Reward(type="unlock_example", id="demo_example"),
        ],
    )
    game.content.achievements["reward_test"] = achievement
    assert not game.progression_state.is_skin_unlocked("locked_test_skin")
    game.events.publish(Sold(money=1, items={"stone": 1}))
    assert game.progression_state.is_completed("reward_test")
    assert game.progression_state.is_skin_unlocked("locked_test_skin")
    assert game.progression_state.is_example_unlocked("demo_example")
    assert game.progression.is_skin_unlocked("locked_test_skin")
    assert game.progression.is_example_unlocked("demo_example")


def test_saved_version_1_fixture_migrates(tmp_path):
    path = FIXTURES / "save_v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    migrated = migrate(data)
    assert migrated["version"] == 6
    assert migrated["selected_skin"] == DEFAULT_SKIN

    savegame = SaveGame.load(path)
    assert savegame.version == 6
    assert savegame.selected_skin == DEFAULT_SKIN

    game = Game.load(path)
    assert game.progression_state.get_counter("max_distance") == 0
    assert game.progression_state.get_counter("regens") == 0
    assert game.progression_state.is_skin_unlocked("rusty_bot")
    assert game.selected_skin == DEFAULT_SKIN


def test_saved_version_2_fixture_migrates(content):
    path = FIXTURES / "save_v2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    migrated = migrate(data)
    assert migrated["version"] == 6

    savegame = SaveGame.load(path)
    assert savegame.version == 6
    assert savegame.selected_skin == "steel_walker"
    assert savegame.progression["counters"]["tiles_moved"] == 12

    game = Game.load(path)
    state = game.progression_state
    assert state.get_counter("tiles_moved") == 12
    assert state.get_counter("max_distance") == 0
    assert state.get_counter("good_estimates") == 0
    assert state.is_completed("hello_miner")
    for skin in content.skins.values():
        assert state.is_skin_unlocked(skin.id) is (skin.unlocked_by is None)
    for example in content.examples.values():
        assert state.is_example_unlocked(example.id) is (example.unlocked_by is None)
    assert not state.is_skin_unlocked("steel_walker")
    assert game.selected_skin == DEFAULT_SKIN


def _copy_content(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "src" / "minesim" / "content"
    destination = tmp_path / "content"
    destination.mkdir()
    for item in source.iterdir():
        shutil.copy(item, destination / item.name)
    return destination


def test_content_validation_unknown_new_counter(tmp_path):
    content_dir = _copy_content(tmp_path)
    path = content_dir / "achievements.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[0]["criteria"] = {"type": "counter", "counter": "no_such_counter", "target": 1}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_content(content_dir)
    assert "achievements.json" in str(excinfo.value)
    assert "no_such_counter" in str(excinfo.value)


def test_content_validation_unknown_script_feature(tmp_path):
    content_dir = _copy_content(tmp_path)
    path = content_dir / "achievements.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[0]["criteria"] = {"type": "script_feature", "feature": "no_such_feature"}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_content(content_dir)
    assert "achievements.json" in str(excinfo.value)
    assert "no_such_feature" in str(excinfo.value)


def test_content_validation_unknown_skin_reward(tmp_path):
    content_dir = _copy_content(tmp_path)
    path = content_dir / "achievements.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[0]["rewards"] = [{"type": "unlock_skin", "id": "no_such_skin"}]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_content(content_dir)
    assert "achievements.json" in str(excinfo.value)
    assert "no_such_skin" in str(excinfo.value)


def test_example_reward_validation_skipped_until_examples_file_exists(tmp_path):
    content_dir = _copy_content(tmp_path)
    (content_dir / "examples.json").unlink()
    path = content_dir / "achievements.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[0]["rewards"] = [{"type": "unlock_example", "id": "no_such_example"}]
    path.write_text(json.dumps(data), encoding="utf-8")
    load_content(content_dir)

    (content_dir / "examples.json").write_text(
        json.dumps([{"id": "demo", "title": "Demo", "file": "demo.py", "unlocked_by": None}]),
        encoding="utf-8",
    )
    with pytest.raises(ContentError) as excinfo:
        load_content(content_dir)
    assert "achievements.json" in str(excinfo.value)
    assert "no_such_example" in str(excinfo.value)


def _documented_counters() -> list[str]:
    text = (Path(__file__).resolve().parents[1] / "docs" / "PROGRESSION.md").read_text(
        encoding="utf-8"
    )
    counters = []
    for line in text.splitlines():
        if line.startswith("## Script features"):
            break
        if not line.startswith("| `"):
            continue
        name = line.split("|")[1].strip().strip("`")
        if name and name != "Counter":
            counters.append(name)
    return counters


def test_headless_scripted_session_moves_every_documented_counter():
    game = Game.new(seed=12345)
    state = game.progression_state

    # Rule failures for all reasons.
    _submit(game, Mine())  # nothing_to_mine on the base
    game.miner.x, game.miner.y = _find_tile(game, "coal")
    assert _submit(game, Mine())["reason"] == "locked_ore"
    game.progression_state.unlock_ore("copper")
    game.miner.x, game.miner.y = _find_tile(game, "copper")
    game.miner.tool_tier = 0
    assert _submit(game, Mine())["reason"] == "tool_too_weak"
    game.miner.x, game.miner.y = _find_tile(game, "stone")
    game.miner.tool_tier = 10
    game.miner.capacity = 0
    assert _submit(game, Mine())["reason"] == "inventory_full"

    # Attempts, successes, misses and streaks.
    game.miner.capacity = 10**6
    for _ in range(400):
        game.world.delta.clear()
        game.miner.inventory.clear()
        _submit(game, Mine())

    # Distinct ores.
    _mine_success(game, "coal")
    _mine_success(game, "copper")

    # Sales.
    game.miner.x, game.miner.y = 0, 0
    game.miner.inventory = {"stone": 3, "coal": 2, "copper": 1}
    assert _submit(game, Sell())["ok"]

    # Upgrade.
    game.miner.money = 10**6
    assert _submit(game, BuyUpgrade("backpack"))["ok"]

    # Regeneration through the engine.
    game.world.delta.clear()
    game.miner.x, game.miner.y = _find_tile(game, "stone")
    game.miner.capacity = 10**6
    for _ in range(500):
        game.world.delta.clear()
        if _submit(game, Mine()).get("ok"):
            break
    for _ in range(400):
        game.engine.step()

    # Scripts and estimates (the estimate function arrives in prompt 12).
    game.events.publish(ScriptStarted(defines_function=True, features=frozenset(FEATURES)))
    game.events.publish(ScriptFinished())
    game.events.publish(
        EstimateSubmitted(ore_id="stone", p=0.95, error=0.0, attempts=400, good=True)
    )

    # A different biome and a far-away tile.
    target = None
    for radius in range(1, 20):
        for dx, dy in ((radius, 0), (0, radius), (-radius, 0), (0, -radius)):
            x, y = dx * 32, dy * 32
            biome_id = game.world.generator.biome_id_at(x, y)
            if biome_id != "quarry":
                target = (x, y, biome_id)
                break
        if target is not None:
            break
    assert target is not None
    x, y, biome_id = target
    game.miner.x, game.miner.y = x - 1, y
    _submit(game, Move(Direction.EAST))
    assert state.get_counter(f"biome:{biome_id}") >= 1

    counters = state.counters
    for name in _documented_counters():
        if "<" in name:
            prefix = name.split("<", 1)[0]
            assert any(key.startswith(prefix) for key in counters), name
        else:
            assert counters.get(name, 0) > 0, name
