"""Offscreen tests for the lit terrain renderer (prompt 09)."""

from __future__ import annotations

import logging
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from digscript.core.content import load_content
from digscript.core.world import World, WorldGenerator
from digscript.core.world.world import Tile

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from digscript.ui.terrain_shader import (  # noqa: E402
    compute_light,
    posterize,
    render_chunk,
)
from digscript.ui.world_view import WorldView  # noqa: E402

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def content():
    return load_content()


class _FlatWorld:
    """Minimal world stub whose tiles are all empty quarry floor."""

    def __init__(self, content) -> None:
        self.content = content
        self.chunk_size = content.config.chunk_size
        self.seed = content.config.seed_default

    def tile_at(self, x: int, y: int, tick: int = 0) -> Tile:
        return Tile(ore_id=None, biome_id="quarry")


def _image_colors(image) -> set[tuple[int, int, int]]:
    colors = set()
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            colors.add((color.red(), color.green(), color.blue()))
    return colors


def _pixmap_variance(pixmap) -> int:
    image = pixmap.toImage()
    colors = set()
    for y in range(0, image.height(), 3):
        for x in range(0, image.width(), 3):
            color = image.pixelColor(x, y)
            colors.add((color.red(), color.green(), color.blue()))
    return len(colors)


def test_flat_height_field_has_uniform_lighting(monkeypatch, content) -> None:
    import digscript.ui.terrain_shader as shader

    monkeypatch.setattr(shader, "tile_height", lambda *args, **kwargs: 1.0)
    world = _FlatWorld(content)
    image = render_chunk(world, 0, 0, 0)
    assert not image.isNull()
    assert image.width() == content.config.chunk_size * content.config.art_px_per_tile
    assert len(_image_colors(image)) == 1


def test_compute_light_flat_uses_only_sun_height() -> None:
    heights = np.full((8, 8), 3.0)
    light = compute_light(heights, (-0.6, -0.7, 0.45))
    assert np.allclose(light, light[0, 0])
    assert 0.0 <= light[0, 0] <= 1.0


def test_posterization_yields_at_most_light_bands_levels() -> None:
    samples = np.linspace(0.0, 1.0, 1001)
    for bands in (2, 3, 4, 6):
        levels = np.unique(posterize(samples, bands))
        assert len(levels) <= bands


def test_render_chunk_is_bounded_by_bands(content) -> None:
    world = World(WorldGenerator(content.config.seed_default, content), content)
    image = render_chunk(world, 0, 0, 0)
    assert not image.isNull()
    assert len(_image_colors(image)) > 1


def test_render_chunk_performance(content, caplog) -> None:
    world = World(WorldGenerator(content.config.seed_default, content), content)
    render_chunk(world, 0, 0, 0)  # warm-up
    repeats = 3
    started = time.perf_counter()
    for _ in range(repeats):
        render_chunk(world, 1, 0, 0)
    elapsed_ms = (time.perf_counter() - started) * 1000.0 / repeats
    caplog.set_level(logging.INFO)
    logger.info("render_chunk rebuilt one chunk in %.2f ms", elapsed_ms)
    assert elapsed_ms < 100.0


def test_lit_and_flat_renderers_produce_non_blank_images(qapp, content) -> None:
    world = World(WorldGenerator(content.config.seed_default, content), content)
    view = WorldView(world, content=content)
    view.resize(640, 480)
    view.show()
    qapp.processEvents()
    view.set_terrain_lighting(True, persist=False)
    view.grab()
    lit = view.grab()
    assert _pixmap_variance(lit) > 5
    view.set_terrain_lighting(False, persist=False)
    flat = view.grab()
    assert _pixmap_variance(flat) > 5
    view.close()


def test_one_tile_change_invalidates_chunk_and_neighbours_only(qapp, content) -> None:
    world = World(WorldGenerator(content.config.seed_default, content), content)
    view = WorldView(world, content=content)
    view.set_terrain_lighting(True, persist=False)
    x, y = 5, 5
    size = world.chunk_size
    cx, cy = x // size, y // size
    coordinates = [(cx + dx, cy + dy) for dx in range(-2, 3) for dy in range(-2, 3)]
    before = {coord: view._version_signature(*coord) for coord in coordinates}
    assert world.mine_tile(x, y, 0) is not None
    after = {coord: view._version_signature(*coord) for coord in coordinates}
    changed = {coord for coord in coordinates if before[coord] != after[coord]}
    expected = {(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    assert changed == expected
