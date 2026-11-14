"""Tests for the refinery and delivery contracts (prompt 17)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from minesim.core.commands import (
    Contracts,
    Deliver,
    Mine,
    Recipes,
    Refine,
    RefineryStatus,
    Unload,
)
from minesim.core.content import ContentError, load_content
from minesim.core.contracts import ContractBoard
from minesim.core.engine import GameEngine
from minesim.core.events import EventBus
from minesim.core.game import Game
from minesim.core.items import ItemCatalog
from minesim.core.miner import Miner
from minesim.core.refinery import Refinery
from minesim.core.save import SaveGame, migrate
from minesim.core.warehouse import Warehouse
from minesim.core.world import World, WorldGenerator


@pytest.fixture(scope="module")
def content():
    return load_content()


@pytest.fixture(scope="module")
def catalog(content):
    return ItemCatalog(content)


def _engine(content, *, capacity=None):
    world = World(WorldGenerator(content.config.seed_default, content), content)
    miner = Miner.from_config(content)
    engine = GameEngine(world, miner, content, EventBus())
    if capacity is not None:
        engine.warehouse.capacity = capacity
    return engine


def _submit(engine, command):
    ticket = engine.submit(command)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


def _subject(content):
    return content.recipes


def test_recipes_content_is_valid_and_loaded(content):
    assert set(content.recipes) == {
        "copper_bar",
        "iron_bar",
        "steel_bar",
        "silver_bar",
        "gold_bar",
        "cut_ruby",
    }
    assert content.get_recipe("copper_bar").inputs == {"copper": 3}
    assert content.get_recipe("steel_bar").inputs == {"iron_bar": 2, "coal": 2}
    assert content.get_recipe("cut_ruby").ticks == 200
    assert all(recipe.unlocked_by is None for recipe in content.recipes.values())


def test_invalid_recipe_item_raises_content_error(tmp_path):
    target = tmp_path / "content"
    shutil.copytree(Path(__file__).resolve().parents[1] / "src/minesim/content", target)
    recipes_path = target / "recipes.json"
    recipes = json.loads(recipes_path.read_text(encoding="utf-8"))
    recipes[0]["inputs"] = {"unobtainium": 1}
    recipes_path.write_text(json.dumps(recipes), encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_content(target)
    assert "recipes.json" in str(excinfo.value)
    assert "unobtainium" in str(excinfo.value)


def test_refinery_consumes_inputs_and_finishes(content):
    warehouse = Warehouse(20)
    warehouse.add("copper", 6)
    refinery = Refinery(content.recipes, 1, warehouse=warehouse)
    job = refinery.start("copper_bar", 2, warehouse, 0)
    assert job.duration == 120
    assert warehouse.count("copper") == 0
    assert refinery.advance(60) == []
    status = refinery.status()
    assert status[0]["recipe"] == "copper_bar"
    assert status[0]["progress"] == pytest.approx(0.5)
    assert status[0]["ticks_left"] == 60
    finished = refinery.advance(120)
    assert finished == [{"recipe": "copper_bar", "times": 2, "outputs": {"copper_bar": 2}}]
    assert warehouse.count("copper_bar") == 2
    assert refinery.status() == []


def test_refinery_validates_slots_inputs_and_recipes(content):
    warehouse = Warehouse(20)
    warehouse.add("copper", 3)
    refinery = Refinery(content.recipes, 1, warehouse=warehouse)
    refinery.start("copper_bar", 1, warehouse, 0)
    with pytest.raises(ValueError, match="no_free_slot"):
        refinery.start("copper_bar", 1, warehouse, 0)
    other = Refinery(content.recipes, 1, warehouse=warehouse)
    with pytest.raises(ValueError, match="insufficient_inputs"):
        other.start("copper_bar", 1, warehouse, 0)
    with pytest.raises(KeyError):
        other.start("nope", 1, warehouse, 0)


def test_refinery_blocks_when_output_does_not_fit(content):
    warehouse = Warehouse(3)
    warehouse.add("copper", 3)
    refinery = Refinery(content.recipes, 1, warehouse=warehouse)
    refinery.start("copper_bar", 1, warehouse, 0)
    warehouse.add("stone", 3)
    assert refinery.advance(60) == []
    assert refinery.status()[0]["blocked"] is True
    warehouse.remove("stone", 3)
    assert refinery.advance(60)[0]["outputs"] == {"copper_bar": 1}
    assert warehouse.count("copper_bar") == 1


def test_contract_board_generation_is_deterministic(content, catalog):
    first = ContractBoard(4242, catalog, content.config, content.recipes)
    second = ContractBoard(4242, catalog, content.config, content.recipes)
    for tick in range(1, 9001):
        first.advance(tick)
        second.advance(tick)
    assert first.to_dict() == second.to_dict()
    assert first.contracts
    third = ContractBoard(9999, catalog, content.config, content.recipes)
    for tick in range(1, 9001):
        third.advance(tick)
    assert third.to_dict() != first.to_dict()


def test_contract_delivery_requires_full_stock_and_pays_reward(content, catalog):
    board = ContractBoard(7, catalog, content.config, content.recipes)
    for tick in range(1, 3001):
        board.advance(tick)
    contract = board.contracts[0]
    warehouse = Warehouse(1_000_000)
    warehouse.add(contract.item, contract.quantity - 1)
    with pytest.raises(ValueError, match="insufficient_stock"):
        board.deliver(contract.id, warehouse)
    warehouse.add(contract.item, 1)
    reward = board.deliver(contract.id, warehouse)
    assert reward == contract.reward
    assert warehouse.count(contract.item) == 0
    assert board.contracts == []


def test_contracts_expire(content, catalog):
    config = SimpleNamespace(
        contract_interval_ticks=5000,
        contract_start_slots=1,
        contract_deadline_min=100,
        contract_deadline_max=100,
        contract_premium_min=1.3,
        contract_premium_max=2.0,
        contract_value_min=500,
        contract_value_max=500,
    )
    board = ContractBoard(11, catalog, config, content.recipes)
    generated, expired = board.advance(5000)
    assert len(generated) == 1
    assert expired == []
    generated, expired = board.advance(5100)
    assert generated == []
    assert [contract.id for contract in expired] == [1]
    assert board.contracts == []


def test_refinery_and_contract_api_commands_are_json_safe(content):
    engine = _engine(content, capacity=1_000_000)
    assert json.dumps(_submit(engine, Recipes()))
    engine.warehouse.add("copper", 3)
    refine_result = _submit(engine, Refine("copper_bar", 1))
    assert refine_result["ok"] is True
    assert json.dumps(refine_result)
    status = _submit(engine, RefineryStatus())
    assert isinstance(status["jobs"], list)
    assert json.dumps(status)
    for _ in range(3000):
        engine.step()
    contracts = _submit(engine, Contracts())["contracts"]
    assert contracts
    contract = contracts[0]
    engine.warehouse.add(contract["item"], contract["quantity"])
    assert json.dumps(_submit(engine, Deliver(contract["id"])))
    assert not engine.contracts.contracts


def test_save_v5_fixture_migrates_to_refinery_and_contracts():
    fixture = Path(__file__).parent / "fixtures" / "save_v5.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    migrated = migrate(data)
    assert migrated["version"] == 6
    assert migrated["refinery"] == {}
    assert migrated["contracts"] == {}
    savegame = SaveGame.load(fixture)
    assert savegame.version == 6
    game = Game.load(fixture)
    assert game.engine.warehouse.count("stone") == 2
    assert game.engine.refinery.jobs == []
    assert game.engine.contracts.contracts == []


def test_refinery_and_contracts_round_trip_through_save(tmp_path):
    game = Game.new(seed=123)
    game.engine.warehouse.capacity = 1_000_000
    game.engine.warehouse.add("copper", 3)
    assert game.start_refine("copper_bar", 1)["ok"] is True
    for _ in range(3000):
        game.step()
    path = tmp_path / "slot.json"
    game.save(path)
    loaded = Game.load(path)
    assert loaded.engine.refinery.status() == game.engine.refinery.status()
    assert loaded.engine.contracts.status() == game.engine.contracts.status()
    loaded.step()
    game.step()
    assert loaded.engine.warehouse.count("copper_bar") == game.engine.warehouse.count("copper_bar")


def test_headless_session_mines_refines_sells_and_delivers():
    game = Game.new(seed=12345)
    game.engine.warehouse.capacity = 1_000_000
    game.progression_state.unlock_ore("copper")
    game.player_stats.tool_tier = 1
    tile = None
    for radius in range(0, 30):
        for x in range(-radius, radius + 1):
            for y in range(-radius, radius + 1):
                candidate = game.world.tile_at(x, y, game.tick)
                if getattr(candidate, "ore_id", None) == "copper":
                    tile = (x, y)
                    break
            if tile:
                break
        if tile:
            break
    assert tile is not None
    game.miner.x, game.miner.y = tile
    for _ in range(20):
        game.submit(Mine())
        game.run_until_idle()
        if game.miner.inventory.get("copper"):
            break
    assert game.miner.inventory.get("copper", 0) >= 1
    game.miner.x, game.miner.y = 0, 0
    assert _submit(game.engine, Unload())["ok"] is True
    game.engine.warehouse.add("copper", max(0, 3 - game.engine.warehouse.count("copper")))
    assert game.start_refine("copper_bar", 1)["ok"] is True
    for _ in range(60):
        game.step()
    assert game.engine.warehouse.count("copper_bar") == 1
    sold = game.sell_stock("copper_bar")
    assert sold["ok"] is True and sold["money"] > 0
    while not game.engine.contracts.contracts:
        game.step()
    contract = game.engine.contracts.contracts[0]
    game.engine.warehouse.add(contract.item, contract.quantity)
    delivered = game.deliver_contract(contract.id)
    assert delivered["ok"] is True
    assert delivered["reward"] > 0
