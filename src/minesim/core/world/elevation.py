"""Deterministic terrain elevation (pure Python, no numpy).

The height field is two octaves of value noise built on
:func:`~minesim.core.rng.mix64`: integer lattice corners are hashed
to a value in ``[0, 1]`` and smoothly interpolated with the
smoothstep curve. The first octave varies over
``terrain_noise_scale`` tiles, the second over half of that, and the
two are averaged. The result is a pure function of the seed and the
tile coordinates, identical on every OS.

The renderer turns these heights into a lit 2.5D look; gameplay never
reads them.
"""

from __future__ import annotations

import math
from typing import Any

from minesim.core.rng import mix64, unit

__all__ = ["BASE_TILE_HEIGHT", "elevation_at", "tile_height", "value_noise"]

# Base tiles are flat and slightly raised; this is a visual constant,
# not a gameplay number.
BASE_TILE_HEIGHT = 0.5

# Fallback matching the packaged content; callers pass the configured
# terrain_noise_scale whenever it is available.
DEFAULT_TERRAIN_NOISE_SCALE = 12.0

# Hash salt so elevation noise does not correlate with ore or biome
# hashes for the same coordinates.
_ELEVATION_SALT = 0xE1E7A710

_OCTAVE_AMPLITUDES = (1.0, 0.5)


def _smoothstep(t: float) -> float:
    """Smoothstep easing for the unit interval."""
    return t * t * (3.0 - 2.0 * t)


def _corner(
    seed: int,
    octave: int,
    ix: int,
    iy: int,
    cache: dict[tuple[int, int, int], float] | None = None,
) -> float:
    """Hash one lattice corner to a value in ``[0, 1)``.

    A caller rendering many nearby tiles may pass ``cache`` to reuse
    corner hashes within one pass.
    """
    if cache is None:
        return unit(mix64(seed, octave, ix, iy, _ELEVATION_SALT))
    key = (octave, ix, iy)
    value = cache.get(key)
    if value is None:
        value = unit(mix64(seed, octave, ix, iy, _ELEVATION_SALT))
        cache[key] = value
    return value


def value_noise(
    seed: int,
    x: float,
    y: float,
    scale: float,
    octave: int = 0,
    *,
    cache: dict[tuple[int, int, int], float] | None = None,
) -> float:
    """Return one octave of smooth value noise in ``[0, 1]``.

    ``scale`` is the distance, in tiles, between lattice corners.
    """
    if scale <= 0:
        return 0.5
    fx = float(x) / scale
    fy = float(y) / scale
    ix = math.floor(fx)
    iy = math.floor(fy)
    tx = _smoothstep(fx - ix)
    ty = _smoothstep(fy - iy)
    n00 = _corner(seed, octave, ix, iy, cache)
    n10 = _corner(seed, octave, ix + 1, iy, cache)
    n01 = _corner(seed, octave, ix, iy + 1, cache)
    n11 = _corner(seed, octave, ix + 1, iy + 1, cache)
    top = n00 + (n10 - n00) * tx
    bottom = n01 + (n11 - n01) * tx
    return top + (bottom - top) * ty


def elevation_at(
    seed: int,
    x: int,
    y: int,
    *,
    noise_scale: float = DEFAULT_TERRAIN_NOISE_SCALE,
    cache: dict[tuple[int, int, int], float] | None = None,
) -> float:
    """Return the terrain elevation at tile ``(x, y)`` in ``[0, 1]``."""
    total = 0.0
    amplitude_sum = 0.0
    scale = float(noise_scale)
    for octave, amplitude in enumerate(_OCTAVE_AMPLITUDES):
        total += amplitude * value_noise(seed, x, y, scale, octave, cache=cache)
        amplitude_sum += amplitude
        scale *= 0.5
    return total / amplitude_sum


def tile_height(
    world: Any,
    x: int,
    y: int,
    tick: int = 0,
    *,
    tile: Any | None = None,
    noise_cache: dict[tuple[int, int, int], float] | None = None,
) -> float:
    """Return the render height of tile ``(x, y)``.

    Base tiles use :data:`BASE_TILE_HEIGHT`. Other tiles combine the
    biome-scaled elevation with a bump for hard ores and a pit for
    depleted tiles. Callers that already resolved the tile may pass it
    in to avoid a second lookup.
    """
    content = world.content
    config = content.config
    if tile is None:
        tile = world.tile_at(x, y, tick)
    if tile.is_base:
        return BASE_TILE_HEIGHT
    biome = content.get_biome(tile.biome_id)
    height = (
        elevation_at(
            world.seed,
            x,
            y,
            noise_scale=float(config.terrain_noise_scale),
            cache=noise_cache,
        )
        * float(biome.relief)
        * float(config.height_scale)
    )
    if tile.depleted:
        height -= float(config.pit_depth)
    elif tile.ore_id is not None:
        ore = content.get_ore(tile.ore_id)
        height += float(config.ore_bump_per_hardness) * float(ore.hardness)
    return height
