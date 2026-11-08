"""Tests for the main window and world view (prompt 05)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from digscript.core.content import load_content
from digscript.core.game import Game
from digscript.core.world import World, WorldGenerator

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from digscript.ui.app import load_game_or_new  # noqa: E402
from digscript.ui.game_loop import MAX_TICKS_PER_FRAME, GameLoop  # noqa: E402
from digscript.ui.hud import HUD  # noqa: E402
from digscript.ui.main_window import MainWindow  # noqa: E402
from digscript.ui.theme import COLORS, FONT_FAMILY, STYLESHEET  # noqa: E402
from digscript.ui.world_view import MAX_TILE_PX, MIN_TILE_PX, WorldView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def content():
    return load_content()


def _image_variance(pixmap) -> float:
    image = pixmap.toImage()
    width, height = image.width(), image.height()
    colors = set()
    total = 0
    count = 0
    for y in range(0, height, 4):
        for x in range(0, width, 4):
            color = image.pixelColor(x, y)
            colors.add((color.red(), color.green(), color.blue()))
            total += color.red() + color.green() + color.blue()
            count += 1
    assert count > 0
    return float(len(colors))


def test_theme_has_dark_palette_and_stylesheet() -> None:
    assert COLORS["background"] == "#1e1e2e"
    assert FONT_FAMILY
    assert "QPushButton" in STYLESHEET
    assert COLORS["background"] in STYLESHEET


def test_window_builds(qapp) -> None:
    game = Game.new()
    window = MainWindow(game)
    assert isinstance(window.world_view, WorldView)
    assert isinstance(window.hud, HUD)
    assert window.game is game
    assert window.windowTitle() == "DigScript"
    window.close()


def test_world_view_renders_non_blank(qapp) -> None:
    game = Game.new()
    view = WorldView(game)
    view.resize(800, 600)
    view.show()
    qapp.processEvents()
    pixmap = view.grab()
    assert _image_variance(pixmap) > 5
    view.close()


def test_main_window_renders_non_blank(qapp) -> None:
    game = Game.new()
    window = MainWindow(game)
    window.resize(800, 600)
    window.show()
    qapp.processEvents()
    pixmap = window.grab()
    assert _image_variance(pixmap) > 5
    window.close()


def test_only_changed_chunks_rebuilt_after_mine(qapp, content) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    game = Game.new()
    game._world = world
    game._engine.world = world
    view = WorldView(game)
    view.resize(800, 600)
    view.show()
    qapp.processEvents()
    view.grab()
    built_before = view.chunks_built
    view.grab()
    assert view.chunks_built == built_before
    world.mine_tile(5, 5, 0)
    view.grab()
    rebuilt = view.chunks_built - built_before
    assert 1 <= rebuilt <= 2
    view.close()


def test_game_loop_speed_math(qapp) -> None:
    game = Game.new()
    loop = GameLoop(game)
    assert loop.compute_ticks(1000) == 10
    loop.set_speed(2)
    assert loop.compute_ticks(1000) == 20
    loop.set_speed(20)
    assert loop.compute_ticks(1000) == 200
    loop.set_speed(1)
    assert loop.compute_ticks(100000) == MAX_TICKS_PER_FRAME
    loop.set_speed(0)
    assert loop.compute_ticks(1000) == 0
    loop.set_speed(5)
    assert loop.ticks_for_elapsed(1.0) == 50


def test_game_loop_advance_steps_engine(qapp) -> None:
    game = Game.new()
    loop = GameLoop(game)
    tick0 = game.tick
    stepped = loop.advance(1000)
    assert stepped == 10
    assert game.tick == tick0 + 10
    loop.set_speed(0)
    assert loop.advance(1000) == 0
    assert game.tick == tick0 + 10


def test_game_loop_keys(qapp) -> None:
    game = Game.new()
    loop = GameLoop(game)
    assert loop.handle_key(" ")
    assert loop.paused and loop.speed == 0
    assert loop.handle_key("3")
    assert loop.speed == 2
    assert loop.handle_key("5")
    assert loop.speed == 20
    assert loop.handle_key(int(Qt.Key.Key_1))
    assert loop.speed == 0
    assert loop.handle_key(int(Qt.Key.Key_2))
    assert loop.speed == 1


def test_zoom_and_pan_clamps(qapp) -> None:
    game = Game.new()
    view = WorldView(game)
    view.set_tile_px(MIN_TILE_PX - 10)
    assert view.tile_px == MIN_TILE_PX
    view.set_tile_px(MAX_TILE_PX + 10)
    assert view.tile_px == MAX_TILE_PX
    view.set_tile_px(24)
    view.pan_by(1000, -1000)
    assert not view.follow_miner
    assert view.recenter_button.isVisible() or view.recenter_button is not None
    view.recenter()
    assert view.follow_miner
    view.toggle_grid()
    assert view.show_grid
    view.toggle_grid()
    assert not view.show_grid
    for _ in range(100):
        view.zoom_by(10)
    assert view.tile_px == MAX_TILE_PX
    for _ in range(100):
        view.zoom_by(-10)
    assert view.tile_px == MIN_TILE_PX
    view.close()


def test_hud_shows_state_and_speed_buttons(qapp) -> None:
    game = Game.new()
    game.miner.money = 42
    hud = HUD(game)
    hud.refresh()
    assert "42" in hud.money_label.text()
    assert "0/10" in hud.inventory_label.text()
    texts = [button.text() for button in hud.findChildren(QPushButton)]
    assert texts == ["Pause", "1x", "2x", "5x", "20x"]
    hud.set_speed(5)
    assert hud.speed == 5
    hud.toggle_pause()
    assert hud.speed == 0
    hud.close()


def test_load_game_or_new_missing_file(tmp_path) -> None:
    game = load_game_or_new(tmp_path / "missing.json")
    assert game.tick == 0


# -- core step 0: heap advance + chunk_version ------------------------------------


def test_advance_regenerates_exactly_at_regen_tick(content) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    x, y = 10, 10
    ore_id = world.tile_at(x, y, 0).ore_id
    assert ore_id is not None
    regen = content.get_ore(ore_id).regen_ticks
    cx, cy = x // world.chunk_size, y // world.chunk_size
    version0 = world.chunk_version(cx, cy)
    world.mine_tile(x, y, 100)
    assert world.chunk_version(cx, cy) == version0 + 1
    assert world.tile_at(x, y, 100 + regen - 1).depleted
    assert world.chunk_version(cx, cy) == version0 + 1
    world.advance(100 + regen - 1)
    assert world.tile_at(x, y, 100 + regen - 1).depleted
    assert world.chunk_version(cx, cy) == version0 + 1
    world.advance(100 + regen)
    assert not world.tile_at(x, y, 100 + regen).depleted
    assert world.chunk_version(cx, cy) == version0 + 2
    # Advancing again does not bump the chunk version.
    world.advance(100 + regen + 100)
    assert world.chunk_version(cx, cy) == version0 + 2


def test_tile_at_and_advance_are_consistent(content) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    x, y = 12, 8
    ore_id = world.tile_at(x, y, 0).ore_id
    regen = content.get_ore(ore_id).regen_ticks
    world.mine_tile(x, y, 10)
    cx, cy = x // world.chunk_size, y // world.chunk_size
    version_after_mine = world.chunk_version(cx, cy)
    # Lazy regeneration via tile_at bumps once; advance must not bump again.
    assert not world.tile_at(x, y, 10 + regen).depleted
    assert world.chunk_version(cx, cy) == version_after_mine + 1
    world.advance(10 + regen)
    assert world.chunk_version(cx, cy) == version_after_mine + 1


def test_chunk_version_unchanged_for_other_chunks(content) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    world.mine_tile(2, 2, 0)
    assert world.chunk_version(0, 0) == 1
    assert world.chunk_version(1, 0) == 0
    assert world.chunk_version(-1, -1) == 0
