"""Tests for closable editor tabs and script file management (prompt 27)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim.core.game import Game  # noqa: E402
from minesim.ui.editor_panel import is_valid_module_name  # noqa: E402
from minesim.ui.main_window import MainWindow  # noqa: E402
from minesim.ui.theme import (  # noqa: E402
    HUD_SELECTED_BACKGROUND,
    HUD_SELECTED_TEXT,
    miner_badge_color,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_settings(qapp):
    QSettings("MineSim", "MineSim").clear()
    yield
    QSettings("MineSim", "MineSim").clear()


def _window(qapp, scripts_dir):
    game = Game.new()
    window = MainWindow(game, scripts_dir=scripts_dir)
    window.show()
    qapp.processEvents()
    return game, window


def _make_scripts(tmp_path):
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "alpha.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "beta.py").write_text("b = 1\n", encoding="utf-8")
    (tmp_path / "gamma.py").write_text("c = 1\n", encoding="utf-8")


def _tab_names(panel):
    return [panel._tab_name(index) for index in range(panel.tabs.count())]


def test_closing_a_tab_saves_and_keeps_the_file(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    editor = panel.get_editor("alpha.py")
    assert editor is not None
    editor.selectAll()
    editor.insertPlainText("a = 42\n")
    qapp.processEvents()
    assert editor.document().isModified()
    assert panel.close_tab_by_name("alpha.py")
    assert "alpha.py" not in _tab_names(panel)
    assert (tmp_path / "alpha.py").read_text(encoding="utf-8") == "a = 42\n"
    window.close()


def test_dirty_dot_and_autosave_after_two_seconds(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    editor = panel.get_editor("alpha.py")
    assert editor is not None
    editor.setFocus()
    editor.selectAll()
    editor.insertPlainText("a = 7\n")
    qapp.processEvents()
    assert panel.tabs.tabText(panel.tab_index("alpha.py")).endswith(" ●")
    assert panel._autosave_timer.interval() == 2000
    panel._autosave_current_editor()
    assert (tmp_path / "alpha.py").read_text(encoding="utf-8") == "a = 7\n"
    assert not panel.tabs.tabText(panel.tab_index("alpha.py")).endswith(" ●")
    window.close()


def test_reopen_last_closed_tab_with_ctrl_shift_t(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    panel.tabs.setCurrentIndex(panel.tab_index("alpha.py"))
    qapp.processEvents()
    panel.close_tab_by_name("alpha.py")
    assert panel.tab_index("alpha.py") < 0
    editor = window.code_editor
    assert editor is not None
    editor.setFocus()
    qapp.processEvents()
    QTest.keyClick(
        editor,
        Qt.Key.Key_T,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    qapp.processEvents()
    assert panel.tab_index("alpha.py") >= 0
    assert panel.current_filename() == "alpha.py"
    window.close()


def test_ctrl_w_closes_only_with_editor_focus(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    panel.tabs.setCurrentIndex(panel.tab_index("alpha.py"))
    window.world_view.setFocus()
    qapp.processEvents()
    window.keyPressEvent(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    )
    assert panel.tab_index("alpha.py") >= 0
    editor = panel.get_editor("alpha.py")
    assert editor is not None
    editor.setFocus()
    qapp.processEvents()
    QTest.keyClick(editor, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    qapp.processEvents()
    assert panel.tab_index("alpha.py") < 0
    window.close()


def test_middle_click_closes_a_tab(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    panel.tabs.setCurrentIndex(panel.tab_index("alpha.py"))
    qapp.processEvents()
    index = panel.tab_index("alpha.py")
    rect = panel.tabs.tabBar().tabRect(index)
    QTest.mouseClick(panel.tabs.tabBar(), Qt.MouseButton.MiddleButton, pos=rect.center())
    qapp.processEvents()
    assert panel.tab_index("alpha.py") < 0
    assert (tmp_path / "alpha.py").is_file()
    window.close()


def test_open_lists_only_closed_files_newest_first(qapp, tmp_path):
    _make_scripts(tmp_path)
    (tmp_path / ".trash").mkdir()
    (tmp_path / ".trash" / "old.py").write_text("old = 1\n", encoding="utf-8")
    os.utime(tmp_path / "alpha.py", (1000, 1000))
    os.utime(tmp_path / "beta.py", (2000, 2000))
    os.utime(tmp_path / "gamma.py", (3000, 3000))
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    names = [path.name for path in panel.closed_files()]
    assert names == ["gamma.py", "beta.py", "alpha.py"]
    popup = panel.open_dialog()
    qapp.processEvents()
    assert popup.isVisible()
    items = [popup.list_widget.item(index).text() for index in range(popup.list_widget.count())]
    assert items == ["gamma.py", "beta.py", "alpha.py"]
    assert "old.py" not in items
    popup.hide()
    window.close()


def test_rename_validation_and_rename_keeps_content(qapp, tmp_path):
    _make_scripts(tmp_path)
    for invalid in ("", "1bad", "for", "a-b", "with space"):
        assert not is_valid_module_name(invalid)
    assert is_valid_module_name("valid_name")
    assert is_valid_module_name("helper2.py")
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    assert not panel.rename_file("alpha.py", "not a module")
    assert (tmp_path / "alpha.py").is_file()
    assert panel.rename_file("alpha.py", "renamed")
    assert not (tmp_path / "alpha.py").exists()
    assert (tmp_path / "renamed.py").read_text(encoding="utf-8") == "a = 1\n"
    assert panel.tab_index("renamed.py") >= 0
    window.close()


def test_delete_moves_to_trash_and_restore_brings_it_back(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    assert panel.delete_file("alpha.py", confirm=False)
    assert not (tmp_path / "alpha.py").exists()
    trashed = panel.trashed_files()
    assert len(trashed) == 1
    assert trashed[0].parent == tmp_path / ".trash"
    assert "2026" in trashed[0].name or trashed[0].name[:8].isdigit()
    assert panel.restore_deleted_file(trashed[0].name) is not None
    assert (tmp_path / "alpha.py").read_text(encoding="utf-8") == "a = 1\n"
    assert panel.tab_index("alpha.py") >= 0
    window.close()


def test_tabs_and_active_tab_persist_across_restart(qapp, tmp_path):
    _make_scripts(tmp_path)
    game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    panel.add_file(tmp_path / "beta.py")
    panel.tabs.setCurrentIndex(panel.tab_index("beta.py"))
    qapp.processEvents()
    window.close()
    qapp.processEvents()
    _game2, window2 = _window(qapp, tmp_path)
    panel2 = window2.editor_panel
    assert _tab_names(panel2) == ["main.py", "alpha.py", "beta.py"]
    assert panel2.current_filename() == "beta.py"
    window2.close()


def test_external_delete_closes_the_tab_with_console_info(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    panel.add_file(tmp_path / "alpha.py")
    (tmp_path / "alpha.py").unlink()
    panel.refresh_files()
    qapp.processEvents()
    assert panel.tab_index("alpha.py") < 0
    assert "alpha.py" in panel.console_panel.to_plain_text()
    assert "removed on disk" in panel.console_panel.to_plain_text()
    window.close()


def test_running_script_shows_coloured_dot(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    panel = window.editor_panel
    editor = panel.get_editor("main.py")
    assert editor is not None
    editor.setPlainText("while True:\n    pass\n")
    panel.run()
    qapp.processEvents()
    panel.refresh_tab_indicators()
    assert panel.tab_running_color("main.py") == miner_badge_color(0)
    panel.stop()
    qapp.processEvents()
    panel.refresh_tab_indicators()
    assert panel.tab_running_color("main.py") is None
    window.close()


def _relative_luminance(color: QColor) -> float:
    channels = []
    for value in (color.redF(), color.greenF(), color.blueF()):
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: QColor, second: QColor) -> float:
    lighter = max(_relative_luminance(first), _relative_luminance(second))
    darker = min(_relative_luminance(first), _relative_luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


def test_selected_speed_button_label_has_high_contrast(qapp, tmp_path):
    _make_scripts(tmp_path)
    _game, window = _window(qapp, tmp_path)
    button = window.hud.speed_buttons[1]
    assert button.isChecked()
    button.show()
    qapp.processEvents()
    QTest.qWait(20)
    image = button.grab().toImage()
    background = QColor(HUD_SELECTED_BACKGROUND)
    text = QColor(HUD_SELECTED_TEXT)
    colors = [
        QColor(image.pixel(x, y))
        for x in range(0, image.width(), max(1, image.width() // 30))
        for y in range(0, image.height(), max(1, image.height() // 12))
    ]

    def near(first: QColor, second: QColor, tolerance: int = 60) -> bool:
        return (
            abs(first.red() - second.red()) <= tolerance
            and abs(first.green() - second.green()) <= tolerance
            and abs(first.blue() - second.blue()) <= tolerance
        )

    assert any(near(color, background) for color in colors)
    assert any(near(color, text) for color in colors)
    assert _contrast(background, text) >= 4.5
    window.close()
