"""The mining robot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from minesim.core.direction import Direction

__all__ = ["Miner", "MinerStats"]


@dataclass(slots=True)
class MinerStats:
    """Counters tracked for the miner (used by the player API and progression)."""

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

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(slots=True)
class Miner:
    """The mining robot and its carried state."""

    x: int = 0
    y: int = 0
    facing: Direction = Direction.NORTH
    inventory: dict[str, int] = field(default_factory=dict)
    capacity: int = 10
    money: int = 0
    tool_power: int = 1
    tool_tier: int = 0
    move_ticks: int = 4
    scan_radius: int = 0
    stats: MinerStats = field(default_factory=MinerStats)
    upgrades: dict[str, int] = field(default_factory=dict)
    estimates: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.facing, str):
            self.facing = Direction.parse(self.facing)
        if self.stats is None:
            self.stats = MinerStats()
        if self.inventory is None:
            self.inventory = {}
        if self.upgrades is None:
            self.upgrades = {}
        if self.estimates is None:
            self.estimates = {}

    @property
    def upgrade_levels(self) -> dict[str, int]:
        """Alias for :attr:`upgrades`."""
        return self.upgrades

    @classmethod
    def from_config(cls, content: Any, x: int = 0, y: int = 0) -> Miner:
        """Create a miner with the start values from ``content.config``."""
        config = content.config
        return cls(
            x=x,
            y=y,
            facing=Direction.NORTH,
            inventory={},
            capacity=int(config.start_capacity),
            money=0,
            tool_power=int(config.start_tool_power),
            tool_tier=int(config.start_tool_tier),
            move_ticks=int(config.move_ticks),
            scan_radius=int(config.start_scan_radius),
        )

    @classmethod
    def new(cls, content: Any, x: int = 0, y: int = 0) -> Miner:
        """Alias for :meth:`from_config`."""
        return cls.from_config(content, x=x, y=y)

    @classmethod
    def create(cls, content: Any, x: int = 0, y: int = 0) -> Miner:
        """Alias for :meth:`from_config`."""
        return cls.from_config(content, x=x, y=y)

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

    @classmethod
    def from_dict(cls, data: Any) -> Miner:
        """Rebuild a miner from its :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            raise ValueError("miner data must be a mapping")
        stats_data = data.get("stats") or {}
        stats = MinerStats(
            attempts={str(k): int(v) for k, v in dict(stats_data.get("attempts", {})).items()},
            successes={str(k): int(v) for k, v in dict(stats_data.get("successes", {})).items()},
            total_mined=int(stats_data.get("total_mined", 0)),
            total_earned=int(stats_data.get("total_earned", 0)),
            tiles_moved=int(stats_data.get("tiles_moved", 0)),
            sales=int(stats_data.get("sales", 0)),
        )
        facing_raw = data.get("facing", "north")
        facing = Direction.parse(facing_raw) if isinstance(facing_raw, str) else facing_raw
        return cls(
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            facing=facing,
            inventory={str(k): int(v) for k, v in dict(data.get("inventory", {})).items()},
            capacity=int(data.get("capacity", 10)),
            money=int(data.get("money", 0)),
            tool_power=int(data.get("tool_power", 1)),
            tool_tier=int(data.get("tool_tier", 0)),
            move_ticks=int(data.get("move_ticks", 4)),
            scan_radius=int(data.get("scan_radius", 0)),
            stats=stats,
            upgrades={str(k): int(v) for k, v in dict(data.get("upgrades", {})).items()},
            estimates={str(k): int(v) for k, v in dict(data.get("estimates", {})).items()},
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the miner state."""
        return {
            "x": self.x,
            "y": self.y,
            "facing": self.facing.name.lower()
            if isinstance(self.facing, Direction)
            else self.facing,
            "inventory": dict(self.inventory),
            "capacity": self.capacity,
            "money": self.money,
            "tool_power": self.tool_power,
            "tool_tier": self.tool_tier,
            "move_ticks": self.move_ticks,
            "scan_radius": self.scan_radius,
            "stats": self.stats.to_dict(),
            "upgrades": dict(self.upgrades),
            "estimates": dict(self.estimates),
        }
