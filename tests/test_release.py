"""Release checks for v0.3.1 packaging and documentation."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from minesim.core.direction import Direction
from minesim.core.game import Game
from minesim.core.save import CURRENT_VERSION, migrate

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_project_version_is_0_3_1() -> None:
    assert 'version = "0.3.1"' in _read("pyproject.toml")


def test_changelog_has_0_3_1_entry() -> None:
    changelog = _read("CHANGELOG.md")
    assert "## [0.3.1]" in changelog
    for phrase in (
        "closable editor tabs",
        "ctrl+w",
        "ctrl+shift+t",
        "open…",
        "trash",
        "to miners",
        "high-contrast",
    ):
        assert phrase in changelog.lower()


def test_changelog_has_0_3_0_entry() -> None:
    changelog = _read("CHANGELOG.md")
    assert "## [0.3.0]" in changelog
    for phrase in (
        "fleet of miners",
        "per-miner scripts",
        "shared",
        "warehouse",
        "market",
        "price history",
        "refinery",
        "six recipes",
        "contracts",
        "world events",
        "route",
        "trading",
        "oop helpers",
        "eight new example scripts",
        "28 new achievements",
        "eight tabs",
        "save format version 8",
    ):
        assert phrase in changelog.lower()


def test_readme_documents_features_screenshots_and_links() -> None:
    readme = _read("README.md")
    assert readme.startswith("# MineSim")
    assert "MineSim is an open-source" in readme
    for image in (
        "docs/screenshot.png",
        "docs/screenshot-market.png",
        "docs/screenshot-miners.png",
    ):
        assert image in readme
        assert (ROOT / image).is_file()
    for target in ("docs/API.md", "docs/GUIDE.md", "docs/PROGRESSION.md", "docs/BALANCE.md"):
        assert target in readme
        assert (ROOT / target).is_file()
    for key in ("`B`", "`M`", "`T`", "`H`", "`K`"):
        assert key in readme
    for feature in (
        "69 achievements",
        "eight tabs",
        "fleet of miners",
        "warehouse",
        "price history",
        "six recipes",
        "contracts",
        "world events",
        "35 player API functions",
        "16 example scripts",
        "save format v9",
    ):
        assert feature.lower() in readme.lower()
    assert "## Features" in readme
    assert "## Controls" in readme


def test_spec_bundles_examples_assets_and_numpy() -> None:
    spec = _read("minesim.spec")
    assert '"src/minesim/examples"' in spec
    assert '"assets"' in spec
    assert '"numpy"' in spec


def test_frozen_build_supports_multi_miner_scripts() -> None:
    main = _read("src/minesim/__main__.py")
    assert "multiprocessing.freeze_support()" in main
    assert main.index("multiprocessing.freeze_support()") < main.index("ArgumentParser")
    host = _read("src/minesim/scripting/host.py")
    assert 'multiprocessing.get_context("spawn")' in host
    workflow = _read(".github/workflows/release.yml")
    assert "--selftest " in workflow or "--selftest\n" in workflow
    assert "--selftest-ui" in workflow


def test_v0_2_0_save_fixture_migrates() -> None:
    path = FIXTURES / "save_v0.2.0.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["version"] == 3

    migrated = migrate(raw)
    assert CURRENT_VERSION == 13
    assert migrated["version"] == CURRENT_VERSION
    assert migrated["player_stats"]["money"] == 43
    assert migrated["fleet"] == [
        {
            "id": 0,
            "x": 0,
            "y": 0,
            "layer": 0,
            "facing": "west",
            "inventory": {},
            "script": "",
            "energy": 300,
            "temperature": 0.0,
            "cooldown_remaining": 0,
        }
    ]
    assert migrated["warehouse"] == {}
    assert migrated["market"] == {}

    game = Game.load(path)
    assert game.tick == 21
    assert game.player_stats.money == 43
    assert len(game.miners) == 1
    assert (game.miner.x, game.miner.y) == (0, 0)
    assert game.miner.facing is Direction.WEST
    assert game.progression_state.is_completed("first_dig")
    assert game.progression_state.is_completed("first_sale")
    assert game.engine.warehouse.total() == 0
    assert game.engine.market.step == 0


def test_selftest_ui_renders_chunk_and_sprite(qapp, capsys) -> None:
    pytest.importorskip("PySide6")
    from minesim.__main__ import _run_selftest_ui

    assert _run_selftest_ui() == 0
    output = capsys.readouterr().out
    assert "selftest-ui OK" in output
    assert "lit chunk" in output
    assert "skin sprite" in output
