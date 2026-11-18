"""Migration of save games from drone identifiers to miner identifiers."""

from __future__ import annotations

from minesim.core.save import CURRENT_VERSION, migrate


def _legacy_v8() -> dict:
    return {
        "version": 8,
        "seed": 1,
        "tick": 0,
        "fleet": [{"id": 0, "drone_id": 0}],
        "player_stats": {"upgrades": {"drone_bay": 2}},
        "progression": {
            "counters": {
                "drones_spawned": 3,
                "max_drones_alive": 2,
                "api:spawn_drone": 1,
                "api:kill_drone": 1,
                "api:drone_id": 2,
                "api:drones": 4,
                "unloads": 5,
            },
            "completed": {"first_drone": True},
            "unlocked_features": ["drones"],
            "unlocked_upgrades": ["drone_bay"],
            "unlocked_functions": ["spawn_drone", "kill_drone", "drone_id", "drones"],
            "unlocked_examples": ["12_two_drones"],
        },
    }


def test_v8_save_names_migrate_to_miner_names() -> None:
    migrated = migrate(_legacy_v8())
    assert migrated["version"] == CURRENT_VERSION == 10
    progression = migrated["progression"]
    assert progression["counters"] == {
        "miners_spawned": 3,
        "max_miners_alive": 2,
        "api:spawn_miner": 1,
        "api:kill_miner": 1,
        "api:miner_id": 2,
        "api:miners": 4,
        "unloads": 5,
    }
    assert progression["completed"] == {"first_miner": True}
    assert progression["unlocked_features"] == ["miners"]
    assert progression["unlocked_upgrades"] == ["miner_bay"]
    assert progression["unlocked_functions"] == [
        "spawn_miner",
        "kill_miner",
        "miner_id",
        "miners",
    ]
    assert progression["unlocked_examples"] == ["12_two_miners"]


def test_v8_save_upgrade_and_fleet_keys_migrate() -> None:
    migrated = migrate(_legacy_v8())
    assert migrated["player_stats"]["upgrades"] == {"miner_bay": 2}
    assert migrated["fleet"][0]["miner_id"] == 0
    assert "drone_id" not in migrated["fleet"][0]


def test_save_game_from_dict_applies_legacy_name_migration() -> None:
    from minesim.core.save import SaveGame

    savegame = SaveGame.from_dict(_legacy_v8())
    assert savegame.version == 10
    assert savegame.progression["counters"]["miners_spawned"] == 3
    assert savegame.player_stats["upgrades"] == {"miner_bay": 2}
