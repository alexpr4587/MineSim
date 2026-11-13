"""Pixel-art sprites for the miner and the base building.

Sprites are data: 16x16 (miner) and 48x48 (base) text grids where every
character is a palette role. :class:`SpriteBook` validates those grids,
swaps in a skin palette, scales the result to the current tile size with
nearest-neighbour filtering and caches the pixmaps.

A skin may also provide ``assets/skins/<id>.png``: a 4x4 sheet of 16x16
frames (rows down, up, left, right; columns walk0, walk1, mine0, mine1).
When the file exists it replaces the generated miner frames for that skin.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap

from minesim.core.schemas import ContentError

__all__ = [
    "ANIMATIONS",
    "BASE_ROLES",
    "BASE_SIZE",
    "DIRECTIONS",
    "MINER_ROLES",
    "MINER_SIZE",
    "SpriteBook",
    "default_assets_dir",
]

MINER_SIZE = 16
BASE_SIZE = 48
DIRECTIONS = ("down", "up", "left", "right")
ANIMATIONS = ("walk0", "walk1", "mine0", "mine1")
MINER_ROLES = frozenset("bavdms")
BASE_ROLES = MINER_ROLES | frozenset("rw")
ALL_ROLES = BASE_ROLES


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_mapping(value: Any) -> Any:
    """Convert a pydantic model to a plain mapping if needed."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="python")
        except Exception:
            pass
    return value


def default_assets_dir() -> Path:
    """Return the default ``assets`` directory (override with MINESIM_ASSETS_DIR)."""
    override = os.environ.get("MINESIM_ASSETS_DIR")
    if override:
        return Path(override)
    root = Path(__file__).resolve().parents[3]
    if getattr(sys, "frozen", False):
        bundled = Path(getattr(sys, "_MEIPASS", root)) / "assets"
        if bundled.is_dir():
            return bundled
    return root / "assets"


class SpriteBook:
    """Builds and caches skin-coloured sprite pixmaps."""

    def __init__(
        self,
        content: Any = None,
        *,
        sprites: Any = None,
        skins: Any = None,
        asset_dir: str | Path | None = None,
    ) -> None:
        self.content = content
        if sprites is None:
            sprites = _get(content, "sprites")
        if skins is None:
            skins = _get(content, "skins")
        self.sprites: dict[str, Any] = _as_mapping(sprites) or {}
        raw_skins = _as_mapping(skins) or {}
        if isinstance(raw_skins, list):
            raw_skins = {str(_get(skin, "id", "")): skin for skin in raw_skins if _get(skin, "id")}
        self.skins: dict[str, Any] = dict(raw_skins)
        self.asset_dir = Path(asset_dir) if asset_dir is not None else default_assets_dir()
        self._cache: dict[tuple[Any, ...], QPixmap] = {}
        self._base_cache: dict[tuple[Any, ...], QPixmap] = {}
        self._sheet_cache: dict[str, QPixmap] = {}
        self.validate()

    # -- validation ----------------------------------------------------------

    def validate(self) -> None:
        """Validate the miner and base grids, raising ContentError on errors."""
        miner = self.sprites.get("miner")
        if not isinstance(miner, dict):
            raise ContentError("sprites.json: $.miner: expected an object of directions")
        for direction in DIRECTIONS:
            frames = miner.get(direction)
            if not isinstance(frames, dict):
                raise ContentError(f"sprites.json: $.miner.{direction}: missing frame set")
            for animation in ANIMATIONS:
                self._validate_grid(
                    frames.get(animation),
                    MINER_SIZE,
                    MINER_ROLES,
                    f"$.miner.{direction}.{animation}",
                )
        self._validate_grid(self.sprites.get("base"), BASE_SIZE, BASE_ROLES, "$.base")
        for skin_id, skin in self.skins.items():
            self._palette(skin_id, skin)

    def _validate_grid(self, grid: Any, size: int, roles: frozenset[str], path: str) -> None:
        if not isinstance(grid, (list, tuple)) or len(grid) != size:
            raise ContentError(f"sprites.json: {path}: expected {size} rows of {size} characters")
        for row_index, row in enumerate(grid):
            if not isinstance(row, str) or len(row) != size:
                raise ContentError(f"sprites.json: {path}.{row_index}: expected {size} characters")
            for column, role in enumerate(row):
                if role != "." and role not in roles:
                    raise ContentError(
                        f"sprites.json: {path}.{row_index}.{column}: unknown palette role {role!r}"
                    )

    def _palette(self, skin_id: str, skin: Any = None) -> dict[str, str]:
        if skin is None:
            skin = self.skins.get(str(skin_id))
        if skin is None:
            raise ContentError(f"skins.json: $.id: unknown skin id '{skin_id}'")
        palette = _as_mapping(_get(skin, "palette")) or {}
        if not isinstance(palette, dict):
            raise ContentError(f"skins.json: $.{skin_id}.palette: expected an object")
        for role in sorted(ALL_ROLES):
            color = palette.get(role)
            if color is None:
                raise ContentError(f"skins.json: $.{skin_id}.palette.{role}: missing palette role")
            if not QColor(str(color)).isValid():
                raise ContentError(
                    f"skins.json: $.{skin_id}.palette.{role}: invalid color {color!r}"
                )
        return {str(role): str(color) for role, color in palette.items()}

    # -- public helpers ------------------------------------------------------

    @property
    def skin_ids(self) -> list[str]:
        """All skin ids in file order."""
        return list(self.skins)

    def skin(self, skin_id: str) -> Any:
        """Return the raw skin entry."""
        return self.skins[str(skin_id)]

    def has_png_override(self, skin_id: str) -> bool:
        """Return True when the skin has an ``assets/skins/<id>.png`` sheet."""
        return self._sheet_path(skin_id).is_file()

    def _sheet_path(self, skin_id: str) -> Path:
        return self.asset_dir / "skins" / f"{skin_id}.png"

    # -- pixmaps -------------------------------------------------------------

    def miner_pixmap(
        self,
        skin_id: str,
        direction: str,
        animation: str,
        frame: int,
        tile_px: int,
    ) -> QPixmap:
        """Return the miner pixmap for one skin/direction/animation frame."""
        direction = str(direction).lower()
        if direction not in DIRECTIONS:
            raise ValueError(f"unknown sprite direction: {direction!r}")
        animation = str(animation).lower()
        if animation in ANIMATIONS:
            animation, frame = animation[:-1], int(animation[-1])
        if animation not in ("walk", "mine"):
            raise ValueError(f"unknown animation: {animation!r}")
        frame = int(frame) % 2
        tile_px = max(1, int(tile_px))
        key = (str(skin_id), direction, animation, frame, tile_px)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        frame_name = f"{animation}{frame}"
        if self.has_png_override(skin_id):
            pixmap = self._png_miner_frame(skin_id, direction, frame_name, tile_px)
        else:
            grid = self.sprites["miner"][direction][frame_name]
            pixmap = self._render_grid(grid, self._palette(skin_id), MINER_SIZE, tile_px)
        self._cache[key] = pixmap
        return pixmap

    def base_pixmap(self, skin_id: str, tile_px: int, span: int = 3) -> QPixmap:
        """Return the base building pixmap covering ``span`` tiles."""
        tile_px = max(1, int(tile_px))
        span = max(1, int(span))
        key = (str(skin_id), "base", span, tile_px)
        cached = self._base_cache.get(key)
        if cached is not None:
            return cached
        grid = self.sprites["base"]
        size = tile_px * span
        pixmap = self._render_grid(grid, self._palette(skin_id), BASE_SIZE, size)
        self._base_cache[key] = pixmap
        return pixmap

    def clear_cache(self) -> None:
        """Drop all cached pixmaps."""
        self._cache.clear()
        self._base_cache.clear()
        self._sheet_cache.clear()

    # -- rendering -----------------------------------------------------------

    def _render_grid(
        self,
        grid: list[str],
        palette: dict[str, str],
        source_size: int,
        target_px: int,
    ) -> QPixmap:
        image = QImage(source_size, source_size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        for y, row in enumerate(grid):
            for x, role in enumerate(row):
                if role == ".":
                    continue
                color = QColor(palette[role])
                image.setPixelColor(x, y, color)
        pixmap = QPixmap.fromImage(image)
        return pixmap.scaled(
            target_px,
            target_px,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

    def _png_miner_frame(
        self, skin_id: str, direction: str, frame_name: str, tile_px: int
    ) -> QPixmap:
        sheet = self._sheet_cache.get(str(skin_id))
        if sheet is None:
            path = self._sheet_path(skin_id)
            sheet = QPixmap(str(path))
            if sheet.isNull():
                raise ContentError(f"assets/skins/{skin_id}.png: could not load sprite sheet")
            if sheet.width() < MINER_SIZE * 4 or sheet.height() < MINER_SIZE * 4:
                raise ContentError(
                    f"assets/skins/{skin_id}.png: expected a 4x4 sheet of "
                    f"{MINER_SIZE}x{MINER_SIZE} frames"
                )
            self._sheet_cache[str(skin_id)] = sheet
        row = DIRECTIONS.index(direction)
        column = ANIMATIONS.index(frame_name)
        cell = sheet.copy(column * MINER_SIZE, row * MINER_SIZE, MINER_SIZE, MINER_SIZE)
        return cell.scaled(
            tile_px,
            tile_px,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
