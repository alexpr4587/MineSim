"""Tests for achievements, upgrades and toasts (prompt 07)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from digscript.core.events import AchievementUnlocked  # noqa: E402
from digscript.core.game import Game  # noqa: E402
from digscript.ui.achievements_panel import AchievementsPanel, layout_tree  # noqa: E402
from digscript.ui.main_window import MainWindow  # noqa: E402
from digscript.ui.toasts import ToastManager  # noqa: E402
from digscript.ui.upgrades_panel import UpgradesPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_settings(qapp):
    QSettings("DigScript", "DigScript").clear()
    yield
    QSettings("DigScript", "DigScript").clear()


# -- layout_tree ---------------------------------------------------------------


def test_layout_tree_no_overlaps_parents_left():
    nodes = [
        {"id": "a", "parent": None},
        {"id": "b", "parent": "a"},
        {"id": "c", "parent": "a"},
        {"id": "d", "parent": "b"},
        {"id": "e", "parent": None},
    ]
    pos = layout_tree(nodes)
    cells = list(pos.values())
    assert len(cells) == len(set(cells))  # no two nodes share a cell
    assert pos["a"][0] == 0 and pos["e"][0] == 0  # roots at column 0
    assert pos["a"][0] < pos["b"][0]  # parent left of child
    assert pos["a"][0] < pos["c"][0]
    assert pos["b"][0] < pos["d"][0]
    assert pos["b"][1] != pos["c"][1]  # siblings never overlap


def test_panel_has_five_tabs_without_overlaps(qapp):
    game = Game.new()
    panel = AchievementsPanel(game=game)
    panel.refresh()
    assert panel.tabs.count() == 5
    labels = [panel.tabs.tabText(index) for index in range(panel.tabs.count())]
    assert labels == ["Code", "Mining", "Business", "Explorer", "Data"]
    for tab_id, view in panel._views.items():
        nodes = [node for node in panel._achievements() if str(node.get("tab")) == tab_id]
        assert nodes
        positions = layout_tree(nodes)
        cells = list(positions.values())
        assert len(cells) == len(set(cells))
        for node in nodes:
            parent = node.get("parent")
            if parent is not None:
                assert positions[str(parent)][0] < positions[str(node["id"])][0]
        assert view.scene() is not None
    panel.close()


# -- helpers -------------------------------------------------------------------


def _window(qapp, tmp_path):
    game = Game.new()
    window = MainWindow(game, scripts_dir=tmp_path)
    window.show()
    qapp.processEvents()
    return game, window


def _key(window, key):
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.NoModifier))


# -- node states after events --------------------------------------------------


def test_achievement_node_states_after_starter(qapp, tmp_path):
    game, window = _window(qapp, tmp_path)
    window.editor_panel.run()
    # pump until the starter script finished so hello_miner completes
    for _ in range(2000):
        window.game_loop.advance(100)
        QApplication.instance().processEvents()
        if str(window.host.state) != "RUNNING":
            break
    assert "hello_miner" in game.progression_state.completed

    panel = AchievementsPanel(game=game, parent=window)
    panel.refresh()
    assert panel._node_items["hello_miner"].state == "completed"
    # wanderer is a child of hello_miner, not yet met -> available
    assert panel._node_items["wanderer"].state == "available"
    # locked nodes deeper in the chain
    assert panel._node_items["scout"].state == "locked"
    panel.close()
    window.close()


# -- keyboard toggles ----------------------------------------------------------


def test_l_and_u_toggle_panels(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path)
    window.world_view.setFocus()
    qapp.processEvents()
    assert not window.achievements_panel.isVisible()
    assert not window.upgrades_panel.isVisible()
    _key(window, Qt.Key.Key_L)
    assert window.achievements_panel.isVisible()
    _key(window, Qt.Key.Key_L)
    assert not window.achievements_panel.isVisible()
    _key(window, Qt.Key.Key_U)
    assert window.upgrades_panel.isVisible()
    _key(window, Qt.Key.Key_U)
    assert not window.upgrades_panel.isVisible()
    window.close()


# -- buying an upgrade changes miner stats and money --------------------------


def test_buying_upgrade_changes_stats_and_money(qapp):
    game = Game.new()
    game.progression_state.unlock_upgrade("backpack")
    game.miner.money = 100
    parent = QWidget()
    panel = UpgradesPanel(game=game, parent=parent)
    panel.refresh()
    row = panel._rows["backpack"]
    assert row.buy.isEnabled()
    row._buy()
    assert game.miner.capacity == 20  # 10 + 10
    assert game.miner.money == 75  # 100 - 25
    assert game.miner.upgrades["backpack"] == 1
    row._buy()
    assert game.miner.capacity == 30
    assert game.miner.money == 15
    panel.close()
    parent.close()


# -- toast queue ---------------------------------------------------------------


def test_toast_queue_delivers_in_order(qapp):
    window = QWidget()
    window.resize(400, 300)
    window.show()
    game = Game.new()
    manager = ToastManager(window, game)

    def unlock(achievement_id):
        manager._on_achievement_unlocked(AchievementUnlocked(id=achievement_id))

    # Fabricate unlocks by directly completing achievements in state + publishing.
    for aid in ("hello_miner", "wanderer", "first_dig"):
        game.progression_state.complete(aid, 0)
        unlock(aid)

    # The first unlock shows immediately; the rest are queued.
    assert len(manager._queue) == 2
    assert manager._current is not None
    first = manager._current

    # Drain the queue through the chain timer callback.
    manager._on_chain()
    assert manager._current is not None and manager._current is not first
    assert len(manager._queue) == 1
    manager._on_chain()
    assert manager._current is not None
    assert len(manager._queue) == 0
    manager._on_chain()
    assert manager._current is None
    window.close()
