"""Typed event bus and engine events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AchievementUnlocked",
    "ContractDelivered",
    "ContractExpired",
    "ContractGenerated",
    "DroneRemoved",
    "DroneSpawned",
    "EstimateSubmitted",
    "EventBus",
    "MineAttempted",
    "Moved",
    "OreMined",
    "RefineFinished",
    "RefineStarted",
    "ScriptFailed",
    "ScriptFinished",
    "ScriptStarted",
    "Sold",
    "StockSold",
    "TickAdvanced",
    "TileRegenerated",
    "Unloaded",
    "UpgradeBought",
]


@dataclass(frozen=True, slots=True)
class Moved:
    """A drone moved one tile."""

    drone_id: int = 0
    x: int = 0
    y: int = 0
    direction: str | None = None


@dataclass(frozen=True, slots=True)
class MineAttempted:
    """A mine() call was evaluated.

    ``reason`` is ``None`` on success, ``'miss'`` when the dice rolled a
    failure, and otherwise a rule failure (``locked_ore``,
    ``tool_too_weak``, ``inventory_full`` or ``nothing_to_mine``). Only
    a success or a ``'miss'`` counts as an attempt.
    """

    drone_id: int = 0
    ore_id: str | None = None
    success: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class OreMined:
    """An ore item was mined."""

    drone_id: int = 0
    ore_id: str | None = None
    amount: int = 1


@dataclass(frozen=True, slots=True)
class Sold:
    """A drone sold ore at the base."""

    drone_id: int = 0
    money: int = 0
    items: dict[str, int] | None = None
    avg_index: float = 1.0


@dataclass(frozen=True, slots=True)
class Unloaded:
    """A drone moved items into the base warehouse."""

    items: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class StockSold:
    """Items were sold from the warehouse at market prices."""

    item: str = ""
    amount: int = 0
    money: int = 0


@dataclass(frozen=True, slots=True)
class RefineStarted:
    """A refinery job started."""

    recipe: str = ""
    times: int = 1


@dataclass(frozen=True, slots=True)
class RefineFinished:
    """A refinery job finished and its outputs reached the warehouse."""

    recipe: str = ""
    times: int = 1
    outputs: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class ContractGenerated:
    """A new delivery contract appeared on the board."""

    id: int = 0


@dataclass(frozen=True, slots=True)
class ContractDelivered:
    """A delivery contract was completed and paid."""

    id: int = 0
    reward: int = 0


@dataclass(frozen=True, slots=True)
class ContractExpired:
    """A delivery contract expired without being delivered."""

    id: int = 0


@dataclass(frozen=True, slots=True)
class TileRegenerated:
    """A depleted tile regenerated during :meth:`World.advance`."""

    x: int = 0
    y: int = 0


@dataclass(frozen=True, slots=True)
class EstimateSubmitted:
    """A player submitted an estimate for an ore's mining probability."""

    ore_id: str = ""
    p: float = 0.0
    error: float = 0.0
    attempts: int = 0
    good: bool = False


@dataclass(frozen=True, slots=True)
class UpgradeBought:
    """An upgrade level was bought."""

    drone_id: int = 0
    id: str = ""
    level: int = 0


@dataclass(frozen=True, slots=True)
class DroneSpawned:
    """A drone was added to the fleet."""

    id: int = 0


@dataclass(frozen=True, slots=True)
class DroneRemoved:
    """A drone was removed from the fleet."""

    id: int = 0


@dataclass(frozen=True, slots=True)
class ScriptStarted:
    """A player script started."""

    defines_function: bool = False
    features: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ScriptFinished:
    """A player script finished normally."""


@dataclass(frozen=True, slots=True)
class ScriptFailed:
    """A player script failed."""

    error_type: str = ""


@dataclass(frozen=True, slots=True)
class AchievementUnlocked:
    """An achievement was unlocked."""

    id: str = ""


@dataclass(frozen=True, slots=True)
class TickAdvanced:
    """The engine advanced to a new tick."""

    tick: int = 0


class EventBus:
    """A tiny typed event bus (no threads, no global state)."""

    def __init__(self) -> None:
        self._subscribers: dict[type[Any], list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: type[Any], fn: Callable[[Any], None]) -> Callable[[], None]:
        """Subscribe ``fn`` to events of ``event_type``.

        Returns an unsubscribe callable.
        """
        self._subscribers.setdefault(event_type, []).append(fn)

        def unsubscribe() -> None:
            handlers = self._subscribers.get(event_type)
            if handlers is not None and fn in handlers:
                handlers.remove(fn)

        return unsubscribe

    def publish(self, event: Any) -> None:
        """Publish ``event`` to subscribers of its exact type."""
        for fn in list(self._subscribers.get(type(event), ())):
            fn(event)

    def clear(self) -> None:
        """Remove all subscribers."""
        self._subscribers.clear()
