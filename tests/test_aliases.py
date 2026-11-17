"""Deprecated player API aliases."""

from __future__ import annotations

from minesim.runner.aliases import (
    DEPRECATED_ALIASES,
    alias_warning,
    translate_kwargs,
)


def test_deprecated_aliases_point_at_miner_functions() -> None:
    assert DEPRECATED_ALIASES == {
        "drone_id": "miner_id",
        "drones": "miners",
        "spawn_drone": "spawn_miner",
        "kill_drone": "kill_miner",
    }


def test_alias_warning_uses_one_line_console_text() -> None:
    assert alias_warning("spawn_drone", "spawn_miner") == "spawn_drone is now spawn_miner"


def test_translate_kwargs_renames_old_keyword() -> None:
    translated = translate_kwargs({"drone_id": 2, "script_name": "worker.py"})
    assert translated == {"miner_id": 2, "script_name": "worker.py"}


def test_translate_kwargs_keeps_explicit_new_keyword() -> None:
    translated = translate_kwargs({"drone_id": 2, "miner_id": 3})
    assert translated == {"drone_id": 2, "miner_id": 3}
