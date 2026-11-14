"""Tests for prompt 19: seed/tick-pure world events."""

from __future__ import annotations

import math
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from minesim.core.commands import Events, Mine, Move
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.engine import AllUnlocked, GameEngine
from minesim.core.events import EventBus, Moved, OreMined, WorldEventEnded, WorldEventStarted
from minesim.core.miner import Miner
from minesim.core.world import World, WorldGenerator
from minesim.core.worldevents import WorldEvents

ROOT_SEED = 424242


@pytest.fixture(scope="module")
def content():
    return load_content()


def _definitions(**overrides):
    defaults = {
        "kind": "rich_vein",
        "radius": 100,
        "duration": 100000,
        "yield_multiplier": 2,
        "move_cost_multiplier": 2,
        "min_distance": 0,
        "max_distance": 0,
        "factor_choices": [1.5],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _events(
    kind: str,
    *,
    factor_choices=None,
    chance=1.0,
    item_ids=("stone",),
    **definition_overrides,
):
    definition = _definitions(
        kind=kind,
        factor_choices=[1.5] if factor_choices is None else factor_choices,
        **definition_overrides,
    )
    config = SimpleNamespace(
        world_event_interval_ticks=2500,
        world_event_chance=chance,
    )
    return WorldEvents(
        7,
        config,
        {kind: definition},
        item_ids=item_ids,
    )


def _engine(content, world_events, *, progression=None):
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    bus = EventBus()
    engine = GameEngine(
        world,
        miner,
        content,
        bus,
        progression or AllUnlocked(),
        world_events=world_events,
    )
    return engine, world, miner, bus


def _find_ore(world, ore_id, radius=40, *, min_distance=0):
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            if max(abs(x), abs(y)) < min_distance:
                continue
            if world.tile_at(x, y, 0).ore_id == ore_id:
                return x, y
    raise AssertionError(f"no {ore_id} tile")


# -- determinism and distribution -------------------------------------------------


def test_events_are_a_pure_function_of_seed_and_tick(content):
    first = WorldEvents(ROOT_SEED, content.config, content)
    second = WorldEvents(ROOT_SEED, content.config, content)
    ticks = [0, 1, 2499, 2500, 4300, 9000, 50000]
    for tick in ticks:
        assert first.active_at(tick) == second.active_at(tick)
        assert first.modifiers_at(12, -9, tick) == second.modifiers_at(12, -9, tick)


def test_about_world_event_chance_of_slots_have_an_event(content):
    events = WorldEvents(ROOT_SEED, content.config, content)
    count = sum(1 for slot in range(200) if events.event_for_slot(slot) is not None)
    assert 80 <= count <= 160


def test_positions_respect_min_and_max_distance(content):
    events = WorldEvents(ROOT_SEED, content.config, content)
    checked = 0
    for slot in range(300):
        event = events.event_for_slot(slot)
        if event is None or event.x is None or event.y is None:
            continue
        definition = content.events[event.kind]
        chebyshev = max(abs(event.x), abs(event.y))
        euclidean = math.hypot(event.x, event.y)
        assert definition.min_distance <= chebyshev <= definition.max_distance
        assert definition.min_distance <= euclidean <= definition.max_distance
        assert isinstance(event.x, int) and isinstance(event.y, int)
        checked += 1
    assert checked > 0


def test_modifiers_inside_and_outside_the_radius():
    events = _events("rich_vein", duration=10)
    event = events.active_at(0)[0]
    assert events.modifiers_at(0, 0, 0)["yield_multiplier"] == 2
    assert events.modifiers_at(event.x + 101, event.y, 0)["yield_multiplier"] == 1
    assert events.modifiers_at(0, 0, event.ends)["yield_multiplier"] == 1


# -- engine effects ---------------------------------------------------------------


def test_mining_inside_a_rich_vein_doubles_the_yield(content):
    events = _events("rich_vein")
    engine, world, miner, bus = _engine(content, events)
    mined: list[OreMined] = []
    bus.subscribe(OreMined, mined.append)
    miner.x, miner.y = _find_ore(world, "stone")
    for _ in range(40):
        result = engine.submit(Mine())
        engine.run_until_idle()
        if result.done and result.result and result.result.get("ok"):
            break
    assert result.result is not None and result.result["ok"]
    assert result.result["amount"] == 2
    assert result.result["in_rich_vein"] is True
    assert mined[-1].amount == 2
    assert mined[-1].in_rich_vein is True


def test_mining_outside_the_radius_keeps_the_normal_yield(content):
    events = _events("rich_vein", radius=1)
    engine, world, miner, bus = _engine(content, events)
    mined: list[OreMined] = []
    bus.subscribe(OreMined, mined.append)
    miner.x, miner.y = _find_ore(world, "stone", min_distance=3)
    for _ in range(40):
        result = engine.submit(Mine())
        engine.run_until_idle()
        if result.done and result.result and result.result.get("ok"):
            break
    assert result.result is not None and result.result["ok"]
    assert result.result["amount"] == 1
    assert mined[-1].in_rich_vein is False


def test_moving_inside_a_slow_zone_costs_double(content):
    events = _events("slow_zone")
    engine, _, miner, bus = _engine(content, events)
    moved: list[Moved] = []
    bus.subscribe(Moved, moved.append)
    assert Move(Direction.EAST).cost_ticks(engine) == int(math.ceil(miner.move_ticks * 2))
    ticket = engine.submit(Move(Direction.EAST))
    engine.run_until_idle()
    assert ticket.done
    assert moved and moved[-1].in_slow_zone is True


def test_market_news_changes_the_price_and_ends_on_time(content):
    events = _events(
        "market_news",
        factor_choices=[1.5],
        item_ids=("stone",),
        duration=5,
    )
    engine, _, _, _ = _engine(content, events)
    event = events.active_at(0)[0]
    assert event.item == "stone"
    assert engine.market.shock("stone") == pytest.approx(1.5)
    base = content.get_ore("stone").base_value
    assert engine.market.price("stone") == pytest.approx(base * 1.5)
    for _ in range(event.ends):
        engine.step()
    assert engine.market.shock("stone") == pytest.approx(1.0)


def test_world_event_started_and_ended_are_published(content):
    events = _events("slow_zone", duration=3)
    engine, _, _, bus = _engine(content, events)
    engine.tick = 2499
    engine._prime_world_events()
    started: list[WorldEventStarted] = []
    ended: list[WorldEventEnded] = []
    bus.subscribe(WorldEventStarted, started.append)
    bus.subscribe(WorldEventEnded, ended.append)
    engine.step()
    assert started and started[-1].kind == "slow_zone"
    for _ in range(3):
        engine.step()
    assert ended and ended[-1].id == started[-1].id


# -- API command ------------------------------------------------------------------


def test_events_command_hides_locked_news_and_never_shows_the_factor(content):
    events = _events("market_news", factor_choices=[0.6], item_ids=("coal",))
    engine, _, _, _ = _engine(content, events, progression=_OnlyStone())
    result = engine.submit(Events()).result
    assert result is not None and result["events"] == []

    events = _events("market_news", factor_choices=[0.6], item_ids=("stone",))
    engine, _, _, _ = _engine(content, events)
    result = engine.submit(Events()).result
    assert result is not None
    listed = result["events"]
    assert len(listed) == 1
    assert listed[0]["kind"] == "market_news"
    assert listed[0]["direction"] == "glut"
    assert "factor" not in listed[0]


class _OnlyStone:
    def is_ore_unlocked(self, ore_id):
        return ore_id == "stone"

    def is_recipe_unlocked(self, recipe_id):
        return True

    def is_function_unlocked(self, name):
        return True

    def is_upgrade_unlocked(self, upgrade_id):
        return True

    def is_module_unlocked(self, name):
        return True

    def is_skin_unlocked(self, skin_id):
        return True

    def is_example_unlocked(self, example_id):
        return True


# -- overlay ----------------------------------------------------------------------


def test_world_view_renders_the_event_overlay(qapp, content):
    from minesim.core.game import Game
    from minesim.ui.world_view import WorldView

    game = Game.new()
    game.engine.world_events = _events("rich_vein")
    game.engine._active_world_events = {}
    game.engine._prime_world_events()
    view = WorldView(game)
    view.set_terrain_lighting(False, persist=False)
    view.resize(640, 480)
    view.show()
    qapp.processEvents()
    pixmap = view.grab()
    image = pixmap.toImage()
    colors = set()
    for y in range(0, image.height(), 8):
        for x in range(0, image.width(), 8):
            color = image.pixelColor(x, y)
            colors.add((color.red(), color.green(), color.blue()))
    assert len(colors) > 5
    view.close()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
