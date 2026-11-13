"""Progression service: watches events and completes achievements."""

from __future__ import annotations

from typing import Any

from minesim.core.events import (
    AchievementUnlocked,
    EstimateSubmitted,
    EventBus,
    MineAttempted,
    Moved,
    OreMined,
    ScriptFinished,
    ScriptStarted,
    Sold,
    TickAdvanced,
    TileRegenerated,
    UpgradeBought,
)
from minesim.core.progression.state import ProgressionState

__all__ = ["ProgressionService"]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _is_content(obj: Any) -> bool:
    return obj is not None and hasattr(obj, "ores") and hasattr(obj, "config")


def _is_state(obj: Any) -> bool:
    return obj is not None and hasattr(obj, "counters") and hasattr(obj, "completed")


def _is_bus(obj: Any) -> bool:
    return obj is not None and hasattr(obj, "subscribe") and hasattr(obj, "publish")


def _is_engine(obj: Any) -> bool:
    return obj is not None and hasattr(obj, "miner") and hasattr(obj, "world")


def _is_miner(obj: Any) -> bool:
    return (
        obj is not None
        and hasattr(obj, "inventory")
        and hasattr(obj, "money")
        and hasattr(obj, "x")
    )


class ProgressionService:
    """Tracks counters from engine/script events and unlocks achievements."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        content = kwargs.pop("content", None)
        state = kwargs.pop("state", None)
        if state is None:
            state = kwargs.pop("progression_state", None)
        if state is None:
            state = kwargs.pop("progression", None)
            if state is not None and not _is_state(state):
                state = None
        events = kwargs.pop("events", None)
        if events is None:
            events = kwargs.pop("event_bus", None)
        if events is None:
            events = kwargs.pop("bus", None)
        miner = kwargs.pop("miner", None)
        world = kwargs.pop("world", None)
        engine = kwargs.pop("engine", None)
        if engine is None:
            engine = kwargs.pop("game", None)
        if engine is None:
            engine = kwargs.pop("game_engine", None)
        for arg in args:
            if arg is None:
                continue
            if _is_content(arg):
                if content is None:
                    content = arg
            elif _is_state(arg):
                if state is None:
                    state = arg
            elif _is_engine(arg):
                if engine is None:
                    engine = arg
            elif _is_bus(arg):
                if events is None:
                    events = arg
            elif _is_miner(arg):
                if miner is None:
                    miner = arg
            elif isinstance(arg, dict) and content is None and "ores" in arg:
                content = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        self._content = content
        self._state: ProgressionState = state if state is not None else ProgressionState(content)
        self._engine = engine
        self._miner = miner
        if engine is not None and self._miner is None:
            self._miner = _get(engine, "miner")
        self._world = world
        if self._world is None and engine is not None:
            self._world = _get(engine, "world")
        if events is None and engine is not None:
            events = _get(engine, "events") or _get(engine, "event_bus") or _get(engine, "bus")
        self._events = events if events is not None else EventBus()
        self._tick = 0
        self._current_streak = int(getattr(self._state, "current_streak", 0) or 0)
        self._current_fail_streak = int(getattr(self._state, "current_fail_streak", 0) or 0)
        self._checking = False
        self._subscribed_bus: Any = None
        self._subscribe(self._events)

    @property
    def content(self) -> Any:
        """The game content."""
        return self._content

    @content.setter
    def content(self, value: Any) -> None:
        self._content = value

    @property
    def state(self) -> ProgressionState:
        """The progression state."""
        return self._state

    @state.setter
    def state(self, value: ProgressionState) -> None:
        self._state = value
        self._current_streak = int(getattr(value, "current_streak", 0) or 0)
        self._current_fail_streak = int(getattr(value, "current_fail_streak", 0) or 0)

    @property
    def progression_state(self) -> ProgressionState:
        """Alias for :attr:`state`."""
        return self._state

    @progression_state.setter
    def progression_state(self, value: ProgressionState) -> None:
        self.state = value

    @property
    def events(self) -> Any:
        """The event bus."""
        return self._events

    @events.setter
    def events(self, value: Any) -> None:
        self._events = value
        self._subscribe(value)

    @property
    def event_bus(self) -> Any:
        """Alias for :attr:`events`."""
        return self._events

    @event_bus.setter
    def event_bus(self, value: Any) -> None:
        self._events = value
        self._subscribe(value)

    @property
    def bus(self) -> Any:
        """Alias for :attr:`events`."""
        return self._events

    @property
    def miner(self) -> Any:
        """The miner (for money rewards), if known."""
        if self._miner is not None:
            return self._miner
        if self._engine is not None:
            return _get(self._engine, "miner")
        return None

    @miner.setter
    def miner(self, value: Any) -> None:
        self._miner = value

    @property
    def engine(self) -> Any:
        """The engine, if attached."""
        return self._engine

    @engine.setter
    def engine(self, value: Any) -> None:
        self._engine = value
        if value is not None:
            if self._miner is None:
                self._miner = _get(value, "miner")
            if self._world is None:
                self._world = _get(value, "world")
            bus = _get(value, "events") or _get(value, "event_bus") or _get(value, "bus")
            if bus is not None:
                self._subscribe(bus)

    @property
    def counters(self) -> dict[str, int]:
        """Alias for the state's counters."""
        return self._state.counters

    @property
    def completed(self) -> dict[str, int]:
        """Alias for the state's completed achievements."""
        return self._state.completed

    @property
    def unlocked_functions(self) -> set[str]:
        """Alias for the state's unlocked functions."""
        return self._state.unlocked_functions

    @property
    def unlocked_ores(self) -> set[str]:
        """Alias for the state's unlocked ores."""
        return self._state.unlocked_ores

    @property
    def unlocked_upgrades(self) -> set[str]:
        """Alias for the state's unlocked upgrades."""
        return self._state.unlocked_upgrades

    @property
    def unlocked_modules(self) -> set[str]:
        """Alias for the state's unlocked modules."""
        return self._state.unlocked_modules

    @property
    def unlocked_skins(self) -> set[str]:
        """Alias for the state's unlocked skins."""
        return self._state.unlocked_skins

    @property
    def unlocked_examples(self) -> set[str]:
        """Alias for the state's unlocked examples."""
        return self._state.unlocked_examples

    @property
    def tick(self) -> int:
        """The current tick (from the engine if attached)."""
        if self._engine is not None:
            tick = _get(self._engine, "tick")
            if tick is None:
                tick = _get(self._engine, "current_tick")
            if tick is not None:
                return int(tick)
        return int(self._tick)

    def attach_engine(self, engine: Any) -> None:
        """Attach ``engine`` (miner/tick source and event bus)."""
        self.engine = engine

    def set_engine(self, engine: Any) -> None:
        """Alias for :meth:`attach_engine`."""
        self.attach_engine(engine)

    def bind_engine(self, engine: Any) -> None:
        """Alias for :meth:`attach_engine`."""
        self.attach_engine(engine)

    def _subscribe(self, bus: Any) -> None:
        if bus is None or bus is self._subscribed_bus:
            return
        try:
            bus.subscribe(Moved, self._on_moved)
            bus.subscribe(MineAttempted, self._on_mine_attempted)
            bus.subscribe(OreMined, self._on_ore_mined)
            bus.subscribe(Sold, self._on_sold)
            bus.subscribe(ScriptStarted, self._on_script_started)
            bus.subscribe(ScriptFinished, self._on_script_finished)
            bus.subscribe(TickAdvanced, self._on_tick)
            bus.subscribe(TileRegenerated, self._on_tile_regenerated)
            bus.subscribe(EstimateSubmitted, self._on_estimate_submitted)
            bus.subscribe(UpgradeBought, self._on_upgrade_bought)
        except Exception:
            return
        self._subscribed_bus = bus

    def _publish(self, event: Any) -> None:
        bus = self._events
        if bus is not None and hasattr(bus, "publish"):
            bus.publish(event)
            return
        if self._engine is not None:
            bus = _get(self._engine, "events") or _get(self._engine, "event_bus")
            if bus is not None and hasattr(bus, "publish"):
                bus.publish(event)

    def _biome_id_at(self, x: int, y: int) -> str | None:
        world = self._world
        if world is None and self._engine is not None:
            world = _get(self._engine, "world")
        if world is None:
            return None
        try:
            tile = world.tile_at(x, y, self.tick)
        except Exception:
            return None
        biome_id = _get(tile, "biome_id")
        return str(biome_id) if biome_id else None

    def _on_moved(self, event: Any) -> None:
        x = int(_get(event, "x", 0) or 0)
        y = int(_get(event, "y", 0) or 0)
        self._state.add_counter("tiles_moved", 1)
        distance = max(abs(x), abs(y))
        if distance > self._state.get_counter("max_distance"):
            self._state.counters["max_distance"] = distance
        biome_id = self._biome_id_at(x, y)
        if biome_id:
            counter = f"biome:{biome_id}"
            if self._state.get_counter(counter) == 0:
                self._state.add_counter("biomes_visited", 1)
            self._state.counters[counter] = 1
        self._check_achievements()

    def _on_mine_attempted(self, event: Any) -> None:
        ore_id = _get(event, "ore_id")
        success = bool(_get(event, "success", False))
        reason = _get(event, "reason")
        if reason is None and not success:
            reason = "miss"
        is_attempt = success or reason == "miss"
        if is_attempt:
            self._state.add_counter("attempts:any", 1)
            if ore_id:
                self._state.add_counter(f"attempts:{ore_id}", 1)
            if success:
                self._current_streak += 1
                self._current_fail_streak = 0
                if self._current_streak > self._state.get_counter("streak"):
                    self._state.counters["streak"] = self._current_streak
            else:
                self._current_streak = 0
                self._current_fail_streak += 1
                if self._current_fail_streak > self._state.get_counter("fail_streak"):
                    self._state.counters["fail_streak"] = self._current_fail_streak
                self._state.add_counter(f"fail:{reason}", 1)
            self._state.current_streak = self._current_streak
            self._state.current_fail_streak = self._current_fail_streak
        elif reason:
            self._state.add_counter(f"fail:{reason}", 1)
        self._check_achievements()

    def _on_ore_mined(self, event: Any) -> None:
        amount = int(_get(event, "amount", 1) or 1)
        ore_id = _get(event, "ore_id")
        self._state.add_counter("mined:any", amount)
        if ore_id:
            if amount > 0 and self._state.get_counter(f"mined:{ore_id}") == 0:
                self._state.add_counter("unique_ores_mined", 1)
            self._state.add_counter(f"mined:{ore_id}", amount)
        self._check_achievements()

    def _on_sold(self, event: Any) -> None:
        money = int(_get(event, "money", 0) or 0)
        items = _get(event, "items") or {}
        if money > 0:
            self._state.add_counter("sales", 1)
            self._state.add_counter("money_earned", money)
            if money > self._state.get_counter("largest_sale"):
                self._state.counters["largest_sale"] = money
            distinct = sum(1 for count in items.values() if int(count) > 0)
            if distinct > self._state.get_counter("ores_in_one_sale"):
                self._state.counters["ores_in_one_sale"] = distinct
        self._check_achievements()

    def _on_script_started(self, event: Any) -> None:
        features = {str(feature) for feature in (_get(event, "features") or ())}
        if _get(event, "defines_function"):
            features.add("defines_function")
        for feature in features:
            self._state.counters[f"script_feature:{feature}"] = 1
        if "defines_function" in features:
            self._state.counters["script_defines_function"] = 1
            self._state.counters["scripts_defines_function"] = 1
        self._state.add_counter("scripts_run", 1)
        self._check_achievements()

    def _on_script_finished(self, event: Any) -> None:
        self._state.add_counter("scripts_finished", 1)
        self._check_achievements()

    def _on_tick(self, event: Any) -> None:
        tick = _get(event, "tick")
        if tick is not None:
            self._tick = int(tick)

    def _on_tile_regenerated(self, event: Any) -> None:
        self._state.add_counter("regens", 1)
        self._check_achievements()

    def _on_estimate_submitted(self, event: Any) -> None:
        if _get(event, "good"):
            self._state.add_counter("good_estimates", 1)
        self._check_achievements()

    def _on_upgrade_bought(self, event: Any) -> None:
        self._state.add_counter("upgrades_bought", 1)
        self._check_achievements()

    def handle_event(self, event: Any) -> None:
        """Dispatch ``event`` manually (same logic as subscriptions)."""
        if isinstance(event, Moved):
            self._on_moved(event)
        elif isinstance(event, MineAttempted):
            self._on_mine_attempted(event)
        elif isinstance(event, OreMined):
            self._on_ore_mined(event)
        elif isinstance(event, Sold):
            self._on_sold(event)
        elif isinstance(event, ScriptStarted):
            self._on_script_started(event)
        elif isinstance(event, ScriptFinished):
            self._on_script_finished(event)
        elif isinstance(event, TickAdvanced):
            self._on_tick(event)
        elif isinstance(event, TileRegenerated):
            self._on_tile_regenerated(event)
        elif isinstance(event, EstimateSubmitted):
            self._on_estimate_submitted(event)
        elif isinstance(event, UpgradeBought):
            self._on_upgrade_bought(event)
        else:
            name = type(event).__name__
            if name == "Moved":
                self._on_moved(event)
            elif name == "MineAttempted":
                self._on_mine_attempted(event)
            elif name == "OreMined":
                self._on_ore_mined(event)
            elif name == "Sold":
                self._on_sold(event)
            elif name == "ScriptStarted":
                self._on_script_started(event)
            elif name == "ScriptFinished":
                self._on_script_finished(event)
            elif name == "TickAdvanced":
                self._on_tick(event)
            elif name == "TileRegenerated":
                self._on_tile_regenerated(event)
            elif name == "EstimateSubmitted":
                self._on_estimate_submitted(event)
            elif name == "UpgradeBought":
                self._on_upgrade_bought(event)

    def handle(self, event: Any) -> None:
        """Alias for :meth:`handle_event`."""
        self.handle_event(event)

    def on_event(self, event: Any) -> None:
        """Alias for :meth:`handle_event`."""
        self.handle_event(event)

    def _achievements(self) -> list[Any]:
        raw = _get(self._content, "achievements") if self._content is not None else None
        if raw is None:
            raw = self._content.get("achievements") if isinstance(self._content, dict) else None
        if raw is None:
            return []
        if isinstance(raw, dict):
            return list(raw.values())
        return list(raw)

    def _achievement_by_id(self, achievement_id: str) -> Any:
        raw = _get(self._content, "achievements") if self._content is not None else None
        if isinstance(raw, dict):
            return raw.get(achievement_id)
        for achievement in self._achievements():
            if _get(achievement, "id") == achievement_id:
                return achievement
        return None

    def _criteria_current_target(self, achievement: Any) -> tuple[int, int]:
        criteria = _get(achievement, "criteria")
        criteria_type = _get(criteria, "type")
        if criteria_type == "counter":
            counter = str(_get(criteria, "counter", ""))
            target = int(_get(criteria, "target", 1) or 1)
            current = int(self._state.counters.get(counter, 0))
            return current, target
        if criteria_type == "script_defines_function":
            current = 1
            if not (
                self._state.counters.get("script_feature:defines_function")
                or self._state.counters.get("script_defines_function")
                or self._state.counters.get("scripts_defines_function")
            ):
                current = 0
            return current, 1
        if criteria_type == "script_feature":
            feature = str(_get(criteria, "feature", ""))
            current = 1 if self._state.counters.get(f"script_feature:{feature}") else 0
            return current, 1
        return 0, 1

    def _criteria_met(self, achievement: Any) -> bool:
        current, target = self._criteria_current_target(achievement)
        return current >= target

    def is_available(self, achievement_id: str) -> bool:
        """Return True if the achievement can still be completed."""
        if achievement_id in self._state.completed:
            return False
        achievement = self._achievement_by_id(achievement_id)
        if achievement is None:
            return False
        parent = _get(achievement, "parent")
        if parent is None:
            return True
        return parent in self._state.completed

    def available_achievements(self) -> list[str]:
        """Return ids of achievements that are available (not completed)."""
        result = []
        for achievement in self._achievements():
            achievement_id = _get(achievement, "id")
            if achievement_id and self.is_available(str(achievement_id)):
                result.append(str(achievement_id))
        return result

    def is_achievement_available(self, achievement_id: str) -> bool:
        """Alias for :meth:`is_available`."""
        return self.is_available(achievement_id)

    def available(self, achievement_id: str) -> bool:
        """Alias for :meth:`is_available`."""
        return self.is_available(achievement_id)

    def is_achievement_unlocked(self, achievement_id: str) -> bool:
        """Return True if the achievement is completed."""
        return achievement_id in self._state.completed

    def is_completed(self, achievement_id: str) -> bool:
        """Alias for :meth:`is_achievement_unlocked`."""
        return self.is_achievement_unlocked(achievement_id)

    def _apply_rewards(self, achievement: Any) -> None:
        rewards = _get(achievement, "rewards") or []
        for reward in rewards:
            reward_type = _get(reward, "type")
            reward_id = _get(reward, "id")
            if reward_type == "unlock_function" and reward_id:
                self._state.unlock_function(str(reward_id))
            elif reward_type == "unlock_ore" and reward_id:
                self._state.unlock_ore(str(reward_id))
            elif reward_type == "unlock_upgrade" and reward_id:
                self._state.unlock_upgrade(str(reward_id))
            elif reward_type == "unlock_module" and reward_id:
                self._state.unlock_module(str(reward_id))
            elif reward_type == "unlock_skin" and reward_id:
                self._state.unlock_skin(str(reward_id))
            elif reward_type == "unlock_example" and reward_id:
                self._state.unlock_example(str(reward_id))
            elif reward_type == "money":
                amount = _get(reward, "amount")
                if amount is not None:
                    miner = self.miner
                    if miner is not None:
                        try:
                            miner.money = int(miner.money) + int(amount)
                        except Exception:
                            pass

    def _complete(self, achievement: Any) -> None:
        achievement_id = str(_get(achievement, "id"))
        self._state.complete(achievement_id, self.tick)
        self._apply_rewards(achievement)
        self._publish(AchievementUnlocked(id=achievement_id))

    def _check_achievements(self) -> None:
        if self._checking:
            return
        self._checking = True
        try:
            while True:
                progressed = False
                for achievement in self._achievements():
                    achievement_id = _get(achievement, "id")
                    if not achievement_id:
                        continue
                    achievement_id = str(achievement_id)
                    if not self.is_available(achievement_id):
                        continue
                    if self._criteria_met(achievement):
                        self._complete(achievement)
                        progressed = True
                if not progressed:
                    break
        finally:
            self._checking = False

    def check_achievements(self) -> None:
        """Re-evaluate achievements against the current counters."""
        self._check_achievements()

    def refresh(self) -> None:
        """Alias for :meth:`check_achievements`."""
        self._check_achievements()

    def evaluate(self) -> None:
        """Alias for :meth:`check_achievements`."""
        self._check_achievements()

    def is_ore_unlocked(self, ore_id: str) -> bool:
        """Return True if the ore is unlocked."""
        return self._state.is_ore_unlocked(ore_id)

    def is_function_unlocked(self, name: str) -> bool:
        """Return True if the function is unlocked."""
        return self._state.is_function_unlocked(name)

    def is_upgrade_unlocked(self, upgrade_id: str) -> bool:
        """Return True if the upgrade is unlocked."""
        return self._state.is_upgrade_unlocked(upgrade_id)

    def is_module_unlocked(self, name: str) -> bool:
        """Return True if the module is unlocked."""
        return self._state.is_module_unlocked(name)

    def is_skin_unlocked(self, skin_id: str) -> bool:
        """Return True if the skin is unlocked."""
        return self._state.is_skin_unlocked(skin_id)

    def is_example_unlocked(self, example_id: str) -> bool:
        """Return True if the example script is unlocked."""
        return self._state.is_example_unlocked(example_id)

    def is_unlocked(self, kind: str, ident: str) -> bool:
        """Return True if ``ident`` of ``kind`` is unlocked."""
        return self._state.is_unlocked(kind, ident)

    def requirement_title(self, kind: Any, ident: Any = None) -> str:
        """Title of the achievement that unlocks ``ident`` of ``kind``.

        Accepts ``(kind, id)`` where ``id`` is the locked thing (ore,
        function, upgrade or module) or an achievement id, and also a
        single achievement/thing id.
        """
        if ident is None:
            single = str(kind)
            achievement = self._achievement_by_id(single)
            if achievement is not None:
                title = _get(achievement, "title")
                if title:
                    return str(title)
            for collection_name in ("ores", "functions", "upgrades", "modules"):
                raw = _get(self._content, collection_name) if self._content is not None else None
                if isinstance(raw, dict) and single in raw:
                    unlocked_by = _get(raw[single], "unlocked_by")
                    if unlocked_by:
                        ach = self._achievement_by_id(str(unlocked_by))
                        if ach is not None and _get(ach, "title"):
                            return str(_get(ach, "title"))
                        return str(unlocked_by)
            if achievement is not None:
                return single
            return single.replace("_", " ").title()
        kind_str = str(kind).lower().rstrip("s")
        ident_str = str(ident)
        collection_map = {
            "ore": "ores",
            "function": "functions",
            "upgrade": "upgrades",
            "module": "modules",
        }
        collection_name = collection_map.get(kind_str)
        if collection_name is not None:
            raw = _get(self._content, collection_name) if self._content is not None else None
            entry = raw.get(ident_str) if isinstance(raw, dict) else None
            if entry is None and isinstance(raw, dict):
                entry = None
            if entry is not None:
                unlocked_by = _get(entry, "unlocked_by")
                if unlocked_by:
                    ach = self._achievement_by_id(str(unlocked_by))
                    if ach is not None and _get(ach, "title"):
                        return str(_get(ach, "title"))
                    return str(unlocked_by)
                return ""
        achievement = self._achievement_by_id(ident_str)
        if achievement is not None:
            title = _get(achievement, "title")
            if title:
                return str(title)
        for name in ("ores", "functions", "upgrades", "modules"):
            raw = _get(self._content, name) if self._content is not None else None
            if isinstance(raw, dict) and ident_str in raw:
                unlocked_by = _get(raw[ident_str], "unlocked_by")
                if unlocked_by:
                    ach = self._achievement_by_id(str(unlocked_by))
                    if ach is not None and _get(ach, "title"):
                        return str(_get(ach, "title"))
                    return str(unlocked_by)
                return ""
        return ident_str.replace("_", " ").title()

    def achievement_title(self, *args: Any) -> str:
        """Alias for :meth:`requirement_title`."""
        return self.requirement_title(*args)

    def title_for(self, *args: Any) -> str:
        """Alias for :meth:`requirement_title`."""
        return self.requirement_title(*args)

    def get_requirement_title(self, *args: Any) -> str:
        """Alias for :meth:`requirement_title`."""
        return self.requirement_title(*args)

    def progress(self, achievement_id: str) -> tuple[int, int]:
        """Return ``(current, target)`` progress for an achievement."""
        achievement = self._achievement_by_id(str(achievement_id))
        if achievement is None:
            raise KeyError(str(achievement_id))
        current, target = self._criteria_current_target(achievement)
        return (min(current, target), target)

    def progress_for(self, achievement_id: str) -> tuple[int, int]:
        """Alias for :meth:`progress`."""
        return self.progress(achievement_id)
