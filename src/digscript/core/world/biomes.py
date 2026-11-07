"""Biome regions of the infinite plane.

The plane is split into square regions of
``region_size_chunks * chunk_size`` tiles. The origin region is
centered on (0, 0). Each region deterministically picks a biome with
:func:`digscript.core.rng.weighted_choice` among the biomes whose
``min_distance`` is at most the Chebyshev distance from (0, 0) to the
region center. The region containing (0, 0) is always ``quarry``.
"""

from __future__ import annotations

from digscript.core.content import Content
from digscript.core.rng import mix64, weighted_choice
from digscript.core.schemas import Biome

__all__ = [
    "BiomeSelector",
    "biome_at",
    "biome_for_region",
    "biome_id_at",
    "region_center",
    "region_for_tile",
    "region_size_tiles",
]

# Salt so biome hashes do not correlate with ore hashes for the same
# coordinates. This is a hash constant, not a gameplay number.
_BIOME_HASH_SALT = 0xB10E5


def region_size_tiles(content: Content) -> int:
    """Return the side length of a biome region, in tiles."""
    return content.config.chunk_size * content.config.region_size_chunks


def region_for_tile(x: int, y: int, size: int) -> tuple[int, int]:
    """Return the region coordinates ``(rx, ry)`` containing ``(x, y)``.

    Region (0, 0) is centered on (0, 0): for a region size of 32 it
    covers x and y in [-16, 15].
    """
    if size <= 0:
        raise ValueError("region size must be > 0")
    half = size // 2
    return ((x + half) // size, (y + half) // size)


def region_center(rx: int, ry: int, size: int) -> tuple[int, int]:
    """Return the center tile of region ``(rx, ry)``."""
    return (rx * size, ry * size)


def _eligible_biomes(content: Content, distance: int) -> list[Biome]:
    eligible = [b for b in content.biomes.values() if b.min_distance <= distance]
    if eligible:
        return eligible
    # No biome unlocked at this distance (custom content without a
    # min_distance 0 biome): fall back to the closest biomes.
    closest = min(b.min_distance for b in content.biomes.values())
    return [b for b in content.biomes.values() if b.min_distance == closest]


def biome_for_region(rx: int, ry: int, seed: int, content: Content) -> Biome:
    """Return the biome of region ``(rx, ry)`` for a world ``seed``."""
    if not content.biomes:
        raise ValueError("content has no biomes")
    if (rx, ry) == (0, 0) and "quarry" in content.biomes:
        return content.biomes["quarry"]
    size = region_size_tiles(content)
    center_x, center_y = region_center(rx, ry, size)
    distance = max(abs(center_x), abs(center_y))
    eligible = _eligible_biomes(content, distance)
    items = [(biome.id, biome.weight) for biome in eligible]
    biome_id = weighted_choice(mix64(seed, rx, ry, _BIOME_HASH_SALT), items)
    return content.biomes[biome_id]


def biome_at(x: int, y: int, seed: int, content: Content) -> Biome:
    """Return the biome of the tile at ``(x, y)``."""
    size = region_size_tiles(content)
    rx, ry = region_for_tile(x, y, size)
    return biome_for_region(rx, ry, seed, content)


def biome_id_at(x: int, y: int, seed: int, content: Content) -> str:
    """Return the biome id of the tile at ``(x, y)``."""
    return biome_at(x, y, seed, content).id


class BiomeSelector:
    """Deterministic biome lookup for a seed and content."""

    def __init__(self, seed: int, content: Content) -> None:
        self.seed = seed
        self.content = content

    def biome_for_region(self, rx: int, ry: int) -> Biome:
        """Return the biome of region ``(rx, ry)``."""
        return biome_for_region(rx, ry, self.seed, self.content)

    def biome_at(self, x: int, y: int) -> Biome:
        """Return the biome of the tile at ``(x, y)``."""
        return biome_at(x, y, self.seed, self.content)

    def biome_id_at(self, x: int, y: int) -> str:
        """Return the biome id of the tile at ``(x, y)``."""
        return biome_id_at(x, y, self.seed, self.content)

    def region_for_tile(self, x: int, y: int) -> tuple[int, int]:
        """Return the region containing ``(x, y)``."""
        return region_for_tile(x, y, region_size_tiles(self.content))
