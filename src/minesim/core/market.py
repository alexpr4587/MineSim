"""The dynamic market: per-item price indices, impact and news shocks."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from minesim.core.items import ItemCatalog
from minesim.core.rng import mix64, unit

__all__ = ["Market"]


@dataclass(slots=True)
class _Entry:
    """The market parameters of one item."""

    volatility: float = 0.0
    reversion: float = 0.0
    min_index: float = 0.0
    max_index: float = 0.0


@dataclass(slots=True)
class _State:
    """The mutable market state of one item."""

    index: float = 1.0
    impact: float = 0.0
    shock: float = 1.0
    shock_until: int | None = None
    history: deque[float] = field(default_factory=deque)


def _entry_from(value: Any) -> _Entry:
    if isinstance(value, dict):
        return _Entry(
            volatility=float(value.get("volatility", 0.0)),
            reversion=float(value.get("reversion", 0.0)),
            min_index=float(value.get("min_index", 0.0)),
            max_index=float(value.get("max_index", 0.0)),
        )
    return _Entry(
        volatility=float(getattr(value, "volatility", 0.0)),
        reversion=float(getattr(value, "reversion", 0.0)),
        min_index=float(getattr(value, "min_index", 0.0)),
        max_index=float(getattr(value, "max_index", 0.0)),
    )


def _entry_item(value: Any) -> str | None:
    if isinstance(value, dict):
        item = value.get("item")
    else:
        item = getattr(value, "item", None)
    return str(item) if item is not None else None


def _normalise_entries(market_config: Any) -> dict[str, _Entry]:
    entries: dict[str, _Entry] = {}
    if market_config is None:
        return entries
    if isinstance(market_config, dict):
        for item_id, value in market_config.items():
            entries[str(item_id)] = _entry_from(value)
        return entries
    if isinstance(market_config, (list, tuple)):
        for value in market_config:
            item_id = _entry_item(value)
            if item_id is not None:
                entries[item_id] = _entry_from(value)
    return entries


class Market:
    """A seeded, deterministic market for every item in the catalog."""

    def __init__(
        self,
        seed: int,
        catalog: ItemCatalog,
        config: Any,
        market_config: Any = None,
    ) -> None:
        self.seed = int(seed)
        self.catalog = catalog
        self.config = config
        self.interval = max(1, int(getattr(config, "market_interval_ticks", 100)))
        self.history_len = max(1, int(getattr(config, "market_history_len", 240)))
        self.impact_per_unit = float(getattr(config, "impact_per_unit", 0.0))
        self.impact_recovery = float(getattr(config, "impact_recovery", 0.0))
        self.impact_cap = float(getattr(config, "impact_cap", 1.0))
        self.entries = _normalise_entries(market_config)
        self.step = 0
        self._states: dict[str, _State] = {
            item_id: _State(history=deque(maxlen=self.history_len)) for item_id in self.catalog.ids
        }

    # -- state access --------------------------------------------------------

    def _state(self, item: str) -> _State:
        item = str(item)
        try:
            return self._states[item]
        except KeyError:
            self.catalog.get(item)
            state = _State(history=deque(maxlen=self.history_len))
            self._states[item] = state
            return state

    def index(self, item: str) -> float:
        """Return the current price index of ``item``."""
        return float(self._state(item).index)

    def impact(self, item: str) -> float:
        """Return the current sale impact of ``item``."""
        return float(self._state(item).impact)

    def shock(self, item: str) -> float:
        """Return the current news shock factor of ``item``."""
        return float(self._state(item).shock)

    def price(self, item: str) -> float:
        """Return the current price of ``item`` in money."""
        base_value = self.catalog.base_value(item)
        state = self._state(item)
        return base_value * state.index * (1.0 - state.impact) * state.shock

    def history(self, item: str, n: int | None = None) -> list[float]:
        """Return the last ``n`` price samples of ``item`` (all when None)."""
        samples = list(self._state(item).history)
        if n is None:
            return samples
        limit = max(0, int(n))
        return samples[len(samples) - limit :] if limit else []

    # -- simulation ----------------------------------------------------------

    def _expire_shocks(self, tick: int) -> None:
        for state in self._states.values():
            if state.shock_until is not None and tick >= state.shock_until:
                state.shock = 1.0
                state.shock_until = None

    def _step_once(self) -> None:
        self.step += 1
        for item_id in self.catalog.ids:
            state = self._states[item_id]
            entry = self.entries.get(item_id)
            if entry is not None:
                roll = unit(mix64(self.seed, self.catalog.position(item_id), self.step))
                shock = roll * 2.0 - 1.0
                state.index += entry.reversion * (1.0 - state.index) + entry.volatility * shock
                state.index = min(max(state.index, entry.min_index), entry.max_index)
            state.impact *= 1.0 - self.impact_recovery
            if state.impact < 1e-6:
                state.impact = 0.0
            state.history.append(self.price(item_id))

    def advance(self, tick: int) -> None:
        """Perform every market step due at ``tick``."""
        tick = int(tick)
        self._expire_shocks(tick)
        target = tick // self.interval
        while self.step < target:
            self._step_once()

    # -- trading -------------------------------------------------------------

    def sell(self, item: str, n: int) -> int:
        """Sell ``n`` units of ``item`` unit by unit; return the revenue."""
        amount = max(0, int(n))
        state = self._state(item)
        total = 0.0
        for _ in range(amount):
            total += self.price(item)
            state.impact = min(self.impact_cap, state.impact + self.impact_per_unit)
        return int(math.floor(total))

    def apply_news(self, item: str, factor: float, until_tick: int) -> None:
        """Apply a news shock to ``item`` until ``until_tick``."""
        state = self._state(item)
        state.shock = float(factor)
        state.shock_until = int(until_tick)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the market state."""
        items: dict[str, Any] = {}
        for item_id in self.catalog.ids:
            state = self._states[item_id]
            items[item_id] = {
                "index": state.index,
                "impact": state.impact,
                "shock": state.shock,
                "shock_until": state.shock_until,
                "history": list(state.history),
            }
        return {"step": int(self.step), "items": items}

    def from_dict(self, data: Any) -> Market:
        """Restore this market from a :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            return self
        self.step = int(data.get("step", 0) or 0)
        for state in self._states.values():
            state.index = 1.0
            state.impact = 0.0
            state.shock = 1.0
            state.shock_until = None
            state.history.clear()
        raw_items = data.get("items", {})
        if not isinstance(raw_items, dict):
            return self
        for item_id, raw in raw_items.items():
            item_id = str(item_id)
            if item_id not in self._states or not isinstance(raw, dict):
                continue
            state = self._states[item_id]
            state.index = float(raw.get("index", state.index))
            state.impact = float(raw.get("impact", state.impact))
            state.shock = float(raw.get("shock", state.shock))
            shock_until = raw.get("shock_until")
            state.shock_until = None if shock_until is None else int(shock_until)
            history = raw.get("history", [])
            state.history = deque(
                (float(value) for value in history),
                maxlen=self.history_len,
            )
        return self

    @classmethod
    def load(
        cls,
        data: Any,
        seed: int,
        catalog: ItemCatalog,
        config: Any,
        market_config: Any = None,
    ) -> Market:
        """Build a market from a :meth:`to_dict` payload."""
        market = cls(seed, catalog, config, market_config)
        market.from_dict(data)
        return market
