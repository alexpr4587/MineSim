"""Deterministic tile generation.

The generated layer is a pure function of (seed, x, y, epoch): it is
computed on demand and never stored. All randomness goes through
:mod:`minesim.core.rng`, so the same seed always yields the same
world on every OS and Python version.
"""

from __future__ import annotations

from minesim.core.content import Content
from minesim.core.rng import mix64, weighted_choice
from minesim.core.schemas import Biome
from minesim.core.world.biomes import BiomeSelector

__all__ = ["WorldGenerator"]


class WorldGenerator:
    """Generates ore ids for arbitrary coordinates and epochs."""

    def __init__(self, seed: int, content: Content) -> None:
        self.seed = seed
        self.content = content
        self._biomes = BiomeSelector(seed, content)

    def is_base(self, x: int, y: int, layer: int = 0) -> bool:
        """Return True for base/station tiles (no ore, never minable).

        Layer 0 has the surface base: the square of tiles within
        ``base_half_size`` of (0, 0) in Chebyshev distance. Every other
        layer has a station of ``station_half_size`` instead.
        """
        config = self.content.config
        if layer == 0:
            half = config.base_half_size
        else:
            half = config.station_half_size
        return max(abs(x), abs(y)) <= half

    def is_station(self, x: int, y: int, layer: int = 0) -> bool:
        """Return True on a shaft station (the surface base or a station)."""
        return self.is_base(x, y, layer)

    def biome_at(self, x: int, y: int, layer: int = 0) -> Biome:
        """Return the biome of the tile at ``(x, y)`` on ``layer``."""
        return self._biomes.biome_at(x, y, layer)

    def biome_id_at(self, x: int, y: int, layer: int = 0) -> str:
        """Return the biome id of the tile at ``(x, y)`` on ``layer``."""
        return self._biomes.biome_id_at(x, y, layer)

    def _ore_hash(self, x: int, y: int, epoch: int, layer: int) -> int:
        """Hash a tile, mixing the layer only for underground layers."""
        if layer == 0:
            return mix64(self.seed, x, y, epoch)
        return mix64(self.seed, x, y, epoch, layer)

    def ore_at(
        self,
        x: int,
        y: int,
        epoch: int = 0,
        *,
        biome: Biome | None = None,
        layer: int = 0,
    ) -> str | None:
        """Return the ore id generated at ``(x, y, layer)`` for ``epoch``.

        Returns ``None`` for base/station tiles. The ore is picked from
        the biome's ``ore_weights`` with ``mix64(seed, x, y, epoch)``;
        non-surface layers are mixed into the hash.
        Callers that already resolved the biome may pass it in to
        avoid a second lookup.
        """
        if self.is_base(x, y, layer):
            return None
        if biome is None:
            biome = self.biome_at(x, y, layer)
        return weighted_choice(self._ore_hash(x, y, epoch, layer), biome.ore_weights)
