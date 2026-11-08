"""Tests for floating panels, code editor and script execution (prompt 06)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QTextCursor  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from digscript.core.game import Game  # noqa: E402
from digscript.ui.code_editor import CodeEditor, PythonHighlighter  # noqa: E402
from digscript.ui.console_panel import ConsolePanel  # noqa: E402
from digscript.ui.editor_panel import STARTER_SCRIPT  # noqa: E402
from digscript.ui.floating_panel import FloatingPanel  # noqa: E402
from digscript.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_settings(qapp):
    QSettings("DigScript", "DigScript").clear()
    yield
    QSettings("DigScript", "DigScript").clear()


def _window(qapp, tmp_path):
    game = Game.new()
    window = MainWindow(game, scripts_dir=tmp_path)
    window.show()
    qapp.processEvents()
    return game, window


def test_line_number_width_grows(qapp):
    editor = CodeEditor()
    editor.setPlainText("x = 1\n")
    small = editor.line_number_area_width()
    assert small > 0
    assert editor.lineNumberAreaWidth() == small
    editor.setPlainText("\n".join(f"x{i} = {i}" for i in range(1000)))
    assert editor.line_number_area_width() > small
    editor.close()


def test_highlighter_formats_on_sample(qapp):
    editor = CodeEditor()
    editor.setPlainText(
        'def foo():\n    return 42 # comment\n    s = "hi"\n    move(East)\n    print(s)\n'
    )
    editor.show()
    qapp.processEvents()
    highlighter = editor.highlighter
    assert isinstance(highlighter, PythonHighlighter)
    assert highlighter.keyword_format.foreground().color().name()
    assert highlighter.api_format.foreground().color() != (
        highlighter.keyword_format.foreground().color()
    )
    assert highlighter.builtin_format is not highlighter.api_format
    doc = editor.document()
    collected: list[tuple[int, str]] = []
    for index in range(doc.blockCount()):
        block = doc.findBlockByNumber(index)
        for fmt_range in block.layout().formats():
            collected.append((fmt_range.start, fmt_range.format.foreground().color().name()))
    colors = {color for _start, color in collected}
    assert highlighter.keyword_format.foreground().color().name() in colors
    assert highlighter.number_format.foreground().color().name() in colors
    assert highlighter.string_format.foreground().color().name() in colors
    assert highlighter.comment_format.foreground().color().name() in colors
    assert highlighter.api_format.foreground().color().name() in colors
    assert highlighter.builtin_format.foreground().color().name() in colors
    assert highlighter.function_format.foreground().color().name() in colors
    editor.close()


def test_editor_editing_keys(qapp):
    editor = CodeEditor()
    editor.show()
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.toPlainText() == "    "
    editor.setPlainText("if True:")
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Return)
    assert editor.toPlainText() == "if True:\n    "
    editor.setPlainText("    x = 1")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    assert editor.toPlainText() == "x = 1"
    editor.setPlainText("x = 1")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)
    QTest.keyClick(editor, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier)
    assert editor.toPlainText() == "# x = 1"
    QTest.keyClick(editor, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier)
    assert editor.toPlainText() == "x = 1"
    editor.close()


def test_floating_panel_stays_inside_and_restores(qapp):
    parent = QWidget()
    parent.resize(900, 700)
    parent.show()
    panel = FloatingPanel("TestPanelRestoreXY", parent=parent)
    panel.show()
    panel.move(9999, 9999)
    assert panel.pos().x() + panel.width() <= parent.width()
    assert panel.pos().y() + panel.height() <= parent.height()
    panel.move(123, 111)
    panel.resize(380, 280)
    panel.save_geometry()
    panel.close()
    restored = FloatingPanel("TestPanelRestoreXY", parent=parent)
    assert restored.pos().x() == 123
    assert restored.pos().y() == 111
    assert restored.width() == 380
    assert not restored.isWindow()
    restored.close()
    parent.close()


def test_hotkeys_do_not_fire_while_editor_has_focus(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path)
    window.world_view.setFocus()
    qapp.processEvents()
    assert window.editor_panel.isVisible()
    window.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_E, Qt.NoModifier))
    assert not window.editor_panel.isVisible()
    window.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_E, Qt.NoModifier))
    assert window.editor_panel.isVisible()
    window.code_editor.setFocus()
    qapp.processEvents()
    assert window.code_editor.hasFocus()
    speed_before = window.game_loop.speed
    window.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_E, Qt.NoModifier))
    assert window.editor_panel.isVisible()
    window.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.NoModifier))
    assert window.game_loop.speed == speed_before
    QTest.keyClick(window.code_editor, Qt.Key.Key_Escape)
    assert window.world_view.hasFocus()
    window.close()


def test_starter_file_and_api_panel(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path)
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == STARTER_SCRIPT
    assert window.editor_panel.tabs.count() >= 1
    assert window.editor_panel.state_label.text() == "Idle"
    assert window.console_panel is not None
    assert window.api_panel.plain_text() != ""
    assert "move(direction)" in window.api_panel.plain_text()
    assert "goto(x, y)" in window.api_panel.plain_text()
    assert "import random" in window.api_panel.plain_text()
    assert "Locked, unlock with the achievement First Dig" in window.api_panel.plain_text()
    window.close()


def test_console_clear_and_traceback_jump(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path)
    console = ConsolePanel()
    console.append_line("out line", "out")
    console.append_line("err line", "err")
    console.append_line("info line", "info")
    assert "out line" in console.to_plain_text()
    console.set_editor(window.code_editor)
    console.append_line('  File "main.py", line 2, in <module>', "err")
    console._jump_to_line(2)
    assert window.code_editor.textCursor().blockNumber() == 1
    console.clear()
    assert console.to_plain_text() == ""
    console.close()
    window.close()


def _run_until_done(window, timeout_loops=1000):
    for _ in range(timeout_loops):
        window.game_loop.advance(100)
        from PySide6.QtWidgets import QApplication

        QApplication.instance().processEvents()
        if str(window.host.state) != "RUNNING":
            break


def test_running_starter_script_moves_miner_and_unlocks(qapp, tmp_path):
    game, window = _window(qapp, tmp_path)
    window.editor_panel.run()
    assert window.editor_panel.state_label.text() == "Running"
    _run_until_done(window)
    assert str(window.host.state) == "FINISHED"
    assert window.editor_panel.state_label.text() == "Finished"
    assert (game.miner.x, game.miner.y) == (10, 0)
    assert "hello_miner" in game.progression_state.completed
    window.close()


def test_script_error_highlights_right_line(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path)
    window.code_editor.setPlainText('x = 1\nraise ValueError("boom")\ny = 2\n')
    window.editor_panel.run()
    _run_until_done(window)
    assert str(window.host.state) == "FAILED"
    assert window.editor_panel.state_label.text() == "Error"
    assert window.code_editor.error_line == 2
    assert "line 2" in window.console_panel.to_plain_text()
    window.close()


def test_stop_kills_running_script(qapp, tmp_path):
    _game, window = _window(qapp, tmp_path)
    window.code_editor.setPlainText("while True:\n    pass\n")
    window.editor_panel.run()
    assert str(window.host.state) == "RUNNING"
    window.editor_panel.stop()
    assert str(window.host.state) == "STOPPED"
    process = window.host.process
    assert process is None or not process.is_alive()
    window.close()
