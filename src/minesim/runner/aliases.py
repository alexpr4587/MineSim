"""Deprecated player API names kept as aliases for older scripts."""

from __future__ import annotations

__all__ = ["DEPRECATED_ALIASES", "alias_warning"]

DEPRECATED_ALIASES: dict[str, str] = {
    "drone_id": "miner_id",
    "drones": "miners",
    "spawn_drone": "spawn_miner",
    "kill_drone": "kill_miner",
}

DEPRECATED_KEYWORDS: dict[str, str] = {
    "drone_id": "miner_id",
}


def alias_warning(old: str, new: str) -> str:
    """Return the one-line console notice printed for a deprecated alias."""
    return f"{old} is now {new}"


def translate_kwargs(kwargs: dict[str, object]) -> dict[str, object]:
    """Rename deprecated keyword arguments to their new names."""
    translated = dict(kwargs)
    for old, new in DEPRECATED_KEYWORDS.items():
        if old in translated and new not in translated:
            translated[new] = translated.pop(old)
    return translated
