"""Delivery contracts: timed requests to bring items to the base."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from minesim.core.items import ItemCatalog
from minesim.core.rng import mix64, unit, weighted_choice

__all__ = ["Contract", "ContractBoard"]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _recipe_entries(recipes: Any) -> list[Any]:
    if recipes is None:
        return []
    if isinstance(recipes, dict):
        return list(recipes.values())
    return list(recipes)


def _item_outputs(recipe: Any) -> dict[str, int]:
    outputs = _get(recipe, "outputs", {})
    if not isinstance(outputs, dict):
        return {}
    return {str(item): int(count) for item, count in outputs.items() if int(count) > 0}


@dataclass(slots=True)
class Contract:
    """One delivery contract."""

    id: int
    item: str
    quantity: int
    reward: int
    created: int
    deadline: int
    slot: int = 0

    def ticks_left(self, tick: int) -> int:
        """Return the ticks left before the deadline (never negative)."""
        return max(0, int(self.deadline) - int(tick))

    def expired(self, tick: int) -> bool:
        """Return True when the contract has reached its deadline."""
        return int(tick) >= int(self.deadline)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the contract."""
        return {
            "id": int(self.id),
            "item": self.item,
            "quantity": int(self.quantity),
            "reward": int(self.reward),
            "created": int(self.created),
            "deadline": int(self.deadline),
            "slot": int(self.slot),
        }

    @classmethod
    def from_dict(cls, data: Any) -> Contract:
        """Rebuild a contract from a :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            raise ValueError("contract data must be a mapping")
        return cls(
            id=int(data.get("id", 0)),
            item=str(data.get("item", "")),
            quantity=max(1, int(data.get("quantity", 1))),
            reward=max(0, int(data.get("reward", 0))),
            created=int(data.get("created", 0)),
            deadline=int(data.get("deadline", 0)),
            slot=max(0, int(data.get("slot", 0))),
        )


class ContractBoard:
    """A seeded board that generates, expires and pays delivery contracts."""

    def __init__(
        self,
        seed: int,
        catalog: ItemCatalog,
        config: Any,
        recipes: Any = None,
        progression: Any = None,
    ) -> None:
        self.seed = int(seed)
        self.catalog = catalog
        self.config = config
        self.recipes = _recipe_entries(recipes)
        self.progression = progression
        self.interval = max(1, int(_get(config, "contract_interval_ticks", 3000)))
        self.slots = max(1, int(_get(config, "contract_start_slots", 3)))
        self.deadline_min = max(1, int(_get(config, "contract_deadline_min", 4000)))
        self.deadline_max = max(
            self.deadline_min, int(_get(config, "contract_deadline_max", 12000))
        )
        self.premium_min = float(_get(config, "contract_premium_min", 1.3))
        self.premium_max = max(self.premium_min, float(_get(config, "contract_premium_max", 2.0)))
        self.value_min = max(1, int(_get(config, "contract_value_min", 500)))
        self.value_max = max(self.value_min, int(_get(config, "contract_value_max", 4000)))
        self.contracts: list[Contract] = []
        self.tick = 0
        self.generation = 0
        self.next_id = 1

    # -- availability --------------------------------------------------------

    def _is_ore_unlocked(self, item_id: str) -> bool:
        checker = getattr(self.progression, "is_ore_unlocked", None)
        if callable(checker):
            try:
                return bool(checker(item_id))
            except Exception:
                pass
        try:
            return self.catalog.get(item_id).unlocked_by is None
        except KeyError:
            return False

    def _recipe_for_item(self, item_id: str) -> Any:
        for recipe in self.recipes:
            if item_id in _item_outputs(recipe):
                return recipe
        return None

    def _is_recipe_unlocked(self, recipe: Any) -> bool:
        recipe_id = str(_get(recipe, "id", ""))
        checker = getattr(self.progression, "is_recipe_unlocked", None)
        if callable(checker):
            try:
                return bool(checker(recipe_id))
            except Exception:
                pass
        return _get(recipe, "unlocked_by") is None

    def available_items(self) -> list[str]:
        """Return the item ids a contract may ask for right now."""
        available: list[str] = []
        for item_id in self.catalog.ids:
            item = self.catalog.get(item_id)
            if item.kind == "ore":
                if self._is_ore_unlocked(item_id):
                    available.append(item_id)
                continue
            recipe = self._recipe_for_item(item_id)
            if recipe is not None and self._is_recipe_unlocked(recipe):
                available.append(item_id)
        return available

    def _unlocked_ore_fraction(self) -> float:
        ores = [item_id for item_id in self.catalog.ids if self.catalog.kind(item_id) == "ore"]
        if not ores:
            return 1.0
        unlocked = sum(1 for item_id in ores if self._is_ore_unlocked(item_id))
        return unlocked / len(ores)

    # -- generation ----------------------------------------------------------

    def _free_slot(self) -> int | None:
        used = {contract.slot for contract in self.contracts}
        for slot in range(self.slots):
            if slot not in used:
                return slot
        return None

    def _generate(self, tick: int) -> Contract | None:
        available = self.available_items()
        if not available:
            return None
        slot = self._free_slot()
        if slot is None:
            return None
        k = int(self.generation)
        h = mix64(self.seed, slot, k)
        weights = [(item_id, 1.0) for item_id in available]
        item_id = str(weighted_choice(mix64(h, 1), weights))
        base_value = max(1, int(self.catalog.base_value(item_id)))
        fraction = self._unlocked_ore_fraction()
        raw_target = self.value_min + (self.value_max - self.value_min) * unit(mix64(h, 2))
        target = max(1.0, raw_target * fraction)
        quantity = max(1, int(math.ceil(target / base_value)))
        premium = self.premium_min + (self.premium_max - self.premium_min) * unit(mix64(h, 3))
        reward = max(1, int(math.floor(quantity * base_value * premium)))
        delay = self.deadline_min + (self.deadline_max - self.deadline_min) * unit(mix64(h, 4))
        contract = Contract(
            id=int(self.next_id),
            item=item_id,
            quantity=quantity,
            reward=reward,
            created=int(tick),
            deadline=int(tick) + max(1, int(delay)),
            slot=slot,
        )
        self.next_id += 1
        self.contracts.append(contract)
        return contract

    def _expire_until(self, tick: int) -> list[Contract]:
        expired = [contract for contract in self.contracts if contract.expired(tick)]
        if expired:
            self.contracts = [contract for contract in self.contracts if not contract.expired(tick)]
        return expired

    def advance(self, tick: int) -> tuple[list[Contract], list[Contract]]:
        """Generate due contracts and expire late ones.

        Returns ``(generated, expired)``.
        """
        tick = int(tick)
        self.tick = tick
        generated: list[Contract] = []
        expired: list[Contract] = []
        next_boundary = (self.generation + 1) * self.interval
        while next_boundary <= tick:
            expired.extend(self._expire_until(next_boundary))
            self.generation += 1
            if self._free_slot() is not None:
                contract = self._generate(next_boundary)
                if contract is not None:
                    generated.append(contract)
            next_boundary = (self.generation + 1) * self.interval
        expired.extend(self._expire_until(tick))
        return generated, expired

    # -- access and delivery -------------------------------------------------

    def get(self, contract_id: Any) -> Contract:
        """Return contract ``contract_id`` or raise KeyError."""
        target = int(contract_id)
        for contract in self.contracts:
            if contract.id == target:
                return contract
        raise KeyError(f"unknown contract id {target}")

    def contract(self, contract_id: Any) -> Contract:
        """Alias for :meth:`get`."""
        return self.get(contract_id)

    def status(self) -> list[dict[str, Any]]:
        """Return every contract with its live progress."""
        result: list[dict[str, Any]] = []
        for contract in self.contracts:
            item = self.catalog.get(contract.item)
            result.append(
                {
                    "id": int(contract.id),
                    "item": contract.item,
                    "name": item.name,
                    "quantity": int(contract.quantity),
                    "reward": int(contract.reward),
                    "created": int(contract.created),
                    "deadline": int(contract.deadline),
                    "ticks_left": contract.ticks_left(self.tick),
                    "base_value": int(item.base_value),
                    "slot": int(contract.slot),
                }
            )
        return result

    def deliver(self, contract_id: Any, warehouse: Any) -> int:
        """Deliver contract ``contract_id`` from ``warehouse``.

        The full quantity must be in stock; it is removed and the reward
        is returned. Raises KeyError for unknown contracts and ValueError
        for insufficient stock.
        """
        contract = self.get(contract_id)
        if warehouse is None:
            raise ValueError("no_warehouse")
        if warehouse.count(contract.item) < contract.quantity:
            raise ValueError("insufficient_stock")
        warehouse.remove(contract.item, contract.quantity)
        self.contracts.remove(contract)
        return int(contract.reward)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the board state."""
        return {
            "slots": int(self.slots),
            "tick": int(self.tick),
            "generation": int(self.generation),
            "next_id": int(self.next_id),
            "contracts": [contract.to_dict() for contract in self.contracts],
        }

    def from_dict(self, data: Any) -> ContractBoard:
        """Restore this board from a :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            return self
        if "slots" in data:
            self.slots = max(1, int(data.get("slots", self.slots)))
        self.tick = int(data.get("tick", 0) or 0)
        self.generation = max(0, int(data.get("generation", 0) or 0))
        next_id = int(data.get("next_id", 0) or 0)
        contracts: list[Contract] = []
        for entry in data.get("contracts", []) or []:
            try:
                contracts.append(Contract.from_dict(entry))
            except (TypeError, ValueError):
                continue
        self.contracts = contracts
        if next_id <= 0:
            next_id = max((contract.id for contract in contracts), default=0) + 1
        self.next_id = next_id
        return self

    @classmethod
    def load(
        cls,
        data: Any,
        seed: int,
        catalog: ItemCatalog,
        config: Any,
        recipes: Any = None,
        progression: Any = None,
    ) -> ContractBoard:
        """Build a board from a :meth:`to_dict` payload."""
        board = cls(seed, catalog, config, recipes, progression)
        board.from_dict(data)
        return board
