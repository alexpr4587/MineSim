"""UI coverage for the shared dock status (prompt 32)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim.core.commands import BuyUpgrade, Unload  # noqa: E402
from minesim.core.game import Game  # noqa: E402
from minesim.ui.base_panel import BasePanel  # noqa: E402
from minesim.ui.hud import HUD  # noqa: E402
from minesim.ui.miners_panel import MinersPanel  # noqa: E402
from minesim.ui.world_view import WorldView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_settings(qapp):
    QSettings("MineSim", "MineSim").clear()
    yield
    QSettings("MineSim", "MineSim").clear()


def _queued_game() -> Game:
    game = Game.new(seed=12345)
    game.miner.inventory = {"stone": 1}
    game.engine.spawn_miner().inventory = {"stone": 1}
    game.submit(Unload(), miner_id=0)
    game.submit(Unload(), miner_id=1)
    return game


def test_hud_reports_the_dock_queue(qapp) -> None:
    game = _queued_game()
    hud = HUD(game=game)
    hud.refresh()
    assert hud.dock_label.objectName() == "hud_dock_label"
    assert hud.dock_label.text() == "Dock: busy (1 queued)"
    game.step()
    game.step()
    hud.refresh()
    assert hud.dock_label.text() == "Dock: free"
    hud.close()


def test_base_panel_shows_the_dock_rate(qapp) -> None:
    game = Game.new(seed=12345)
    game.player_stats.money = 1000
    game.submit(BuyUpgrade("dock"))
    panel = BasePanel(game=game)
    panel.show()
    qapp.processEvents()
    assert panel.dock_rate_label.objectName() == "base_dock_rate"
    assert panel.dock_rate_label.text() == "Dock rate: 6/tick"
    panel.close()


def test_miners_panel_labels_a_waiting_miner_as_queued(qapp, tmp_path: Path) -> None:
    game = _queued_game()
    panel = MinersPanel(game=game, scripts_dir=tmp_path)
    panel.show()
    qapp.processEvents()
    panel.refresh()
    assert panel.rows[1].state_label.text() == "Queued"
    panel.close()


def test_world_view_draws_a_dock_badge(qapp) -> None:
    game = _queued_game()
    view = WorldView(game)
    view.resize(800, 600)
    view.show()
    qapp.processEvents()
    assert view.dock_badge_text() == "Dock 1"
    assert not view.grab().isNull()
    game.step()
    game.step()
    view.update()
    qapp.processEvents()
    assert view.dock_badge_text() == ""
    view.close()
