"""Game facade: wires content, world, miner, engine and progression."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from digscript.core.content import load_content
from digscript.core.direction import Direction
from digscript.core.engine import GameEngine
from digscript.core.events import EventBus
from digscript.core.miner import Miner, MinerStats
from digscript.core.progression.service import ProgressionService
from digscript.core.progression.state import ProgressionState
from digscript.core.save import SaveGame, default_save_path
from digscript.core.world import World, WorldGenerator

__all__ = ["Game"]


def _miner_from_dict(data: Any) -> Miner:
    """Rebuild a Miner from its ``to_dict()`` payload."""
    if not isinstance(data, dict):
        raise ValueError("miner save data must be a mapping")
    stats_data = data.get("stats") or {}
    if not isinstance(stats_data, dict):
        stats_data = {}
    stats = MinerStats(
        attempts={str(k): int(v) for k, v in dict(stats_data.get("attempts", {})).items()},
        successes={str(k): int(v) for k, v in dict(stats_data.get("successes", {})).items()},
        total_mined=int(stats_data.get("total_mined", 0)),
        total_earned=int(stats_data.get("total_earned", 0)),
        tiles_moved=int(stats_data.get("tiles_moved", 0)),
        sales=int(stats_data.get("sales", 0)),
    )
    facing_raw = data.get("facing", "north")
    try:
        facing = Direction.parse(facing_raw) if isinstance(facing_raw, str) else facing_raw
    except ValueError:
        facing = Direction.NORTH
    inventory = {str(k): int(v) for k, v in dict(data.get("inventory", {})).items()}
    upgrades = {str(k): int(v) for k, v in dict(data.get("upgrades", {})).items()}
    return Miner(
        x=int(data.get("x", 0)),
        y=int(data.get("y", 0)),
        facing=facing,
        inventory=inventory,
        capacity=int(data.get("capacity", 10)),
        money=int(data.get("money", 0)),
        tool_power=int(data.get("tool_power", 1)),
        tool_tier=int(data.get("tool_tier", 0)),
        move_ticks=int(data.get("move_ticks", 4)),
        scan_radius=int(data.get("scan_radius", 0)),
        stats=stats,
        upgrades=upgrades,
    )


class Game:
    """The single entry point wiring all core systems together."""

    def __init__(
        self,
        content: Any = None,
        seed: Any = None,
        *,
        miner: Any = None,
        world: Any = None,
        engine: Any = None,
        events: Any = None,
        progression_state: Any = None,
        progression_service: Any = None,
        state: Any = None,
        **kwargs: Any,
    ) -> None:
        if kwargs:
            if seed is None and "seed" in kwargs:
                seed = kwargs.pop("seed")
            if content is None and "content" in kwargs:
                content = kwargs.pop("content")
            if kwargs:
                raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        if progression_state is None and state is not None:
            progression_state = state
        if engine is not None:
            self._engine = engine
            self._world = world if world is not None else engine.world
            self._miner = miner if miner is not None else engine.miner
            self._content = (
                content
                if content is not None
                else getattr(engine, "content", None) or getattr(self._world, "content", None)
            )
            self._events = events if events is not None else getattr(engine, "events", EventBus())
            if progression_service is not None:
                self._progression_service = progression_service
                self._progression_state = (
                    progression_state
                    if progression_state is not None
                    else progression_service.state
                )
            elif progression_state is not None:
                self._progression_state = progression_state
                self._progression_service = ProgressionService(
                    self._content, progression_state, self._events, self._miner
                )
            else:
                self._progression_state = ProgressionState(self._content)
                self._progression_service = ProgressionService(
                    self._content, self._progression_state, self._events, self._miner
                )
            self._progression_service.attach_engine(engine)
            return
        if content is None:
            if world is not None and getattr(world, "content", None) is not None:
                content = world.content
            else:
                content = load_content()
        seed_value = int(content.config.seed_default if seed is None else int(seed))
        if world is None:
            generator = WorldGenerator(seed_value, content)
            world = World(generator, content)
        if miner is None:
            miner = Miner.from_config(content)
        if events is None:
            events = EventBus()
        if progression_state is None:
            progression_state = ProgressionState(content)
        if progression_service is None:
            progression_service = ProgressionService(content, progression_state, events, miner)
        engine = GameEngine(world, miner, content, events, progression_service)
        progression_service.attach_engine(engine)
        self._content = content
        self._world = world
        self._miner = miner
        self._events = events
        self._engine = engine
        self._progression_state = progression_state
        self._progression_service = progression_service

    @property
    def content(self) -> Any:
        """The game content."""
        return self._content

    @property
    def world(self) -> Any:
        """The world."""
        return self._world

    @property
    def miner(self) -> Any:
        """The miner."""
        return self._miner

    @miner.setter
    def miner(self, value: Any) -> None:
        self._miner = value
        if self._engine is not None:
            try:
                self._engine.miner = value
            except Exception:
                pass

    @property
    def engine(self) -> Any:
        """The tick engine."""
        return self._engine

    @engine.setter
    def engine(self, value: Any) -> None:
        self._engine = value

    @property
    def events(self) -> Any:
        """The event bus."""
        return self._events

    @property
    def event_bus(self) -> Any:
        """Alias for :attr:`events`."""
        return self._events

    @property
    def bus(self) -> Any:
        """Alias for :attr:`events`."""
        return self._events

    @property
    def progression_service(self) -> Any:
        """The progression service (implements the progression view)."""
        return self._progression_service

    @property
    def progression(self) -> Any:
        """Alias for :attr:`progression_service`."""
        return self._progression_service

    @property
    def progression_view(self) -> Any:
        """Alias for :attr:`progression_service`."""
        return self._progression_service

    @property
    def progression_state(self) -> Any:
        """The progression state."""
        return self._progression_state

    @property
    def state(self) -> Any:
        """Alias for :attr:`progression_state`."""
        return self._progression_state

    @property
    def seed(self) -> int:
        """The world seed."""
        try:
            return int(self._world.seed)
        except Exception:
            return int(getattr(self._engine, "seed", 0) or 0)

    @property
    def tick(self) -> int:
        """The current engine tick."""
        return int(getattr(self._engine, "tick", 0) or 0)

    @tick.setter
    def tick(self, value: int) -> None:
        try:
            self._engine.tick = int(value)
        except Exception:
            pass

    @property
    def attempt_counter(self) -> int:
        """The engine's mining attempt counter."""
        return int(getattr(self._engine, "attempt_counter", 0) or 0)

    @attempt_counter.setter
    def attempt_counter(self, value: int) -> None:
        try:
            self._engine.attempt_counter = int(value)
        except Exception:
            pass

    @property
    def is_idle(self) -> bool:
        """Return True when the engine is idle."""
        return bool(getattr(self._engine, "is_idle", True))

    @classmethod
    def new(cls, seed: Any = None, content: Any = None, **kwargs: Any) -> Game:
        """Create a new game (``seed`` defaults to the content default)."""
        if content is None and "content" in kwargs:
            content = kwargs.pop("content")
        return cls(content, seed, **kwargs)

    @classmethod
    def create(cls, seed: Any = None, content: Any = None, **kwargs: Any) -> Game:
        """Alias for :meth:`new`."""
        return cls.new(seed, content, **kwargs)

    def save(self, path: str | Path | None = None) -> Path:
        """Save this game to ``path`` (default save path) and return the path."""
        savegame = SaveGame(
            version=1,
            seed=self.seed,
            tick=self.tick,
            miner=self._miner.to_dict(),
            world_delta=self._world.to_dict(),
            progression=self._progression_state.to_dict(),
        )
        return savegame.save(path)

    @classmethod
    def load(cls, path: str | Path | None = None, content: Any = None, **kwargs: Any) -> Game:
        """Load a game from ``path`` (default save path)."""
        if content is None and "content" in kwargs:
            content = kwargs.pop("content")
        savegame = SaveGame.load(path)
        if content is None:
            content = load_content()
        game = cls.new(savegame.seed, content)
        miner = _miner_from_dict(savegame.miner)
        game._miner = miner
        try:
            game._engine.miner = miner
        except Exception:
            pass
        game._world.load_dict(savegame.world_delta)
        restored = ProgressionState.from_dict(savegame.progression, content=content)
        game._progression_state = restored
        game._progression_service._state = restored
        game._engine.tick = int(savegame.tick)
        attempts = miner.stats.attempts or {}
        try:
            game._engine.attempt_counter = int(sum(int(v) for v in attempts.values()))
        except Exception:
            pass
        return game

    @classmethod
    def load_save(cls, path: str | Path | None = None, content: Any = None) -> Game:
        """Alias for :meth:`load`."""
        return cls.load(path, content)

    @classmethod
    def from_save(cls, path: str | Path | None = None, content: Any = None) -> Game:
        """Alias for :meth:`load`."""
        return cls.load(path, content)

    def submit(self, command: Any) -> Any:
        """Submit ``command`` to the engine and return its ticket."""
        return self._engine.submit(command)

    def step(self) -> None:
        """Advance the engine by one tick."""
        self._engine.step()

    def run_until_idle(self, max_ticks: int = 10000) -> None:
        """Step until idle or ``max_ticks`` ticks have passed."""
        self._engine.run_until_idle(max_ticks)

    def run(self, max_ticks: int = 10000) -> None:
        """Alias for :meth:`run_until_idle`."""
        self.run_until_idle(max_ticks)

    def default_save_path(self) -> Path:
        """Return the default save path."""
        return default_save_path()
