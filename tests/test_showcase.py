"""Showcase checks: README links, press assets, presets and the Help menu."""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim import __version__  # noqa: E402
from minesim.core.game import Game  # noqa: E402
from minesim.ui import links  # noqa: E402
from minesim.ui.main_window import MainWindow  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "docs" / "press"
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
LOCAL_SCHEMES = ("http://", "https://", "mailto:", "data:")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _local_targets(path: Path) -> list[Path]:
    targets: list[Path] = []
    for raw in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
        target = raw.strip().strip("<>")
        target = target.split(" ", 1)[0].split("#", 1)[0]
        if not target or target.startswith(LOCAL_SCHEMES):
            continue
        targets.append((path.parent / target).resolve())
    return targets


def _load_screenshot_tool():
    path = ROOT / "tools" / "screenshot.py"
    spec = importlib.util.spec_from_file_location("minesim_screenshot_tool", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_readme_and_press_markdown_links_exist() -> None:
    documents = [ROOT / "README.md", *sorted(PRESS.glob("*.md"))]
    assert documents
    for document in documents:
        for target in _local_targets(document):
            assert target.exists(), f"{document.relative_to(ROOT)} references missing {target}"


def test_press_assets_exist_with_expected_sizes(qapp) -> None:
    for name in (
        "hero.png",
        "hero-vertical.png",
        "editor.png",
        "editor-vertical.png",
        "layers.png",
        "layers-vertical.png",
        "market.png",
        "market-vertical.png",
        "miners.png",
        "miners-vertical.png",
        "base.png",
        "base-vertical.png",
        "social-preview.png",
    ):
        assert (PRESS / name).is_file(), f"missing press image {name}"
    assert QImage(str(PRESS / "hero.png")).size().toTuple() == (1920, 1080)
    assert QImage(str(PRESS / "hero-vertical.png")).size().toTuple() == (1080, 1920)
    assert QImage(str(PRESS / "social-preview.png")).size().toTuple() == (1280, 640)


@pytest.mark.parametrize("preset", ("hero", "editor", "layers", "market", "miners", "base"))
def test_screenshot_presets_are_deterministic(qapp, tmp_path, preset) -> None:
    tool = _load_screenshot_tool()
    sizes = ((1280, 720),)
    first = tool.render_preset(preset, tmp_path / "first", sizes=sizes)
    second = tool.render_preset(preset, tmp_path / "second", sizes=sizes)
    assert len(first) == len(second) == 1
    for left, right in zip(first, second, strict=True):
        assert left.read_bytes() == right.read_bytes(), f"{preset} is not deterministic"


def test_hero_portrait_is_deterministic(qapp, tmp_path) -> None:
    tool = _load_screenshot_tool()
    sizes = ((720, 1280),)
    first = tool.render_preset("hero", tmp_path / "portrait-first", sizes=sizes)
    second = tool.render_preset("hero", tmp_path / "portrait-second", sizes=sizes)
    assert first[0].read_bytes() == second[0].read_bytes()


def test_help_menu_entries_and_urls(qapp, tmp_path) -> None:
    QSettings("MineSim", "MineSim").clear()
    game = Game.new(seed=12345)
    window = MainWindow(game, scripts_dir=tmp_path)
    try:
        menu = window._help_menu
        texts = [action.text() for action in menu.actions()]
        for expected in (
            "Report a bug",
            "Send feedback",
            "Open the project page",
            "About MineSim",
        ):
            assert expected in texts
        assert window._report_bug_action.data() == links.BUG_REPORT_URL
        assert window._feedback_action.data() == links.FEEDBACK_URL
        assert window._project_page_action.data() == links.PROJECT_PAGE_URL
        assert links.PROJECT_PAGE_URL == links.PROJECT_URL
        assert links.BUG_REPORT_URL.startswith(links.PROJECT_URL)
        assert links.FEEDBACK_URL.startswith(links.PROJECT_URL)
        about = window.about_text()
        assert __version__ in about
        assert str(game.seed) in about
        assert "MIT" in about
    finally:
        window.close()
        window.deleteLater()
        QApplication.instance().processEvents()
        QSettings("MineSim", "MineSim").clear()
