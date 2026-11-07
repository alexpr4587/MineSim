"""Pydantic schemas for game content data."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContentError(Exception):
    """Raised when content data is invalid.

    The message always names the content file and the JSON path of
    the offending field, e.g. ``ores.json: $.0.hardness: ...``.
    """


class _ContentModel(BaseModel):
    """Base model for content entries (extra keys are ignored for
    forward compatibility with later prompts that add new keys)."""

    model_config = ConfigDict(extra="ignore", frozen=True)


class Config(_ContentModel):
    """Game configuration (config.json)."""

    seed_default: int
    chunk_size: int = Field(gt=0)
    region_size_chunks: int = Field(gt=0)
    base_half_size: int = Field(ge=0)
    tick_hz: int = Field(gt=0)
    move_ticks: int = Field(default=4, ge=1)
    mine_tick_base: int = Field(default=3, ge=0)
    sell_ticks: int = Field(default=2, ge=0)
    scan_ticks_per_radius: int = Field(default=1, ge=0)
    start_capacity: int = Field(default=10, ge=0)
    start_tool_power: int = Field(default=1, ge=1)
    start_tool_tier: int = Field(default=0, ge=0)
    start_scan_radius: int = Field(default=0, ge=0)
    free_calls_before_forced_tick: int = Field(default=200, ge=0)
    script_idle_timeout_s: float = Field(default=5, ge=0)
    console_max_lines: int = Field(default=500, ge=0)


class Ore(_ContentModel):
    """A minable ore (ores.json)."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    tier: int = Field(ge=0)
    hardness: int = Field(ge=1)
    base_value: int = Field(ge=0)
    mine_probability: float = Field(ge=0.0, le=1.0)
    regen_ticks: int = Field(ge=0)
    color: str = Field(min_length=1)
    unlocked_by: str | None = None


class Biome(_ContentModel):
    """A mine/biome (biomes.json)."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    min_distance: int = Field(ge=0)
    weight: float = Field(gt=0)
    floor_color: str = Field(min_length=1)
    ore_weights: dict[str, float]

    @field_validator("ore_weights")
    @classmethod
    def _check_ore_weights(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            raise ValueError("ore_weights must not be empty")
        for ore_id, weight in value.items():
            if not ore_id:
                raise ValueError("ore_weights keys must not be empty")
            if weight < 0:
                raise ValueError("ore_weights values must be >= 0")
        if not any(weight > 0 for weight in value.values()):
            raise ValueError("ore_weights must have a positive weight")
        return value


class Upgrade(_ContentModel):
    """An upgrade (upgrades.json).

    ``stat`` names the miner stat(s) changed and ``per_level`` the
    change per level. A single-stat upgrade uses a string and an int
    (``{"stat": "capacity", "per_level": 10}``); an upgrade changing
    several stats (``pickaxe``) uses lists/dicts. Both forms are
    applied by the engine when a level is bought.
    """

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    stat: str | list[str] = Field(min_length=1)
    per_level: int | dict[str, int] | list[int]
    max_level: int = Field(ge=1)
    costs: list[int] = Field(min_length=1)
    unlocked_by: str | None = None

    @field_validator("costs")
    @classmethod
    def _check_costs(cls, value: list[int]) -> list[int]:
        if any(cost < 0 for cost in value):
            raise ValueError("costs must be >= 0")
        return value

    def cost_for_level(self, level: int) -> int:
        """Return the cost to buy ``level`` (0-based) or raise IndexError."""
        if level < 0 or level >= len(self.costs):
            raise IndexError(f"no cost for level {level} of upgrade '{self.id}'")
        return self.costs[level]

    def stat_changes(self) -> dict[str, int]:
        """Return the per-level stat change as a ``{stat: delta}`` dict."""
        if isinstance(self.stat, str):
            if "+" in self.stat or "," in self.stat:
                stats = [part.strip() for part in self.stat.replace(",", "+").split("+")]
                stats = [stat for stat in stats if stat]
            else:
                stats = [self.stat]
        else:
            stats = list(self.stat)
        if isinstance(self.per_level, dict):
            changes = {stat: int(self.per_level[stat]) for stat in stats if stat in self.per_level}
            if self.id == "pickaxe" and "tool_tier" not in changes:
                changes["tool_tier"] = changes.get("tool_power", 1)
            return changes
        if isinstance(self.per_level, list):
            return {stat: int(delta) for stat, delta in zip(stats, self.per_level, strict=True)}
        changes = {stat: int(self.per_level) for stat in stats}
        if self.id == "pickaxe" and "tool_tier" not in changes:
            changes["tool_tier"] = changes.get("tool_power", int(self.per_level))
        return changes


__all__ = ["Biome", "Config", "ContentError", "Ore", "Upgrade"]
