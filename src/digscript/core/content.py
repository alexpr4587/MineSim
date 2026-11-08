"""Content loading and validation.

Loads the JSON files in ``digscript/content/`` with
``importlib.resources``, validates them with the pydantic models in
``core/schemas.py`` and returns a :class:`Content` object. Invalid
data raises :class:`ContentError` naming the file and JSON path.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from digscript.core.schemas import (
    Achievement,
    Biome,
    Config,
    ContentError,
    FunctionSpec,
    ModuleSpec,
    Ore,
    Upgrade,
)

__all__ = [
    "Content",
    "ContentError",
    "load_content",
    "load_content_from_dir",
]

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Content:
    """Validated game content."""

    config: Config
    ores: dict[str, Ore] = field(default_factory=dict)
    biomes: dict[str, Biome] = field(default_factory=dict)
    upgrades: dict[str, Upgrade] = field(default_factory=dict)
    functions: dict[str, FunctionSpec] = field(default_factory=dict)
    modules: dict[str, ModuleSpec] = field(default_factory=dict)
    achievements: dict[str, Achievement] = field(default_factory=dict)

    def get_achievement(self, achievement_id: str) -> Achievement:
        """Return the achievement with ``achievement_id`` or raise ContentError."""
        try:
            return self.achievements[achievement_id]
        except KeyError:
            raise ContentError(
                f"achievements.json: $.id: unknown achievement id '{achievement_id}'"
            ) from None

    def achievement(self, achievement_id: str) -> Achievement:
        """Alias for :meth:`get_achievement`."""
        return self.get_achievement(achievement_id)

    @property
    def achievement_list(self) -> list[Achievement]:
        """All achievements in file order."""
        return list(self.achievements.values())

    @property
    def achievements_by_id(self) -> dict[str, Achievement]:
        """Alias for :attr:`achievements`."""
        return self.achievements

    def get_ore(self, ore_id: str) -> Ore:
        """Return the ore with ``ore_id`` or raise ContentError."""
        try:
            return self.ores[ore_id]
        except KeyError:
            raise ContentError(f"ores.json: $.id: unknown ore id '{ore_id}'") from None

    def get_biome(self, biome_id: str) -> Biome:
        """Return the biome with ``biome_id`` or raise ContentError."""
        try:
            return self.biomes[biome_id]
        except KeyError:
            raise ContentError(f"biomes.json: $.id: unknown biome id '{biome_id}'") from None

    def get_upgrade(self, upgrade_id: str) -> Upgrade:
        """Return the upgrade with ``upgrade_id`` or raise ContentError."""
        try:
            return self.upgrades[upgrade_id]
        except KeyError:
            raise ContentError(f"upgrades.json: $.id: unknown upgrade id '{upgrade_id}'") from None

    def get_function(self, name: str) -> FunctionSpec:
        """Return the function spec with ``name`` or raise ContentError."""
        try:
            return self.functions[name]
        except KeyError:
            raise ContentError(f"functions.json: $.name: unknown function '{name}'") from None

    def get_module(self, name: str) -> ModuleSpec:
        """Return the module spec with ``name`` or raise ContentError."""
        try:
            return self.modules[name]
        except KeyError:
            raise ContentError(f"modules.json: $.name: unknown module '{name}'") from None

    def function(self, name: str) -> FunctionSpec:
        """Alias for :meth:`get_function`."""
        return self.get_function(name)

    def module(self, name: str) -> ModuleSpec:
        """Alias for :meth:`get_module`."""
        return self.get_module(name)

    @property
    def function_list(self) -> list[FunctionSpec]:
        """All function specs in file order."""
        return list(self.functions.values())

    @property
    def module_list(self) -> list[ModuleSpec]:
        """All module specs in file order."""
        return list(self.modules.values())

    @property
    def functions_by_name(self) -> dict[str, FunctionSpec]:
        """Alias for :attr:`functions`."""
        return self.functions

    @property
    def modules_by_name(self) -> dict[str, ModuleSpec]:
        """Alias for :attr:`modules`."""
        return self.modules

    def ore(self, ore_id: str) -> Ore:
        """Alias for :meth:`get_ore`."""
        return self.get_ore(ore_id)

    def biome(self, biome_id: str) -> Biome:
        """Alias for :meth:`get_biome`."""
        return self.get_biome(biome_id)

    @property
    def ore_list(self) -> list[Ore]:
        """All ores in file order."""
        return list(self.ores.values())

    @property
    def biome_list(self) -> list[Biome]:
        """All biomes in file order."""
        return list(self.biomes.values())

    def upgrade(self, upgrade_id: str) -> Upgrade:
        """Alias for :meth:`get_upgrade`."""
        return self.get_upgrade(upgrade_id)

    @property
    def upgrade_list(self) -> list[Upgrade]:
        """All upgrades in file order."""
        return list(self.upgrades.values())

    @property
    def upgrades_by_id(self) -> dict[str, Upgrade]:
        """Alias for :attr:`upgrades`."""
        return self.upgrades

    @property
    def ores_by_id(self) -> dict[str, Ore]:
        """Alias for :attr:`ores`."""
        return self.ores

    @property
    def biomes_by_id(self) -> dict[str, Biome]:
        """Alias for :attr:`biomes`."""
        return self.biomes


def _format_path(loc: tuple[Any, ...]) -> str:
    path = "$"
    for part in loc:
        if isinstance(part, int):
            path += f".{part}"
        else:
            path += f".{part}"
    return path


def _validate(data: Any, adapter: TypeAdapter[Any], filename: str) -> Any:
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0] if exc.errors() else {}
        loc = tuple(first.get("loc", ()))
        message = str(first.get("msg", "invalid value"))
        raise ContentError(f"{filename}: {_format_path(loc)}: {message}") from None


def _read_json(base: Any, filename: str) -> Any:
    path = base.joinpath(filename)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ContentError(f"{filename}: file not found: {path}") from None
    except OSError as exc:
        raise ContentError(f"{filename}: could not read file: {exc}") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContentError(f"{filename}: $: invalid JSON: {exc}") from None


def _index_by_id(items: list[Any], filename: str, kind: str) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for index, item in enumerate(items):
        if item.id in indexed:
            raise ContentError(f"{filename}: $.{index}.id: duplicate {kind} id '{item.id}'")
        indexed[item.id] = item
    return indexed


def _index_by_name(items: list[Any], filename: str, kind: str) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for index, item in enumerate(items):
        if item.name in indexed:
            raise ContentError(f"{filename}: $.{index}.name: duplicate {kind} name '{item.name}'")
        indexed[item.name] = item
    return indexed


def _load_named_specs(
    base_path: Any, filename: str, wrapper: str, adapter: TypeAdapter[Any]
) -> dict[str, Any]:
    try:
        data = _read_json(base_path, filename)
    except ContentError as exc:
        if "file not found" in str(exc):
            return {}
        raise
    if isinstance(data, dict):
        data = data.get(wrapper, data)
    items = _validate(data, adapter, filename)
    return _index_by_name(items, filename, wrapper.rstrip("s"))


_KNOWN_COUNTERS = {
    "mined:any",
    "attempts:any",
    "tiles_moved",
    "sales",
    "money_earned",
    "scripts_finished",
}


def _cross_validate(
    ores: dict[str, Ore],
    biomes: dict[str, Biome],
    achievements: dict[str, Achievement] | None = None,
    upgrades: dict[str, Upgrade] | None = None,
    functions: dict[str, FunctionSpec] | None = None,
    modules: dict[str, ModuleSpec] | None = None,
) -> None:
    for biome_index, biome in enumerate(biomes.values()):
        for ore_id in biome.ore_weights:
            if ore_id not in ores:
                raise ContentError(
                    f"biomes.json: $.{biome_index}.ore_weights.{ore_id}: "
                    f"unknown ore id '{ore_id}' in biome '{biome.id}'"
                )
    if achievements is None:
        achievements = {}
    if upgrades is None:
        upgrades = {}
    if functions is None:
        functions = {}
    if modules is None:
        modules = {}
    for ach_index, achievement in enumerate(achievements.values()):
        if achievement.parent is not None:
            if achievement.parent == achievement.id:
                raise ContentError(
                    f"achievements.json: $.{ach_index}.parent: "
                    f"achievement '{achievement.id}' cannot be its own parent"
                )
            if achievement.parent not in achievements:
                raise ContentError(
                    f"achievements.json: $.{ach_index}.parent: "
                    f"unknown achievement id '{achievement.parent}'"
                )
        criteria = achievement.criteria
        if getattr(criteria, "type", None) == "counter":
            counter = getattr(criteria, "counter", "")
            if counter in _KNOWN_COUNTERS:
                pass
            elif isinstance(counter, str) and counter.startswith("mined:"):
                ore_id = counter[len("mined:") :]
                if ore_id not in ores:
                    raise ContentError(
                        f"achievements.json: $.{ach_index}.criteria.counter: "
                        f"unknown ore id '{ore_id}'"
                    )
            else:
                raise ContentError(
                    f"achievements.json: $.{ach_index}.criteria.counter: "
                    f"unknown counter '{counter}'"
                )
        for reward_index, reward in enumerate(achievement.rewards):
            reward_type = getattr(reward, "type", "")
            if reward_type == "money":
                if getattr(reward, "amount", None) is None:
                    raise ContentError(
                        f"achievements.json: $.{ach_index}.rewards.{reward_index}.amount: "
                        "money reward requires an amount"
                    )
                continue
            reward_id = getattr(reward, "id", None)
            if not reward_id:
                raise ContentError(
                    f"achievements.json: $.{ach_index}.rewards.{reward_index}.id: "
                    f"reward of type '{reward_type}' requires an id"
                )
            targets: dict[str, Any] = {
                "unlock_function": functions,
                "unlock_ore": ores,
                "unlock_upgrade": upgrades,
                "unlock_module": modules,
            }
            target = targets.get(reward_type)
            if target is not None and reward_id not in target:
                kind_names = {
                    "unlock_function": "function",
                    "unlock_ore": "ore",
                    "unlock_upgrade": "upgrade",
                    "unlock_module": "module",
                }
                raise ContentError(
                    f"achievements.json: $.{ach_index}.rewards.{reward_index}.id: "
                    f"unknown {kind_names[reward_type]} id '{reward_id}'"
                )

    def _check_unlocked_by(entries: dict[str, Any], filename: str, key_attr: str) -> None:
        for index, entry in enumerate(entries.values()):
            unlocked_by = getattr(entry, "unlocked_by", None)
            if unlocked_by is not None and unlocked_by not in achievements:
                entry_id = getattr(entry, key_attr, "")
                raise ContentError(
                    f"{filename}: $.{index}.unlocked_by: "
                    f"unknown achievement id '{unlocked_by}' for '{entry_id}'"
                )

    _check_unlocked_by(ores, "ores.json", "id")
    _check_unlocked_by(upgrades, "upgrades.json", "id")
    _check_unlocked_by(functions, "functions.json", "name")
    _check_unlocked_by(modules, "modules.json", "name")


def load_content(content_dir: str | Path | None = None) -> Content:
    """Load and validate all content JSON files.

    ``content_dir`` may be given for tests; by default the packaged
    ``digscript.content`` directory is used via ``importlib.resources``.
    """
    if content_dir is None:
        base_path: Any = files("digscript").joinpath("content")
    else:
        base_path = Path(content_dir)

    config_data = _read_json(base_path, "config.json")
    config = _validate(config_data, TypeAdapter(Config), "config.json")

    ores_data = _read_json(base_path, "ores.json")
    if isinstance(ores_data, dict):
        # Tolerate {"ores": [...]} wrappers from hand-written files.
        ores_data = ores_data.get("ores", ores_data)
    ores_list = _validate(ores_data, TypeAdapter(list[Ore]), "ores.json")
    ores = _index_by_id(ores_list, "ores.json", "ore")

    biomes_data = _read_json(base_path, "biomes.json")
    if isinstance(biomes_data, dict):
        biomes_data = biomes_data.get("biomes", biomes_data)
    biomes_list = _validate(biomes_data, TypeAdapter(list[Biome]), "biomes.json")
    biomes = _index_by_id(biomes_list, "biomes.json", "biome")

    upgrades: dict[str, Upgrade] = {}
    try:
        upgrades_data = _read_json(base_path, "upgrades.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(upgrades_data, dict):
            upgrades_data = upgrades_data.get("upgrades", upgrades_data)
        upgrades_list = _validate(upgrades_data, TypeAdapter(list[Upgrade]), "upgrades.json")
        upgrades = _index_by_id(upgrades_list, "upgrades.json", "upgrade")

    functions = _load_named_specs(
        base_path, "functions.json", "functions", TypeAdapter(list[FunctionSpec])
    )
    modules = _load_named_specs(base_path, "modules.json", "modules", TypeAdapter(list[ModuleSpec]))

    achievements: dict[str, Achievement] = {}
    try:
        achievements_data = _read_json(base_path, "achievements.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(achievements_data, dict):
            achievements_data = achievements_data.get("achievements", achievements_data)
        achievements_list = _validate(
            achievements_data, TypeAdapter(list[Achievement]), "achievements.json"
        )
        achievements = _index_by_id(achievements_list, "achievements.json", "achievement")

    _cross_validate(ores, biomes, achievements, upgrades, functions, modules)
    logger.debug(
        "Loaded content: %d ores, %d biomes, %d upgrades, %d functions, %d modules, "
        "%d achievements",
        len(ores),
        len(biomes),
        len(upgrades),
        len(functions),
        len(modules),
        len(achievements),
    )
    return Content(
        config=config,
        ores=ores,
        biomes=biomes,
        upgrades=upgrades,
        functions=functions,
        modules=modules,
        achievements=achievements,
    )


def load_content_from_dir(content_dir: str | Path) -> Content:
    """Alias for :func:`load_content` with an explicit directory."""
    return load_content(content_dir)
