"""Tests for the v0.2 content wiring (prompt 13)."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pytest

from minesim.core.content import load_content
from minesim.core.events import (
    EstimateSubmitted,
    MineAttempted,
    Moved,
    OreMined,
    ScriptFinished,
    ScriptStarted,
    TileRegenerated,
)
from minesim.core.game import Game
from minesim.core.progression.state import ProgressionState

ROOT = Path(__file__).resolve().parents[1]
TABS = {"code", "mining", "business", "explorer", "data"}


@pytest.fixture(scope="module")
def content():
    return load_content()


def test_content_validation_passes_and_has_five_tabs(content):
    assert len(content.achievements) == 41
    assert {achievement.tab for achievement in content.achievements.values()} == TABS


def test_achievement_graph_has_no_cycles_and_same_tab_parents(content):
    for achievement in content.achievements.values():
        parent_id = achievement.parent
        if parent_id is None:
            continue
        assert parent_id in content.achievements
        parent = content.achievements[parent_id]
        assert parent.tab == achievement.tab
        seen = {achievement.id}
        cursor = achievement
        while cursor.parent is not None:
            assert cursor.parent not in seen
            seen.add(cursor.parent)
            cursor = content.achievements[cursor.parent]


def test_every_unlockable_thing_has_exactly_one_unlocking_achievement(content):
    collections = {
        "function": content.functions,
        "ore": content.ores,
        "upgrade": content.upgrades,
        "module": content.modules,
        "skin": content.skins,
        "example": content.examples,
    }
    reward_kinds = {
        "unlock_function": "function",
        "unlock_ore": "ore",
        "unlock_upgrade": "upgrade",
        "unlock_module": "module",
        "unlock_skin": "skin",
        "unlock_example": "example",
    }
    rewarders: dict[tuple[str, str], list[str]] = defaultdict(list)
    for achievement in content.achievements.values():
        for reward in achievement.rewards:
            kind = reward_kinds.get(reward.type)
            if kind is None:
                continue
            assert reward.id is not None
            rewarders[(kind, str(reward.id))].append(achievement.id)

    for kind, entries in collections.items():
        for ident, entry in entries.items():
            unlocked_by = entry.unlocked_by
            matching = rewarders.get((kind, ident), [])
            if unlocked_by is None:
                assert not matching, f"{kind} '{ident}' has a reward but no unlocked_by"
                continue
            assert unlocked_by in content.achievements
            assert matching == [unlocked_by], (
                f"{kind} '{ident}' should be unlocked by exactly '{unlocked_by}', got {matching}"
            )


def test_initial_unlock_sets(content):
    state = ProgressionState(content)
    assert state.unlocked_ores == {"stone"}
    assert state.unlocked_functions == {"move", "mine", "peek", "position"}
    assert state.unlocked_modules == {"math"}
    assert state.unlocked_upgrades == {"drone_bay"}
    assert state.unlocked_skins == {"rusty_bot"}
    assert state.unlocked_examples == {"01_hello"}


def _find_biome(game: Game, biome_id: str) -> tuple[int, int]:
    for radius in range(0, 40):
        for rx in range(-radius, radius + 1):
            for ry in range(-radius, radius + 1):
                x, y = rx * 32, ry * 32
                if game.world.generator.biome_id_at(x, y) == biome_id:
                    return x, y
    raise AssertionError(f"no biome {biome_id}")


def test_scripted_headless_session_unlocks_the_chain():
    game = Game.new(seed=12345)
    bus = game.events
    state = game.progression_state

    bus.publish(ScriptFinished())
    assert "hello_miner" in state.completed
    assert state.is_function_unlocked("inventory")

    features = frozenset(
        {"uses_import", "uses_comprehension", "uses_class", "uses_try", "uses_recursion"}
    )
    bus.publish(ScriptStarted(defines_function=True, features=features))
    for achievement_id in (
        "custom_function",
        "import_it",
        "one_liner",
        "own_class",
        "safe_hands",
        "recursion",
    ):
        assert achievement_id in state.completed
    assert state.is_module_unlocked("itertools")
    assert state.is_module_unlocked("functools")
    assert state.is_module_unlocked("dataclasses")
    assert state.is_module_unlocked("typing")
    assert state.is_example_unlocked("08_dataclass_logbook")
    assert game.miner.money == 200

    for _ in range(4):
        bus.publish(ScriptFinished())
    assert "clockwork" in state.completed
    assert state.is_function_unlocked("tick")

    bus.publish(OreMined(ore_id="stone", amount=1))
    assert "first_dig" in state.completed
    for ore_id, count in (
        ("coal", 20),
        ("copper", 20),
        ("iron", 20),
        ("silver", 20),
        ("gold", 10),
        ("ruby", 1),
    ):
        for _ in range(count):
            bus.publish(OreMined(ore_id=ore_id, amount=1))
    for achievement_id in (
        "coal_miner",
        "copper_age",
        "iron_will",
        "silver_lining",
        "gold_rush",
        "ruby_hunter",
        "completionist",
        "appraiser",
    ):
        assert achievement_id in state.completed
    assert state.is_skin_unlocked("copper_core")
    assert state.is_skin_unlocked("steel_walker")
    assert state.is_skin_unlocked("golden_hauler")
    assert state.is_skin_unlocked("ruby_runner")

    bus.publish(TileRegenerated(x=1, y=1))
    assert "patience" in state.completed
    assert state.is_function_unlocked("wait")
    assert state.is_example_unlocked("07_regen_cycle")

    bus.publish(MineAttempted(ore_id="copper", success=False, reason="tool_too_weak"))
    assert "know_your_limits" in state.completed
    assert state.is_function_unlocked("inspect")

    for _ in range(5):
        bus.publish(MineAttempted(ore_id="stone", success=True, reason=None))
    assert "lucky_strike" in state.completed
    for _ in range(8):
        bus.publish(MineAttempted(ore_id="stone", success=False, reason="miss"))
    assert "unlucky" in state.completed

    bus.publish(Moved(x=20, y=0))
    assert "far_from_home" in state.completed
    assert state.is_function_unlocked("distance")
    bus.publish(Moved(x=40, y=0))
    assert "deep_diver" in state.completed
    assert state.is_function_unlocked("biome")
    assert state.is_example_unlocked("04_explorer_spiral")

    crystal_x, crystal_y = _find_biome(game, "crystal_caverns")
    bus.publish(Moved(x=crystal_x, y=crystal_y))
    assert "crystal_hunter" in state.completed
    deep_x, deep_y = _find_biome(game, "deep_vein")
    bus.publish(Moved(x=deep_x, y=deep_y))
    assert "cartographer" in state.completed

    for _ in range(2000):
        bus.publish(Moved(x=0, y=0))
    assert "marathon" in state.completed

    for _ in range(100):
        bus.publish(MineAttempted(ore_id="coal", success=False, reason="miss"))
    assert "sampler" in state.completed
    assert state.is_function_unlocked("submit_estimate")
    assert state.is_example_unlocked("05_probability_lab")

    for _ in range(2000):
        bus.publish(MineAttempted(ore_id="stone", success=False, reason="miss"))
    assert "big_numbers" in state.completed

    for _ in range(4):
        bus.publish(EstimateSubmitted(ore_id="coal", p=0.9, error=0.0, attempts=100, good=True))
    assert "calibrated" in state.completed
    assert "well_calibrated" in state.completed


def test_generated_guide_is_up_to_date(tmp_path):
    sys.path.insert(0, str(ROOT))
    try:
        from tools import gen_docs
    finally:
        sys.path.pop(0)
    output = tmp_path / "GUIDE.md"
    gen_docs.generate_guide_md(output)
    assert output.read_text(encoding="utf-8") == (ROOT / "docs" / "GUIDE.md").read_text(
        encoding="utf-8"
    )
