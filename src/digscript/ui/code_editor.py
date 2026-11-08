"""Code editor: line numbers, current-line highlight and Python highlighting.

Adapted from the official Qt for Python *Code Editor* example (line
number area and current-line highlight) and the official *Syntax
Highlighter* example (regexp rules for keywords, builtins, strings,
comments, numbers, function/class names and our game API names).
"""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextBlock,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QWheelEvent,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from digscript.ui.theme import (
    ERROR,
    FONT_FAMILY,
    FONT_SIZE,
    SYNTAX_API,
    SYNTAX_BUILTIN,
    SYNTAX_CLASS,
    SYNTAX_COMMENT,
    SYNTAX_FUNCTION,
    SYNTAX_KEYWORD,
    SYNTAX_NUMBER,
    SYNTAX_STRING,
    TEXT_DIM,
)

__all__ = [
    "API_FUNCTIONS",
    "BUILTINS",
    "KEYWORDS",
    "CodeEditor",
    "CodeHighlighter",
    "LineNumberArea",
    "PythonCodeEditor",
    "PythonHighlighter",
    "PythonSyntaxHighlighter",
    "SyntaxHighlighter",
]

KEYWORDS = (
    "False",
    "None",
    "True",
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "case",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "match",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "try",
    "while",
    "with",
    "yield",
)

BUILTINS = (
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "filter",
    "float",
    "int",
    "isinstance",
    "len",
    "list",
    "map",
    "max",
    "min",
    "print",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    "Exception",
    "ValueError",
    "TypeError",
    "NameError",
    "RuntimeError",
    "IndexError",
    "KeyError",
    "AttributeError",
    "ImportError",
    "NotUnlockedError",
)

API_FUNCTIONS = (
    "move",
    "mine",
    "peek",
    "position",
    "sell",
    "inventory",
    "scan",
    "stats",
    "buy_upgrade",
    "North",
    "East",
    "South",
    "West",
    "goto",
    "go_home",
    "sweep",
    "spiral",
    "mine_here",
)


def _api_names(content: Any = None, extra: Any = None) -> tuple[str, ...]:
    names: list[str] = list(API_FUNCTIONS)
    if extra:
        for item in extra:
            text = str(item)
            if text not in names:
                names.append(text)
    raw = getattr(content, "functions", None) if content is not None else None
    items: list[Any] = []
    if isinstance(raw, dict):
        items = list(raw.values())
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    for item in items:
        name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
        if name and str(name) not in names:
            names.append(str(name))
    if content is None:
        try:
            from digscript.core.content import load_content

            loaded = load_content()
            for spec in loaded.functions.values():
                if spec.name not in names:
                    names.append(spec.name)
        except Exception:
            pass
    return tuple(names)


def _make_format(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class PythonHighlighter(QSyntaxHighlighter):
    """Highlights Python code plus the DigScript game API names."""

    def __init__(self, document: Any = None, *args: Any, **kwargs: Any) -> None:
        content = kwargs.pop("content", None)
        api_names = kwargs.pop("api_names", None) or kwargs.pop("api_functions", None)
        api_names = kwargs.pop("api", None) if api_names is None else api_names
        game = kwargs.pop("game", None)
        if game is not None and content is None:
            content = getattr(game, "content", None)
        for arg in args:
            if arg is None:
                continue
            if hasattr(arg, "functions") and hasattr(arg, "config"):
                if content is None:
                    content = arg
            elif isinstance(arg, (list, tuple, set)):
                if api_names is None:
                    api_names = list(arg)  # type: ignore[assignment]
        if document is None:
            document = QTextDocument()
        super().__init__(document)
        self.content = content
        self.api_names: tuple[str, ...] = _api_names(content, api_names)
        self.api_functions = self.api_names

        self.keyword_format = _make_format(SYNTAX_KEYWORD, bold=True)
        self.builtin_format = _make_format(SYNTAX_BUILTIN)
        self.string_format = _make_format(SYNTAX_STRING)
        self.comment_format = _make_format(SYNTAX_COMMENT, italic=True)
        self.number_format = _make_format(SYNTAX_NUMBER)
        self.function_format = _make_format(SYNTAX_FUNCTION)
        self.class_format = _make_format(SYNTAX_CLASS, bold=True)
        self.def_format = self.function_format
        self.api_format = _make_format(SYNTAX_API, bold=True)

        self.formats: dict[str, QTextCharFormat] = {
            "keyword": self.keyword_format,
            "builtin": self.builtin_format,
            "string": self.string_format,
            "comment": self.comment_format,
            "number": self.number_format,
            "function": self.function_format,
            "def": self.function_format,
            "class": self.class_format,
            "api": self.api_format,
        }
        # Aliases that tests / other code may look for.
        self.keywords_format = self.keyword_format
        self.builtins_format = self.builtin_format
        self.strings_format = self.string_format
        self.comments_format = self.comment_format
        self.numbers_format = self.number_format
        self.functions_format = self.function_format
        self.classes_format = self.class_format
        self.game_api_format = self.api_format

        keyword_pattern = r"\b(?:" + "|".join(re.escape(word) for word in KEYWORDS) + r")\b"
        builtin_pattern = r"\b(?:" + "|".join(re.escape(word) for word in BUILTINS) + r")\b"
        api_pattern = r"\b(?:" + "|".join(re.escape(word) for word in self.api_names) + r")\b"
        rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(r"\bdef\s+[A-Za-z_][A-Za-z0-9_]*"), self.function_format),
            (QRegularExpression(r"\bclass\s+[A-Za-z_][A-Za-z0-9_]*"), self.class_format),
            (QRegularExpression(api_pattern), self.api_format),
            (QRegularExpression(keyword_pattern), self.keyword_format),
            (QRegularExpression(builtin_pattern), self.builtin_format),
            (QRegularExpression(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"), self.number_format),
            (
                QRegularExpression(
                    r"\"\"\"[^\"\\]*(?:\\.[^\"\\]*)*\"\"\"|'''[^'\\]*(?:\\.[^'\\]*)*'''|\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'"
                ),
                self.string_format,
            ),
            (QRegularExpression(r"#.*"), self.comment_format),
        ]
        self.rules = rules
        self.highlighting_rules = rules
        self.syntax_highlighter_rules = rules
        self._rules = rules

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt override name
        for pattern, fmt in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                if match.hasCaptured(0):
                    self.setFormat(match.capturedStart(0), match.capturedLength(0), fmt)


SyntaxHighlighter = PythonHighlighter
CodeHighlighter = PythonHighlighter
PythonSyntaxHighlighter = PythonHighlighter


class LineNumberArea(QWidget):
    """Left gutter showing line numbers (Code Editor example)."""

    def __init__(self, editor: CodeEditor) -> None:
        super().__init__(editor)
        self.editor = editor
        self.code_editor = editor

    def sizeHint(self) -> Any:  # noqa: N802
        from PySide6.QtCore import QSize

        try:
            return QSize(self.editor.line_number_area_width(), 0)
        except Exception:
            return QSize(40, 0)

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        try:
            painter.fillRect(event.rect(), QColor("#252535"))
            block = self.editor.firstVisibleBlock()
            number = block.blockNumber()
            top = int(
                self.editor.blockBoundingGeometry(block)
                .translated(self.editor.contentOffset())
                .top()
            )
            error_line = self.editor.error_line
            while block.isValid() and top <= event.rect().bottom():
                width = self.width()
                height = int(self.editor.blockBoundingGeometry(block).height())
                if error_line is not None and number + 1 == error_line:
                    painter.setPen(QColor(ERROR))
                    font = QFont(FONT_FAMILY)
                    font.setBold(True)
                    painter.setFont(font)
                else:
                    painter.setPen(QColor(TEXT_DIM))
                painter.drawText(
                    0, top, width, height, Qt.AlignmentFlag.AlignRight, str(number + 1)
                )
                block = block.next()
                number += 1
                top += height
        finally:
            painter.end()
        super().paintEvent(event)


class CodeEditor(QPlainTextEdit):
    """Python code editor with line numbers and current-line highlight."""

    run_requested = Signal()
    stop_requested = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        parent = kwargs.pop("parent", None)
        content = kwargs.pop("content", None)
        for arg in args:
            if isinstance(arg, QWidget) and parent is None:
                parent = arg
            elif hasattr(arg, "functions") and hasattr(arg, "config"):
                content = arg
        super().__init__(parent)
        self.content = content
        self.error_line: int | None = None
        self._error_line_for_selections: int | None = None
        font = QFont(FONT_FAMILY)
        font.setPointSize(FONT_SIZE)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.line_number_area = LineNumberArea(self)
        self.lineNumberArea = self.line_number_area
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        self.blockCountChanged.connect(self._update_line_number_viewport)
        self.updateRequest.connect(self.line_number_area.update)
        self.cursorPositionChanged.connect(self._update_current_line_highlight)
        self.highlighter = PythonHighlighter(self.document(), content=content)
        self.syntax_highlighter = self.highlighter
        self._update_current_line_highlight()

    # -- line numbers ---------------------------------------------------------

    def line_number_area_width(self) -> int:
        """Return the width of the line number area for the block count."""
        digits = max(1, len(str(max(1, self.blockCount()))))
        width = 3 + self.fontMetrics().horizontalAdvance("9" * digits)
        return max(24, width)

    def lineNumberAreaWidth(self) -> int:  # noqa: N802
        """Alias for :meth:`line_number_area_width`."""
        return self.line_number_area_width()

    @property
    def line_number_width(self) -> int:
        """Current line number area width."""
        return self.line_number_area_width()

    def _update_line_number_viewport(self, _new_block_count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        self.line_number_area.update()

    def update_line_number_area_width(self) -> None:
        """Alias for the viewport-margin update."""
        self._update_line_number_viewport()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.line_number_area.setGeometry(
            rect.left(), rect.top(), self.line_number_area_width(), rect.height()
        )

    # -- current line / error line ----------------------------------------------

    def _update_current_line_highlight(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        cursor = self.textCursor()
        if cursor is not None:
            line_selection = QTextEdit.ExtraSelection()
            line_selection.cursor = cursor
            line_selection.cursor.clearSelection()
            line_selection.cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor("#2a2a3d"))
            line_selection.format = fmt
            line_selection.format.setProperty(QTextCharFormat.Property.UserProperty, 0)
            selections.append(line_selection)
        error_line = self._error_line_for_selections
        if error_line is not None and 1 <= error_line <= self.blockCount():
            block = self.document().findBlockByNumber(error_line - 1)
            if block.isValid():
                error_cursor = QTextCursor(self.document())
                error_cursor.setPosition(block.position())
                error_cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                error_selection = QTextEdit.ExtraSelection()
                error_selection.cursor = error_cursor
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#5a1f2b"))
                fmt.setForeground(QColor(ERROR))
                error_selection.format = fmt
                selections.append(error_selection)
        self.setExtraSelections(selections)

    def highlight_current_line(self) -> None:
        """Refresh the current-line highlight."""
        self._update_current_line_highlight()

    @property
    def error_line_number(self) -> int | None:
        """Alias for :attr:`error_line`."""
        return self.error_line

    @error_line_number.setter
    def error_line_number(self, value: int | None) -> None:
        self.set_error_line(value)

    def set_error_line(self, line_number: int | None) -> None:
        """Mark ``line_number`` (1-based) with a red marker, or clear it."""
        self.error_line = int(line_number) if line_number is not None else None
        self._error_line_for_selections = self.error_line
        self._update_current_line_highlight()
        self.line_number_area.update()

    def highlight_error_line(self, line_number: int | None = None) -> None:
        """Alias for :meth:`set_error_line`."""
        self.set_error_line(self.error_line if line_number is None else line_number)

    def mark_error_line(self, line_number: int | None = None) -> None:
        """Alias for :meth:`set_error_line`."""
        self.set_error_line(self.error_line if line_number is None else line_number)

    def show_error_line(self, line_number: int | None = None) -> None:
        """Alias for :meth:`set_error_line`."""
        self.set_error_line(self.error_line if line_number is None else line_number)

    def clear_error_line(self) -> None:
        """Clear the error marker."""
        self.set_error_line(None)

    def clear_error(self) -> None:
        """Alias for :meth:`clear_error_line`."""
        self.clear_error_line()

    def goto_line(self, line_number: int, column: int = 0) -> None:
        """Move the cursor to ``line_number`` (1-based)."""
        index = max(0, int(line_number) - 1)
        index = min(index, max(0, self.blockCount() - 1))
        block = self.document().findBlockByNumber(index)
        cursor = self.textCursor()
        if block.isValid():
            cursor.setPosition(block.position() + max(0, int(column)))
        self.setTextCursor(cursor)
        self.centerOnScroll()

    def go_to_line(self, line_number: int, column: int = 0) -> None:
        """Alias for :meth:`goto_line`."""
        self.goto_line(line_number, column)

    def set_cursor_to_line(self, line_number: int, column: int = 0) -> None:
        """Alias for :meth:`goto_line`."""
        self.goto_line(line_number, column)

    def move_cursor_to_line(self, line_number: int, column: int = 0) -> None:
        """Alias for :meth:`goto_line`."""
        self.goto_line(line_number, column)

    # -- editing helpers ---------------------------------------------------------

    def toggle_comment(self) -> None:
        """Toggle ``#`` comments on the current / selected lines."""
        cursor = self.textCursor()
        start_block = cursor.block()
        end_block = cursor.block()
        if cursor.hasSelection():
            end_block = self.document().findBlock(cursor.selectionEnd() - 1)
        blocks: list[QTextBlock] = []
        block = start_block
        while block.isValid():
            blocks.append(block)
            if block == end_block:
                break
            block = block.next()
        texts = [block.text() for block in blocks]
        non_empty = [text for text in texts if text.strip()]
        all_commented = bool(non_empty) and all(text.lstrip().startswith("#") for text in non_empty)
        cursor.beginEditBlock()
        try:
            for block, text in zip(blocks, texts, strict=False):
                if not text.strip():
                    continue
                block_cursor = QTextCursor(self.document())
                block_cursor.setPosition(block.position())
                if all_commented:
                    stripped = text.lstrip()
                    indent_len = len(text) - len(stripped)
                    comment_len = 2 if stripped.startswith("# ") else 1
                    block_cursor.movePosition(
                        QTextCursor.MoveOperation.Right,
                        QTextCursor.MoveMode.KeepAnchor,
                        indent_len + comment_len,
                    )
                    block_cursor.removeSelectedText()
                else:
                    block_cursor.insertText("# ")
        finally:
            cursor.endEditBlock()
        self.setTextCursor(cursor)

    def toggle_line_comment(self) -> None:
        """Alias for :meth:`toggle_comment`."""
        self.toggle_comment()

    def toggle_comments(self) -> None:
        """Alias for :meth:`toggle_comment`."""
        self.toggle_comment()

    def dedent_selection(self) -> None:
        """Remove one level of indentation from the current/selected lines."""
        cursor = self.textCursor()
        start_block = cursor.block()
        end_block = (
            self.document().findBlock(cursor.selectionEnd() - 1)
            if cursor.hasSelection()
            else start_block
        )
        blocks: list[QTextBlock] = []
        block = start_block
        while block.isValid():
            blocks.append(block)
            if block == end_block:
                break
            block = block.next()
        cursor.beginEditBlock()
        try:
            for block in blocks:
                text = block.text()
                if text.startswith("    "):
                    remove = 4
                elif text.startswith("\t"):
                    remove = 1
                elif text.startswith(" "):
                    remove = 1
                else:
                    continue
                block_cursor = QTextCursor(self.document())
                block_cursor.setPosition(block.position())
                block_cursor.movePosition(
                    QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, remove
                )
                block_cursor.removeSelectedText()
        finally:
            cursor.endEditBlock()

    def dedent(self) -> None:
        """Alias for :meth:`dedent_selection`."""
        self.dedent_selection()

    def indent_selection(self) -> None:
        """Add one level of indentation to the current/selected lines."""
        cursor = self.textCursor()
        start_block = cursor.block()
        end_block = (
            self.document().findBlock(cursor.selectionEnd() - 1)
            if cursor.hasSelection()
            else start_block
        )
        blocks: list[QTextBlock] = []
        block = start_block
        while block.isValid():
            blocks.append(block)
            if block == end_block:
                break
            block = block.next()
        cursor.beginEditBlock()
        try:
            for block in blocks:
                block_cursor = QTextCursor(self.document())
                block_cursor.setPosition(block.position())
                block_cursor.insertText("    ")
        finally:
            cursor.endEditBlock()

    # -- font zoom ----------------------------------------------------------------

    def set_font_size(self, size: int) -> None:
        """Set the editor font point size."""
        font = self.font()
        font.setPointSize(max(6, int(size)))
        self.setFont(font)
        self._update_line_number_viewport()

    def increase_font_size(self, steps: int = 1) -> None:
        """Increase the font size by ``steps`` points."""
        current = self.font().pointSize()
        if current <= 0:
            current = FONT_SIZE
        self.set_font_size(current + int(steps))

    def decrease_font_size(self, steps: int = 1) -> None:
        """Decrease the font size by ``steps`` points."""
        current = self.font().pointSize()
        if current <= 0:
            current = FONT_SIZE
        self.set_font_size(current - int(steps))

    def zoom_in(self) -> None:
        """Alias for :meth:`increase_font_size`."""
        self.increase_font_size()

    def zoom_out(self) -> None:
        """Alias for :meth:`decrease_font_size`."""
        self.decrease_font_size()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() // 120
            if steps == 0:
                steps = 1 if event.angleDelta().y() > 0 else -1
            if steps > 0:
                self.increase_font_size(int(steps))
            else:
                self.decrease_font_size(int(-steps))
            event.accept()
        else:
            super().wheelEvent(event)

    # -- focus / world ---------------------------------------------------------------

    def _focus_world(self) -> None:
        widget: Any = self
        while widget is not None:
            world_view = getattr(widget, "world_view", None)
            if world_view is not None and hasattr(world_view, "setFocus"):
                world_view.setFocus()
                return
            widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None
        # Fallback: parent chain may reach a MainWindow via window().
        try:
            window = self.window()
            world_view = getattr(window, "world_view", None)
            if world_view is not None:
                world_view.setFocus()
                return
        except Exception:
            pass
        self.clearFocus()

    def focus_world(self) -> None:
        """Alias for :meth:`_focus_world`."""
        self._focus_world()

    # -- keys ---------------------------------------------------------------------------

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802
        key = event.key()
        modifiers = event.modifiers()
        # Ctrl+R: run, Ctrl+.: stop
        if modifiers & Qt.KeyboardModifier.ControlModifier and key in (Qt.Key.Key_R,):
            self.run_requested.emit()
            event.accept()
            return
        if modifiers & Qt.KeyboardModifier.ControlModifier and key in (Qt.Key.Key_Period,):
            self.stop_requested.emit()
            event.accept()
            return
        if modifiers & Qt.KeyboardModifier.ControlModifier and key in (Qt.Key.Key_Slash,):
            self.toggle_comment()
            event.accept()
            return
        if key == Qt.Key.Key_Escape:
            self._focus_world()
            event.accept()
            return
        if key == Qt.Key.Key_Tab:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.dedent_selection()
            elif self.textCursor().hasSelection():
                self.indent_selection()
            else:
                self.insertPlainText("    ")
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
            modifiers & Qt.KeyboardModifier.ControlModifier
        ):
            block = self.textCursor().block()
            line = block.text() if block.isValid() else ""
            indent_text = line[: len(line) - len(line.lstrip())]
            needs_extra = line.rstrip().endswith(":")
            super().keyPressEvent(event)
            extra = "    " if needs_extra else ""
            if indent_text or extra:
                self.insertPlainText(indent_text + extra)
            event.accept()
            return
        super().keyPressEvent(event)


PythonCodeEditor = CodeEditor
