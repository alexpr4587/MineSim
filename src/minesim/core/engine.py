"""The tick engine: FIFO commands, tick costs and events."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Protocol

from minesim.core.events import EventBus, TickAdvanced, TileRegenerated

__all__ = ["AllUnlocked", "GameEngine", "ProgressionView", "Ticket"]

_ZERO_COST_NAMES = {
    "Biome",
    "Distance",
    "Inspect",
    "Inventory",
    "OreInfo",
    "Peek",
    "Position",
    "Stats",
    "SubmitEstimate",
    "Tick",
}


class ProgressionView(Protocol):
    """Read-only view of what the player has unlocked."""

    def is_ore_unlocked(self, ore_id: str) -> bool:
        """Return True if the ore is unlocked."""
        ...

    def is_function_unlocked(self, name: str) -> bool:
        """Return True if the function is unlocked."""
        ...

    def is_upgrade_unlocked(self, upgrade_id: str) -> bool:
        """Return True if the upgrade is unlocked."""
        ...

    def is_module_unlocked(self, name: str) -> bool:
        """Return True if the module is unlocked."""
        ...

    def is_skin_unlocked(self, skin_id: str) -> bool:
        """Return True if the skin is unlocked."""
        ...

    def is_example_unlocked(self, example_id: str) -> bool:
        """Return True if the example script is unlocked."""
        ...


class AllUnlocked:
    """A progression view that unlocks everything (for tests)."""

    def is_ore_unlocked(self, ore_id: str) -> bool:
        """Return True for every ore."""
        return True

    def is_function_unlocked(self, name: str) -> bool:
        """Return True for every function."""
        return True

    def is_upgrade_unlocked(self, upgrade_id: str) -> bool:
        """Return True for every upgrade."""
        return True

    def is_module_unlocked(self, name: str) -> bool:
        """Return True for every module."""
        return True

    def is_skin_unlocked(self, skin_id: str) -> bool:
        """Return True for every skin."""
        return True

    def is_example_unlocked(self, example_id: str) -> bool:
        """Return True for every example."""
        return True


@dataclass(slots=True)
class Ticket:
    """The ticket for a submitted command."""

    command: Any = None
    done: bool = False
    result: dict[str, Any] | None = None

    @property
    def is_done(self) -> bool:
        """Alias for :attr:`done`."""
        return self.done


@dataclass(slots=True)
class _Entry:
    """A queued/active command with its ticket."""

    command: Any
    ticket: Ticket
    remaining: int = 0


class GameEngine:
    """Runs commands on a tick counter, FIFO, publishing events."""

    def __init__(
        self,
        world: Any,
        miner: Any,
        content: Any = None,
        events: Any = None,
        progression_view: Any = None,
        **kwargs: Any,
    ) -> None:
        if events is None:
            events = kwargs.get("event_bus") or kwargs.get("bus")
        if progression_view is None:
            progression_view = kwargs.get("progression") or kwargs.get("view")
        if content is None:
            content = kwargs.get("content")
        self.world = world
        self.miner = miner
        self.content = content if content is not None else getattr(world, "content", None)
        self._events = events if events is not None else EventBus()
        self.progression_view = progression_view if progression_view is not None else AllUnlocked()
        self.progression = self.progression_view
        self.tick: int = 0
        self.attempt_counter: int = 0
        self._queue: deque[_Entry] = deque()
        self._active: _Entry | None = None
        self._upgrade_levels: dict[str, int] = {}

    @property
    def events(self) -> Any:
        """The event bus."""
        return self._events

    @events.setter
    def events(self, value: Any) -> None:
        self._events = value

    @property
    def current_tick(self) -> int:
        """Alias for :attr:`tick`."""
        return self.tick

    @current_tick.setter
    def current_tick(self, value: int) -> None:
        self.tick = int(value)

    @property
    def event_bus(self) -> Any:
        """Alias for :attr:`events`."""
        return self._events

    @property
    def bus(self) -> Any:
        """Alias for :attr:`events`."""
        return self._events

    @property
    def seed(self) -> int:
        """The world seed."""
        seed = getattr(self.world, "seed", None)
        if seed is not None:
            return int(seed)
        generator = getattr(self.world, "generator", None)
        seed = getattr(generator, "seed", None)
        if seed is not None:
            return int(seed)
        config = getattr(self.content, "config", None)
        seed = getattr(config, "seed_default", 0)
        return int(seed or 0)

    @property
    def upgrade_levels(self) -> dict[str, int]:
        """Upgrade levels bought so far (mirrors ``miner.upgrades``)."""
        upgrades = getattr(self.miner, "upgrades", None)
        if upgrades is None:
            return self._upgrade_levels
        return upgrades

    @property
    def is_idle(self) -> bool:
        """Return True when no command is active or queued."""
        return self._active is None and not self._queue

    @property
    def pending(self) -> int:
        """Number of commands not yet done."""
        count = len(self._queue)
        if self._active is not None:
            count += 1
        return count

    @property
    def active_command(self) -> Any:
        """The command currently occupying the miner, if any."""
        return self._active.command if self._active is not None else None

    @property
    def queue(self) -> list[Any]:
        """Queued commands (excluding the active one)."""
        return [entry.command for entry in self._queue]

    def _is_static_zero_cost(self, command: Any) -> bool:
        if type(command).__name__ in _ZERO_COST_NAMES:
            return True
        result = getattr(command, "is_zero_cost", None)
        return bool(result) if result is not None else False

    def _execute_now(self, entry: _Entry) -> None:
        result = entry.command.execute(self)
        entry.ticket.result = result
        entry.ticket.done = True

    def _activate_next(self) -> None:
        """Promote queued commands until one occupies the miner or the queue empties.

        Zero-cost commands at the head execute immediately without
        consuming a tick; the first positive-cost command becomes active.
        """
        while self._active is None and self._queue:
            entry = self._queue[0]
            try:
                cost = int(entry.command.cost_ticks(self))
            except Exception:
                cost = 0
            if cost <= 0:
                self._queue.popleft()
                self._execute_now(entry)
                continue
            self._queue.popleft()
            entry.remaining = cost
            self._active = entry

    def submit(self, command: Any) -> Ticket:
        """Submit ``command`` and return its ticket.

        Zero-cost commands execute immediately on submit; other
        commands run FIFO, occupying the miner for their tick cost.
        """
        ticket = Ticket(command=command)
        entry = _Entry(command=command, ticket=ticket)
        if self._is_static_zero_cost(command):
            self._execute_now(entry)
            return ticket
        self._queue.append(entry)
        if self._active is None:
            self._activate_next()
        return ticket

    def step(self) -> None:
        """Advance the engine by one tick."""
        self.tick += 1
        self._events.publish(TickAdvanced(tick=self.tick))
        advance = getattr(self.world, "advance", None)
        if callable(advance):
            try:
                regenerated = advance(self.tick)
            except Exception:
                regenerated = None
            if regenerated:
                for x, y in regenerated:
                    self._events.publish(TileRegenerated(x=x, y=y))
        if self._active is None:
            self._activate_next()
        if self._active is not None:
            self._active.remaining -= 1
            if self._active.remaining <= 0:
                entry = self._active
                self._active = None
                self._execute_now(entry)
                self._activate_next()

    def run_until_idle(self, max_ticks: int = 10000) -> None:
        """Step until idle or ``max_ticks`` ticks have passed."""
        stepped = 0
        while not self.is_idle and stepped < int(max_ticks):
            self.step()
            stepped += 1

    def run(self, max_ticks: int = 10000) -> None:
        """Alias for :meth:`run_until_idle`."""
        self.run_until_idle(max_ticks)
