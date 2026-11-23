"""Tests for the v0.4 content wiring (prompt 35)."""

from __future__ import annotations

import pytest

from minesim.core.content import load_content
from minesim.core.events import DockServed, LayerChanged, MoveRefused, Sold
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
    "engineering",
    "depths",
}

ACHIEVEMENTS = {
    "out_of_juice": ("engineering", None),
    "power_user": ("engineering", "out_of_juice"),
    "first_charge": ("engineering", "out_of_juice"),
    "rescued": ("engineering", "out_of_juice"),
    "efficiency_expert": ("engineering", "power_user"),
    "traffic_jam": ("engineering", None),
    "dock_master": ("engineering", "traffic_jam"),
    "deep_ambition": ("depths", None),
    "first_descent": ("depths", "deep_ambition"),
    "galleries_veteran": ("depths", "first_descent"),
    "feel_the_heat": ("depths", "first_descent"),
    "cool_head": ("depths", "feel_the_heat"),
    "meltdown": ("depths", "feel_the_heat"),
    "deep_miner": ("depths", "feel_the_heat"),
    "fresh_air": ("depths", "feel_the_heat"),
    "abyss_gazer": ("depths", "deep_miner"),
    "abyssal_haul": ("depths", "abyss_gazer"),
}


@pytest.fixture(scope="module")
def content():
    return load_content()


def test_v04_achievements_exist_with_ten_tabs(content):
    assert len(content.achievements) == 86
    assert {achievement.tab for achievement in content.achievements.values()} == TABS
    for achievement_id, (tab, parent) in ACHIEVEMENTS.items():
        achievement = content.achievements[achievement_id]
        assert achievement.tab == tab
        assert achievement.parent == parent


def test_v04_achievement_graph_parents_and_cycles(content):
    for achievement_id in ACHIEVEMENTS:
        achievement = content.achievements[achievement_id]
        seen = {achievement.id}
        cursor = achievement
        while cursor.parent is not None:
            assert cursor.parent in content.achievements
            assert content.achievements[cursor.parent].tab == achievement.tab
            assert cursor.parent not in seen
            seen.add(cursor.parent)
            cursor = content.achievements[cursor.parent]


def test_v04_unlock_wiring(content):
    functions = {
        "battery": "out_of_juice",
        "charge": "out_of_juice",
        "energy_cost": "out_of_juice",
        "temperature": "feel_the_heat",
        "cool": "feel_the_heat",
        "climate": "feel_the_heat",
        "dock_free": "traffic_jam",
        "dock_rate": "traffic_jam",
        "layer": "deep_ambition",
        "layers": "deep_ambition",
        "descend": "deep_ambition",
        "ascend": "deep_ambition",
    }
    for name, achievement_id in functions.items():
        assert content.functions[name].unlocked_by == achievement_id

    upgrades = {
        "shaft": "deep_ambition",
        "battery": "out_of_juice",
        "charger": "first_charge",
        "cooling": "feel_the_heat",
        "ventilation": "feel_the_heat",
        "dock": "traffic_jam",
    }
    for upgrade_id, achievement_id in upgrades.items():
        assert content.upgrades[upgrade_id].unlocked_by == achievement_id

    assert content.modules["json"].unlocked_by == "power_user"
    assert content.modules["copy"].unlocked_by == "galleries_veteran"

    examples = {
        "17_energy_budget": "power_user",
        "18_go_deep": "first_descent",
        "19_climate_watch": "cool_head",
        "20_dock_etiquette": "dock_master",
        "21_night_shift": "efficiency_expert",
        "22_layer_prospector": "abyss_gazer",
        "23_vent_manager": "fresh_air",
        "24_full_automation": "abyssal_haul",
    }
    for example_id, achievement_id in examples.items():
        assert content.examples[example_id].unlocked_by == achievement_id


def test_v04_initial_unlock_sets(content):
    state = ProgressionState(content)
    assert state.unlocked_functions == {"move", "mine", "peek", "position"}
    assert state.unlocked_upgrades == set()
    assert state.unlocked_modules == {"math"}
    assert state.unlocked_examples == {"01_hello"}


def test_scripted_session_unlocks_v04_roots():
    game = Game.new(seed=12345)
    bus = game.events
    state = game.progression_state

    bus.publish(MoveRefused(reason="low_energy"))
    assert "out_of_juice" in state.completed
    assert state.is_function_unlocked("battery")
    assert state.is_function_unlocked("charge")
    assert state.is_function_unlocked("energy_cost")
    assert state.is_upgrade_unlocked("battery")

    bus.publish(DockServed(miner_id=0, units=100, waited_ticks=50))
    assert "traffic_jam" in state.completed
    assert state.is_function_unlocked("dock_free")
    assert state.is_function_unlocked("dock_rate")
    assert state.is_upgrade_unlocked("dock")

    bus.publish(Sold(money=8000, items={"stone": 1}, avg_index=1.0))
    assert "deep_ambition" in state.completed
    for name in ("layer", "layers", "descend", "ascend"):
        assert state.is_function_unlocked(name)
    assert state.is_upgrade_unlocked("shaft")

    bus.publish(LayerChanged(miner_id=0, from_layer=0, to_layer=1))
    assert "first_descent" in state.completed
    assert state.is_example_unlocked("18_go_deep")

    bus.publish(LayerChanged(miner_id=0, from_layer=1, to_layer=2))
    assert "feel_the_heat" in state.completed
    for name in ("temperature", "cool", "climate"):
        assert state.is_function_unlocked(name)
    assert state.is_upgrade_unlocked("cooling")
    assert state.is_upgrade_unlocked("ventilation")
