"""Tests for the v0.3 progression extension (prompt 23)."""

from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from minesim.core.commands import SpawnDrone
from minesim.core.content import load_content
from minesim.core.events import (
    ApiCalled,
    ContractDelivered,
    Moved,
    OreMined,
    RefineFinished,
    Sold,
    Unloaded,
    WorldEventStarted,
)
from minesim.core.game import Game
from minesim.core.progression.state import ProgressionState
from minesim.core.save import migrate
from minesim.core.schemas import Achievement, CounterCriteria, Feature, Reward
from minesim.scripting.host import analyze_features


@pytest.fixture(scope="module")
def content():
    return load_content()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_new_counters_move_on_their_events():
    game = Game.new(seed=123)
    state = game.progression_state

    game.engine.warehouse.add("stone", 5)
    game.events.publish(Unloaded(items={"stone": 5}))
    assert state.get_counter("unloads") == 1
    assert state.get_counter("warehouse_peak") >= 5

    game.events.publish(Unloaded(items={}))
    assert state.get_counter("unloads") == 1

    game.events.publish(Sold(money=100, items={"stone": 7}, avg_index=1.5))
    assert state.get_counter("sold_high") == 7
    game.events.publish(Sold(money=100, items={"stone": 7}, avg_index=1.0))
    assert state.get_counter("sold_high") == 7

    game.events.publish(
        RefineFinished(
            recipe="copper_bar",
            times=2,
            outputs={"copper_bar": 2},
        )
    )
    assert state.get_counter("recipe:copper_bar") == 2
    assert state.get_counter("bars_made") == 2

    game.events.publish(ContractDelivered(id=1, reward=450))
    assert state.get_counter("contracts_done") == 1
    assert state.get_counter("contract_reward_total") == 450

    game.engine.spawn_drone()
    assert state.get_counter("drones_spawned") == 1
    assert state.get_counter("max_drones_alive") == 2

    game.events.publish(WorldEventStarted(kind="rich_vein", id=9))
    assert state.get_counter("events_started") == 1

    game.events.publish(OreMined(ore_id="stone", amount=3, in_rich_vein=True))
    assert state.get_counter("rich_vein_mined") == 3

    game.events.publish(Moved(x=1, y=0, in_slow_zone=True))
    assert state.get_counter("slow_zone_moves") == 1

    game.events.publish(ApiCalled(function="move", drone_id=0))
    game.events.publish(ApiCalled(function="move", drone_id=1))
    game.events.publish(ApiCalled(function="mine", drone_id=0))
    assert state.get_counter("api:move") == 2
    assert state.get_counter("api:mine") == 1


def test_recipe_and_feature_initial_unlocks(content):
    state = ProgressionState(content)
    for recipe in content.recipes.values():
        assert state.is_recipe_unlocked(recipe.id) is (recipe.unlocked_by is None)
    assert state.unlocked_features == {
        "warehouse",
        "market",
        "refinery",
        "contracts",
        "drones",
    }


def test_recipe_and_feature_rewards():
    game = Game.new(seed=7)
    state = game.progression_state
    state.unlocked_recipes.discard("copper_bar")
    state.unlocked_features.discard("market")
    game.content.achievements["v03_reward"] = Achievement(
        id="v03_reward",
        tab="business",
        parent=None,
        title="V03 Reward",
        criteria=CounterCriteria(counter="unloads", target=1),
        rewards=[
            Reward(type="unlock_recipe", id="copper_bar"),
            Reward(type="unlock_feature", id="market"),
        ],
    )
    game.events.publish(Unloaded(items={"stone": 1}))
    assert state.is_completed("v03_reward")
    assert state.is_recipe_unlocked("copper_bar")
    assert state.is_feature_unlocked("market")
    assert game.progression.is_recipe_unlocked("copper_bar")
    assert game.progression.is_feature_unlocked("market")


def test_game_actions_refuse_locked_features():
    game = Game.new(seed=8)
    state = game.progression_state

    state.unlocked_features.discard("warehouse")
    result = game.unload(0)
    assert result["reason"] == "locked_feature"
    assert result["feature"] == "warehouse"
    assert "Unlocks with:" in result["message"]

    state.unlocked_features.discard("market")
    assert game.sell_stock("stone")["feature"] == "market"

    state.unlocked_features.discard("refinery")
    assert game.start_refine("copper_bar")["feature"] == "refinery"

    state.unlocked_features.discard("contracts")
    assert game.deliver_contract(1)["feature"] == "contracts"

    state.unlocked_features.discard("drones")
    result = SpawnDrone().execute(game.engine)
    assert result["reason"] == "locked_feature"
    assert result["feature"] == "drones"


def test_locked_recipe_refuses_refine():
    game = Game.new(seed=9)
    game.engine.warehouse.add("copper", 3)
    game.progression_state.unlocked_recipes.discard("copper_bar")
    result = game.start_refine("copper_bar")
    assert result["ok"] is False
    assert result["reason"] == "locked_recipe"


@pytest.mark.integration
def test_host_publishes_api_called_for_real_scripts(tmp_path):
    from minesim.scripting.manager import ScriptManager

    game = Game.new(seed=14)
    manager = ScriptManager(game, tmp_path)
    manager.start(0, "main.py", "move(East)\nmove(West)\n")
    for _ in range(500):
        manager.pump()
        if not manager.host(0).is_running:
            break
        game.step()
        time.sleep(0.001)
    manager.pump()
    assert game.progression_state.get_counter("api:move") == 2


def test_uses_inheritance_feature():
    assert "uses_inheritance" not in analyze_features("class A:\n    pass\n")
    assert "uses_inheritance" not in analyze_features("class A(object):\n    pass\n")
    features = analyze_features("class A(Mixin):\n    pass\n")
    assert "uses_inheritance" in features
    assert "uses_class" in features


def test_save_v7_migrates_and_new_unlock_sets_default(content):
    data = {"version": 7, "seed": 1, "progression": {"counters": {"unloads": 3}}}
    migrated = migrate(data)
    assert migrated["version"] == 8
    state = ProgressionState.from_dict(migrated["progression"], content=content)
    assert state.get_counter("unloads") == 3
    assert state.unlocked_recipes == {
        recipe.id for recipe in content.recipes.values() if recipe.unlocked_by is None
    }
    assert state.unlocked_features == {
        feature.id for feature in content.features.values() if feature.unlocked_by is None
    }


def test_locked_recipe_and_feature_survive_save_round_trip(tmp_path):
    path = tmp_path / "slot.json"
    game = Game.new(seed=10)
    game.progression_state.unlocked_recipes.discard("copper_bar")
    game.progression_state.unlocked_features.discard("market")
    game.save(path)

    loaded = Game.load(path)
    assert not loaded.progression_state.is_recipe_unlocked("copper_bar")
    assert not loaded.progression_state.is_feature_unlocked("market")


def _lock_market(game):
    game.content.features["market"] = Feature(
        id="market",
        name="Market",
        unlocked_by="first_dig",
    )
    game.progression_state.unlocked_features.discard("market")


def test_market_panel_shows_lock_overlay(qapp):
    from minesim.ui.market_panel import MarketPanel

    game = Game.new(seed=11)
    _lock_market(game)
    panel = MarketPanel(game=game)
    panel.show()
    qapp.processEvents()
    assert panel.lock_overlay.locked
    assert panel.lock_overlay.isVisible()
    assert "Unlocks with: First Dig" in panel.lock_overlay.message_label.text()
    panel.close()


def test_drones_panel_shows_lock_overlay(qapp):
    from minesim.ui.drones_panel import DronesPanel

    game = Game.new(seed=12)
    game.content.features["drones"] = Feature(
        id="drones",
        name="Drones",
        unlocked_by="first_dig",
    )
    game.progression_state.unlocked_features.discard("drones")
    panel = DronesPanel(game=game, scripts_dir="/nonexistent")
    panel.show()
    qapp.processEvents()
    assert panel.lock_overlay.locked
    assert panel.lock_overlay.isVisible()
    assert "Unlocks with: First Dig" in panel.lock_overlay.message_label.text()
    panel.close()


def test_base_panel_shows_lock_overlay_per_tab(qapp):
    from minesim.ui.base_panel import BasePanel

    game = Game.new(seed=13)
    game.content.features["refinery"] = Feature(
        id="refinery",
        name="Refinery",
        unlocked_by="first_dig",
    )
    game.progression_state.unlocked_features.discard("refinery")
    panel = BasePanel(game=game)
    panel.show()
    panel.tabs.setCurrentIndex(1)
    qapp.processEvents()
    overlay = panel._lock_overlays["refinery"]
    assert overlay.locked
    assert overlay.isVisible()
    assert "Unlocks with: First Dig" in overlay.message_label.text()
    assert not panel._lock_overlays["warehouse"].locked
    panel.close()
