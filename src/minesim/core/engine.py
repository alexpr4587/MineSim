"""The tick engine: one FIFO command slot per drone, tick costs and events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from minesim.core.contracts import ContractBoard
from minesim.core.events import (
    ContractExpired,
    ContractGenerated,
    DroneRemoved,
    DroneSpawned,
    EventBus,
    RefineFinished,
    TickAdvanced,
    TileRegenerated,
)
from minesim.core.items import ItemCatalog
from minesim.core.market import Market
from minesim.core.miner import Drone, PlayerStats
from minesim.core.refinery import Refinery
from minesim.core.warehouse import Warehouse

__all__ = ["AllUnlocked", "GameEngine", "ProgressionView", "Ticket"]

_ZERO_COST_NAMES = {
    "Biome",
    "Distance",
    "Inspect",
    "Inventory",
    "OreInfo",
    "Peek",
    "Position",
    "Price",
    "PriceHistory",
    "Prices",
    "Recipes",
    "RemoveDrone",
    "SpawnDrone",
    "Stats",
    "Stock",
    "RefineryStatus",
    "Contracts",
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
    drone_id: int = 0

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
    drone_id: int = 0


class GameEngine:
    """Runs one FIFO command slot per drone, publishing events."""

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
        self._upgrade_levels: dict[str, int] = {}
        if miner is None:
            drone = Drone.from_config(self.content) if self.content is not None else Drone()
        else:
            drone = miner
        player_stats = getattr(drone, "player_stats", None)
        if player_stats is None:
            player_stats = (
                PlayerStats.from_config(self.content) if self.content is not None else PlayerStats()
            )
            try:
                drone.player_stats = player_stats
            except Exception:
                pass
        self.player_stats: PlayerStats = player_stats
        try:
            drone.id = 0
        except Exception:
            pass
        self._drones: dict[int, Any] = {0: drone}
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
        """Upgrade levels bought so far (shared by all drones)."""
        upgrades = getattr(self.player_stats, "upgrades", None)
        if upgrades is None:
            return self._upgrade_levels
        return upgrades

    @property
    def max_drones(self) -> int:
        """The current fleet size limit (1 + drone_bay level)."""
        return 1 + int(self.upgrade_levels.get("drone_bay", 0))

    # -- fleet ---------------------------------------------------------------

    @property
    def drones(self) -> dict[int, Any]:
        """The fleet, keyed by drone id."""
        return self._drones

    def drone(self, drone_id: int = 0) -> Any:
        """Return the drone with ``drone_id`` (KeyError if unknown)."""
        try:
            return self._drones[int(drone_id)]
        except KeyError:
            raise KeyError(f"unknown drone id {drone_id}") from None

    def has_drone(self, drone_id: int) -> bool:
        """Return True if ``drone_id`` is in the fleet."""
        return int(drone_id) in self._drones

    def spawn_drone(self) -> Any:
        """Add a new drone on the base with the next free id."""
        next_id = 0
        while next_id in self._drones:
            next_id += 1
        drone = Drone(
            id=next_id,
            x=0,
            y=0,
            inventory={},
            player_stats=self.player_stats,
        )
        self._drones[next_id] = drone
        self._next_id = max(self._next_id, next_id + 1)
        self._events.publish(DroneSpawned(id=next_id))
        return drone

    def remove_drone(self, drone_id: int) -> bool:
        """Remove ``drone_id`` from the fleet (never drone 0).

        A drone removed while standing on the base unloads its
        inventory into the warehouse (up to its capacity); otherwise
        the inventory is lost. Returns True when a drone was removed.
        """
        drone_id = int(drone_id)
        if drone_id == 0 or drone_id not in self._drones:
            return False
        drone = self._drones.pop(drone_id)
        try:
            tile = self.world.tile_at(drone.x, drone.y, self.tick)
        except Exception:
            tile = None
        if tile is not None and getattr(tile, "is_base", False):
            for item_id, count in sorted(dict(drone.inventory).items()):
                accepted = self.warehouse.add(item_id, int(count))
                if accepted >= int(count):
                    drone.inventory.pop(item_id, None)
                elif accepted > 0:
                    drone.inventory[item_id] = int(count) - accepted
        try:
            drone.queue.clear()
        except Exception:
            pass
        drone.active = None
        drone.busy_timer = 0
        self._events.publish(DroneRemoved(id=drone_id))
        return True

    # -- legacy single-miner view -------------------------------------------

    @property
    def miner(self) -> Any:
        """Drone 0 (kept for backwards compatibility)."""
        return self._drones[0]

    @miner.setter
    def miner(self, value: Any) -> None:
        player_stats = getattr(value, "player_stats", None)
        if player_stats is not None:
            self.player_stats = player_stats
        try:
            value.id = 0
        except Exception:
            pass
        self._drones[0] = value

    @property
    def is_idle(self) -> bool:
        """Return True when no drone has a command active or queued."""
        return all(drone.active is None and not drone.queue for drone in self._drones.values())

    @property
    def pending(self) -> int:
        """Number of commands not yet done across the fleet."""
        count = 0
        for drone in self._drones.values():
            count += len(drone.queue)
            if drone.active is not None:
                count += 1
        return count

    @property
    def active_command(self) -> Any:
        """The command currently occupying drone 0, if any."""
        active = self._drones[0].active
        return active.command if active is not None else None

    def active_command_for(self, drone_id: int = 0) -> Any:
        """The command currently occupying ``drone_id``, if any."""
        active = self.drone(drone_id).active
        return active.command if active is not None else None

    @property
    def queue(self) -> list[Any]:
        """Drone 0's queued commands (excluding the active one)."""
        return [entry.command for entry in self._drones[0].queue]

    # -- scheduling ----------------------------------------------------------

    def _is_static_zero_cost(self, command: Any) -> bool:
        if type(command).__name__ in _ZERO_COST_NAMES:
            return True
        result = getattr(command, "is_zero_cost", None)
        return bool(result) if result is not None else False

    def _execute_now(self, entry: _Entry) -> None:
        drone = self._drones[entry.drone_id]
        result = entry.command.execute(self, drone)
        entry.ticket.result = result
        entry.ticket.done = True

    def _activate_next(self, drone: Any) -> None:
        """Promote queued commands until one occupies ``drone`` or it empties.

        Zero-cost commands at the head execute immediately without
        consuming a tick; the first positive-cost command becomes active.
        """
        while drone.active is None and drone.queue:
            entry = drone.queue[0]
            try:
                cost = int(entry.command.cost_ticks(self, drone))
            except Exception:
                cost = 0
            if cost <= 0:
                drone.queue.popleft()
                self._execute_now(entry)
                continue
            drone.queue.popleft()
            entry.remaining = cost
            drone.active = entry
            drone.busy_timer = cost

    def submit(self, command: Any, drone_id: int = 0) -> Ticket:
        """Submit ``command`` to ``drone_id`` and return its ticket.

        Zero-cost commands execute immediately on submit; other
        commands run FIFO per drone, occupying it for their tick cost.
        """
        drone = self.drone(drone_id)
        ticket = Ticket(command=command, drone_id=int(drone_id))
        entry = _Entry(command=command, ticket=ticket, drone_id=int(drone_id))
        if self._is_static_zero_cost(command):
            self._execute_now(entry)
            return ticket
        drone.queue.append(entry)
        if drone.active is None:
            self._activate_next(drone)
        return ticket

    def step(self) -> None:
        """Advance the engine by one tick, processing drones by id."""
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
        for drone_id in sorted(self._drones):
            drone = self._drones[drone_id]
            if drone.active is None:
                self._activate_next(drone)
            active = drone.active
            if active is None:
                continue
            active.remaining -= 1
            drone.busy_timer = max(0, active.remaining)
            if active.remaining <= 0:
                drone.active = None
                drone.busy_timer = 0
                self._execute_now(active)
                self._activate_next(drone)

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
