"""Tests for the infinite deterministic world (prompt 01)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from digscript.core.content import ContentError, load_content
from digscript.core.rng import mix64, unit, weighted_choice
from digscript.core.world import World, WorldGenerator
from digscript.core.world.biomes import biome_for_region, region_for_tile


@pytest.fixture(scope="module")
def content():
    return load_content()


@pytest.fixture()
def world(content):
    generator = WorldGenerator(content.config.seed_default, content)
    return World(generator, content)


def _write_content(tmp_path: Path, *, config=None, ores=None, biomes=None) -> Path:
    base = load_content()
    data = {
        "config.json": config if config is not None else base.config.model_dump(),
        "ores.json": ores if ores is not None else [o.model_dump() for o in base.ore_list],
        "biomes.json": biomes if biomes is not None else [b.model_dump() for b in base.biome_list],
    }
    for name, payload in data.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


# -- rng -------------------------------------------------------------------


def test_mix64_is_masked_deterministic_and_sensitive() -> None:
    assert mix64(1, 2, 3) == mix64(1, 2, 3)
    assert 0 <= mix64(1, 2, 3) < 2**64
    assert 0 <= mix64(-1, 10**6, -5) < 2**64
    assert mix64(1, 2, 3) != mix64(1, 2, 4)
    assert mix64(0) != mix64(1)
    assert mix64(-1) == mix64(2**64 - 1)


def test_unit_is_in_unit_interval() -> None:
    for value in (0, 1, 2**63, 2**64 - 1, mix64(42)):
        assert 0.0 <= unit(value) < 1.0


def test_weighted_choice_respects_weights_and_order() -> None:
    items = {"a": 1, "b": 3}
    assert weighted_choice(0, items) == "a"  # unit(0) == 0
    seen = {weighted_choice(mix64(i), items) for i in range(1000)}
    assert seen == {"a", "b"}
    with pytest.raises(ValueError):
        weighted_choice(0, {})
    with pytest.raises(ValueError):
        weighted_choice(0, {"a": 0})


# -- content -----------------------------------------------------------------


def test_load_content_values(content) -> None:
    assert content.config.seed_default == 12345
    assert content.config.chunk_size == 16
    assert content.config.region_size_chunks == 2
    assert content.config.base_half_size == 1
    assert content.config.tick_hz == 10
    assert content.get_ore("stone").regen_ticks == 300
    assert content.get_ore("coal").unlocked_by == "first_dig"
    assert content.get_ore("stone").unlocked_by is None
    assert content.get_biome("quarry").ore_weights == {"stone": 70, "coal": 20, "copper": 10}
    deep = content.get_biome("deep_vein")
    assert deep.min_distance == 40
    assert content.get_biome("crystal_caverns").min_distance == 100


def test_content_error_names_file_and_field(tmp_path: Path) -> None:
    ores = [
        {
            "id": "stone",
            "name": "Stone",
            "tier": 0,
            "hardness": "very-hard",
            "base_value": 1,
            "mine_probability": 0.95,
            "regen_ticks": 300,
            "color": "#7a7a7a",
            "unlocked_by": None,
        }
    ]
    directory = _write_content(tmp_path, ores=ores)
    with pytest.raises(ContentError) as excinfo:
        load_content(directory)
    message = str(excinfo.value)
    assert "ores.json" in message
    assert "hardness" in message


def test_content_error_for_unknown_ore_in_biome(tmp_path: Path) -> None:
    biomes = [
        {
            "id": "quarry",
            "name": "Quarry",
            "min_distance": 0,
            "weight": 10,
            "floor_color": "#000000",
            "ore_weights": {"unobtanium": 1},
        }
    ]
    directory = _write_content(tmp_path, biomes=biomes)
    with pytest.raises(ContentError) as excinfo:
        load_content(directory)
    assert "biomes.json" in str(excinfo.value)
    assert "unobtanium" in str(excinfo.value)


def test_content_error_for_invalid_json(tmp_path: Path) -> None:
    directory = _write_content(tmp_path)
    (directory / "config.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ContentError) as excinfo:
        load_content(directory)
    assert "config.json" in str(excinfo.value)


# -- generator / world --------------------------------------------------------


def test_same_seed_same_tiles_and_different_seed_differs(content) -> None:
    gen_a = WorldGenerator(123, content)
    gen_b = WorldGenerator(123, content)
    gen_c = WorldGenerator(124, content)
    coords = [(x, y) for x in range(-50, 50) for y in range(-50, 50)]
    assert [gen_a.ore_at(x, y) for x, y in coords] == [gen_b.ore_at(x, y) for x, y in coords]
    assert [gen_a.ore_at(x, y) for x, y in coords] != [gen_c.ore_at(x, y) for x, y in coords]


def test_origin_region_is_quarry_and_base_is_clear(content, world) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    size = content.config.chunk_size * content.config.region_size_chunks
    # Every tile of the origin region is quarry.
    for x in range(-size // 2, size // 2):
        for y in range(-size // 2, size // 2):
            assert generator.biome_id_at(x, y) == "quarry"
    assert biome_for_region(0, 0, 999, content).id == "quarry"
    assert region_for_tile(0, 0, size) == (0, 0)
    # Base tiles have no ore and are never minable.
    half = content.config.base_half_size
    for x in range(-half, half + 1):
        for y in range(-half, half + 1):
            tile = world.tile_at(x, y, 0)
            assert tile.is_base
            assert tile.ore_id is None
            assert generator.ore_at(x, y) is None
            assert world.mine_tile(x, y, 0) is None


def test_quarry_ore_frequencies_within_15_percent(content) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    weights = content.get_biome("quarry").ore_weights
    total_weight = sum(weights.values())
    counts: Counter[str] = Counter()
    total = 0
    # Collect >20000 quarry, non-base tiles scanning outward.
    radius = 0
    while total < 20000:
        radius += 25
        counts = Counter()
        total = 0
        for x in range(-radius, radius + 1):
            for y in range(-radius, radius + 1):
                if generator.is_base(x, y):
                    continue
                if generator.biome_id_at(x, y) != "quarry":
                    continue
                ore_id = generator.ore_at(x, y)
                assert ore_id is not None
                counts[ore_id] += 1
                total += 1
    assert total >= 20000
    for ore_id, weight in weights.items():
        expected = weight / total_weight
        observed = counts[ore_id] / total
        assert observed == pytest.approx(expected, rel=0.15), (
            f"{ore_id}: observed {observed:.3f}, expected {expected:.3f}"
        )


def test_mine_tile_depletes_and_regenerates_with_next_epoch(content, world) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    x, y = 10, 10
    original = world.tile_at(x, y, 0)
    assert original.ore_id is not None
    assert not original.depleted
    ore = content.get_ore(original.ore_id)

    mined = world.mine_tile(x, y, 100)
    assert mined == original.ore_id
    depleted = world.tile_at(x, y, 100)
    assert depleted.depleted
    assert depleted.ore_id is None
    # Still depleted just before the regen tick.
    assert world.tile_at(x, y, 100 + ore.regen_ticks - 1).depleted
    # Mining a depleted tile does nothing.
    assert world.mine_tile(x, y, 100) is None

    regen_at = 100 + ore.regen_ticks
    back = world.tile_at(x, y, regen_at)
    assert not back.depleted
    assert back.ore_id is not None
    # Re-rolled with epoch + 1.
    assert back.ore_id == generator.ore_at(x, y, epoch=1)
    assert world.delta[(x, y)] == (1, None)


def test_version_grows_on_mining(world) -> None:
    version0 = world.version
    world.mine_tile(20, 20, 0)
    assert world.version > version0


def test_to_dict_from_dict_round_trip(world) -> None:
    world.mine_tile(10, 10, 5)
    world.mine_tile(-8, 30, 7)
    data = world.to_dict()
    checksum_before = [world.tile_at(x, y, 50) for x, y in [(10, 10), (-8, 30), (3, 3), (0, 0)]]

    restored = World.from_dict(world.generator, world.content, data)
    assert restored.to_dict() == data
    assert [restored.tile_at(x, y, 50) for x, y in [(10, 10), (-8, 30), (3, 3), (0, 0)]] == (
        checksum_before
    )

    # Instance-style restore works too, and only the delta is stored.
    other = World(world.generator, world.content)
    other.from_dict(data)
    assert other.to_dict() == data
    assert set(data) == {"delta"}
    assert len(data["delta"]) == 2


def test_chunk_tiles_shape_and_consistency(world) -> None:
    chunk_size = world.content.config.chunk_size
    rows = world.chunk_tiles(0, 0, 0)
    assert len(rows) == chunk_size
    assert all(len(row) == chunk_size for row in rows)
    for dy, row in enumerate(rows):
        for dx, tile in enumerate(row):
            assert tile == world.tile_at(dx, dy, 0)
    # Negative chunk coordinates use floor division.
    rows_neg = world.chunk_tiles(-1, -1, 0)
    assert rows_neg[0][0] == world.tile_at(-chunk_size, -chunk_size, 0)


def test_cache_eviction_does_not_change_results(content) -> None:
    generator = WorldGenerator(content.config.seed_default, content)
    small = World(generator, content, cache_size=2)
    expected = {}
    for cx in range(4):
        for cy in range(4):
            expected[(cx, cy)] = small.chunk_tiles(cx, cy, 0)
    assert len(small.chunk_cache) <= 2
    # Re-reading evicted chunks gives identical tiles.
    for (cx, cy), rows in expected.items():
        assert small.chunk_tiles(cx, cy, 0) == rows
    fresh = World(generator, content)
    for (cx, cy), rows in expected.items():
        assert fresh.chunk_tiles(cx, cy, 0) == rows
    # Mining invalidates the cached chunk.
    small.mine_tile(5, 5, 0)
    assert small.chunk_tiles(0, 0, 0)[5][5].depleted
    world_after = World(generator, content)
    world_after.mine_tile(5, 5, 0)
    assert world_after.chunk_tiles(0, 0, 0)[5][5].depleted


def test_extreme_coordinates_work(world) -> None:
    for x, y in [(-5, -5), (10**6, 10**6), (-(10**6), 3), (0, -(10**6))]:
        tile = world.tile_at(x, y, 0)
        assert tile.biome_id in world.content.biomes
        assert tile.ore_id is None or tile.ore_id in world.content.ores
        chunk = world.chunk_tiles(x // 16, y // 16, 0)
        assert len(chunk) == 16
