"""The tick engine: one FIFO command slot per miner, tick costs and events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from minesim.core.contracts import ContractBoard
from minesim.core.events import (
    ContractExpired,
    ContractGenerated,
    EventBus,
    MinerRemoved,
    MinerSpawned,
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

_ZERO_COST_NAMES = {
    "Biome",
    "Distance",
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
        result = entry.command.execute(self, miner)
        entry.ticket.result = result
        entry.ticket.done = True

    def _activate_next(self, miner: Any) -> None:
        """Promote queued commands until one occupies ``miner`` or it empties.

        Zero-cost commands at the head execute immediately without
        consuming a tick; the first positive-cost command becomes active.
        """
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
            if miner.active is None:
                self._activate_next(miner)
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
