"""Tests for the deterministic terrain elevation field (prompt 09)."""

from __future__ import annotations

import pytest

from minesim.core.content import load_content
from minesim.core.world import World, WorldGenerator
from minesim.core.world.elevation import tile_height


@pytest.fixture(scope="module")
def content():
    return load_content()


@pytest.fixture()
def world(content):
    return World(WorldGenerator(content.config.seed_default, content), content)


def test_elevation_is_deterministic_and_in_range() -> None:
    from minesim.core.world.elevation import elevation_at

    coordinates = [(0, 0), (1, 0), (-7, 13), (999, -999), (-5000, 5000)]
    for seed in (0, 1, 12345, 2**40):
        for x, y in coordinates:
            first = elevation_at(seed, x, y)
            assert 0.0 <= first <= 1.0
            assert first == elevation_at(seed, x, y)


def test_elevation_changes_with_seed_and_position() -> None:
    from minesim.core.world.elevation import elevation_at

    assert elevation_at(1, 0, 0) != elevation_at(2, 0, 0)
    assert elevation_at(1, 0, 0) != elevation_at(1, 10, 10)


def test_elevation_is_continuous_between_neighbours() -> None:
    from minesim.core.world.elevation import elevation_at

    for seed in (0, 12345):
        for x in range(-30, 30):
            for y in range(-10, 10):
                dx = abs(elevation_at(seed, x + 1, y) - elevation_at(seed, x, y))
                dy = abs(elevation_at(seed, x, y + 1) - elevation_at(seed, x, y))
                assert dx < 0.2
                assert dy < 0.2


def _find_ore_tile(world) -> tuple[int, int]:
    for y in range(-4, 20):
        for x in range(-4, 20):
            if world.tile_at(x, y, 0).ore_id is not None:
                return (x, y)
    raise AssertionError("no ore tile found near the origin")


def test_depleted_tile_is_lower_than_full_tile(world) -> None:
    x, y = _find_ore_tile(world)
    full_height = tile_height(world, x, y, 0)
    assert world.mine_tile(x, y, 0) is not None
    assert tile_height(world, x, y, 0) < full_height


def test_base_tiles_use_a_constant_height(world) -> None:
    heights = {tile_height(world, x, y, 0) for x in (-1, 0, 1) for y in (-1, 0, 1)}
    assert len(heights) == 1
