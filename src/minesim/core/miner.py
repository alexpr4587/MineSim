"""Miners and the player-wide stats shared by a fleet."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from minesim.core.direction import Direction

__all__ = ["Miner", "MinerStats", "PlayerStats"]


@dataclass(slots=True)
class MinerStats:
    """Aggregate counters tracked for the player (used by API and progression)."""

    attempts: dict[str, int] = field(default_factory=dict)
    successes: dict[str, int] = field(default_factory=dict)
    total_mined: int = 0
    total_earned: int = 0
    tiles_moved: int = 0
    sales: int = 0

    def record_attempt(self, ore_id: str, success: bool) -> None:
        """Record one mining attempt for ``ore_id``."""
        self.attempts[ore_id] = self.attempts.get(ore_id, 0) + 1
        if success:
            self.successes[ore_id] = self.successes.get(ore_id, 0) + 1
            self.total_mined += 1

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the stats."""
        return {
            "attempts": dict(self.attempts),
            "successes": dict(self.successes),
            "total_mined": self.total_mined,
            "total_earned": self.total_earned,
            "tiles_moved": self.tiles_moved,
            "sales": self.sales,
        }

    @classmethod
    def from_dict(cls, data: Any) -> MinerStats:
        """Rebuild aggregate stats from their :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            data = {}
        return cls(
            attempts={str(k): int(v) for k, v in dict(data.get("attempts", {})).items()},
            successes={str(k): int(v) for k, v in dict(data.get("successes", {})).items()},
            total_mined=int(data.get("total_mined", 0)),
            total_earned=int(data.get("total_earned", 0)),
            tiles_moved=int(data.get("tiles_moved", 0)),
            sales=int(data.get("sales", 0)),
        )

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(slots=True)
class PlayerStats:
    """Money, upgrades and aggregate stats shared by every miner."""

    money: int = 0
    capacity: int = 10
    tool_power: int = 1
    tool_tier: int = 0
    move_ticks: int = 4
    scan_radius: int = 0
    battery_capacity: int = 300
    charge_rate: int = 10
    stats: MinerStats = field(default_factory=MinerStats)
    upgrades: dict[str, int] = field(default_factory=dict)
    estimates: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stats is None:
            self.stats = MinerStats()
        if isinstance(self.stats, dict):
            self.stats = MinerStats.from_dict(self.stats)
        if self.upgrades is None:
            self.upgrades = {}
        if self.estimates is None:
            self.estimates = {}

    @classmethod
    def from_config(cls, content: Any) -> PlayerStats:
        """Create player stats with the start values from ``content.config``."""
        config = content.config
        return cls(
            money=0,
            capacity=int(config.start_capacity),
            tool_power=int(config.start_tool_power),
            tool_tier=int(config.start_tool_tier),
            move_ticks=int(config.move_ticks),
            scan_radius=int(config.start_scan_radius),
            battery_capacity=int(config.battery_start),
            charge_rate=int(config.charge_rate),
        )

    @classmethod
    def from_dict(cls, data: Any, content: Any = None) -> PlayerStats:
        """Rebuild player stats from their :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            data = {}
        default_capacity = 10
        default_power = 1
        default_move = 4
        default_battery = 300
        default_charge = 10
        if content is not None:
            config = getattr(content, "config", None)
            default_capacity = int(getattr(config, "start_capacity", default_capacity))
            default_power = int(getattr(config, "start_tool_power", default_power))
            default_move = int(getattr(config, "move_ticks", default_move))
            default_battery = int(getattr(config, "battery_start", default_battery))
            default_charge = int(getattr(config, "charge_rate", default_charge))
        return cls(
            money=int(data.get("money", 0)),
            capacity=int(data.get("capacity", default_capacity)),
            tool_power=int(data.get("tool_power", default_power)),
            tool_tier=int(data.get("tool_tier", 0)),
            move_ticks=int(data.get("move_ticks", default_move)),
            scan_radius=int(data.get("scan_radius", 0)),
            battery_capacity=int(data.get("battery_capacity", default_battery)),
            charge_rate=int(data.get("charge_rate", default_charge)),
            stats=MinerStats.from_dict(data.get("stats")),
            upgrades={str(k): int(v) for k, v in dict(data.get("upgrades", {})).items()},
            estimates={str(k): int(v) for k, v in dict(data.get("estimates", {})).items()},
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the player stats."""
        return {
            "money": self.money,
            "capacity": self.capacity,
            "tool_power": self.tool_power,
            "tool_tier": self.tool_tier,
            "move_ticks": self.move_ticks,
            "scan_radius": self.scan_radius,
            "battery_capacity": self.battery_capacity,
            "charge_rate": self.charge_rate,
            "stats": self.stats.to_dict(),
            "upgrades": dict(self.upgrades),
            "estimates": dict(self.estimates),
        }


@dataclass(slots=True)
class Miner:
    """One mining miner: position, inventory and its own command slot.

    Money, upgrades and aggregate statistics live in the shared
    :class:`PlayerStats` referenced by :attr:`player_stats`.
    """

    id: int = 0
    x: int = 0
    y: int = 0
    layer: int = 0
    facing: Direction = Direction.NORTH
    inventory: dict[str, int] = field(default_factory=dict)
    player_stats: PlayerStats = field(default_factory=PlayerStats)
    queue: deque[Any] = field(default_factory=deque, repr=False)
    active: Any = field(default=None, repr=False)
    busy_timer: int = 0
    script: str = ""
    energy: int | None = None
    stranded_since: int | None = None
    temperature: float = 0.0
    cooldown_remaining: int = 0
    dock_state: str | None = None

    def __post_init__(self) -> None:
        self.id = int(self.id)
        self.layer = int(self.layer)
        if isinstance(self.facing, str):
            self.facing = Direction.parse(self.facing)
        if self.inventory is None:
            self.inventory = {}
        if self.player_stats is None:
            self.player_stats = PlayerStats()
        capacity = max(0, int(self.player_stats.battery_capacity))
        if self.energy is None:
            self.energy = capacity
        else:
            self.energy = max(0, min(int(self.energy), capacity))
        self.temperature = max(0.0, min(100.0, float(self.temperature or 0.0)))
        self.cooldown_remaining = max(0, int(self.cooldown_remaining or 0))

    # -- shared player stats -------------------------------------------------

    @property
    def money(self) -> int:
        """Player money shared by all miners."""
        return self.player_stats.money

    @money.setter
    def money(self, value: int) -> None:
        self.player_stats.money = int(value)

    @property
    def capacity(self) -> int:
        """Shared inventory capacity."""
        return self.player_stats.capacity

    @capacity.setter
    def capacity(self, value: int) -> None:
        self.player_stats.capacity = int(value)

    @property
    def tool_power(self) -> int:
        """Shared mining tool power."""
        return self.player_stats.tool_power

    @tool_power.setter
    def tool_power(self, value: int) -> None:
        self.player_stats.tool_power = int(value)

    @property
    def tool_tier(self) -> int:
        """Shared mining tool tier."""
        return self.player_stats.tool_tier

    @tool_tier.setter
    def tool_tier(self, value: int) -> None:
        self.player_stats.tool_tier = int(value)

    @property
    def move_ticks(self) -> int:
        """Shared ticks per tile moved."""
        return self.player_stats.move_ticks

    @move_ticks.setter
    def move_ticks(self, value: int) -> None:
        self.player_stats.move_ticks = int(value)

    @property
    def scan_radius(self) -> int:
        """Shared scanner radius."""
        return self.player_stats.scan_radius

    @scan_radius.setter
    def scan_radius(self, value: int) -> None:
        self.player_stats.scan_radius = int(value)

    @property
    def battery_capacity(self) -> int:
        """Shared battery capacity across the fleet."""
        return self.player_stats.battery_capacity

    @battery_capacity.setter
    def battery_capacity(self, value: int) -> None:
        self.player_stats.battery_capacity = max(0, int(value))

    @property
    def charge_rate(self) -> int:
        """Shared charging speed in energy per tick."""
        return self.player_stats.charge_rate

    @charge_rate.setter
    def charge_rate(self, value: int) -> None:
        self.player_stats.charge_rate = max(1, int(value))

    @property
    def is_stranded(self) -> bool:
        """Return True while this miner is waiting for a rescue."""
        return self.stranded_since is not None

    @property
    def is_overheated(self) -> bool:
        """Return True while the miner is shut down by overheating."""
        return int(self.cooldown_remaining) > 0

    @property
    def stats(self) -> MinerStats:
        """Shared aggregate mining stats."""
        return self.player_stats.stats

    @stats.setter
    def stats(self, value: MinerStats) -> None:
        self.player_stats.stats = value

    @property
    def upgrades(self) -> dict[str, int]:
        """Shared upgrade levels."""
        return self.player_stats.upgrades

    @upgrades.setter
    def upgrades(self, value: dict[str, int]) -> None:
        self.player_stats.upgrades = value

    @property
    def estimates(self) -> dict[str, int]:
        """Shared probability-estimate submissions."""
        return self.player_stats.estimates

    @estimates.setter
    def estimates(self, value: dict[str, int]) -> None:
        self.player_stats.estimates = value

    @property
    def upgrade_levels(self) -> dict[str, int]:
        """Alias for :attr:`upgrades`."""
        return self.upgrades

    # -- construction --------------------------------------------------------

    @classmethod
    def from_config(
        cls, content: Any, x: int = 0, y: int = 0, miner_id: int = 0, layer: int = 0
    ) -> Miner:
        """Create a miner with the start values from ``content.config``."""
        return cls(
            id=int(miner_id),
            x=x,
            y=y,
            layer=int(layer),
            facing=Direction.NORTH,
            inventory={},
            player_stats=PlayerStats.from_config(content),
        )

    @classmethod
    def new(cls, content: Any, x: int = 0, y: int = 0, miner_id: int = 0) -> Miner:
        """Alias for :meth:`from_config`."""
        return cls.from_config(content, x=x, y=y, miner_id=miner_id)

    @classmethod
    def create(cls, content: Any, x: int = 0, y: int = 0, miner_id: int = 0) -> Miner:
        """Alias for :meth:`from_config`."""
        return cls.from_config(content, x=x, y=y, miner_id=miner_id)

    @classmethod
    def from_fleet_dict(cls, data: Any, player_stats: PlayerStats | None = None) -> Miner:
        """Rebuild a miner from a save ``fleet`` entry."""
        if not isinstance(data, dict):
            raise ValueError("miner data must be a mapping")
        facing_raw = data.get("facing", "north")
        facing = Direction.parse(facing_raw) if isinstance(facing_raw, str) else facing_raw
        return cls(
            id=int(data.get("id", 0)),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            layer=int(data.get("layer", 0)),
            facing=facing,
            inventory={str(k): int(v) for k, v in dict(data.get("inventory", {})).items()},
            player_stats=player_stats if player_stats is not None else PlayerStats(),
            script=str(data.get("script", "") or ""),
            energy=None if data.get("energy") is None else int(data.get("energy", 0)),
            temperature=float(data.get("temperature", 0.0) or 0.0),
            cooldown_remaining=int(data.get("cooldown_remaining", 0) or 0),
        )

    # -- inventory -----------------------------------------------------------

    @property
    def inventory_size(self) -> int:
        """Total number of items carried."""
        return sum(self.inventory.values())

    @property
    def total_items(self) -> int:
        """Alias for :attr:`inventory_size`."""
        return self.inventory_size

    @property
    def used_capacity(self) -> int:
        """Alias for :attr:`inventory_size`."""
        return self.inventory_size

    @property
    def position(self) -> tuple[int, int]:
        """The miner position as ``(x, y)``."""
        return (self.x, self.y)

    @property
    def is_inventory_full(self) -> bool:
        """Return True when the miner cannot carry another item."""
        return self.inventory_size >= self.capacity

    def can_carry(self, amount: int = 1) -> bool:
        """Return True if ``amount`` more items fit in the inventory."""
        return self.inventory_size + amount <= self.capacity

    def add_item(self, ore_id: str, amount: int = 1) -> None:
        """Add ``amount`` items of ``ore_id`` to the inventory."""
        self.inventory[ore_id] = self.inventory.get(ore_id, 0) + amount

    # -- serialisation -------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Any) -> Miner:
        """Rebuild a miner (with its player stats) from :meth:`to_dict`."""
        if not isinstance(data, dict):
            raise ValueError("miner data must be a mapping")
        player_stats = PlayerStats.from_dict(data)
        facing_raw = data.get("facing", "north")
        try:
            facing = Direction.parse(facing_raw) if isinstance(facing_raw, str) else facing_raw
        except ValueError:
            facing = Direction.NORTH
        return cls(
            id=int(data.get("id", 0)),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            layer=int(data.get("layer", 0)),
            facing=facing,
            inventory={str(k): int(v) for k, v in dict(data.get("inventory", {})).items()},
            player_stats=player_stats,
            energy=None if data.get("energy") is None else int(data.get("energy", 0)),
            temperature=float(data.get("temperature", 0.0) or 0.0),
            cooldown_remaining=int(data.get("cooldown_remaining", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the miner and player stats."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "layer": self.layer,
            "facing": self.facing.name.lower()
            if isinstance(self.facing, Direction)
            else self.facing,
            "inventory": dict(self.inventory),
            "energy": self.energy,
            "temperature": self.temperature,
            "cooldown_remaining": self.cooldown_remaining,
            **self.player_stats.to_dict(),
        }

    def to_fleet_dict(self) -> dict[str, Any]:
        """Return the compact fleet entry used by save version 4."""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "layer": self.layer,
            "facing": self.facing.name.lower()
            if isinstance(self.facing, Direction)
            else self.facing,
            "inventory": dict(self.inventory),
            "script": str(self.script),
            "energy": self.energy,
            "temperature": self.temperature,
            "cooldown_remaining": self.cooldown_remaining,
        }
