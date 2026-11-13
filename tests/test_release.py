"""Release checks for v0.2.0 packaging and documentation."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_project_version_is_0_2_0() -> None:
    assert 'version = "0.2.0"' in _read("pyproject.toml")


def test_changelog_has_0_2_0_entry() -> None:
    changelog = _read("CHANGELOG.md")
    assert "## [0.2.0]" in changelog
    for phrase in (
        "lit 2.5d terrain",
        "skins and pixel-art sprites",
        "41 achievements",
        "seven new player api functions",
        "minerlib",
        "four new python modules",
        "eight example scripts",
        "save format version 3",
    ):
        assert phrase in changelog.lower()


def test_readme_documents_features_and_links() -> None:
    readme = _read("README.md")
    assert "docs/screenshot.png" in readme
    assert "docs/screenshot-wardrobe.png" in readme
    for target in ("docs/API.md", "docs/GUIDE.md", "docs/BALANCE.md"):
        assert target in readme
        assert (ROOT / target).is_file()
    assert "`K`" in readme
    assert "`H`" in readme
    assert "## Features" in readme


def test_spec_bundles_examples_assets_and_numpy() -> None:
    spec = _read("minesim.spec")
    assert '"src/minesim/examples"' in spec
    assert '"assets"' in spec
    assert '"numpy"' in spec


def test_selftest_ui_renders_chunk_and_sprite(qapp, capsys) -> None:
    pytest.importorskip("PySide6")
    from minesim.__main__ import _run_selftest_ui

    assert _run_selftest_ui() == 0
    output = capsys.readouterr().out
    assert "selftest-ui OK" in output
    assert "lit chunk" in output
    assert "skin sprite" in output
