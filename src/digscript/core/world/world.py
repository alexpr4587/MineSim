"""World storage: generated layer plus a small delta of mined tiles.

The generated layer is never stored -- tiles are computed on demand
by :class:`~digscript.core.world.generator.WorldGenerator`. Only
mined tiles are recorded, in ``delta``: ``{(x, y): (epoch, regen_at)}``
where ``regen_at`` is the tick at which the tile regenerates (or
``None`` once it has regenerated). The tile is re-rolled with
``epoch + 1`` after regeneration.

Generated chunks are kept in an LRU cache (default 256 chunks) for
the UI; evicting a chunk never changes any result.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from digscript.core.content import Content
from digscript.core.world.generator import WorldGenerator

__all__ = ["Tile", "World"]

logger = logging.getLogger(__name__)

Delta = dict[tuple[int, int], tuple[int, int | None]]


@dataclass(frozen=True, slots=True)
class Tile:
    """A single world tile."""

    ore_id: str | None
    biome_id: str
    is_base: bool = False
    depleted: bool = False

    @property
    def has_ore(self) -> bool:
        """Return True if this tile currently holds an ore."""
        return self.ore_id is not None

    @property
    def is_empty(self) -> bool:
        """Return True if this tile has no ore (base or depleted)."""
        return self.ore_id is None


def _parse_delta(data: Any) -> Delta:
    """Parse a to_dict() payload (or a raw delta mapping) into a delta."""
    if data is None:
        return {}
    raw: Any = data.get("delta", data) if isinstance(data, Mapping) else data
    if not isinstance(raw, Mapping):
        raise ValueError("world delta must be a mapping")
    delta: Delta = {}
    for key, value in raw.items():
        if isinstance(key, (tuple, list)) and len(key) == 2:
            x, y = int(key[0]), int(key[1])
        elif isinstance(key, str):
            parts = key.replace("(", "").replace(")", "").split(",")
            if len(parts) != 2:
                raise ValueError(f"invalid world delta key: {key!r}")
            x, y = int(parts[0]), int(parts[1])
        else:
            raise ValueError(f"invalid world delta key: {key!r}")
        if isinstance(value, Mapping):
            epoch = int(value.get("epoch", 0))
            regen_at = value.get("regen_at_tick", value.get("regen_at"))
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            epoch = int(value[0])
            regen_at = value[1]
        else:
            raise ValueError(f"invalid world delta value for {key!r}: {value!r}")
        delta[(x, y)] = (epoch, None if regen_at is None else int(regen_at))
    return delta


class _dualmethod:
    """Descriptor allowing from_dict() as classmethod and instance method."""

    def __init__(self, class_fn: Any, instance_fn: Any) -> None:
        self._class_fn = class_fn
        self._instance_fn = instance_fn

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is not None:
            instance_fn = self._instance_fn
            return lambda *args, **kwargs: instance_fn(obj, *args, **kwargs)
        class_fn = self._class_fn
        return lambda *args, **kwargs: class_fn(objtype, *args, **kwargs)


def _world_from_dict_class(cls: type[World], *args: Any, **kwargs: Any) -> World:
    generator = kwargs.pop("generator", None)
    content = kwargs.pop("content", None)
    data = kwargs.pop("data", None)
    cache_size = kwargs.pop("cache_size", 256)
    for arg in args:
        if isinstance(arg, WorldGenerator):
            generator = arg
        elif isinstance(arg, Content):
            content = arg
        elif isinstance(arg, Mapping):
            data = arg
    if generator is None:
        raise TypeError("from_dict requires a WorldGenerator and content")
    world = cls(generator, content, cache_size=cache_size)
    world._load_delta(data)
    return world


def _world_from_dict_instance(self: World, data: Any = None, *args: Any, **kwargs: Any) -> World:
    if data is None and args:
        data = args[0]
    if data is None:
        data = kwargs.get("data")
    self._load_delta(data)
    return self


class World:
    """An infinite, deterministic, regenerating world."""

    def __init__(
        self,
        generator: WorldGenerator | int,
        content: Content | None = None,
        cache_size: int = 256,
        *,
        chunk_cache_size: int | None = None,
    ) -> None:
        if isinstance(generator, int):
            # Convenience: World(seed, content).
            if content is None:
                raise TypeError("World(seed, content) requires content")
            generator = WorldGenerator(generator, content)
        if content is None:
            content = generator.content
        self.generator = generator
        self.content = content
        size = chunk_cache_size if chunk_cache_size is not None else cache_size
        self._cache_size = max(1, int(size))
        self.delta: Delta = {}
        self.version: int = 0
        self._chunk_cache: OrderedDict[tuple[int, int], tuple[tuple[Tile, ...], ...]] = (
            OrderedDict()
        )
        self._chunk_versions: dict[tuple[int, int], int] = {}

    # -- basic properties -------------------------------------------------

    @property
    def seed(self) -> int:
        """The world seed."""
        return self.generator.seed

    @property
    def cache_size(self) -> int:
        """Maximum number of cached chunks."""
        return self._cache_size

    @property
    def chunk_size(self) -> int:
        """Side length of a chunk, in tiles."""
        return self.content.config.chunk_size

    @property
    def chunk_cache(self) -> OrderedDict[tuple[int, int], tuple[tuple[Tile, ...], ...]]:
        """The live LRU chunk cache (exposed for tests/debugging)."""
        return self._chunk_cache

    def chunk_version(self, cx: int, cy: int) -> int:
        """Per-chunk counter, bumped when a tile of the chunk changes."""
        return self._chunk_versions.get((cx, cy), 0)

    # -- internal helpers --------------------------------------------------

    def _chunk_of(self, x: int, y: int) -> tuple[int, int]:
        size = self.chunk_size
        return (x // size, y // size)

    def _bump_chunk(self, x: int, y: int) -> None:
        chunk = self._chunk_of(x, y)
        self._chunk_versions[chunk] = self._chunk_versions.get(chunk, 0) + 1
        self._chunk_cache.pop(chunk, None)

    def _advance_tile_if_due(self, x: int, y: int, tick: int) -> None:
        """Regenerate a depleted tile whose regen tick has been reached."""
        entry = self.delta.get((x, y))
        if entry is None:
            return
        epoch, regen_at = entry
        if regen_at is not None and tick >= regen_at:
            self.delta[(x, y)] = (epoch + 1, None)
            self.version += 1
            self._bump_chunk(x, y)

    def _advance_chunk_if_due(self, cx: int, cy: int, tick: int) -> None:
        size = self.chunk_size
        x0, y0 = cx * size, cy * size
        for x, y in list(self.delta):
            if x0 <= x < x0 + size and y0 <= y < y0 + size:
                self._advance_tile_if_due(x, y, tick)

    # -- public API --------------------------------------------------------

    def tile_at(self, x: int, y: int, tick: int = 0) -> Tile:
        """Return the tile at ``(x, y)`` as of ``tick``."""
        biome_id = self.generator.biome_id_at(x, y)
        if self.generator.is_base(x, y):
            return Tile(ore_id=None, biome_id=biome_id, is_base=True, depleted=False)
        self._advance_tile_if_due(x, y, tick)
        epoch, regen_at = self.delta.get((x, y), (0, None))
        if regen_at is not None:
            return Tile(ore_id=None, biome_id=biome_id, is_base=False, depleted=True)
        ore_id = self.generator.ore_at(x, y, epoch=epoch)
        return Tile(ore_id=ore_id, biome_id=biome_id, is_base=False, depleted=False)

    def mine_tile(self, x: int, y: int, tick: int = 0) -> str | None:
        """Mark the tile at ``(x, y)`` depleted until it regenerates.

        Returns the mined ore id, or ``None`` if the tile is base,
        already depleted, or has no ore. The tile regenerates at
        ``tick + ore.regen_ticks`` and is then re-rolled with the
        next epoch.
        """
        tile = self.tile_at(x, y, tick)
        if tile.is_base or tile.depleted or tile.ore_id is None:
            return None
        ore = self.content.get_ore(tile.ore_id)
        epoch = self.delta.get((x, y), (0, None))[0]
        self.delta[(x, y)] = (epoch, tick + ore.regen_ticks)
        self.version += 1
        self._bump_chunk(x, y)
        return tile.ore_id

    def advance(self, tick: int) -> None:
        """Process all regenerations due at ``tick``."""
        for x, y in list(self.delta):
            self._advance_tile_if_due(x, y, tick)

    def chunk_tiles(self, cx: int, cy: int, tick: int = 0) -> tuple[tuple[Tile, ...], ...]:
        """Return the tiles of chunk ``(cx, cy)`` as rows of tiles.

        Row 0 is the smallest y in the chunk, column 0 the smallest
        x. Results are served from an LRU cache; a cached chunk is
        rebuilt whenever a tile in it is mined or regenerates.
        """
        key = (cx, cy)
        self._advance_chunk_if_due(cx, cy, tick)
        cached = self._chunk_cache.get(key)
        if cached is not None:
            self._chunk_cache.move_to_end(key)
            return cached
        size = self.chunk_size
        x0, y0 = cx * size, cy * size
        rows = tuple(
            tuple(self.tile_at(x0 + dx, y0 + dy, tick) for dx in range(size)) for dy in range(size)
        )
        self._chunk_cache[key] = rows
        self._chunk_cache.move_to_end(key)
        while len(self._chunk_cache) > self._cache_size:
            self._chunk_cache.popitem(last=False)
        return rows

    # -- serialisation (delta only) ---------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict holding only the delta."""
        return {
            "delta": {
                f"{x},{y}": [epoch, regen_at]
                for (x, y), (epoch, regen_at) in sorted(self.delta.items())
            }
        }

    def _load_delta(self, data: Any) -> None:
        self.delta = _parse_delta(data)
        self._chunk_cache.clear()
        self._chunk_versions.clear()
        self.version += 1

    def load_dict(self, data: Any) -> None:
        """Replace the delta from a :meth:`to_dict` payload."""
        self._load_delta(data)

    def load_delta(self, data: Any) -> None:
        """Alias for :meth:`load_dict`."""
        self._load_delta(data)

    from_dict = _dualmethod(_world_from_dict_class, _world_from_dict_instance)


__all__ = ["Tile", "World"]
