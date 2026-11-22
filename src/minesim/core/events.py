"""Typed event bus and engine events."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AchievementUnlocked",
    "ApiCalled",
    "ContractDelivered",
    "Charged",
    "ContractExpired",
    "ContractGenerated",
    "DockQueued",
    "DockServed",
    "EnergySpent",
    "MinerOverheated",
    "MinerRecovered",
    "MinerRemoved",
    "MinerRescued",
    "MinerSpawned",
    "MinerStranded",
    "EstimateSubmitted",
    "EventBus",
    "LayerChanged",
    "MineAttempted",
    "MoveRefused",
    "Moved",
    "OreMined",
    "RefineFinished",
    "RefineStarted",
    "ScriptFailed",
    "ScriptFinished",
    "ScriptStarted",
    "Sold",
    "StockSold",
    "TemperatureChanged",
    "TickAdvanced",
    "TileRegenerated",
    "Unloaded",
    "UpgradeBought",
    "WorldEventEnded",
    "WorldEventStarted",
]


@dataclass(frozen=True, slots=True)
class Moved:
    """A miner moved one tile."""

    miner_id: int = 0
    x: int = 0
    y: int = 0
    layer: int = 0
    direction: str | None = None
    in_slow_zone: bool = False


@dataclass(frozen=True, slots=True)
class MoveRefused:
    """A move was refused before it started."""

    miner_id: int = 0
    reason: str = ""


@dataclass(frozen=True, slots=True)
class MineAttempted:
    """A mine() call was evaluated.

    ``reason`` is ``None`` on success, ``'miss'`` when the dice rolled a
    failure, and otherwise a rule failure (``locked_ore``,
    ``tool_too_weak``, ``inventory_full`` or ``nothing_to_mine``). Only
    a success or a ``'miss'`` counts as an attempt.
    """

    miner_id: int = 0
    ore_id: str | None = None
    layer: int = 0
    success: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class OreMined:
    """An ore item was mined."""

    miner_id: int = 0
    ore_id: str | None = None
    amount: int = 1
    layer: int = 0
    in_rich_vein: bool = False


@dataclass(frozen=True, slots=True)
class Sold:
    """A miner sold ore at the base."""

    miner_id: int = 0
    money: int = 0
    items: dict[str, int] | None = None
    avg_index: float = 1.0


@dataclass(frozen=True, slots=True)
class Unloaded:
    """A miner moved items into the base warehouse."""

    items: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class DockQueued:
    """A miner started waiting for the shared surface dock."""

    miner_id: int = 0
    units: int = 0


@dataclass(frozen=True, slots=True)
class DockServed:
    """The shared surface dock finished serving a miner."""

    miner_id: int = 0
    units: int = 0
    waited_ticks: int = 0


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
    layer: int = 0


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

    miner_id: int = 0
    id: str = ""
    level: int = 0


@dataclass(frozen=True, slots=True)
class MinerOverheated:
    """A miner reached the overheat threshold and shut down."""

    miner_id: int = 0


@dataclass(frozen=True, slots=True)
class MinerRecovered:
    """An overheated miner cooled down and restarted."""

    miner_id: int = 0


@dataclass(frozen=True, slots=True)
class TemperatureChanged:
    """A miner's temperature changed without overheating."""

    miner_id: int = 0
    temperature: float = 0.0


@dataclass(frozen=True, slots=True)
class MinerSpawned:
    """A miner was added to the fleet."""

    id: int = 0


@dataclass(frozen=True, slots=True)
class MinerRemoved:
    """A miner was removed from the fleet."""

    id: int = 0


@dataclass(frozen=True, slots=True)
class EnergySpent:
    """A miner spent energy to start an action."""

    miner_id: int = 0
    amount: int = 0


@dataclass(frozen=True, slots=True)
class Charged:
    """A miner restored energy at a base or station."""

    miner_id: int = 0
    amount: int = 0


@dataclass(frozen=True, slots=True)
class MinerStranded:
    """A miner ran out of energy away from a base or station."""

    miner_id: int = 0


@dataclass(frozen=True, slots=True)
class MinerRescued:
    """A stranded miner was towed back to a station."""

    miner_id: int = 0
    lost_items: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class LayerChanged:
    """A miner descended to or ascended from a layer."""

    miner_id: int = 0
    from_layer: int = 0
    to_layer: int = 0


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
class ApiCalled:
    """A player script successfully called a game API function."""

    function: str = ""
    miner_id: int = 0


@dataclass(frozen=True, slots=True)
class TickAdvanced:
    """The engine advanced to a new tick."""

    tick: int = 0


@dataclass(frozen=True, slots=True)
class WorldEventStarted:
    """A random world event became active."""

    kind: str = ""
    id: int = 0


@dataclass(frozen=True, slots=True)
class WorldEventEnded:
    """A random world event stopped being active."""

    kind: str = ""
    id: int = 0


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
