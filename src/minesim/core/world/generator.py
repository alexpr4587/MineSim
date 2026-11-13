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

    def is_base(self, x: int, y: int) -> bool:
        """Return True for base tiles (no ore, never minable).

        Base tiles are the square of tiles within ``base_half_size``
        of (0, 0) in Chebyshev distance.
        """
        half = self.content.config.base_half_size
        return max(abs(x), abs(y)) <= half

    def biome_at(self, x: int, y: int) -> Biome:
        """Return the biome of the tile at ``(x, y)``."""
        return self._biomes.biome_at(x, y)

    def biome_id_at(self, x: int, y: int) -> str:
        """Return the biome id of the tile at ``(x, y)``."""
        return self._biomes.biome_id_at(x, y)

    def ore_at(
        self,
        x: int,
        y: int,
        epoch: int = 0,
        *,
        biome: Biome | None = None,
    ) -> str | None:
        """Return the ore id generated at ``(x, y)`` for ``epoch``.

        Returns ``None`` for base tiles. The ore is picked from the
        biome's ``ore_weights`` with ``mix64(seed, x, y, epoch)``.
        Callers that already resolved the biome may pass it in to
        avoid a second lookup.
        """
        if self.is_base(x, y):
            return None
        if biome is None:
            biome = self.biome_at(x, y)
        return weighted_choice(mix64(self.seed, x, y, epoch), biome.ore_weights)
