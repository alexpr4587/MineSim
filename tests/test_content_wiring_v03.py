"""Tests for the v0.3 content wiring (prompt 24)."""

from __future__ import annotations

from collections import defaultdict

import pytest

from minesim.core.content import load_content
from minesim.core.events import OreMined, Sold, Unloaded
from minesim.core.game import Game
from minesim.core.progression.state import ProgressionState

TABS = {
    "code",
    "mining",
    "business",
    "trading",
    "industry",
    "fleet",
    "explorer",
    "data",
}


@pytest.fixture(scope="module")
def content():
    return load_content()


def test_v03_achievements_exist_with_eight_tabs(content):
    assert len(content.achievements) == 69
    assert {achievement.tab for achievement in content.achievements.values()} == TABS
    assert content.achievements["storage_unit"].tab == "trading"
    assert content.achievements["smelter"].tab == "industry"
    assert content.achievements["second_pair_of_hands"].tab == "fleet"


def test_v03_achievement_graph_parents_and_cycles(content):
    for achievement in content.achievements.values():
        if achievement.parent is None:
            continue
        assert achievement.parent in content.achievements
        assert content.achievements[achievement.parent].tab == achievement.tab
        seen = {achievement.id}
        cursor = achievement
        while cursor.parent is not None:
            assert cursor.parent not in seen
            seen.add(cursor.parent)
            cursor = content.achievements[cursor.parent]


def test_v03_every_unlockable_thing_has_exactly_one_unlocking_achievement(content):
    collections = {
        "function": content.functions,
        "ore": content.ores,
        "upgrade": content.upgrades,
        "module": content.modules,
        "skin": content.skins,
        "example": content.examples,
        "recipe": content.recipes,
        "feature": content.features,
    }
    reward_kinds = {
        "unlock_function": "function",
        "unlock_ore": "ore",
        "unlock_upgrade": "upgrade",
        "unlock_module": "module",
        "unlock_skin": "skin",
        "unlock_example": "example",
        "unlock_recipe": "recipe",
        "unlock_feature": "feature",
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


def test_v03_initial_unlock_sets(content):
    state = ProgressionState(content)
    assert state.unlocked_recipes == set()
    assert state.unlocked_features == set()
    assert state.unlocked_upgrades == {"shaft", "battery", "charger"}
    assert state.unlocked_modules == {"math"}
    assert state.unlocked_examples == {"01_hello"}
    assert state.unlocked_functions == {
        "move",
        "mine",
        "peek",
        "position",
        "battery",
        "charge",
        "energy_cost",
        "layer",
        "layers",
        "descend",
        "ascend",
    }


def test_scripted_headless_session_unlocks_a_chain_across_tabs():
    game = Game.new(seed=12345)
    bus = game.events
    state = game.progression_state

    for _ in range(5):
        bus.publish(Sold(money=10, items={"stone": 1}, avg_index=1.0))
    assert "storage_unit" in state.completed
    assert state.is_feature_unlocked("warehouse")
    assert state.is_function_unlocked("unload")
    assert state.is_function_unlocked("stock")
    assert state.is_function_unlocked("sell_stock")
    assert state.is_upgrade_unlocked("warehouse")

    for _ in range(3):
        bus.publish(Unloaded(items={"stone": 1}))
    assert "market_watcher" in state.completed
    assert state.is_feature_unlocked("market")
    assert state.is_function_unlocked("price")
    assert state.is_function_unlocked("prices")

    bus.publish(OreMined(ore_id="copper", amount=30))
    assert "smelter" in state.completed
    assert state.is_feature_unlocked("refinery")
    assert state.is_function_unlocked("recipes")
    assert state.is_function_unlocked("refine")
    assert state.is_function_unlocked("refinery")
    assert state.is_recipe_unlocked("copper_bar")
    assert state.is_upgrade_unlocked("furnace")
