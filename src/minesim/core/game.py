"""Game facade: wires content, world, miner, engine and progression."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from minesim.core.content import load_content
from minesim.core.engine import GameEngine
from minesim.core.events import EventBus
from minesim.core.miner import Drone, Miner, PlayerStats
from minesim.core.progression.service import ProgressionService
from minesim.core.progression.state import ProgressionState
from minesim.core.save import CURRENT_VERSION, DEFAULT_SKIN, SaveGame, default_save_path
from minesim.core.world import World, WorldGenerator

__all__ = ["Game"]


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
        self._selected_skin: str = DEFAULT_SKIN
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
            self._player_stats = getattr(engine, "player_stats", None)
            if self._player_stats is None:
                self._player_stats = getattr(self._miner, "player_stats", None)
            if self._player_stats is None:
                self._player_stats = (
                    PlayerStats.from_config(self._content)
                    if self._content is not None
                    else PlayerStats()
                )
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
        self._player_stats = engine.player_stats

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
        player_stats = getattr(value, "player_stats", None)
        if player_stats is not None:
            self._player_stats = player_stats
        if self._engine is not None:
            try:
                self._engine.miner = value
            except Exception:
                pass

    @property
    def player_stats(self) -> PlayerStats:
        """Money, upgrades and aggregate stats shared by the fleet."""
        return self._player_stats

    @property
    def drones(self) -> dict[int, Any]:
        """The fleet, keyed by drone id."""
        return self._engine.drones

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
    def selected_skin(self) -> str:
        """The id of the currently selected miner skin."""
        return self._selected_skin

    @selected_skin.setter
    def selected_skin(self, skin_id: str) -> None:
        self.select_skin(skin_id)

    def is_skin_unlocked(self, skin_id: str) -> bool:
        """Return True if the skin exists and its requirement is met."""
        skins = getattr(self._content, "skins", None) or {}
        skin = skins.get(str(skin_id)) if isinstance(skins, dict) else None
        if skin is None:
            return False
        unlocked_by = getattr(skin, "unlocked_by", None)
        if unlocked_by is None:
            return True
        checker = getattr(self._progression_state, "is_skin_unlocked", None)
        if callable(checker) and checker(str(skin_id)):
            return True
        completed = getattr(self._progression_state, "completed", {}) or {}
        if unlocked_by in completed:
            return True
        service = self._progression_service
        checker = getattr(service, "is_achievement_unlocked", None)
        return bool(checker(unlocked_by)) if callable(checker) else False

    def select_skin(self, skin_id: str) -> str:
        """Select an unlocked skin by id, raising ValueError otherwise."""
        skin_id = str(skin_id)
        skins = getattr(self._content, "skins", None) or {}
        if not isinstance(skins, dict) or skin_id not in skins:
            raise ValueError(f"unknown skin: {skin_id!r}")
        if not self.is_skin_unlocked(skin_id):
            raise ValueError(f"skin is locked: {skin_id!r}")
        self._selected_skin = skin_id
        return skin_id

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
            version=CURRENT_VERSION,
            seed=self.seed,
            tick=self.tick,
            selected_skin=self._selected_skin,
            fleet=[drone.to_fleet_dict() for drone in self._engine.drones.values()],
            player_stats=self._player_stats.to_dict(),
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
        player_stats = PlayerStats.from_dict(savegame.player_stats, content=content)
        drones = [Drone.from_fleet_dict(entry, player_stats) for entry in savegame.fleet]
        if not any(drone.id == 0 for drone in drones):
            drones.insert(0, Drone(id=0, player_stats=player_stats))
        engine = game._engine
        engine.player_stats = player_stats
        engine.drones.clear()
        for drone in drones:
            drone.player_stats = player_stats
            engine.drones[drone.id] = drone
        game._player_stats = player_stats
        game._miner = engine.miner
        game._world.load_dict(savegame.world_delta)
        restored = ProgressionState.from_dict(savegame.progression, content=content)
        game._progression_state = restored
        game._progression_service.state = restored
        try:
            game.select_skin(str(savegame.selected_skin))
        except ValueError:
            game._selected_skin = DEFAULT_SKIN
        game._engine.tick = int(savegame.tick)
        attempts = player_stats.stats.attempts or {}
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

    def submit(self, command: Any, drone_id: int = 0) -> Any:
        """Submit ``command`` to ``drone_id`` and return its ticket."""
        return self._engine.submit(command, drone_id=drone_id)

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
