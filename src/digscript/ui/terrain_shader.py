"""Lit 2.5D terrain renderer.

Builds a small height field for one world chunk (plus a one-tile
margin taken from the neighbouring chunks), upsamples it bilinearly
to art resolution, derives surface normals from finite differences
and shades the result with a posterized sun term. The output is an
art-resolution :class:`QImage`; the world view scales it with
nearest-neighbour filtering so the pixels stay crisp.

numpy is used only here in the UI layer; ``core/`` stays pure Python.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import numpy as np
from PySide6.QtGui import QColor, QImage

from digscript.core.rng import mix64
from digscript.core.world.elevation import tile_height

__all__ = ["compute_light", "normalize_sun", "posterize", "render_chunk"]

logger = logging.getLogger(__name__)

_DEFAULT_SUN = (-0.6, -0.7, 0.45)
_DEFAULT_FLOOR = (74.0, 74.0, 66.0)
_DEFAULT_SHADOW = (43.0, 42.0, 56.0)

# Artistic slope exaggeration so the posterized light bands are
# visible at small art resolutions. Multiplied by art_px_per_tile so
# the per-tile slope is independent of the rendering resolution.
_SLOPE_STRENGTH = 8.0

_UNLOCKED_ORE_RATIO = 0.32
_LOCKED_ORE_RATIO = 0.22
_UNLOCKED_SPECKLE_SALT = 0x5EED0E
_LOCKED_SPECKLE_SALT = 0x10CCED


def _config_value(config: Any, name: str, default: Any) -> Any:
    if config is None:
        return default
    value = getattr(config, name, default)
    return default if value is None else value


def normalize_sun(sun_dir: Any) -> np.ndarray:
    """Return ``sun_dir`` as a unit-length 3-vector."""
    try:
        values = [float(component) for component in sun_dir][:3]
    except (TypeError, ValueError):
        values = list(_DEFAULT_SUN)
    if len(values) != 3:
        values = list(_DEFAULT_SUN)
    vector = np.asarray(values, dtype=np.float64)
    length = float(np.linalg.norm(vector))
    if length <= 0.0:
        return np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
    return vector / length


def compute_light(height: np.ndarray, sun_dir: Any, *, slope: float = 1.0) -> np.ndarray:
    """Return the un-posterized lighting in ``[0, 1]`` for a height field."""
    heights = np.asarray(height, dtype=np.float64)
    if heights.ndim != 2 or heights.size == 0:
        return np.zeros(heights.shape, dtype=np.float64)
    gradient_y, gradient_x = np.gradient(heights)
    normal_x = -gradient_x * float(slope)
    normal_y = -gradient_y * float(slope)
    normal_z = np.ones_like(heights)
    length = np.sqrt(normal_x * normal_x + normal_y * normal_y + normal_z * normal_z)
    length[length == 0.0] = 1.0
    sun = normalize_sun(sun_dir)
    light = (normal_x * sun[0] + normal_y * sun[1] + normal_z * sun[2]) / length
    return np.clip(light, 0.0, 1.0)


def posterize(light: np.ndarray, bands: int) -> np.ndarray:
    """Quantize ``light`` into at most ``bands`` distinct levels."""
    values = np.asarray(light, dtype=np.float64)
    count = max(1, int(bands))
    if count == 1:
        return np.zeros_like(values)
    quantized = np.round(np.clip(values, 0.0, 1.0) * count) / count
    return np.clip(quantized, 0.0, (count - 1) / count)


def _rgb(color: str, fallback: tuple[float, float, float]) -> np.ndarray:
    qcolor = QColor(str(color))
    if not qcolor.isValid():
        return np.asarray(fallback, dtype=np.float64)
    return np.asarray((qcolor.red(), qcolor.green(), qcolor.blue()), dtype=np.float64)


def _bilinear_upsample(heights: np.ndarray, side: int, art: int) -> np.ndarray:
    """Bilinearly upsample the ``(side + 2)`` height grid to art resolution."""
    out_side = side * art
    # Art pixel centres in tile units, offset by the one-tile margin.
    coords = (np.arange(out_side, dtype=np.float64) + 0.5) / float(art) + 1.0
    lower = np.floor(coords).astype(np.int64)
    lower = np.clip(lower, 0, heights.shape[0] - 2)
    upper = lower + 1
    fraction = coords - lower
    fraction_x = fraction[None, :]
    fraction_y = fraction[:, None]
    h00 = heights[np.ix_(lower, lower)]
    h10 = heights[np.ix_(lower, upper)]
    h01 = heights[np.ix_(upper, lower)]
    h11 = heights[np.ix_(upper, upper)]
    return (
        h00 * (1.0 - fraction_y) * (1.0 - fraction_x)
        + h10 * (1.0 - fraction_y) * fraction_x
        + h01 * fraction_y * (1.0 - fraction_x)
        + h11 * fraction_y * fraction_x
    )


def _ore_mask(seed: int, x: int, y: int, art: int, ratio: float, salt: int) -> np.ndarray:
    """Return a compact deterministic ore speckle for one tile.

    The blob is built from the art pixels nearest to a centre picked
    with ``mix64``, so ores read as small props instead of noise while
    still covering about ``ratio`` of the tile.
    """
    h = mix64(seed, x, y, salt)
    centre_x = ((h & 0xFFFF) / 65536.0) * art
    centre_y = (((h >> 16) & 0xFFFF) / 65536.0) * art
    target = max(1, int(round(art * art * ratio)))
    scored: list[tuple[float, int, int]] = []
    for py in range(art):
        for px in range(art):
            distance = (px + 0.5 - centre_x) ** 2 + (py + 0.5 - centre_y) ** 2
            scored.append((distance, py, px))
    scored.sort()
    mask = np.zeros((art, art), dtype=bool)
    for _distance, py, px in scored[:target]:
        mask[py, px] = True
    return mask


def render_chunk(
    world: Any,
    cx: int,
    cy: int,
    tick: int = 0,
    *,
    content: Any | None = None,
    art_px_per_tile: int | None = None,
    is_locked: Callable[[str], bool] | None = None,
) -> QImage:
    """Render chunk ``(cx, cy)`` into an art-resolution :class:`QImage`."""
    started = time.perf_counter()
    content = content if content is not None else getattr(world, "content", None)
    config = getattr(content, "config", None)
    art = int(art_px_per_tile or _config_value(config, "art_px_per_tile", 4))
    art = max(1, art)
    side = int(getattr(world, "chunk_size", None) or _config_value(config, "chunk_size", 16))
    bands = int(_config_value(config, "light_bands", 4))
    ambient = float(_config_value(config, "ambient", 0.35))
    sun = _config_value(config, "sun_dir", _DEFAULT_SUN)
    seed = int(getattr(world, "seed", 0) or 0)
    x0, y0 = int(cx) * side, int(cy) * side
    grid = side + 2

    heights = np.empty((grid, grid), dtype=np.float64)
    tile_grid: list[list[Any]] = [[None for _ in range(grid)] for _ in range(grid)]
    noise_cache: dict[tuple[int, int, int], float] = {}
    for gy in range(-1, side + 1):
        for gx in range(-1, side + 1):
            x, y = x0 + gx, y0 + gy
            tile = world.tile_at(x, y, tick)
            tile_grid[gy + 1][gx + 1] = tile
            heights[gy + 1, gx + 1] = tile_height(
                world, x, y, tick, tile=tile, noise_cache=noise_cache
            )
    tiles = [[tile_grid[gy + 1][gx + 1] for gx in range(side)] for gy in range(side)]

    rgb_cache: dict[tuple[str, tuple[float, float, float]], np.ndarray] = {}

    def cached_rgb(color: str, fallback: tuple[float, float, float]) -> np.ndarray:
        key = (str(color), fallback)
        cached = rgb_cache.get(key)
        if cached is None:
            cached = _rgb(color, fallback)
            rgb_cache[key] = cached
        return cached

    base_tiles = np.empty((side, side, 3), dtype=np.float64)
    shadow_tiles = np.empty((side, side, 3), dtype=np.float64)
    speckles: list[tuple[int, int, np.ndarray, bool]] = []

    for gy in range(side):
        for gx in range(side):
            tile = tiles[gy][gx]
            floor = _DEFAULT_FLOOR
            shadow = _DEFAULT_SHADOW
            try:
                biome = content.get_biome(tile.biome_id)
            except (AttributeError, KeyError):
                biome = None
            if biome is not None:
                floor = cached_rgb(biome.floor_color, _DEFAULT_FLOOR)
                if getattr(biome, "shadow_color", ""):
                    shadow = cached_rgb(biome.shadow_color, _DEFAULT_SHADOW)
                else:
                    shadow = np.asarray(
                        (floor[0] * 0.5, floor[1] * 0.5, floor[2] * 0.6),
                        dtype=np.float64,
                    )
            if tile.depleted:
                floor = floor * 0.7
                shadow = shadow * 0.6
            base_tiles[gy, gx] = floor
            shadow_tiles[gy, gx] = shadow
            if tile.ore_id is not None:
                ore_color = _DEFAULT_FLOOR
                try:
                    ore_color = cached_rgb(content.get_ore(tile.ore_id).color, _DEFAULT_FLOOR)
                except (AttributeError, KeyError):
                    pass
                locked = False
                if is_locked is not None:
                    try:
                        locked = bool(is_locked(tile.ore_id))
                    except Exception:
                        locked = False
                if locked:
                    ore_color = ore_color * 0.35 + shadow * 0.65
                else:
                    ore_color = ore_color * 0.6 + floor * 0.4
                speckles.append((gy, gx, ore_color, locked))

    base_image = np.repeat(np.repeat(base_tiles, art, axis=0), art, axis=1).astype(np.float64)
    shadow_image = np.repeat(np.repeat(shadow_tiles, art, axis=0), art, axis=1)

    for gy, gx, ore_color, locked in speckles:
        ratio = _LOCKED_ORE_RATIO if locked else _UNLOCKED_ORE_RATIO
        salt = _LOCKED_SPECKLE_SALT if locked else _UNLOCKED_SPECKLE_SALT
        mask = _ore_mask(seed, x0 + gx, y0 + gy, art, ratio, salt)
        tile_y = gy * art
        tile_x = gx * art
        base_image[tile_y : tile_y + art, tile_x : tile_x + art][mask] = ore_color
        if not locked and art >= 6:
            outline = np.zeros_like(mask)
            outline[1:, :] |= mask[:-1, :]
            outline[:-1, :] |= mask[1:, :]
            outline[:, 1:] |= mask[:, :-1]
            outline[:, :-1] |= mask[:, 1:]
            outline &= ~mask
            dark = ore_color * 0.35
            tile = base_image[tile_y : tile_y + art, tile_x : tile_x + art]
            tile[outline] = dark

    upsampled = _bilinear_upsample(heights, side, art)
    light = compute_light(upsampled, sun, slope=art * _SLOPE_STRENGTH)
    levels = posterize(light, bands)
    factor = ambient + (1.0 - ambient) * levels
    shaded = shadow_image + (base_image - shadow_image) * factor[:, :, None]
    pixels = np.ascontiguousarray(np.clip(shaded, 0.0, 255.0).round().astype(np.uint8))

    out_side = side * art
    image = QImage(
        pixels.data,
        out_side,
        out_side,
        3 * out_side,
        QImage.Format.Format_RGB888,
    )
    # QImage does not own the numpy buffer, so copy before returning.
    image = image.copy()
    logger.debug(
        "render_chunk(%d,%d) took %.2f ms",
        cx,
        cy,
        (time.perf_counter() - started) * 1000.0,
    )
    return image
