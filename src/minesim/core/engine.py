"""The tick engine: one FIFO command slot per miner, tick costs and events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from minesim.core.commands import Move
from minesim.core.contracts import ContractBoard
from minesim.core.events import (
    ContractExpired,
    ContractGenerated,
    EnergySpent,
    EventBus,
    MinerOverheated,
    MinerRecovered,
    MinerRemoved,
    MinerRescued,
    MinerSpawned,
    MinerStranded,
    RefineFinished,
    TickAdvanced,
    TileRegenerated,
    WorldEventEnded,
    WorldEventStarted,
)
from minesim.core.items import ItemCatalog
from minesim.core.market import Market
from minesim.core.miner import Miner, PlayerStats
from minesim.core.refinery import Refinery
from minesim.core.warehouse import Warehouse
from minesim.core.worldevents import WorldEvents

__all__ = ["AllUnlocked", "GameEngine", "ProgressionView", "Ticket"]


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


_ZERO_COST_NAMES = {
    "Battery",
    "Biome",
    "Climate",
    "Distance",
    "EnergyCost",
    "Events",
    "Layer",
    "Layers",
    "Inspect",
    "Inventory",
    "OreInfo",
    "Peek",
    "Position",
    "Price",
    "PriceHistory",
    "Prices",
    "Recipes",
    "RemoveMiner",
    "Stats",
    "Stock",
    "RefineryStatus",
    "Contracts",
    "MinerId",
    "Miners",
    "SubmitEstimate",
    "Temperature",
    "Tick",
}


class ProgressionView(Protocol):
    """Read-only view of what the player has unlocked."""

    def is_ore_unlocked(self, ore_id: str) -> bool:
        """Return True if the ore is unlocked."""
        ...

    def is_recipe_unlocked(self, recipe_id: str) -> bool:
        """Return True if the recipe is unlocked."""
        ...

    def is_feature_unlocked(self, feature_id: str) -> bool:
        """Return True if the feature is unlocked."""
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

    def is_recipe_unlocked(self, recipe_id: str) -> bool:
        """Return True for every recipe."""
        return True

    def is_feature_unlocked(self, feature_id: str) -> bool:
        """Return True for every feature."""
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
    miner_id: int = 0

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
    miner_id: int = 0
    refused_reason: str | None = None
    refused_cost: int = 0


class GameEngine:
    """Runs one FIFO command slot per miner, publishing events."""

    def __init__(
        self,
        world: Any,
        miner: Any = None,
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
        self.content = content if content is not None else getattr(world, "content", None)
        self._events = events if events is not None else EventBus()
        self.progression_view = progression_view if progression_view is not None else AllUnlocked()
        self.progression = self.progression_view
        self.tick: int = 0
        self.attempt_counter: int = 0
        shared_memory = kwargs.get("shared_memory")
        self.shared_memory: dict[str, Any] = (
            dict(shared_memory) if isinstance(shared_memory, dict) else {}
        )
        self._upgrade_levels: dict[str, int] = {}
        if miner is None:
            miner = Miner.from_config(self.content) if self.content is not None else Miner()
        else:
            miner = miner
        player_stats = getattr(miner, "player_stats", None)
        if player_stats is None:
            player_stats = (
                PlayerStats.from_config(self.content) if self.content is not None else PlayerStats()
            )
            try:
                miner.player_stats = player_stats
            except Exception:
                pass
        self.player_stats: PlayerStats = player_stats
        try:
            miner.id = 0
        except Exception:
            pass
        self._miners: dict[int, Any] = {0: miner}
        self._next_id = 1
        config = getattr(self.content, "config", None)
        self.catalog: ItemCatalog = kwargs.get("catalog") or ItemCatalog(self.content)
        self.warehouse: Warehouse = kwargs.get("warehouse") or Warehouse(
            int(getattr(config, "warehouse_start_capacity", 0) or 0)
        )
        self.market: Market | None = kwargs.get("market")
        if self.market is None and config is not None:
            self.market = Market(
                self.seed,
                self.catalog,
                config,
                getattr(self.content, "market", None),
            )
        recipes = getattr(self.content, "recipes", None)
        start_slots = int(getattr(config, "furnace_start_slots", 1) or 1)
        self.refinery: Refinery = kwargs.get("refinery") or Refinery(
            recipes,
            start_slots,
            self.progression_view,
            self.warehouse,
        )
        if getattr(self.refinery, "warehouse", None) is None:
            self.refinery.set_warehouse(self.warehouse)
        self.contracts: ContractBoard = kwargs.get("contracts") or ContractBoard(
            self.seed,
            self.catalog,
            config,
            recipes,
            self.progression_view,
        )
        self.world_events: WorldEvents | None = kwargs.get("world_events")
        if self.world_events is None and config is not None:
            self.world_events = WorldEvents(self.seed, config, self.content)
        self._active_world_events: dict[int, Any] = {}
        self._prime_world_events()

    # -- world events --------------------------------------------------------

    def _apply_world_event_start(self, event: Any) -> None:
        if self.market is not None and event.kind == "market_news" and event.item:
            try:
                self.market.apply_news(str(event.item), float(event.factor), int(event.ends))
            except Exception:
                pass

    def _prime_world_events(self) -> None:
        """Remember the events active at load time without publishing them."""
        if self.world_events is None:
            return
        active = {event.id: event for event in self.world_events.active_at(self.tick)}
        self._active_world_events = active
        for event in active.values():
            self._apply_world_event_start(event)

    def _sync_world_events(self) -> None:
        """Publish started/ended events and apply or expire news shocks."""
        if self.world_events is None:
            return
        current = {event.id: event for event in self.world_events.active_at(self.tick)}
        previous = self._active_world_events
        for event_id in sorted(previous):
            if event_id not in current:
                event = previous[event_id]
                self._events.publish(WorldEventEnded(kind=str(event.kind), id=int(event_id)))
        for event_id in sorted(current):
            if event_id not in previous:
                event = current[event_id]
                self._apply_world_event_start(event)
                self._events.publish(WorldEventStarted(kind=str(event.kind), id=int(event_id)))
        self._active_world_events = current

    # -- compatibility properties -------------------------------------------

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
        """Upgrade levels bought so far (shared by all miners)."""
        upgrades = getattr(self.player_stats, "upgrades", None)
        if upgrades is None:
            return self._upgrade_levels
        return upgrades

    @property
    def max_miners(self) -> int:
        """The current fleet size limit (1 + miner_bay level)."""
        return 1 + int(self.upgrade_levels.get("miner_bay", 0))

    # -- fleet ---------------------------------------------------------------

    @property
    def miners(self) -> dict[int, Any]:
        """The fleet, keyed by miner id."""
        return self._miners

    def miner_by_id(self, miner_id: int = 0) -> Any:
        """Return the miner with ``miner_id`` (KeyError if unknown)."""
        try:
            return self._miners[int(miner_id)]
        except KeyError:
            raise KeyError(f"unknown miner id {miner_id}") from None

    def has_miner(self, miner_id: int) -> bool:
        """Return True if ``miner_id`` is in the fleet."""
        return int(miner_id) in self._miners

    def spawn_miner(self) -> Any:
        """Add a new miner on the base with the next free id."""
        next_id = 0
        while next_id in self._miners:
            next_id += 1
        miner = Miner(
            id=next_id,
            x=0,
            y=0,
            inventory={},
            player_stats=self.player_stats,
        )
        self._miners[next_id] = miner
        self._next_id = max(self._next_id, next_id + 1)
        self._events.publish(MinerSpawned(id=next_id))
        return miner

    def remove_miner(self, miner_id: int) -> bool:
        """Remove ``miner_id`` from the fleet (never miner 0).

        A miner removed while standing on the base unloads its
        inventory into the warehouse (up to its capacity); otherwise
        the inventory is lost. Returns True when a miner was removed.
        """
        miner_id = int(miner_id)
        if miner_id == 0 or miner_id not in self._miners:
            return False
        miner = self._miners.pop(miner_id)
        try:
            tile = self.world.tile_at(
                miner.x, miner.y, self.tick, layer=int(getattr(miner, "layer", 0) or 0)
            )
        except Exception:
            tile = None
        if (
            tile is not None
            and getattr(tile, "is_base", False)
            and int(getattr(miner, "layer", 0) or 0) == 0
        ):
            for item_id, count in sorted(dict(miner.inventory).items()):
                accepted = self.warehouse.add(item_id, int(count))
                if accepted >= int(count):
                    miner.inventory.pop(item_id, None)
                elif accepted > 0:
                    miner.inventory[item_id] = int(count) - accepted
        try:
            miner.queue.clear()
        except Exception:
            pass
        miner.active = None
        miner.busy_timer = 0
        self._events.publish(MinerRemoved(id=miner_id))
        return True

    # -- legacy single-miner view -------------------------------------------

    @property
    def miner(self) -> Any:
        """Miner 0 (kept for backwards compatibility)."""
        return self._miners[0]

    @miner.setter
    def miner(self, value: Any) -> None:
        player_stats = getattr(value, "player_stats", None)
        if player_stats is not None:
            self.player_stats = player_stats
        try:
            value.id = 0
        except Exception:
            pass
        self._miners[0] = value

    @property
    def is_idle(self) -> bool:
        """Return True when no miner has a command active or queued."""
        return all(miner.active is None and not miner.queue for miner in self._miners.values())

    @property
    def pending(self) -> int:
        """Number of commands not yet done across the fleet."""
        count = 0
        for miner in self._miners.values():
            count += len(miner.queue)
            if miner.active is not None:
                count += 1
        return count

    @property
    def active_command(self) -> Any:
        """The command currently occupying miner 0, if any."""
        active = self._miners[0].active
        return active.command if active is not None else None

    def active_command_for(self, miner_id: int = 0) -> Any:
        """The command currently occupying ``miner_id``, if any."""
        active = self.miner_by_id(miner_id).active
        return active.command if active is not None else None

    @property
    def queue(self) -> list[Any]:
        """Miner 0's queued commands (excluding the active one)."""
        return [entry.command for entry in self._miners[0].queue]

    # -- scheduling ----------------------------------------------------------

    def _is_static_zero_cost(self, command: Any) -> bool:
        if type(command).__name__ in _ZERO_COST_NAMES:
            return True
        result = getattr(command, "is_zero_cost", None)
        return bool(result) if result is not None else False

    def _execute_now(self, entry: _Entry) -> None:
        miner = self._miners[entry.miner_id]
        if entry.refused_reason is not None:
            result = {
                "ok": False,
                "reason": entry.refused_reason,
                "cost": int(entry.refused_cost),
                "energy": int(getattr(miner, "energy", 0) or 0),
            }
        else:
            result = entry.command.execute(self, miner)
        entry.ticket.result = result
        entry.ticket.done = True

    def _command_energy_cost(self, command: Any, miner: Any) -> int:
        """Return the energy ``command`` needs to start for ``miner``."""
        method = getattr(command, "energy_cost", None)
        if not callable(method):
            return 0
        try:
            return max(0, int(method(self, miner)))
        except Exception:
            return 0

    def _spend_energy(self, miner: Any, amount: int) -> None:
        amount = max(0, int(amount))
        if amount <= 0:
            return
        miner.energy = max(0, int(getattr(miner, "energy", 0) or 0) - amount)
        self._events.publish(EnergySpent(miner_id=int(getattr(miner, "id", 0) or 0), amount=amount))

    # -- climate -------------------------------------------------------------

    def _layer_definition(self, layer: int) -> Any:
        layers = getattr(self.content, "layers", None)
        if isinstance(layers, dict):
            return layers.get(int(layer))
        return None

    def layer_heat(self, layer: int) -> int:
        """Return the heat level of ``layer`` (0 when unknown)."""
        return int(_get_attr(self._layer_definition(layer), "heat", 0) or 0)

    def _hot_layer_min_heat(self) -> int:
        config = getattr(self.content, "config", None)
        return max(0, int(_get_attr(config, "hot_layer_min_heat", 1) or 0))

    def _is_hot_layer(self, layer: int) -> bool:
        return self.layer_heat(layer) >= self._hot_layer_min_heat()

    def _upgrade_change(self, upgrade_id: str, stat: str) -> int:
        upgrades = getattr(self.content, "upgrades", None)
        if not isinstance(upgrades, dict):
            return 0
        upgrade = upgrades.get(upgrade_id)
        changes = getattr(upgrade, "stat_changes", None)
        if not callable(changes):
            return 0
        try:
            return int(changes().get(stat, 0) or 0)
        except Exception:
            return 0

    def airflow(self) -> int:
        """Return how many miners can work in hot layers without overload."""
        config = getattr(self.content, "config", None)
        start = max(0, int(_get_attr(config, "airflow_start", 0) or 0))
        level = max(0, int(self.upgrade_levels.get("ventilation", 0) or 0))
        return start + level * self._upgrade_change("ventilation", "airflow_bonus")

    def miners_in_hot_layers(self) -> int:
        """Return the number of miners currently in hot layers."""
        count = 0
        for miner in self._miners.values():
            if self._is_hot_layer(int(_get_attr(miner, "layer", 0) or 0)):
                count += 1
        return count

    def overload(self) -> float:
        """Return the current airflow overload factor for hot layers."""
        config = getattr(self.content, "config", None)
        penalty = max(0.0, float(_get_attr(config, "overload_penalty", 0.0) or 0.0))
        excess = max(0, self.miners_in_hot_layers() - self.airflow())
        return penalty * excess

    def climate_state(self, miner: Any = None) -> dict[str, Any]:
        """Return the climate seen by ``miner`` (defaults to miner 0)."""
        if miner is None:
            miner = self.miner
        layer = int(_get_attr(miner, "layer", 0) or 0)
        return {
            "layer": layer,
            "heat": self.layer_heat(layer),
            "airflow": self.airflow(),
            "miners_in_hot_layers": self.miners_in_hot_layers(),
            "overload": self.overload(),
        }

    def _cooling_reduction(self) -> float:
        level = max(0, int(self.upgrade_levels.get("cooling", 0) or 0))
        percent = self._upgrade_change("cooling", "heat_gain_reduction_percent")
        return max(0.0, min(1.0, (level * percent) / 100.0))

    def _refuse_all_overheated(self, miner: Any) -> None:
        """Refuse the active and queued commands of an overheated miner."""
        entries = []
        if miner.active is not None:
            entries.append(miner.active)
            miner.active = None
        entries.extend(miner.queue)
        miner.queue.clear()
        miner.busy_timer = 0
        for entry in entries:
            entry.refused_reason = "overheated"
            entry.refused_cost = 0
            self._execute_now(entry)

    def _start_overheat(self, miner: Any) -> None:
        config = getattr(self.content, "config", None)
        overheat_at = max(1, int(_get_attr(config, "overheat_at", 100) or 100))
        cooldown = max(0, int(_get_attr(config, "cooldown_ticks", 0) or 0))
        miner.temperature = float(overheat_at)
        miner.cooldown_remaining = cooldown
        self._events.publish(MinerOverheated(miner_id=int(_get_attr(miner, "id", 0) or 0)))
        if cooldown > 0:
            self._refuse_all_overheated(miner)
            return
        miner.temperature = float(_get_attr(config, "cooldown_temperature", 50) or 0)
        self._events.publish(MinerRecovered(miner_id=int(_get_attr(miner, "id", 0) or 0)))

    def _update_cooldown(self, miner: Any) -> bool:
        """Advance a shutdown; return True when this tick is skipped."""
        remaining = max(0, int(_get_attr(miner, "cooldown_remaining", 0) or 0))
        if remaining <= 0:
            return False
        remaining -= 1
        miner.cooldown_remaining = remaining
        if remaining > 0:
            return True
        config = getattr(self.content, "config", None)
        miner.temperature = float(_get_attr(config, "cooldown_temperature", 50) or 0)
        self._events.publish(MinerRecovered(miner_id=int(_get_attr(miner, "id", 0) or 0)))
        return True

    def _apply_climate(self, miner: Any, active: bool) -> bool:
        """Apply heat or cooling; return True when the miner overheated."""
        config = getattr(self.content, "config", None)
        layer = int(_get_attr(miner, "layer", 0) or 0)
        heat = self.layer_heat(layer)
        temperature = max(0.0, float(_get_attr(miner, "temperature", 0.0) or 0.0))
        cool_rate = max(0.0, float(_get_attr(config, "cool_rate", 0.0) or 0.0))
        if layer == 0 or self._on_station(miner):
            miner.temperature = max(0.0, temperature - cool_rate)
            return False
        if not active or heat <= 0 or heat < self._hot_layer_min_heat():
            miner.temperature = temperature
            return False
        gain = max(0.0, float(_get_attr(config, "heat_gain_per_level", 0.0) or 0.0))
        gain *= float(heat)
        gain *= 1.0 + self.overload()
        gain *= 1.0 - self._cooling_reduction()
        overheat_at = max(1, int(_get_attr(config, "overheat_at", 100) or 100))
        temperature = min(float(overheat_at), temperature + gain)
        miner.temperature = temperature
        if temperature >= overheat_at:
            self._start_overheat(miner)
            return True
        return False

    def _activate_next(self, miner: Any) -> None:
        """Promote queued commands until one occupies ``miner`` or it empties.

        Zero-cost commands at the head execute immediately without
        consuming a tick; the first positive-cost command becomes active.
        A command the miner cannot afford is refused after one tick
        without spending anything.
        """
        if int(_get_attr(miner, "cooldown_remaining", 0) or 0) > 0:
            entries = list(miner.queue)
            miner.queue.clear()
            for entry in entries:
                entry.refused_reason = "overheated"
                entry.refused_cost = 0
                self._execute_now(entry)
            return
        while miner.active is None and miner.queue:
            entry = miner.queue[0]
            try:
                cost = int(entry.command.cost_ticks(self, miner))
            except Exception:
                cost = 0
            if cost <= 0:
                miner.queue.popleft()
                self._execute_now(entry)
                continue
            miner.queue.popleft()
            energy = self._command_energy_cost(entry.command, miner)
            if energy > int(getattr(miner, "energy", 0) or 0):
                entry.refused_reason = "low_energy"
                entry.refused_cost = energy
                entry.remaining = 1
                miner.active = entry
                miner.busy_timer = 1
                continue
            self._spend_energy(miner, energy)
            entry.remaining = cost
            miner.active = entry
            miner.busy_timer = cost

    def submit(self, command: Any, miner_id: int = 0) -> Ticket:
        """Submit ``command`` to ``miner_id`` and return its ticket.

        Zero-cost commands execute immediately on submit; other
        commands run FIFO per miner, occupying it for their tick cost.
        """
        miner = self.miner_by_id(miner_id)
        ticket = Ticket(command=command, miner_id=int(miner_id))
        entry = _Entry(command=command, ticket=ticket, miner_id=int(miner_id))
        if self._is_static_zero_cost(command):
            self._execute_now(entry)
            return ticket
        if int(_get_attr(miner, "cooldown_remaining", 0) or 0) > 0:
            entry.refused_reason = "overheated"
            self._execute_now(entry)
            return ticket
        miner.queue.append(entry)
        if miner.active is None:
            self._activate_next(miner)
        return ticket

    def step(self) -> None:
        """Advance the engine by one tick, processing miners by id."""
        self.tick += 1
        self._events.publish(TickAdvanced(tick=self.tick))
        advance_all = getattr(self.world, "advance_all", None)
        if callable(advance_all):
            try:
                regenerated = advance_all(self.tick)
            except Exception:
                regenerated = None
            if regenerated:
                for layer, x, y in regenerated:
                    self._events.publish(TileRegenerated(x=x, y=y, layer=layer))
        else:
            advance = getattr(self.world, "advance", None)
            if callable(advance):
                try:
                    regenerated = advance(self.tick)
                except Exception:
                    regenerated = None
                if regenerated:
                    for x, y in regenerated:
                        self._events.publish(TileRegenerated(x=x, y=y))
        self._sync_world_events()
        if self.market is not None:
            self.market.advance(self.tick)
        if self.refinery is not None:
            for finished in self.refinery.advance(self.tick):
                self._events.publish(
                    RefineFinished(
                        recipe=str(finished.get("recipe", "")),
                        times=int(finished.get("times", 1)),
                        outputs=dict(finished.get("outputs", {})),
                    )
                )
        if self.contracts is not None:
            generated, expired = self.contracts.advance(self.tick)
            for contract in generated:
                self._events.publish(ContractGenerated(id=int(contract.id)))
            for contract in expired:
                self._events.publish(ContractExpired(id=int(contract.id)))
        for miner_id in sorted(self._miners):
            miner = self._miners[miner_id]
            if self._update_cooldown(miner):
                continue
            if miner.active is None:
                self._activate_next(miner)
            if self._apply_climate(miner, miner.active is not None):
                continue
            active = miner.active
            if active is None:
                continue
            active.remaining -= 1
            miner.busy_timer = max(0, active.remaining)
            if active.remaining <= 0:
                miner.active = None
                miner.busy_timer = 0
                self._execute_now(active)
                self._activate_next(miner)
        self._update_stranding()

    # -- energy and rescue ---------------------------------------------------

    def _on_station(self, miner: Any) -> bool:
        """Return True when ``miner`` stands on a base or shaft station."""
        world = getattr(self, "world", None)
        if world is None:
            return True
        try:
            tile = world.tile_at(
                int(_get_attr(miner, "x", 0)),
                int(_get_attr(miner, "y", 0)),
                self.tick,
                layer=int(_get_attr(miner, "layer", 0) or 0),
            )
        except Exception:
            return True
        return bool(_get_attr(tile, "is_base", False))

    def _move_energy_cost(self, miner: Any) -> int:
        return self._command_energy_cost(Move(), miner)

    def _update_stranding(self) -> None:
        """Mark miners that cannot afford a move and rescue them in time."""
        config = getattr(self.content, "config", None)
        rescue_ticks = max(0, int(_get_attr(config, "rescue_ticks", 600) or 0))
        rescue_fraction = float(_get_attr(config, "rescue_energy_fraction", 0.25) or 0.0)
        rescue_loses = bool(_get_attr(config, "rescue_loses_inventory", True))
        for miner_id in sorted(self._miners):
            miner = self._miners[miner_id]
            if self._on_station(miner) or int(getattr(miner, "energy", 0) or 0) >= int(
                self._move_energy_cost(miner)
            ):
                if getattr(miner, "stranded_since", None) is not None:
                    miner.stranded_since = None
                continue
            stranded_since = getattr(miner, "stranded_since", None)
            if stranded_since is None:
                miner.stranded_since = self.tick
                self._events.publish(MinerStranded(miner_id=int(miner_id)))
                stranded_since = self.tick
            if self.tick - int(stranded_since) >= rescue_ticks:
                self._rescue_miner(miner, rescue_fraction, rescue_loses)

    def _rescue_miner(self, miner: Any, fraction: float, loses_inventory: bool) -> None:
        """Tow a stranded miner to the station on its current layer."""
        lost: dict[str, int] = {}
        if loses_inventory:
            lost = {
                str(item_id): int(count)
                for item_id, count in dict(getattr(miner, "inventory", {}) or {}).items()
                if int(count) > 0
            }
            try:
                miner.inventory.clear()
            except Exception:
                pass
        miner.x = 0
        miner.y = 0
        capacity = max(0, int(getattr(miner, "battery_capacity", 0) or 0))
        miner.energy = max(0, min(capacity, int(capacity * max(0.0, float(fraction)))))
        miner.stranded_since = None
        self._events.publish(
            MinerRescued(
                miner_id=int(getattr(miner, "id", 0) or 0),
                lost_items=lost,
            )
        )

    def run_until_idle(self, max_ticks: int = 10000) -> None:
        """Step until idle or ``max_ticks`` ticks have passed."""
        stepped = 0
        while not self.is_idle and stepped < int(max_ticks):
            self.step()
            stepped += 1

    def run(self, max_ticks: int = 10000) -> None:
        """Alias for :meth:`run_until_idle`."""
        self.run_until_idle(max_ticks)

    # -- refinery and contracts ----------------------------------------------

    def start_refine(self, recipe_id: str, times: int = 1) -> dict[str, Any]:
        """Start a refinery job immediately, as the UI does."""
        try:
            job = self.refinery.start(recipe_id, times, self.warehouse, self.tick)
        except KeyError:
            return {"ok": False, "reason": "unknown_recipe", "recipe": str(recipe_id)}
        except ValueError as exc:
            return {"ok": False, "reason": str(exc), "recipe": str(recipe_id)}
        from minesim.core.events import RefineStarted

        self._events.publish(RefineStarted(recipe=str(recipe_id), times=int(times)))
        return {
            "ok": True,
            "recipe": str(recipe_id),
            "times": int(job.times),
            "duration": int(job.duration),
            "finish_tick": int(job.finish_tick),
        }

    def refine(self, recipe_id: str, times: int = 1) -> dict[str, Any]:
        """Alias for :meth:`start_refine`."""
        return self.start_refine(recipe_id, times)

    def refinery_status(self) -> list[dict[str, Any]]:
        """Return the running refinery jobs."""
        return self.refinery.status()

    def contract_status(self) -> list[dict[str, Any]]:
        """Return the open delivery contracts."""
        return self.contracts.status()

    def deliver_contract(self, contract_id: int) -> dict[str, Any]:
        """Deliver a contract immediately, as the UI does."""
        try:
            reward = self.contracts.deliver(int(contract_id), self.warehouse)
        except KeyError:
            return {"ok": False, "reason": "unknown_contract", "id": int(contract_id)}
        except ValueError as exc:
            return {"ok": False, "reason": str(exc), "id": int(contract_id)}
        self.miner.money += int(reward)
        self.miner.stats.total_earned += int(reward)
        from minesim.core.events import ContractDelivered

        self._events.publish(ContractDelivered(id=int(contract_id), reward=int(reward)))
        return {
            "ok": True,
            "id": int(contract_id),
            "reward": int(reward),
            "money": int(self.miner.money),
            "total_money": int(self.miner.money),
            "balance": int(self.miner.money),
        }

    def sell_stock(self, item: str, amount: int | None = None) -> dict[str, Any]:
        """Sell warehouse stock immediately, as the UI does."""
        try:
            self.catalog.get(item)
        except Exception:
            return {"ok": False, "reason": "unknown_item", "item": item}
        stock = int(self.warehouse.count(item))
        quantity = stock if amount is None else max(0, min(int(amount), stock))
        index = float(self.market.index(item)) if self.market is not None else 1.0
        if quantity <= 0:
            return {
                "ok": True,
                "item": item,
                "amount": 0,
                "money": 0,
                "avg_index": index,
                "stock": stock,
                "total_money": int(self.miner.money),
                "balance": int(self.miner.money),
            }
        if self.market is not None:
            money = int(self.market.sell(item, quantity))
        else:
            money = int(self.catalog.base_value(item)) * quantity
        self.warehouse.remove(item, quantity)
        self.miner.money += money
        if money > 0:
            self.miner.stats.total_earned += money
            self.miner.stats.sales += 1
            from minesim.core.events import StockSold

            self._events.publish(StockSold(item=item, amount=quantity, money=money))
        return {
            "ok": True,
            "item": item,
            "amount": quantity,
            "money": money,
            "earned": money,
            "avg_index": index,
            "stock": int(self.warehouse.count(item)),
            "total_money": int(self.miner.money),
            "balance": int(self.miner.money),
        }
