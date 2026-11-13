"""Tests for the item catalog, warehouse and dynamic market (prompt 16)."""

from __future__ import annotations

import math

import pytest

from minesim.core.commands import (
    BuyUpgrade,
    Mine,
    Price,
    PriceHistory,
    Prices,
    SellStock,
    Stock,
    Unload,
    Wait,
)
from minesim.core.content import load_content
from minesim.core.engine import GameEngine
from minesim.core.events import EventBus, StockSold, Unloaded
from minesim.core.game import Game
from minesim.core.items import ItemCatalog
from minesim.core.market import Market
from minesim.core.miner import Miner
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
    return engine, world, miner


def _submit(engine, command):
    ticket = engine.submit(command)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


def test_catalog_unifies_ores_and_products(content, catalog):
    stone = catalog.get("stone")
    assert stone.kind == "ore"
    assert stone.value == content.get_ore("stone").base_value
    assert stone.base_value == stone.value
    assert stone.color == content.get_ore("stone").color
    bar = catalog.get("copper_bar")
    assert bar.kind == "product"
    assert bar.value == content.get_product("copper_bar").base_value
    assert catalog.ids == tuple(sorted(catalog.ids))
    assert catalog.position("coal") < catalog.position("stone")


def test_market_is_deterministic_for_a_seed(content, catalog):
    first = Market(1234, catalog, content.config, content.market)
    second = Market(1234, catalog, content.config, content.market)
    first.advance(5000)
    second.advance(5000)
    for item_id in catalog.ids:
        assert first.price(item_id) == second.price(item_id)
        assert first.history(item_id) == second.history(item_id)
    other = Market(9999, catalog, content.config, content.market)
    other.advance(5000)
    assert other.price("stone") != first.price("stone")


def test_market_bounds_and_history_length(content, catalog):
    market = Market(7, catalog, content.config, content.market)
    for step in range(1, 5001):
        market.advance(step * content.config.market_interval_ticks)
        for item_id, entry in content.market.items():
            assert entry.min_index <= market.index(item_id) <= entry.max_index
    for item_id in catalog.ids:
        assert len(market.history(item_id)) == content.config.market_history_len
        assert len(market.history(item_id, 10)) == 10


def test_market_mean_index_stays_near_one(content, catalog):
    market = Market(2024, catalog, content.config, content.market)
    total = 0.0
    for step in range(1, 5001):
        market.advance(step * content.config.market_interval_ticks)
        total += market.index("iron")
    assert abs(total / 5000 - 1.0) <= 0.15


def test_impact_lowers_price_and_recovers(content, catalog):
    market = Market(11, catalog, content.config, content.market)
    before = market.price("stone")
    revenue = market.sell("stone", 5)
    assert isinstance(revenue, int)
    assert market.impact("stone") == pytest.approx(0.05)
    assert market.price("stone") < before
    market.advance(content.config.market_interval_ticks)
    assert market.impact("stone") == pytest.approx(0.05 * (1.0 - 0.15))
    for step in range(2, 100):
        market.advance(step * content.config.market_interval_ticks)
    assert market.impact("stone") == 0.0


def test_revenue_is_floor_of_iterated_unit_prices(content, catalog):
    market = Market(33, catalog, content.config, content.market)
    expected = 0.0
    for _ in range(7):
        expected += market.price("copper")
        market.sell("copper", 1)
    fresh = Market(33, catalog, content.config, content.market)
    revenue = fresh.sell("copper", 7)
    assert isinstance(revenue, int)
    assert revenue == math.floor(expected)
    assert isinstance(fresh.sell("copper", 0), int)


def test_warehouse_capacity_and_round_trip():
    warehouse = Warehouse(5)
    assert warehouse.add("stone", 3) == 3
    assert warehouse.add("coal", 4) == 2
    assert warehouse.total() == 5
    assert warehouse.free == 0
    assert warehouse.add("coal", 1) == 0
    assert warehouse.count("coal") == 2
    assert warehouse.remove("stone", 10) == 3
    assert warehouse.total() == 2
    restored = Warehouse.load(warehouse.to_dict())
    assert restored.capacity == 5
    assert restored.items == {"coal": 2}


def test_unload_moves_up_to_capacity(content):
    engine, _, miner = _engine(content, capacity=4)
    seen = []
    engine.events.subscribe(Unloaded, seen.append)
    miner.inventory = {"stone": 3, "coal": 3}
    result = _submit(engine, Unload())
    assert result["moved"] == {"coal": 3, "stone": 1}
    assert result["left"] == {"stone": 2}
    assert engine.warehouse.total() == 4
    assert seen and seen[0].items == {"coal": 3, "stone": 1}


def test_unload_requires_base(content):
    engine, world, miner = _engine(content)
    for y in range(3, 40):
        for x in range(3, 40):
            if world.tile_at(x, y, 0).ore_id == "stone":
                miner.x, miner.y = x, y
                miner.inventory = {"stone": 1}
                result = _submit(engine, Unload())
                assert result == {"ok": False, "reason": "not_on_base"}
                assert miner.inventory == {"stone": 1}
                return
    raise AssertionError("no stone tile")


def test_sell_stock_uses_market_and_respects_amount(content):
    engine, _, miner = _engine(content)
    engine.warehouse.add("stone", 10)
    before = engine.market.price("stone")
    seen = []
    engine.events.subscribe(StockSold, seen.append)
    result = _submit(engine, SellStock("stone", 4))
    assert result["ok"] and result["amount"] == 4
    assert engine.warehouse.count("stone") == 6
    assert result["money"] > 0
    assert result["avg_index"] == 1.0
    assert engine.market.price("stone") < before
    assert seen and seen[0].amount == 4 and seen[0].money == result["money"]
    assert _submit(engine, SellStock("stone", 999))["amount"] == 6
    assert engine.warehouse.count("stone") == 0


def test_sell_stock_rules(content):
    engine, _, _ = _engine(content)
    engine.warehouse.add("stone", 2)
    assert _submit(engine, SellStock("stone", 0))["amount"] == 0
    assert _submit(engine, SellStock("unknown", 1))["reason"] == "unknown_item"
    assert _submit(engine, SellStock("stone", -3))["amount"] == 0


def test_stock_and_price_commands(content):
    engine, _, miner = _engine(content)
    engine.warehouse.add("stone", 7)
    stock = _submit(engine, Stock())
    assert stock["items"] == {"stone": 7}
    assert stock["capacity"] == content.config.warehouse_start_capacity
    assert _submit(engine, Price("stone"))["price"] == round(engine.market.price("stone"), 2)
    assert "stone" in _submit(engine, Prices())["prices"]
    history = _submit(engine, PriceHistory("stone", 5))["history"]
    assert history is not None and len(history) <= 5
    game = Game.new(seed=5)
    price_ticket = game.submit(Price("coal"))
    history_ticket = game.submit(PriceHistory("coal", 5))
    game.run_until_idle()
    assert price_ticket.result["price"] is None
    assert history_ticket.result["history"] is None


def test_warehouse_upgrade_increases_capacity(content):
    engine, _, miner = _engine(content)
    miner.money = 150
    assert _submit(engine, BuyUpgrade("warehouse"))["ok"]
    assert engine.warehouse.capacity == content.config.warehouse_start_capacity + 100
    assert miner.money == 0


def test_remove_drone_unloads_only_on_base(content):
    engine, _, _ = _engine(content)
    drone = engine.spawn_drone()
    drone.inventory = {"stone": 3}
    assert engine.remove_drone(drone.id)
    assert engine.warehouse.count("stone") == 3
    other = engine.spawn_drone()
    other.x, other.y = 5, 5
    other.inventory = {"coal": 2}
    assert engine.remove_drone(other.id)
    assert engine.warehouse.count("coal") == 0


def test_save_load_gives_identical_future_prices(content, tmp_path):
    game = Game.new(seed=4242)
    game.engine.warehouse.add("stone", 9)
    for _ in range(7):
        game.step()
    path = game.save(tmp_path / "slot.json")
    loaded = Game.load(path)
    assert loaded.engine.warehouse.to_dict() == game.engine.warehouse.to_dict()
    assert loaded.engine.market.to_dict() == game.engine.market.to_dict()
    for _ in range(500):
        game.step()
        loaded.step()
    assert loaded.engine.market.to_dict() == game.engine.market.to_dict()
    for item_id in loaded.engine.catalog.ids:
        assert loaded.engine.market.price(item_id) == game.engine.market.price(item_id)


def test_headless_session_mines_unloads_waits_and_sells(content):
    game = Game.new(seed=77)
    world = game.world
    for y in range(2, 40):
        for x in range(2, 40):
            if world.tile_at(x, y, 0).ore_id == "stone":
                game.miner.x, game.miner.y = x, y
                mine = game.submit(Mine())
                game.run_until_idle()
                assert mine.done
                break
        else:
            continue
        break
    assert game.miner.inventory
    game.miner.x, game.miner.y = 0, 0
    unload = game.submit(Unload())
    game.run_until_idle()
    assert unload.result["moved"]
    assert game.engine.warehouse.total() > 0
    before = game.engine.market.price("stone")
    wait = game.submit(Wait(200))
    game.run_until_idle()
    assert wait.done
    after = game.engine.market.price("stone")
    assert after != before
    sold = game.submit(SellStock("stone"))
    game.run_until_idle()
    assert sold.result["ok"] and sold.result["money"] > 0
    assert game.engine.warehouse.count("stone") == 0
