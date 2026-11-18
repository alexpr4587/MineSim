"""World storage: generated layers plus a small delta of mined tiles.

The generated layers are never stored -- tiles are computed on demand
by :class:`~minesim.core.world.generator.WorldGenerator`. Only mined
tiles are recorded, per layer, in ``delta``: ``{(x, y): (epoch, regen_at)}``
where ``regen_at`` is the tick at which the tile regenerates (or
``None`` once it has regenerated). The tile is re-rolled with
``epoch + 1`` after regeneration.

Generated chunks are kept in a per-layer LRU cache (default 256 chunks
per layer) for the UI; evicting a chunk never changes any result.
"""

from __future__ import annotations

import heapq
import logging
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from minesim.core.content import Content
from minesim.core.world.generator import WorldGenerator

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


def _serialise_delta(delta: Delta) -> dict[str, list[int | None]]:
    return {f"{x},{y}": [epoch, regen_at] for (x, y), (epoch, regen_at) in sorted(delta.items())}


@dataclass(slots=True)
class _LayerState:
    """The mutable mined-tile state and caches of one layer."""

    delta: Delta
    chunk_cache: OrderedDict[tuple[int, int], tuple[tuple[Tile, ...], ...]]
    chunk_versions: dict[tuple[int, int], int]
    regen_heap: list[tuple[int, int, int]]

    @classmethod
    def empty(cls) -> _LayerState:
        return cls(
            delta={},
            chunk_cache=OrderedDict(),
            chunk_versions={},
            regen_heap=[],
        )


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
    """An infinite, deterministic, regenerating multi-layer world."""

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
        self.version: int = 0
        self._layers: dict[int, _LayerState] = {0: _LayerState.empty()}

    # -- basic properties -------------------------------------------------

    @property
    def seed(self) -> int:
        """The world seed."""
        return self.generator.seed

    @property
    def cache_size(self) -> int:
        """Maximum number of cached chunks per layer."""
        return self._cache_size

    @property
    def chunk_size(self) -> int:
        """Side length of a chunk, in tiles."""
        return self.content.config.chunk_size

    @property
    def delta(self) -> Delta:
        """The layer-0 mined delta (kept for backwards compatibility)."""
        return self._layers[0].delta

    @property
    def deltas(self) -> dict[int, Delta]:
        """The mined deltas of every touched layer."""
        return {layer: state.delta for layer, state in sorted(self._layers.items())}

    @property
    def chunk_cache(self) -> OrderedDict[tuple[int, int], tuple[tuple[Tile, ...], ...]]:
        """The layer-0 LRU chunk cache (exposed for tests/debugging)."""
        return self._layers[0].chunk_cache

    def chunk_cache_for(
        self, layer: int = 0
    ) -> OrderedDict[tuple[int, int], tuple[tuple[Tile, ...], ...]]:
        """Return the live LRU chunk cache of ``layer``."""
        return self._layer_state(layer).chunk_cache

    def chunk_version(self, cx: int, cy: int, layer: int = 0) -> int:
        """Per-chunk counter of ``layer``, bumped when a tile changes."""
        return self._layer_state(layer).chunk_versions.get((cx, cy), 0)

    # -- internal helpers --------------------------------------------------

    def _layer_state(self, layer: int) -> _LayerState:
        layer = int(layer)
        state = self._layers.get(layer)
        if state is None:
            state = _LayerState.empty()
            self._layers[layer] = state
        return state

    def _chunk_of(self, x: int, y: int) -> tuple[int, int]:
        size = self.chunk_size
        return (x // size, y // size)

    def _bump_chunk(self, x: int, y: int, layer: int) -> None:
        state = self._layer_state(layer)
        chunk = self._chunk_of(x, y)
        state.chunk_versions[chunk] = state.chunk_versions.get(chunk, 0) + 1
        state.chunk_cache.pop(chunk, None)

    def _advance_tile_if_due(self, x: int, y: int, tick: int, layer: int = 0) -> bool:
        """Regenerate a depleted tile whose regen tick has been reached.

        Returns True if the tile regenerated. The matching heap entry
        (if any) becomes stale and is skipped by :meth:`advance`.
        """
        state = self._layer_state(layer)
        entry = state.delta.get((x, y))
        if entry is None:
            return False
        epoch, regen_at = entry
        if regen_at is None or tick < regen_at:
            return False
        state.delta[(x, y)] = (epoch + 1, None)
        self.version += 1
        self._bump_chunk(x, y, layer)
        return True

    def _advance_chunk_if_due(self, cx: int, cy: int, tick: int, layer: int = 0) -> None:
        size = self.chunk_size
        x0, y0 = cx * size, cy * size
        state = self._layer_state(layer)
        for x, y in list(state.delta):
            if x0 <= x < x0 + size and y0 <= y < y0 + size:
                self._advance_tile_if_due(x, y, tick, layer)

    # -- public API --------------------------------------------------------

    def tile_at(self, x: int, y: int, tick: int = 0, layer: int = 0) -> Tile:
        """Return the tile at ``(x, y)`` on ``layer`` as of ``tick``."""
        layer = int(layer)
        if self.generator.is_base(x, y, layer):
            biome_id = self.generator.biome_id_at(x, y, layer)
            return Tile(ore_id=None, biome_id=biome_id, is_base=True, depleted=False)
        biome = self.generator.biome_at(x, y, layer)
        self._advance_tile_if_due(x, y, tick, layer)
        state = self._layer_state(layer)
        epoch, regen_at = state.delta.get((x, y), (0, None))
        if regen_at is not None:
            return Tile(ore_id=None, biome_id=biome.id, is_base=False, depleted=True)
        ore_id = self.generator.ore_at(x, y, epoch=epoch, biome=biome, layer=layer)
        return Tile(ore_id=ore_id, biome_id=biome.id, is_base=False, depleted=False)

    def mine_tile(self, x: int, y: int, tick: int = 0, layer: int = 0) -> str | None:
        """Mark the tile at ``(x, y)`` on ``layer`` depleted until it regenerates.

        Returns the mined ore id, or ``None`` if the tile is base,
        already depleted, or has no ore. The tile regenerates at
        ``tick + ore.regen_ticks`` and is then re-rolled with the
        next epoch.
        """
        layer = int(layer)
        tile = self.tile_at(x, y, tick, layer)
        if tile.is_base or tile.depleted or tile.ore_id is None:
            return None
        ore = self.content.get_ore(tile.ore_id)
        state = self._layer_state(layer)
        epoch = state.delta.get((x, y), (0, None))[0]
        regen_at = tick + ore.regen_ticks
        state.delta[(x, y)] = (epoch, regen_at)
        heapq.heappush(state.regen_heap, (regen_at, x, y))
        self.version += 1
        self._bump_chunk(x, y, layer)
        return tile.ore_id

    def advance(self, tick: int, layer: int = 0) -> list[tuple[int, int]]:
        """Process all regenerations due at ``tick`` on ``layer``.

        Pops due entries from the min-heap of ``(regen_at_tick, x, y)``
        so each depleted tile regenerates exactly once, at its regen
        tick, bumping its chunk version exactly once. Stale heap
        entries (tiles already regenerated lazily via ``tile_at``)
        are skipped without bumping the chunk again. ``tile_at``
        stays consistent with this method: a tile mined at tick ``t``
        is depleted for every tick ``< t + ore.regen_ticks`` and
        regenerated from that tick on.

        Returns the coordinates of the tiles that regenerated during
        this call, in regeneration order.
        """
        state = self._layer_state(layer)
        regenerated: list[tuple[int, int]] = []
        heap = state.regen_heap
        while heap and heap[0][0] <= tick:
            regen_at, x, y = heapq.heappop(heap)
            entry = state.delta.get((x, y))
            if entry is None or entry[1] != regen_at:
                continue
            if self._advance_tile_if_due(x, y, tick, layer):
                regenerated.append((x, y))
        return regenerated

    def advance_all(self, tick: int) -> list[tuple[int, int, int]]:
        """Advance every touched layer and return ``(layer, x, y)`` entries."""
        regenerated: list[tuple[int, int, int]] = []
        for layer in sorted(self._layers):
            for x, y in self.advance(tick, layer):
                regenerated.append((layer, x, y))
        return regenerated

    def chunk_tiles(
        self, cx: int, cy: int, tick: int = 0, layer: int = 0
    ) -> tuple[tuple[Tile, ...], ...]:
        """Return the tiles of chunk ``(cx, cy)`` on ``layer`` as rows of tiles.

        Row 0 is the smallest y in the chunk, column 0 the smallest
        x. Results are served from an LRU cache; a cached chunk is
        rebuilt whenever a tile in it is mined or regenerates.
        """
        layer = int(layer)
        key = (cx, cy)
        state = self._layer_state(layer)
        self._advance_chunk_if_due(cx, cy, tick, layer)
        cached = state.chunk_cache.get(key)
        if cached is not None:
            state.chunk_cache.move_to_end(key)
            return cached
        size = self.chunk_size
        x0, y0 = cx * size, cy * size
        rows = tuple(
            tuple(self.tile_at(x0 + dx, y0 + dy, tick, layer) for dx in range(size))
            for dy in range(size)
        )
        state.chunk_cache[key] = rows
        state.chunk_cache.move_to_end(key)
        while len(state.chunk_cache) > self._cache_size:
            state.chunk_cache.popitem(last=False)
        return rows

    # -- serialisation (deltas only) --------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict holding the per-layer deltas."""
        data: dict[str, Any] = {"delta": _serialise_delta(self._layers[0].delta)}
        layer_deltas = {
            str(layer): _serialise_delta(state.delta)
            for layer, state in sorted(self._layers.items())
            if layer != 0 and state.delta
        }
        if layer_deltas:
            data["layer_deltas"] = layer_deltas
        return data

    def _load_delta(self, data: Any) -> None:
        layers: dict[int, _LayerState] = {0: _LayerState.empty()}
        layers[0].delta = _parse_delta(data)
        raw_layers: Any = None
        if isinstance(data, Mapping):
            raw_layers = data.get("layer_deltas")
        if isinstance(raw_layers, Mapping):
            for key, payload in raw_layers.items():
                layer = int(key)
                if layer == 0:
                    layers[0].delta = _parse_delta(payload)
                    continue
                state = _LayerState.empty()
                state.delta = _parse_delta(payload)
                layers[layer] = state
        for state in layers.values():
            state.regen_heap = [
                (regen_at, x, y)
                for (x, y), (_epoch, regen_at) in state.delta.items()
                if regen_at is not None
            ]
            heapq.heapify(state.regen_heap)
        self._layers = layers
        self.version += 1

    def load_dict(self, data: Any) -> None:
        """Replace the deltas from a :meth:`to_dict` payload."""
        self._load_delta(data)

    def load_delta(self, data: Any) -> None:
        """Alias for :meth:`load_dict`."""
        self._load_delta(data)

    from_dict = _dualmethod(_world_from_dict_class, _world_from_dict_instance)


__all__ = ["Tile", "World"]
