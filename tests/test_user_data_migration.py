"""Tests for migrating legacy DigScript user data to MineSim."""

from __future__ import annotations

import logging
from pathlib import Path

from minesim.core.user_data import migrate_legacy_user_data


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_moves_saves_scripts_and_settings(tmp_path: Path, caplog) -> None:
    data_root = tmp_path / "data"
    config_root = tmp_path / "config"
    _write(data_root / "DigScript" / "saves" / "slot1.json", '{"version": 3}')
    _write(data_root / "DigScript" / "scripts" / "hello.py", "print('hi')\n")
    _write(config_root / "DigScript" / "DigScript.conf", "[General]\ntheme=dark\n")

    with caplog.at_level(logging.INFO):
        moved = migrate_legacy_user_data(data_root=data_root, config_root=config_root)

    assert moved == [data_root / "MineSim", config_root / "MineSim"]
    assert not (data_root / "DigScript").exists()
    assert not (config_root / "DigScript").exists()
    assert (data_root / "MineSim" / "saves" / "slot1.json").is_file()
    assert (data_root / "MineSim" / "scripts" / "hello.py").is_file()
    assert (config_root / "MineSim" / "MineSim.conf").is_file()
    assert "Migrated user data" in caplog.text


def test_does_not_overwrite_existing_minesim_data(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    config_root = tmp_path / "config"
    _write(data_root / "DigScript" / "saves" / "slot1.json", "old")
    _write(data_root / "MineSim" / "saves" / "slot1.json", "new")

    moved = migrate_legacy_user_data(data_root=data_root, config_root=config_root)

    assert moved == []
    assert (data_root / "DigScript" / "saves" / "slot1.json").read_text(encoding="utf-8") == "old"
    assert (data_root / "MineSim" / "saves" / "slot1.json").read_text(encoding="utf-8") == "new"


def test_no_legacy_folder_is_a_no_op(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    config_root = tmp_path / "config"

    moved = migrate_legacy_user_data(data_root=data_root, config_root=config_root)

    assert moved == []
    assert not (data_root / "MineSim").exists()
    assert not (config_root / "MineSim").exists()
