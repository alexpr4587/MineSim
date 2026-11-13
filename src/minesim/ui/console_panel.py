"""Console panel: read-only coloured log for script output."""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from minesim.ui.theme import CONSOLE_ERR, CONSOLE_INFO, CONSOLE_OUT, FONT_FAMILY

__all__ = ["ConsolePanel", "LogPanel"]

_TRACEBACK_RE = re.compile(r"line\s+(\d+)")
_FILE_LINE_RE = re.compile(r'File\s+"[^"]+",\s+line\s+(\d+)')


def _kind_of(value: Any) -> str:
    text = str(value or "out").lower()
    if text in ("err", "error", "stderr", "traceback"):
        return "err"
    if text in ("info", "information", "system"):
        return "info"
    return "out"


class _LogTextEdit(QPlainTextEdit):
    """QPlainTextEdit with a ``toHtml`` helper (like QTextEdit)."""

    def toHtml(self) -> str:  # noqa: N802
        """Return simple HTML containing the log lines in their colours."""
        parts: list[str] = ["<html><body>"]
        doc = self.document()
        plain = self.toPlainText()
        index = 0
        for block_text in plain.split("\n"):
            color = "#e6e6e6"
            if index < doc.characterCount():
                probe = self.textCursor()
                probe.setPosition(index)
                fmt_color = probe.charFormat().foreground().color()
                if fmt_color.isValid():
                    color = fmt_color.name()
            escaped = block_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f'<p style="color:{color}">{escaped}</p>')
            index += len(block_text) + 1
        parts.append("</body></html>")
        return "".join(parts)


class ConsolePanel(QWidget):
    """Read-only log with coloured out/err/info lines and auto-scroll."""

    line_clicked = Signal(int)
    traceback_line_clicked = Signal(int)
    error_line_clicked = Signal(int)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        parent = kwargs.pop("parent", None)
        editor = kwargs.pop("editor", None) or kwargs.pop("code_editor", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget):
                if parent is None:
                    parent = arg
            elif hasattr(arg, "toPlainText"):
                if editor is None:
                    editor = arg
        super().__init__(parent)
        self.editor = editor
        self.code_editor = editor
        self.formats: dict[str, QTextCharFormat] = {}
        for kind, color in (("out", CONSOLE_OUT), ("err", CONSOLE_ERR), ("info", CONSOLE_INFO)):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self.formats[kind] = fmt
        self._lines: list[dict[str, Any]] = []
        self._block_line_numbers: list[int | None] = []
        self.lines: list[dict[str, Any]] = self._lines

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        header = QHBoxLayout()
        self.clear_button = QPushButton("Clear", self)
        self.clear_button.setObjectName("clear_button")
        self.clear_button.clicked.connect(self.clear)
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll", self)
        self.auto_scroll_checkbox.setObjectName("auto_scroll_checkbox")
        self.auto_scroll_checkbox.setChecked(True)
        self.autoscroll_checkbox = self.auto_scroll_checkbox
        self.auto_scroll_check = self.auto_scroll_checkbox
        header.addWidget(self.clear_button)
        header.addWidget(self.auto_scroll_checkbox)
        header.addStretch(1)
        layout.addLayout(header)

        self.text_edit = _LogTextEdit(self)
        self.text_edit.setObjectName("console_log")
        self.text_edit.setReadOnly(True)
        from PySide6.QtGui import QFont

        self.text_edit.setFont(QFont(FONT_FAMILY))
        self.log = self.text_edit
        self.console = self.text_edit
        self.output = self.text_edit
        self.view = self.text_edit
        self.text_area = self.text_edit
        self.text_edit.installEventFilter(self)
        layout.addWidget(self.text_edit, 1)

    # -- auto-scroll ------------------------------------------------------------

    @property
    def auto_scroll(self) -> bool:
        """Whether the log auto-scrolls to the newest line."""
        return self.auto_scroll_checkbox.isChecked()

    @auto_scroll.setter
    def auto_scroll(self, value: bool) -> None:
        self.auto_scroll_checkbox.setChecked(bool(value))

    def set_auto_scroll(self, value: bool) -> None:
        """Set auto-scroll on/off."""
        self.auto_scroll_checkbox.setChecked(bool(value))

    def _update_extra_selections(self) -> None:
        from PySide6.QtWidgets import QTextEdit

        selections: list[Any] = []
        doc = self.text_edit.document()
        for index, line in enumerate(self._lines):
            if index >= doc.blockCount():
                break
            block = doc.findBlockByNumber(index)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(doc)
            cursor.setPosition(block.position())
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            selection.cursor = cursor
            fmt = QTextCharFormat()
            fmt.setForeground(self.formats[line["kind"]].foreground())
            selection.format = fmt
            selections.append(selection)
        self.text_edit.setExtraSelections(selections)

    def _scroll_to_bottom(self) -> None:
        if not self.auto_scroll:
            return
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.text_edit.setTextCursor(cursor)

    # -- appending ----------------------------------------------------------------

    def _parse_line_number(self, text: str) -> int | None:
        match = _FILE_LINE_RE.search(text) or _TRACEBACK_RE.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None

    def append_line(self, text: Any = "", kind: Any = "out", **kwargs: Any) -> None:
        """Append one line (or a HostEvent) to the console."""
        line_kind = kind
        line_text = text
        if hasattr(text, "kind") or hasattr(text, "text"):
            event = text
            line_kind = getattr(event, "kind", None) or getattr(event, "type", None) or kind
            line_text = getattr(event, "text", None)
            if line_text is None:
                line_text = getattr(event, "message", "") or str(event)
            if getattr(event, "line_number", None) is not None:
                pass
        if "stream" in kwargs:
            line_kind = kwargs["stream"]
        if "type" in kwargs:
            line_kind = kwargs["type"]
        normalised = _kind_of(line_kind)
        raw = "" if line_text is None else str(line_text)
        # Multi-line payloads (e.g. a traceback) become one console line each.
        parts = raw.split("\n")
        for index, part in enumerate(parts):
            if index == len(parts) - 1 and part == "" and len(parts) > 1:
                continue
            line_number = self._parse_line_number(part)
            # A HostEvent for a failure may carry the line directly.
            if hasattr(text, "line_number") and text.line_number is not None and index == 0:
                try:
                    line_number = int(text.line_number)
                except Exception:
                    pass
            self._lines.append({"text": part, "kind": normalised, "line_number": line_number})
            self._block_line_numbers.append(line_number)
            cursor = self.text_edit.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(part, self.formats[normalised])
            cursor.insertText("\n")
            self.text_edit.setTextCursor(cursor)
        self.lines = self._lines
        self._update_extra_selections()
        self._scroll_to_bottom()

    def add_line(self, text: Any = "", kind: Any = "out", **kwargs: Any) -> None:
        """Alias for :meth:`append_line`."""
        self.append_line(text, kind, **kwargs)

    def append(self, text: Any = "", kind: Any = "out", **kwargs: Any) -> None:
        """Alias for :meth:`append_line`."""
        self.append_line(text, kind, **kwargs)

    def write(self, text: Any = "", kind: Any = "out", **kwargs: Any) -> None:
        """Alias for :meth:`append_line`."""
        self.append_line(text, kind, **kwargs)

    def print_line(self, text: Any = "", kind: Any = "out", **kwargs: Any) -> None:
        """Alias for :meth:`append_line`."""
        self.append_line(text, kind, **kwargs)

    def log_line(self, text: Any = "", kind: Any = "out", **kwargs: Any) -> None:
        """Alias for :meth:`append_line`."""
        self.append_line(text, kind, **kwargs)

    def add_console_line(self, text: Any = "", kind: Any = "out", **kwargs: Any) -> None:
        """Alias for :meth:`append_line`."""
        self.append_line(text, kind, **kwargs)

    def append_events(self, events: Any) -> None:
        """Append every HostEvent in ``events``."""
        for event in events or []:
            self.append_line(event)

    def add_events(self, events: Any) -> None:
        """Alias for :meth:`append_events`."""
        self.append_events(events)

    def handle_events(self, events: Any) -> None:
        """Alias for :meth:`append_events`."""
        self.append_events(events)

    def clear(self) -> None:
        """Clear the console."""
        self.text_edit.clear()
        self._lines.clear()
        self._block_line_numbers.clear()
        self.lines = self._lines
        self.text_edit.setExtraSelections([])

    def clear_console(self) -> None:
        """Alias for :meth:`clear`."""
        self.clear()

    def to_plain_text(self) -> str:
        """Return the console text."""
        return self.text_edit.toPlainText()

    # -- editor link ----------------------------------------------------------------

    def set_editor(self, editor: Any) -> None:
        """Attach a code editor that traceback clicks should jump to."""
        self.editor = editor
        self.code_editor = editor

    def attach_editor(self, editor: Any) -> None:
        """Alias for :meth:`set_editor`."""
        self.set_editor(editor)

    def set_code_editor(self, editor: Any) -> None:
        """Alias for :meth:`set_editor`."""
        self.set_editor(editor)

    def _jump_to_line(self, line_number: int | None) -> None:
        if line_number is None:
            return
        self.line_clicked.emit(int(line_number))
        self.traceback_line_clicked.emit(int(line_number))
        self.error_line_clicked.emit(int(line_number))
        editor = self.editor
        if editor is not None:
            goto = getattr(editor, "goto_line", None) or getattr(editor, "go_to_line", None)
            if callable(goto):
                goto(int(line_number))
                return
            set_cursor = getattr(editor, "setCursorPosition", None)
            if callable(set_cursor):
                set_cursor(int(line_number), 0)

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        if obj is self.text_edit and event.type() == event.Type.MouseButtonPress:
            try:
                cursor = self.text_edit.cursorForPosition(event.position().toPoint())
                block_number = cursor.blockNumber()
                if 0 <= block_number < len(self._block_line_numbers):
                    self._jump_to_line(self._block_line_numbers[block_number])
                    # Also try to parse the clicked block text directly.
                    if self._block_line_numbers[block_number] is None:
                        text = cursor.block().text()
                        self._jump_to_line(self._parse_line_number(text))
            except Exception:
                pass
        return super().eventFilter(obj, event)


LogPanel = ConsolePanel
