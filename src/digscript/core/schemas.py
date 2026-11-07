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


__all__ = ["Biome", "Config", "ContentError", "Ore"]
