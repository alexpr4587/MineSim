"""Deterministic random world events (rich veins, slow zones and news).

Events are a pure function of the world seed and the tick: every slot
of ``world_event_interval_ticks`` may spawn one event, decided by
``mix64(seed, slot, k)``. Nothing is stored, so replays and save loads
always produce the same events.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from minesim.core.rng import mix64, unit

__all__ = ["WorldEvent", "WorldEvents"]

# 16 compass directions with integer components (max component 4).
_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (4, 0),
    (4, 2),
    (3, 3),
    (2, 4),
    (0, 4),
    (-2, 4),
    (-3, 3),
    (-4, 2),
    (-4, 0),
    (-4, -2),
    (-3, -3),
    (-2, -4),
    (0, -4),
    (2, -4),
    (3, -3),
    (4, -2),
)


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """One active or upcoming world event."""

    id: int
    kind: str
    x: int | None = None
    y: int | None = None
    radius: int = 0
    starts: int = 0
    ends: int = 0
    item: str | None = None
    factor: float = 1.0
    yield_multiplier: int = 1
    move_cost_multiplier: int = 1

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _definitions(source: Any) -> dict[str, Any]:
    """Normalise an events source into a ``kind -> definition`` mapping."""
    raw = getattr(source, "events", source)
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        entries: list[Any] = list(raw.values())
    elif isinstance(raw, Iterable) and not isinstance(raw, (str, bytes)):
        entries = list(raw)
    else:
        entries = [raw]
    definitions: dict[str, Any] = {}
    for entry in entries:
        kind = _get(entry, "kind")
        if kind:
            definitions[str(kind)] = entry
    return definitions


def _item_ids(source: Any, explicit: Iterable[str] | None) -> list[str]:
    if explicit is not None:
        return sorted({str(item) for item in explicit})
    ids = _get(source, "ids")
    if ids is not None:
        return sorted({str(item) for item in ids})
    ores = _get(source, "ores")
    products = _get(source, "products")
    if isinstance(ores, Mapping) or isinstance(products, Mapping):
        merged: set[str] = set()
        if isinstance(ores, Mapping):
            merged.update(str(item) for item in ores)
        if isinstance(products, Mapping):
            merged.update(str(item) for item in products)
        return sorted(merged)
    return []


def _ceil_div(value: int, divisor: int) -> int:
    return -((-int(value)) // int(divisor))


class WorldEvents:
    """Generate and query the world events for one seed."""

    def __init__(
        self,
        seed: int,
        config: Any = None,
        catalog: Any = None,
        item_ids: Iterable[str] | None = None,
    ) -> None:
        if catalog is None and _get(config, "config") is not None:
            catalog = config
            config = _get(config, "config")
        self.seed = int(seed)
        self.config = config
        self.interval = max(1, int(_get(config, "world_event_interval_ticks", 2500) or 2500))
        chance = float(_get(config, "world_event_chance", 0.6) or 0.0)
        self.chance = min(1.0, max(0.0, chance))
        self.definitions = _definitions(catalog)
        self.kinds: tuple[str, ...] = tuple(sorted(self.definitions))
        self.items: tuple[str, ...] = tuple(_item_ids(catalog, item_ids))
        self._max_duration = max(
            (int(_get(entry, "duration", 0) or 0) for entry in self.definitions.values()),
            default=0,
        )

    # -- slot generation -----------------------------------------------------

    def _slot_event(self, slot: int) -> WorldEvent | None:
        slot = int(slot)
        if slot < 0 or not self.kinds:
            return None
        if unit(mix64(self.seed, slot, 0)) >= self.chance:
            return None
        kind = self.kinds[mix64(self.seed, slot, 1) % len(self.kinds)]
        definition = self.definitions[kind]
        starts = slot * self.interval
        ends = starts + int(_get(definition, "duration", 0) or 0)
        if kind == "market_news":
            item: str | None = None
            factor = 1.0
            if self.items:
                item = self.items[mix64(self.seed, slot, 2) % len(self.items)]
            choices = list(_get(definition, "factor_choices", []) or [])
            if choices:
                factor = float(choices[mix64(self.seed, slot, 3) % len(choices)])
            return WorldEvent(
                id=slot,
                kind=kind,
                starts=starts,
                ends=ends,
                item=item,
                factor=factor,
            )
        x, y = self._position(slot, definition)
        return WorldEvent(
            id=slot,
            kind=kind,
            x=x,
            y=y,
            radius=int(_get(definition, "radius", 0) or 0),
            starts=starts,
            ends=ends,
            yield_multiplier=int(_get(definition, "yield_multiplier", 1) or 1),
            move_cost_multiplier=int(_get(definition, "move_cost_multiplier", 1) or 1),
        )

    def _position(self, slot: int, definition: Any) -> tuple[int, int]:
        """Place a spatial event inside the configured distance ring.

        The integer direction table keeps every coordinate on a tile.
        The scale is chosen so the position is within ``[min, max]``
        both as Chebyshev distance and as Euclidean distance.
        """
        min_distance = max(0, int(_get(definition, "min_distance", 0) or 0))
        max_distance = max(min_distance, int(_get(definition, "max_distance", 0) or 0))
        index = mix64(self.seed, slot, 2) % len(_DIRECTIONS)
        dx, dy = _DIRECTIONS[index]
        max_component = max(abs(dx), abs(dy))
        length = math.sqrt(dx * dx + dy * dy)
        low = max(1, _ceil_div(min_distance, max_component))
        high = int(max_distance / length)
        if high < low:
            # Fall back to the nearest cardinal direction.
            dx, dy = (1, 0) if dx >= 0 else (-1, 0)
            low = min_distance
            high = max(min_distance, max_distance)
        span = high - low + 1
        if span <= 1:
            scale = low
        else:
            scale = low + int(unit(mix64(self.seed, slot, 3)) * span)
            scale = min(high, max(low, scale))
        return dx * scale, dy * scale

    def event_for_slot(self, slot: int) -> WorldEvent | None:
        """Return the event generated for ``slot`` (or None)."""
        return self._slot_event(slot)

    def event_at_slot(self, slot: int) -> WorldEvent | None:
        """Alias for :meth:`event_for_slot`."""
        return self._slot_event(slot)

    def slot_for_tick(self, tick: int) -> int:
        """Return the slot number containing ``tick``."""
        return int(tick) // self.interval

    # -- queries -------------------------------------------------------------

    def active_at(self, tick: int) -> list[WorldEvent]:
        """Return the events active at ``tick``, ordered by id."""
        tick = int(tick)
        last = tick // self.interval
        first = max(0, (tick - self._max_duration) // self.interval)
        active: list[WorldEvent] = []
        for slot in range(first, last + 1):
            event = self._slot_event(slot)
            if event is not None and event.starts <= tick < event.ends:
                active.append(event)
        active.sort(key=lambda event: event.id)
        return active

    def modifiers_at(self, x: int, y: int, tick: int) -> dict[str, int]:
        """Return the yield and move multipliers at tile ``(x, y)``."""
        yield_multiplier = 1
        move_multiplier = 1
        for event in self.active_at(tick):
            if event.x is None or event.y is None:
                continue
            dx = int(x) - event.x
            dy = int(y) - event.y
            if dx * dx + dy * dy > event.radius * event.radius:
                continue
            if event.kind == "rich_vein":
                yield_multiplier *= max(1, int(event.yield_multiplier))
            elif event.kind == "slow_zone":
                move_multiplier *= max(1, int(event.move_cost_multiplier))
        return {
            "yield_multiplier": yield_multiplier,
            "move_multiplier": move_multiplier,
        }

    def news_direction(self, event: WorldEvent) -> str:
        """Return ``'shortage'`` or ``'glut'`` for a market news event."""
        return "shortage" if float(event.factor) > 1.0 else "glut"
