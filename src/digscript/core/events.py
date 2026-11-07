"""Typed event bus and engine events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "AchievementUnlocked",
    "EventBus",
    "MineAttempted",
    "Moved",
    "OreMined",
    "ScriptFailed",
    "ScriptFinished",
    "ScriptStarted",
    "Sold",
    "TickAdvanced",
    "UpgradeBought",
]


@dataclass(frozen=True, slots=True)
class Moved:
    """The miner moved one tile."""

    x: int = 0
    y: int = 0
    direction: str | None = None


@dataclass(frozen=True, slots=True)
class MineAttempted:
    """A mining attempt was rolled."""

    ore_id: str | None = None
    success: bool = False


@dataclass(frozen=True, slots=True)
class OreMined:
    """An ore item was mined."""

    ore_id: str | None = None
    amount: int = 1


@dataclass(frozen=True, slots=True)
class Sold:
    """The miner sold ore at the base."""

    money: int = 0
    items: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class UpgradeBought:
    """An upgrade level was bought."""

    id: str = ""
    level: int = 0


@dataclass(frozen=True, slots=True)
class ScriptStarted:
    """A player script started."""

    defines_function: bool = False


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
