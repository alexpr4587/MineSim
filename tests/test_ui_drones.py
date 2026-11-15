"""Tests for the drones panel and fleet selection (prompt 21)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim.core.game import Game  # noqa: E402
from minesim.ui.drones_panel import DronesPanel, drone_state_label  # noqa: E402
from minesim.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_settings(qapp):
    QSettings("MineSim", "MineSim").clear()
    yield
    QSettings("MineSim", "MineSim").clear()


def _window(qapp, tmp_path: Path, slots: int = 3) -> tuple[Game, MainWindow]:
    game = Game.new()
    game.player_stats.money = 10000
    game.player_stats.upgrades["drone_bay"] = int(slots)
    window = MainWindow(game, scripts_dir=tmp_path)
    window.resize(1024, 768)
    window.show()
    qapp.processEvents()
    return game, window


def _key(window: MainWindow, key: Qt.Key) -> None:
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.NoModifier))


def test_state_labels_match_the_panel_vocabulary() -> None:
    assert drone_state_label("RUNNING") == "Running"
    assert drone_state_label("FAILED") == "Failed"
    assert drone_state_label("IDLE") == "Idle"
    assert drone_state_label("FINISHED") == "Idle"


def test_panel_rows_follow_spawn_and_kill(qapp, tmp_path):
    game, window = _window(qapp, tmp_path, slots=2)
    panel = window.drones_panel
    assert sorted(panel.rows) == [0]
    assert not panel.rows[0].kill_button.isEnabled()

    game.engine.spawn_drone()
    panel.refresh()
    qapp.processEvents()
    assert sorted(panel.rows) == [0, 1]
    assert panel.rows[1].kill_button.isEnabled()
    assert panel.free_slots() == 1
    assert panel.next_drone_cost() == 800
    assert "Free slots: 1" in panel.spawn_info.text()

    panel.rows[1].kill_button.click()
    qapp.processEvents()
    assert not game.engine.has_drone(1)
    assert sorted(panel.rows) == [0]
    window.close()


def test_selection_drives_console_camera_and_world_click(qapp, tmp_path):
    game, window = _window(qapp, tmp_path, slots=1)
    game.engine.spawn_drone()
    drone = game.engine.drone(1)
    drone.x, drone.y = 5, 3
    panel = window.drones_panel
    panel.refresh()

    assert panel.follow_checkbox.isChecked()
    panel.select_drone(1)
    qapp.processEvents()
    assert panel.selected_drone == 1
    assert window.world_view.selected_drone_id == 1
    assert window.console_panel.selected_drone == 1
    assert int(window.console_panel.drone_selector.currentData()) == 1
    camera_x, camera_y = window.world_view.camera
    assert camera_x == pytest.approx(5.5)
    assert camera_y == pytest.approx(3.5)

    panel.select_drone(0)
    qapp.processEvents()
    assert window.world_view.selected_drone_id == 0
    view = window.world_view
    sx, sy = view.world_to_screen(5.5, 3.5)
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(int(sx), int(sy)))
    qapp.processEvents()
    assert view.selected_drone_id == 1
    assert window.console_panel.selected_drone == 1
    window.close()


def test_follow_toggle_updates_the_world_view(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path, slots=1)
    panel = window.drones_panel
    panel.follow_checkbox.setChecked(False)
    qapp.processEvents()
    assert window.world_view.follow_selected is False
    panel.follow_checkbox.setChecked(True)
    qapp.processEvents()
    assert window.world_view.follow_selected is True
    window.close()


def test_run_on_new_drone_spawns_and_assigns_the_current_file(qapp, tmp_path):
    game, window = _window(qapp, tmp_path, slots=1)
    window.code_editor.setPlainText("print('from new drone')\n")
    assert window.editor_panel.run_on_new_drone()
    qapp.processEvents()
    assert game.engine.has_drone(1)
    assert game.engine.drone(1).script == "main.py"
    assert window.manager.host(1) is not None
    window.drones_panel.refresh()
    assert 1 in window.drones_panel.rows
    assert "Drone 1" in window.editor_panel.drone_name_label.text()
    window.close()


def test_panel_rows_do_not_overlap(qapp, tmp_path):
    game, window = _window(qapp, tmp_path, slots=3)
    for _ in range(3):
        game.engine.spawn_drone()
    panel = window.drones_panel
    window.show_drones()
    panel.resize(420, 520)
    qapp.processEvents()
    rects = [QRect(row.pos(), row.size()) for row in panel.rows.values() if row.isVisible()]
    assert len(rects) == 4
    for first in range(len(rects)):
        for second in range(first + 1, len(rects)):
            assert not rects[first].intersects(rects[second])
    assert window.rect().contains(panel.geometry())
    qapp.processEvents()
    window.close()


def test_d_key_and_view_menu_toggle_the_panel(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path)
    window.world_view.setFocus()
    qapp.processEvents()
    assert not window.drones_panel.isVisible()
    _key(window, Qt.Key.Key_D)
    assert window.drones_panel.isVisible()
    _key(window, Qt.Key.Key_D)
    assert not window.drones_panel.isVisible()
    window._drones_action.trigger()
    assert window.drones_panel.isVisible()
    window.close()


def test_drones_panel_works_without_main_window(qapp, tmp_path):
    game = Game.new()
    game.player_stats.money = 1000
    game.player_stats.upgrades["drone_bay"] = 1
    game.engine.spawn_drone()
    panel = DronesPanel(game=game, scripts_dir=tmp_path)
    panel.resize(420, 400)
    panel.show()
    qapp.processEvents()
    assert set(panel.rows) == {0, 1}
    calls: list[int] = []
    panel.drone_selected.connect(calls.append)
    panel.select_drone(1)
    assert calls == [1]
    assert panel.selected_drone == 1
    panel.close()
