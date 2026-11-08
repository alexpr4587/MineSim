"""Progression state: counters, completed achievements and unlocks."""

from __future__ import annotations

from typing import Any

__all__ = ["ProgressionState"]


def _entries(content: Any, attr: str) -> list[Any]:
    """Return content entries for ``attr`` as a list."""
    if content is None:
        return []
    raw = getattr(content, attr, None)
    if raw is None:
        if isinstance(content, dict):
            raw = content.get(attr)
        else:
            return []
    if isinstance(raw, dict):
        return list(raw.values())
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def _entry_id(entry: Any, kind: str) -> str | None:
    """Return the identifier of a content entry."""
    if isinstance(entry, dict):
        value = entry.get("id" if kind in ("ore", "upgrade") else "name")
        return str(value) if value is not None else None
    value = (
        getattr(entry, "id", None) if kind in ("ore", "upgrade") else getattr(entry, "name", None)
    )
    if value is None:
        value = getattr(entry, "id", None) or getattr(entry, "name", None)
    return str(value) if value is not None else None


def _initial_unlocked(content: Any) -> dict[str, set[str]]:
    """Compute the starting unlocks: everything with unlocked_by null."""
    result: dict[str, set[str]] = {
        "unlocked_functions": set(),
        "unlocked_ores": set(),
        "unlocked_upgrades": set(),
        "unlocked_modules": set(),
    }
    if content is None:
        return result
    mapping = [
        ("functions", "function", "unlocked_functions"),
        ("ores", "ore", "unlocked_ores"),
        ("upgrades", "upgrade", "unlocked_upgrades"),
        ("modules", "module", "unlocked_modules"),
    ]
    for attr, kind, field_name in mapping:
        for entry in _entries(content, attr):
            unlocked_by = (
                entry.get("unlocked_by")
                if isinstance(entry, dict)
                else getattr(entry, "unlocked_by", None)
            )
            if unlocked_by is None:
                entry_id = _entry_id(entry, kind)
                if entry_id is not None:
                    result[field_name].add(entry_id)
    return result


class ProgressionState:
    """Counters, completed achievements and unlocked things."""

    __slots__ = (
        "counters",
        "completed",
        "unlocked_functions",
        "unlocked_ores",
        "unlocked_upgrades",
        "unlocked_modules",
    )

    def __init__(
        self,
        content: Any = None,
        counters: dict[str, int] | None = None,
        completed: dict[str, int] | None = None,
        unlocked_functions: Any = None,
        unlocked_ores: Any = None,
        unlocked_upgrades: Any = None,
        unlocked_modules: Any = None,
        data: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(content, dict) and data is None and counters is None:
            data = content
            content = None
        if data is not None:
            parsed = type(self).from_dict(data, content=content)
            self.counters = parsed.counters
            self.completed = parsed.completed
            self.unlocked_functions = parsed.unlocked_functions
            self.unlocked_ores = parsed.unlocked_ores
            self.unlocked_upgrades = parsed.unlocked_upgrades
            self.unlocked_modules = parsed.unlocked_modules
            return
        if counters is None:
            counters = kwargs.pop("counter_values", None) or {}
        if completed is None:
            completed = kwargs.pop("completed_achievements", None) or {}
        initial = _initial_unlocked(content)
        self.counters = {str(k): int(v) for k, v in dict(counters).items()}
        self.completed = {str(k): int(v) for k, v in dict(completed).items()}
        self.unlocked_functions = (
            set(unlocked_functions)
            if unlocked_functions is not None
            else initial["unlocked_functions"]
        )
        self.unlocked_ores = (
            set(unlocked_ores) if unlocked_ores is not None else initial["unlocked_ores"]
        )
        self.unlocked_upgrades = (
            set(unlocked_upgrades)
            if unlocked_upgrades is not None
            else initial["unlocked_upgrades"]
        )
        self.unlocked_modules = (
            set(unlocked_modules) if unlocked_modules is not None else initial["unlocked_modules"]
        )
        if kwargs:
            unknown = set(kwargs) - {
                "unlocked_function_ids",
                "unlocked_ore_ids",
                "unlocked_upgrade_ids",
                "unlocked_module_ids",
            }
            if unknown:
                raise TypeError(f"unexpected arguments: {sorted(unknown)}")

    def __getattr__(self, name: str) -> Any:
        aliases = {
            "unlocked_function_ids": "unlocked_functions",
            "unlocked_ore_ids": "unlocked_ores",
            "unlocked_upgrade_ids": "unlocked_upgrades",
            "unlocked_module_ids": "unlocked_modules",
            "functions_unlocked": "unlocked_functions",
            "ores_unlocked": "unlocked_ores",
            "upgrades_unlocked": "unlocked_upgrades",
            "modules_unlocked": "unlocked_modules",
            "completed_achievements": "completed",
        }
        if name in aliases:
            return object.__getattribute__(self, aliases[name])
        raise AttributeError(name)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, ProgressionState):
            return self.to_dict() == other.to_dict()
        return NotImplemented

    def __repr__(self) -> str:
        return (
            f"ProgressionState(counters={self.counters!r}, completed={self.completed!r}, "
            f"unlocked_functions={sorted(self.unlocked_functions)!r}, "
            f"unlocked_ores={sorted(self.unlocked_ores)!r}, "
            f"unlocked_upgrades={sorted(self.unlocked_upgrades)!r}, "
            f"unlocked_modules={sorted(self.unlocked_modules)!r})"
        )

    @classmethod
    def from_content(cls, content: Any) -> ProgressionState:
        """Create the starting state for ``content``."""
        return cls(content)

    @classmethod
    def new(cls, content: Any = None) -> ProgressionState:
        """Alias for :meth:`from_content`."""
        return cls(content)

    @classmethod
    def from_dict(cls, data: Any, content: Any = None) -> ProgressionState:
        """Rebuild a state from its :meth:`to_dict` payload."""
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError("progression state must be a mapping")
        counters = {str(k): int(v) for k, v in dict(data.get("counters", {})).items()}
        completed = {str(k): int(v) for k, v in dict(data.get("completed", {})).items()}
        initial = _initial_unlocked(content)
        state = cls.__new__(cls)
        state.counters = counters
        state.completed = completed
        for field_name in (
            "unlocked_functions",
            "unlocked_ores",
            "unlocked_upgrades",
            "unlocked_modules",
        ):
            raw = data.get(field_name)
            if raw is None:
                setattr(state, field_name, set(initial[field_name]))
            elif isinstance(raw, dict):
                setattr(state, field_name, set(raw.keys()))
            else:
                setattr(state, field_name, {str(item) for item in raw})
        return state

    @classmethod
    def load_dict(cls, data: Any, content: Any = None) -> ProgressionState:
        """Alias for :meth:`from_dict`."""
        return cls.from_dict(data, content=content)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the state."""
        return {
            "counters": dict(self.counters),
            "completed": dict(self.completed),
            "unlocked_functions": sorted(self.unlocked_functions),
            "unlocked_ores": sorted(self.unlocked_ores),
            "unlocked_upgrades": sorted(self.unlocked_upgrades),
            "unlocked_modules": sorted(self.unlocked_modules),
        }

    def to_save_dict(self) -> dict[str, Any]:
        """Alias for :meth:`to_dict`."""
        return self.to_dict()

    def copy(self) -> ProgressionState:
        """Return an independent copy."""
        return type(self).from_dict(self.to_dict())

    def add_counter(self, name: str, amount: int = 1) -> int:
        """Add ``amount`` to counter ``name`` and return the new value."""
        new_value = int(self.counters.get(name, 0)) + int(amount)
        self.counters[name] = new_value
        return new_value

    def get_counter(self, name: str) -> int:
        """Return the current value of counter ``name`` (0 if unset)."""
        return int(self.counters.get(name, 0))

    def is_completed(self, achievement_id: str) -> bool:
        """Return True if the achievement is completed."""
        return achievement_id in self.completed

    def complete(self, achievement_id: str, tick: int = 0) -> None:
        """Record completion of ``achievement_id`` at ``tick``."""
        if achievement_id not in self.completed:
            self.completed[achievement_id] = int(tick)

    def unlock_function(self, name: str) -> bool:
        """Unlock a function; return True if it was newly unlocked."""
        if name in self.unlocked_functions:
            return False
        self.unlocked_functions.add(name)
        return True

    def unlock_ore(self, ore_id: str) -> bool:
        """Unlock an ore; return True if it was newly unlocked."""
        if ore_id in self.unlocked_ores:
            return False
        self.unlocked_ores.add(ore_id)
        return True

    def unlock_upgrade(self, upgrade_id: str) -> bool:
        """Unlock an upgrade; return True if it was newly unlocked."""
        if upgrade_id in self.unlocked_upgrades:
            return False
        self.unlocked_upgrades.add(upgrade_id)
        return True

    def unlock_module(self, name: str) -> bool:
        """Unlock a module; return True if it was newly unlocked."""
        if name in self.unlocked_modules:
            return False
        self.unlocked_modules.add(name)
        return True

    def is_ore_unlocked(self, ore_id: str) -> bool:
        """Return True if the ore is unlocked."""
        return ore_id in self.unlocked_ores

    def is_function_unlocked(self, name: str) -> bool:
        """Return True if the function is unlocked."""
        return name in self.unlocked_functions

    def is_upgrade_unlocked(self, upgrade_id: str) -> bool:
        """Return True if the upgrade is unlocked."""
        return upgrade_id in self.unlocked_upgrades

    def is_module_unlocked(self, name: str) -> bool:
        """Return True if the module is unlocked."""
        return name in self.unlocked_modules

    def is_unlocked(self, kind: str, ident: str) -> bool:
        """Return True if ``ident`` of ``kind`` is unlocked."""
        kind_normalised = str(kind).lower().rstrip("s")
        if kind_normalised == "ore":
            return self.is_ore_unlocked(ident)
        if kind_normalised == "function":
            return self.is_function_unlocked(ident)
        if kind_normalised == "upgrade":
            return self.is_upgrade_unlocked(ident)
        if kind_normalised == "module":
            return self.is_module_unlocked(ident)
        raise ValueError(f"unknown kind: {kind!r}")
