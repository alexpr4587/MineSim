"""Renaming rules for save games written before miners replaced drones.

This module only exists for save migration. New content and code use the
miner names; the mappings below translate the identifiers stored in older
save files.
"""

from __future__ import annotations

from typing import Any

__all__ = ["ID_RENAMES", "COUNTER_RENAMES", "KEY_RENAMES", "migrate_names"]

ID_RENAMES: dict[str, str] = {
    "drones": "miners",
    "drone_bay": "miner_bay",
    "first_drone": "first_miner",
    "12_two_drones": "12_two_miners",
    "drone_id": "miner_id",
    "spawn_drone": "spawn_miner",
    "kill_drone": "kill_miner",
}

COUNTER_RENAMES: dict[str, str] = {
    "drones_spawned": "miners_spawned",
    "max_drones_alive": "max_miners_alive",
    "api:drone_id": "api:miner_id",
    "api:drones": "api:miners",
    "api:spawn_drone": "api:spawn_miner",
    "api:kill_drone": "api:kill_miner",
}

KEY_RENAMES: dict[str, str] = {
    "drone_id": "miner_id",
}

_UNLOCK_FIELDS = (
    "unlocked_functions",
    "unlocked_ores",
    "unlocked_upgrades",
    "unlocked_modules",
    "unlocked_skins",
    "unlocked_examples",
    "unlocked_recipes",
    "unlocked_features",
)


def _rename_values(values: Any, mapping: dict[str, str]) -> Any:
    if isinstance(values, dict):
        return {mapping.get(str(key), str(key)): value for key, value in values.items()}
    if isinstance(values, (list, tuple, set)):
        return [mapping.get(str(item), str(item)) for item in values]
    return values


def _rename_keys(values: Any, mapping: dict[str, str]) -> Any:
    if isinstance(values, dict):
        return {mapping.get(str(key), str(key)): value for key, value in values.items()}
    return values


def migrate_names(data: dict[str, Any]) -> dict[str, Any]:
    """Rename legacy drone identifiers throughout a save payload."""
    migrated = dict(data)
    progression = migrated.get("progression")
    if isinstance(progression, dict):
        progression = dict(progression)
        progression["counters"] = _rename_keys(progression.get("counters", {}), COUNTER_RENAMES)
        progression["completed"] = _rename_keys(progression.get("completed", {}), ID_RENAMES)
        for field in _UNLOCK_FIELDS:
            if field in progression:
                progression[field] = _rename_values(progression[field], ID_RENAMES)
        migrated["progression"] = progression

    player_stats = migrated.get("player_stats")
    if isinstance(player_stats, dict):
        player_stats = dict(player_stats)
        player_stats["upgrades"] = _rename_keys(player_stats.get("upgrades", {}), ID_RENAMES)
        migrated["player_stats"] = player_stats

    fleet = migrated.get("fleet")
    if isinstance(fleet, list):
        migrated["fleet"] = [
            _rename_keys(entry, KEY_RENAMES) if isinstance(entry, dict) else entry
            for entry in fleet
        ]
    return migrated
