"""Content loading and validation.

Loads the JSON files in ``minesim/content/`` with
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

from minesim.core.schemas import (
    Achievement,
    Biome,
    Config,
    ContentError,
    Example,
    FunctionSpec,
    MarketEntry,
    ModuleSpec,
    Ore,
    Product,
    Recipe,
    Skin,
    Sprites,
    Upgrade,
    WorldEventDefinition,
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
    products: dict[str, Product] = field(default_factory=dict)
    recipes: dict[str, Recipe] = field(default_factory=dict)
    market: dict[str, MarketEntry] = field(default_factory=dict)
    events: dict[str, WorldEventDefinition] = field(default_factory=dict)
    biomes: dict[str, Biome] = field(default_factory=dict)
    upgrades: dict[str, Upgrade] = field(default_factory=dict)
    functions: dict[str, FunctionSpec] = field(default_factory=dict)
    modules: dict[str, ModuleSpec] = field(default_factory=dict)
    achievements: dict[str, Achievement] = field(default_factory=dict)
    sprites: Sprites | None = None
    skins: dict[str, Skin] = field(default_factory=dict)
    examples: dict[str, Example] = field(default_factory=dict)

    def get_skin(self, skin_id: str) -> Skin:
        """Return the skin with ``skin_id`` or raise ContentError."""
        try:
            return self.skins[skin_id]
        except KeyError:
            raise ContentError(f"skins.json: $.id: unknown skin id '{skin_id}'") from None

    def skin(self, skin_id: str) -> Skin:
        """Alias for :meth:`get_skin`."""
        return self.get_skin(skin_id)

    @property
    def skin_list(self) -> list[Skin]:
        """All skins in file order."""
        return list(self.skins.values())

    @property
    def skins_by_id(self) -> dict[str, Skin]:
        """Alias for :attr:`skins`."""
        return self.skins

    def get_example(self, example_id: str) -> Example:
        """Return the example with ``example_id`` or raise ContentError."""
        try:
            return self.examples[example_id]
        except KeyError:
            raise ContentError(f"examples.json: $.id: unknown example id '{example_id}'") from None

    def example(self, example_id: str) -> Example:
        """Alias for :meth:`get_example`."""
        return self.get_example(example_id)

    @property
    def example_list(self) -> list[Example]:
        """All examples in file order."""
        return list(self.examples.values())

    @property
    def examples_by_id(self) -> dict[str, Example]:
        """Alias for :attr:`examples`."""
        return self.examples

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

    def get_product(self, product_id: str) -> Product:
        """Return the product with ``product_id`` or raise ContentError."""
        try:
            return self.products[product_id]
        except KeyError:
            raise ContentError(f"products.json: $.id: unknown product id '{product_id}'") from None

    def product(self, product_id: str) -> Product:
        """Alias for :meth:`get_product`."""
        return self.get_product(product_id)

    @property
    def product_list(self) -> list[Product]:
        """All products in file order."""
        return list(self.products.values())

    @property
    def products_by_id(self) -> dict[str, Product]:
        """Alias for :attr:`products`."""
        return self.products

    def get_recipe(self, recipe_id: str) -> Recipe:
        """Return the recipe with ``recipe_id`` or raise ContentError."""
        try:
            return self.recipes[recipe_id]
        except KeyError:
            raise ContentError(f"recipes.json: $.id: unknown recipe id '{recipe_id}'") from None

    def recipe(self, recipe_id: str) -> Recipe:
        """Alias for :meth:`get_recipe`."""
        return self.get_recipe(recipe_id)

    @property
    def recipe_list(self) -> list[Recipe]:
        """All recipes in file order."""
        return list(self.recipes.values())

    @property
    def recipes_by_id(self) -> dict[str, Recipe]:
        """Alias for :attr:`recipes`."""
        return self.recipes

    def get_market_entry(self, item_id: str) -> MarketEntry:
        """Return the market parameters for ``item_id`` or raise ContentError."""
        try:
            return self.market[item_id]
        except KeyError:
            raise ContentError(f"market.json: $.item: unknown item id '{item_id}'") from None

    def get_event(self, kind: str) -> WorldEventDefinition:
        """Return the world event definition for ``kind`` or raise ContentError."""
        try:
            return self.events[kind]
        except KeyError:
            raise ContentError(f"events.json: $.kind: unknown event kind '{kind}'") from None

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
    "scripts_run",
    "max_distance",
    "biomes_visited",
    "streak",
    "fail_streak",
    "unique_ores_mined",
    "largest_sale",
    "ores_in_one_sale",
    "upgrades_bought",
    "regens",
    "good_estimates",
    "script_defines_function",
    "scripts_defines_function",
}

_KNOWN_FAIL_REASONS = {
    "miss",
    "locked_ore",
    "tool_too_weak",
    "inventory_full",
    "nothing_to_mine",
}

_KNOWN_SCRIPT_FEATURES = {
    "defines_function",
    "uses_import",
    "uses_comprehension",
    "uses_class",
    "uses_try",
    "uses_recursion",
    "uses_lambda",
    "uses_generator",
}


def _cross_validate(
    ores: dict[str, Ore],
    biomes: dict[str, Biome],
    achievements: dict[str, Achievement] | None = None,
    upgrades: dict[str, Upgrade] | None = None,
    functions: dict[str, FunctionSpec] | None = None,
    modules: dict[str, ModuleSpec] | None = None,
    skins: dict[str, Skin] | None = None,
    examples: dict[str, Example] | None = None,
    products: dict[str, Product] | None = None,
    market: dict[str, MarketEntry] | None = None,
    recipes: dict[str, Recipe] | None = None,
) -> None:
    products = products or {}
    market = market or {}
    recipes = recipes or {}
    for product_id in products:
        if product_id in ores:
            raise ContentError(
                f"products.json: $.id: duplicate item id '{product_id}' (already an ore)"
            )
    known_items = set(ores) | set(products)
    for item_id in market:
        if item_id not in known_items:
            raise ContentError(
                f"market.json: $.item: unknown item id '{item_id}' (expected an ore or product)"
            )
    for recipe_index, recipe in enumerate(recipes.values()):
        for side in ("inputs", "outputs"):
            for item_id in getattr(recipe, side):
                if item_id not in known_items:
                    raise ContentError(
                        f"recipes.json: $.{recipe_index}.{side}.{item_id}: "
                        f"unknown item id '{item_id}' in recipe '{recipe.id}'"
                    )
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
    if skins is None:
        skins = {}
    examples_present = examples is not None
    if examples is None:
        examples = {}
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
            parent = achievements[achievement.parent]
            if parent.tab != achievement.tab:
                raise ContentError(
                    f"achievements.json: $.{ach_index}.parent: "
                    f"achievement '{achievement.id}' and its parent "
                    f"'{achievement.parent}' must be in the same tab"
                )
            seen = {achievement.id}
            cursor: Achievement | None = achievement
            while cursor is not None and cursor.parent is not None:
                if cursor.parent in seen:
                    raise ContentError(
                        f"achievements.json: $.{ach_index}.parent: "
                        f"achievement parent chain for '{achievement.id}' contains a cycle"
                    )
                seen.add(cursor.parent)
                cursor = achievements.get(cursor.parent)
        criteria = achievement.criteria
        criteria_type = getattr(criteria, "type", None)
        if criteria_type == "counter":
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
            elif isinstance(counter, str) and counter.startswith("attempts:"):
                ore_id = counter[len("attempts:") :]
                if ore_id != "any" and ore_id not in ores:
                    raise ContentError(
                        f"achievements.json: $.{ach_index}.criteria.counter: "
                        f"unknown ore id '{ore_id}'"
                    )
            elif isinstance(counter, str) and counter.startswith("biome:"):
                biome_id = counter[len("biome:") :]
                if biome_id not in biomes:
                    raise ContentError(
                        f"achievements.json: $.{ach_index}.criteria.counter: "
                        f"unknown biome id '{biome_id}'"
                    )
            elif isinstance(counter, str) and counter.startswith("fail:"):
                reason = counter[len("fail:") :]
                if reason not in _KNOWN_FAIL_REASONS:
                    raise ContentError(
                        f"achievements.json: $.{ach_index}.criteria.counter: "
                        f"unknown failure reason '{reason}'"
                    )
            else:
                raise ContentError(
                    f"achievements.json: $.{ach_index}.criteria.counter: "
                    f"unknown counter '{counter}'"
                )
        elif criteria_type == "script_feature":
            feature = getattr(criteria, "feature", "")
            if feature not in _KNOWN_SCRIPT_FEATURES:
                raise ContentError(
                    f"achievements.json: $.{ach_index}.criteria.feature: "
                    f"unknown script feature '{feature}'"
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
            if reward_type == "unlock_example" and not examples_present:
                continue
            targets: dict[str, Any] = {
                "unlock_function": functions,
                "unlock_ore": ores,
                "unlock_upgrade": upgrades,
                "unlock_module": modules,
                "unlock_skin": skins,
                "unlock_example": examples,
            }
            target = targets.get(reward_type)
            if target is not None and reward_id not in target:
                kind_names = {
                    "unlock_function": "function",
                    "unlock_ore": "ore",
                    "unlock_upgrade": "upgrade",
                    "unlock_module": "module",
                    "unlock_skin": "skin",
                    "unlock_example": "example",
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
    _check_unlocked_by(products, "products.json", "id")
    _check_unlocked_by(upgrades, "upgrades.json", "id")
    _check_unlocked_by(functions, "functions.json", "name")
    _check_unlocked_by(modules, "modules.json", "name")
    _check_unlocked_by(skins, "skins.json", "id")
    _check_unlocked_by(recipes, "recipes.json", "id")
    if examples_present:
        _check_unlocked_by(examples, "examples.json", "id")


def load_content(content_dir: str | Path | None = None) -> Content:
    """Load and validate all content JSON files.

    ``content_dir`` may be given for tests; by default the packaged
    ``minesim.content`` directory is used via ``importlib.resources``.
    """
    if content_dir is None:
        base_path: Any = files("minesim").joinpath("content")
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

    products: dict[str, Product] = {}
    try:
        products_data = _read_json(base_path, "products.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(products_data, dict):
            products_data = products_data.get("products", products_data)
        products_list = _validate(products_data, TypeAdapter(list[Product]), "products.json")
        products = _index_by_id(products_list, "products.json", "product")

    recipes: dict[str, Recipe] = {}
    try:
        recipes_data = _read_json(base_path, "recipes.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(recipes_data, dict):
            recipes_data = recipes_data.get("recipes", recipes_data)
        recipes_list = _validate(recipes_data, TypeAdapter(list[Recipe]), "recipes.json")
        recipes = _index_by_id(recipes_list, "recipes.json", "recipe")

    market: dict[str, MarketEntry] = {}
    try:
        market_data = _read_json(base_path, "market.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(market_data, dict):
            market_data = market_data.get("market", market_data)
        market_list = _validate(market_data, TypeAdapter(list[MarketEntry]), "market.json")
        for index, entry in enumerate(market_list):
            if entry.item in market:
                raise ContentError(
                    f"market.json: $.{index}.item: duplicate market item '{entry.item}'"
                )
            market[entry.item] = entry

    events: dict[str, WorldEventDefinition] = {}
    try:
        events_data = _read_json(base_path, "events.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(events_data, dict):
            events_data = events_data.get("events", events_data)
        events_list = _validate(events_data, TypeAdapter(list[WorldEventDefinition]), "events.json")
        for index, entry in enumerate(events_list):
            if entry.kind in events:
                raise ContentError(
                    f"events.json: $.{index}.kind: duplicate event kind '{entry.kind}'"
                )
            events[entry.kind] = entry

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

    sprites: Sprites | None = None
    try:
        sprites_data = _read_json(base_path, "sprites.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(sprites_data, dict):
            sprites_data = sprites_data.get("sprites", sprites_data)
        sprites = _validate(sprites_data, TypeAdapter(Sprites), "sprites.json")

    skins: dict[str, Skin] = {}
    try:
        skins_data = _read_json(base_path, "skins.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        if isinstance(skins_data, dict):
            skins_data = skins_data.get("skins", skins_data)
        skins_list = _validate(skins_data, TypeAdapter(list[Skin]), "skins.json")
        skins = _index_by_id(skins_list, "skins.json", "skin")

    examples: dict[str, Example] = {}
    examples_present = False
    try:
        examples_data = _read_json(base_path, "examples.json")
    except ContentError as exc:
        if "file not found" not in str(exc):
            raise
    else:
        examples_present = True
        if isinstance(examples_data, dict):
            examples_data = examples_data.get("examples", examples_data)
        examples_list = _validate(examples_data, TypeAdapter(list[Example]), "examples.json")
        examples = _index_by_id(examples_list, "examples.json", "example")

    _cross_validate(
        ores,
        biomes,
        achievements,
        upgrades,
        functions,
        modules,
        skins,
        examples if examples_present else None,
        products,
        market,
        recipes,
    )
    logger.debug(
        "Loaded content: %d ores, %d products, %d recipes, %d market entries, "
        "%d world event kinds, %d biomes, "
        "%d upgrades, %d functions, %d modules, %d achievements, %d skins, %d examples",
        len(ores),
        len(products),
        len(recipes),
        len(market),
        len(events),
        len(biomes),
        len(upgrades),
        len(functions),
        len(modules),
        len(achievements),
        len(skins),
        len(examples),
    )
    return Content(
        config=config,
        ores=ores,
        products=products,
        recipes=recipes,
        market=market,
        events=events,
        biomes=biomes,
        upgrades=upgrades,
        functions=functions,
        modules=modules,
        achievements=achievements,
        sprites=sprites,
        skins=skins,
        examples=examples,
    )


def load_content_from_dir(content_dir: str | Path) -> Content:
    """Alias for :func:`load_content` with an explicit directory."""
    return load_content(content_dir)
