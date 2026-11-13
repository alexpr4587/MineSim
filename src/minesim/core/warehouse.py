"""The base warehouse: a capacity-limited stock of items."""

from __future__ import annotations

from typing import Any

__all__ = ["Warehouse"]


class Warehouse:
    """A player-wide stock of item id -> count with a capacity in units."""

    def __init__(self, capacity: int = 0) -> None:
        self.capacity = max(0, int(capacity))
        self.items: dict[str, int] = {}

    def add(self, item: str, n: int = 1) -> int:
        """Add up to ``n`` units of ``item``; return the accepted amount."""
        amount = max(0, int(n))
        if amount <= 0:
            return 0
        free = max(0, self.capacity - self.total())
        accepted = min(amount, free)
        if accepted <= 0:
            return 0
        item = str(item)
        self.items[item] = self.items.get(item, 0) + accepted
        return accepted

    def remove(self, item: str, n: int = 1) -> int:
        """Remove up to ``n`` units of ``item``; return the removed amount."""
        amount = max(0, int(n))
        item = str(item)
        have = int(self.items.get(item, 0))
        removed = min(amount, have)
        if removed <= 0:
            return 0
        remaining = have - removed
        if remaining > 0:
            self.items[item] = remaining
        else:
            self.items.pop(item, None)
        return removed

    def count(self, item: str) -> int:
        """Return how many units of ``item`` are stored."""
        return int(self.items.get(str(item), 0))

    def total(self) -> int:
        """Return the total number of stored units."""
        return sum(self.items.values())

    @property
    def used(self) -> int:
        """Alias for :meth:`total`."""
        return self.total()

    @property
    def free(self) -> int:
        """Return the remaining capacity in units."""
        return max(0, self.capacity - self.total())

    def is_empty(self) -> bool:
        """Return True when the warehouse holds nothing."""
        return not self.items

    def clear(self) -> None:
        """Remove all stored items."""
        self.items.clear()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the warehouse."""
        return {
            "capacity": int(self.capacity),
            "items": {str(k): int(v) for k, v in self.items.items() if int(v) > 0},
        }

    def from_dict(self, data: Any) -> Warehouse:
        """Restore this warehouse from a :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            return self
        capacity = data.get("capacity")
        if capacity is not None:
            self.capacity = max(0, int(capacity))
        raw_items = data.get("items", data)
        items: dict[str, int] = {}
        if isinstance(raw_items, dict):
            for key, value in raw_items.items():
                if key in ("capacity", "items"):
                    continue
                count = int(value)
                if count > 0:
                    items[str(key)] = count
        self.items = items
        return self

    @classmethod
    def load(cls, data: Any, capacity: int = 0) -> Warehouse:
        """Build a warehouse from a :meth:`to_dict` payload."""
        warehouse = cls(capacity)
        warehouse.from_dict(data)
        return warehouse
