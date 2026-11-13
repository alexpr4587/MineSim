"""Unified item catalog for ores and refined products."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = ["Item", "ItemCatalog"]


@dataclass(frozen=True, slots=True)
class Item:
    """One tradeable item: an ore or a refined product."""

    id: str
    name: str
    value: int
    kind: str
    color: str
    unlocked_by: str | None = None

    @property
    def base_value(self) -> int:
        """Alias for :attr:`value` (the ore/product base value)."""
        return self.value


def _entry_to_item(entry: Any, kind: str) -> Item:
    return Item(
        id=str(entry.id),
        name=str(entry.name),
        value=int(getattr(entry, "base_value", 0)),
        kind=kind,
        color=str(getattr(entry, "color", "")),
        unlocked_by=getattr(entry, "unlocked_by", None),
    )


class ItemCatalog:
    """Ores and products keyed by item id, sorted deterministically by id."""

    def __init__(
        self,
        content: Any = None,
        items: Mapping[str, Item] | None = None,
    ) -> None:
        self._items: dict[str, Item] = {}
        if items is not None:
            self._items.update(dict(items))
        if content is not None:
            for ore in getattr(content, "ores", {}).values():
                item = _entry_to_item(ore, "ore")
                self._add(item)
            for product in getattr(content, "products", {}).values():
                item = _entry_to_item(product, "product")
                self._add(item)
        self._sorted_ids = tuple(sorted(self._items))

    def _add(self, item: Item) -> None:
        if item.id in self._items:
            raise ValueError(f"duplicate item id '{item.id}' in catalog")
        self._items[item.id] = item

    def __contains__(self, item_id: object) -> bool:
        return str(item_id) in self._items

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Item]:
        return (self._items[item_id] for item_id in self._sorted_ids)

    @property
    def items(self) -> dict[str, Item]:
        """All items keyed by id."""
        return dict(self._items)

    @property
    def ids(self) -> tuple[str, ...]:
        """All item ids in sorted order."""
        return self._sorted_ids

    @property
    def sorted_ids(self) -> tuple[str, ...]:
        """Alias for :attr:`ids`."""
        return self._sorted_ids

    def position(self, item_id: str) -> int:
        """Return the 0-based position of ``item_id`` in the sorted catalog."""
        try:
            return self._sorted_ids.index(str(item_id))
        except ValueError:
            raise KeyError(f"unknown item id '{item_id}'") from None

    def get(self, item_id: str) -> Item:
        """Return the item with ``item_id`` (KeyError if unknown)."""
        try:
            return self._items[str(item_id)]
        except KeyError:
            raise KeyError(f"unknown item id '{item_id}'") from None

    def item(self, item_id: str) -> Item:
        """Alias for :meth:`get`."""
        return self.get(item_id)

    def base_value(self, item_id: str) -> int:
        """Return the base value of ``item_id``."""
        return self.get(item_id).value

    def value(self, item_id: str) -> int:
        """Alias for :meth:`base_value`."""
        return self.base_value(item_id)

    def kind(self, item_id: str) -> str:
        """Return ``"ore"`` or ``"product"`` for ``item_id``."""
        return self.get(item_id).kind

    def name(self, item_id: str) -> str:
        """Return the display name of ``item_id``."""
        return self.get(item_id).name

    def color(self, item_id: str) -> str:
        """Return the display color of ``item_id``."""
        return self.get(item_id).color

    def unlocked_by(self, item_id: str) -> str | None:
        """Return the achievement id that unlocks ``item_id`` (or None)."""
        return self.get(item_id).unlocked_by
