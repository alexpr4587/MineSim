"""Editor panel: script tabs, run/stop controls and the console."""

from __future__ import annotations

import keyword
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QFileSystemWatcher, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from minesim.ui.code_editor import CodeEditor
from minesim.ui.console_panel import ConsolePanel
from minesim.ui.floating_panel import FloatingPanel, ensure_settings_names
from minesim.ui.theme import (
    BACKGROUND,
    BUTTON_BORDER,
    HUD_BACKGROUND,
    TEXT,
    TEXT_DIM,
    miner_badge_color,
)

__all__ = [
    "DEFAULT_SCRIPTS_DIR",
    "OPEN_TABS_KEY",
    "ACTIVE_TAB_KEY",
    "STARTER_SCRIPT",
    "STARTER_SOURCE",
    "TRASH_DIR_NAME",
    "EditorPanel",
    "FileListPopup",
    "default_scripts_dir",
    "get_scripts_dir",
    "is_valid_module_name",
    "validate_module_name",
]

OPEN_TABS_KEY = "editor/open_tabs"
ACTIVE_TAB_KEY = "editor/active_tab"
TRASH_DIR_NAME = ".trash"
AUTOSAVE_MS = 2000
_DIRTY_MARK = " ●"
_TRASH_STAMP_RE = re.compile(r"^\d{8}-\d{6}-\d{6}_(.+)$")


def validate_module_name(name: Any) -> str:
    """Return ``name`` as a ``.py`` file name if it is a valid module name.

    Scripts can be imported by other scripts, so the stem must be a Python
    identifier (and not a keyword).
    """
    text = Path(str(name)).name.strip()
    if text.endswith(".py"):
        text = text[:-3]
    if not text or not text.isidentifier() or keyword.iskeyword(text):
        raise ValueError(f"{name!r} is not a valid Python module name")
    return f"{text}.py"


def is_valid_module_name(name: Any) -> bool:
    """Return True when ``name`` is a valid importable Python module name."""
    try:
        validate_module_name(name)
    except ValueError:
        return False
    return True


class EditorTabBar(QTabBar):
    """Tab bar that paints a running-script dot in each tab."""

    def __init__(self, panel: EditorPanel | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.panel = panel

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        super().paintEvent(event)
        panel = self.panel
        if panel is None:
            return
        painter = QPainter(self)
        try:
            for index in range(self.count()):
                color = panel.tab_running_color_by_index(index)
                if color is None:
                    continue
                rect = self.tabRect(index)
                size = 7
                x = rect.right() - 20
                y = rect.top() + (rect.height() - size) // 2
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(color))
                painter.drawEllipse(x, y, size, size)
        finally:
            painter.end()


class FileListPopup(QFrame):
    """Small searchable list overlay (used by Open and Restore)."""

    file_chosen = Signal(str)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("file_list_popup")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "FileListPopup {"
            f" background-color: {BACKGROUND}; border: 1px solid {BUTTON_BORDER};"
            " }"
            f" QLabel {{ color: {TEXT}; }}"
            f" QLineEdit, QListWidget {{ background-color: {HUD_BACKGROUND};"
            f" color: {TEXT}; border: 1px solid {BUTTON_BORDER}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.title_label = QLabel(title, self)
        self.title_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("file_list_search")
        self.search_edit.setPlaceholderText("Search…")
        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("file_list")
        self.empty_label = QLabel("No files", self)
        self.empty_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.empty_label.hide()
        layout.addWidget(self.title_label)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.list_widget, 1)
        layout.addWidget(self.empty_label)
        self._entries: list[tuple[str, Path]] = []
        self.search_edit.textChanged.connect(self._apply_filter)
        self.list_widget.itemActivated.connect(self._choose_item)
        self.list_widget.itemDoubleClicked.connect(self._choose_item)

    def set_entries(self, entries: list[tuple[str, Path]]) -> None:
        """Populate the list with ``(display name, path)`` entries."""
        self._entries = list(entries)
        self.list_widget.clear()
        for display, path in entries:
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.list_widget.addItem(item)
        self._apply_filter(self.search_edit.text())

    def refresh_files(self) -> None:
        """Re-apply the current search filter."""
        self._apply_filter(self.search_edit.text())

    def _apply_filter(self, text: str) -> None:
        needle = str(text or "").strip().lower()
        visible = 0
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            matches = not needle or needle in item.text().lower()
            item.setHidden(not matches)
            if matches:
                visible += 1
        self.empty_label.setVisible(visible == 0)

    def _choose_item(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path is None:
            return
        self.hide()
        self.file_chosen.emit(str(path))

    def show_popup(self) -> None:
        """Show the popup over its parent and focus the search box."""
        parent = self.parentWidget()
        width = 380
        height = 260
        if parent is not None:
            width = max(220, min(width, parent.width() - 16))
            height = max(150, min(height, parent.height() - 16))
        self.resize(width, height)
        self.move(8, 8)
        self.raise_()
        self.show()
        self.search_edit.setFocus()
        self.search_edit.selectAll()


STARTER_SCRIPT = (
    "# Welcome! Edit this script and press Run (Ctrl+R).\n"
    "for _ in range(10):\n"
    "    if peek() is not None:\n"
    "        mine()\n"
    "    move(East)\n"
)
STARTER_SOURCE = STARTER_SCRIPT


def default_scripts_dir() -> Path:
    """Return ``user_data_dir('MineSim')/scripts`` as a Path."""
    try:
        from platformdirs import user_data_dir

        base = user_data_dir("MineSim")
    except Exception:
        base = str(Path.home() / ".local" / "share" / "MineSim")
    return Path(base) / "scripts"


get_scripts_dir = default_scripts_dir


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class EditorPanel(FloatingPanel):
    """Floating editor panel with tabs for ``scripts_dir/*.py`` files."""

    editor_changed = Signal(object)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Editor"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        host = kwargs.pop("host", None) or kwargs.pop("script_host", None)
        manager = kwargs.pop("manager", None) or kwargs.pop("script_manager", None)
        engine = kwargs.pop("engine", None)
        content = kwargs.pop("content", None)
        progression = kwargs.pop("progression", None) or kwargs.pop("progression_view", None)
        scripts_dir = (
            kwargs.pop("scripts_dir", None)
            or kwargs.pop("script_dir", None)
            or kwargs.pop("scripts_directory", None)
            or kwargs.pop("directory", None)
        )
        console_panel = kwargs.pop("console_panel", None) or kwargs.pop("console", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, str):
                if title is None:
                    title = arg
            elif isinstance(arg, QWidget):
                if parent is None:
                    parent = arg
            elif hasattr(arg, "ensure_host") and hasattr(arg, "pump"):
                if manager is None:
                    manager = arg
            elif hasattr(arg, "start") and hasattr(arg, "pump"):
                if host is None:
                    host = arg
            elif hasattr(arg, "engine") and hasattr(arg, "miner"):
                if game is None:
                    game = arg
            elif hasattr(arg, "submit") and hasattr(arg, "step"):
                if engine is None:
                    engine = arg
            elif hasattr(arg, "config") and hasattr(arg, "ores"):
                if content is None:
                    content = arg
            elif hasattr(arg, "is_function_unlocked"):
                if progression is None:
                    progression = arg
            elif isinstance(arg, (str, Path)):
                if scripts_dir is None:
                    scripts_dir = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        self.game = game
        if game is None and host is None and engine is None:
            try:
                from minesim.core.game import Game

                game = Game.new()
                self.game = game
            except Exception:
                game = None
        if game is not None:
            if engine is None:
                engine = _get(game, "engine")
            if content is None:
                content = _get(game, "content")
            if progression is None:
                progression = (
                    _get(game, "progression_service")
                    or _get(game, "progression")
                    or _get(game, "progression_view")
                )
        self.scripts_dir: Path = (
            Path(scripts_dir) if scripts_dir is not None else default_scripts_dir()
        )
        self.scripts_directory = self.scripts_dir
        self.script_dir = self.scripts_dir
        self.scripts_path = self.scripts_dir
        if self.scripts_dir is not None:
            try:
                self.scripts_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            # Starter script on first run.
            main_py = self.scripts_dir / "main.py"
            if not main_py.exists():
                try:
                    main_py.write_text(STARTER_SCRIPT, encoding="utf-8")
                except Exception:
                    pass
        if manager is None and host is None and game is not None:
            try:
                from minesim.scripting.manager import ScriptManager

                manager = ScriptManager(game, self.scripts_dir)
            except Exception:
                manager = None
        if manager is not None:
            if host is None:
                try:
                    host = manager.host(0) or manager.ensure_host(0)
                except Exception:
                    host = None
        elif host is None:
            try:
                from minesim.scripting.host import ScriptHost

                host = ScriptHost(engine, content, progression, self.scripts_dir)
            except Exception:
                host = None
        self.manager = manager
        self.script_manager = manager
        self.host = host
        self.script_host = host
        self.engine = engine
        self.content_data = content
        self.progression = progression
        self.progression_view = progression

        super().__init__(title, parent=parent)
        self.setWindowTitle(str(title))
        if not self._restored_geometry:
            self.resize(680, 540)
            self.move(60, 48)

        self._editors: dict[str, CodeEditor] = {}
        self.editors: dict[str, CodeEditor] = self._editors
        self._paths: dict[str, Path] = {}
        self._tab_index_by_name: dict[str, int] = {}
        self._saving: bool = False
        self._changing: bool = False
        self._restoring: bool = False
        self._closed_stack: list[Path] = []
        self._autosave_editor: CodeEditor | None = None
        self.editor: CodeEditor | None = None
        self.code_editor: CodeEditor | None = None
        self.current_editor: CodeEditor | None = None

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)

        self.tabs = QTabWidget(self.content_widget)
        self.tab_bar = EditorTabBar(self, self.tabs)
        self.tabs.setTabBar(self.tab_bar)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tab_widget = self.tabs
        self.file_tabs = self.tabs
        self.tabWidget = self.tabs
        body.addWidget(self.tabs, 1)

        controls = QVBoxLayout()
        actions = QHBoxLayout()
        self.open_file_button = QPushButton("Open…", self.content_widget)
        self.new_file_button = QPushButton("New file", self.content_widget)
        self.run_button = QPushButton("Run", self.content_widget)
        self.run_on_new_button = QPushButton("Run on new miner", self.content_widget)
        self.stop_button = QPushButton("Stop", self.content_widget)
        self.open_folder_button = QPushButton("Folder", self.content_widget)
        self.examples_button = QPushButton("Examples", self.content_widget)
        self.file_actions_button = QPushButton("⋯", self.content_widget)
        self.file_actions_menu = QMenu(self.file_actions_button)
        self.file_actions_button.setMenu(self.file_actions_menu)
        self.examples_menu = QMenu(self.examples_button)
        self.examples_button.setMenu(self.examples_menu)
        self._example_actions: dict[str, Any] = {}
        self.new_button = self.new_file_button
        self.open_scripts_folder_button = self.open_folder_button
        self.open_button = self.open_file_button
        self.open_file_button.clicked.connect(lambda: self.open_dialog())
        self.new_file_button.clicked.connect(lambda: self.new_file())
        self.run_button.clicked.connect(self.run)
        self.run_on_new_button.clicked.connect(self.run_on_new_miner)
        self.stop_button.clicked.connect(self.stop)
        self.open_folder_button.clicked.connect(self.open_scripts_folder)
        self.open_file_button.setToolTip(
            "Open an existing script (Ctrl+Shift+T reopens the last closed)"
        )
        self.open_folder_button.setToolTip("Open scripts folder")
        self.examples_button.setToolTip("Open an example script in a new tab")
        self.file_actions_button.setToolTip("File actions")
        self._build_file_actions_menu()
        for button in (
            self.open_file_button,
            self.new_file_button,
            self.run_button,
            self.run_on_new_button,
            self.stop_button,
            self.open_folder_button,
            self.examples_button,
            self.file_actions_button,
        ):
            button.setToolTip(button.toolTip() or button.text())
            actions.addWidget(button)
        actions.addStretch(1)
        controls.addLayout(actions)
        status = QHBoxLayout()
        self.state_label = QLabel("Idle", self.content_widget)
        self.status_label = self.state_label
        self.stateLabel = self.state_label
        status.addWidget(self.state_label)
        self.miner_name_label = QLabel("No miner running this file", self.content_widget)
        self.miner_name_label.setObjectName("editor_miner_name")
        self.miner_name_label.setStyleSheet(f"color: {TEXT_DIM};")
        status.addWidget(self.miner_name_label)
        self.auto_reload_checkbox = QCheckBox("Auto-reload", self.content_widget)
        self.auto_reload_checkbox.setObjectName("auto_reload_checkbox")
        self.auto_reload_checkbox.setChecked(True)
        self.autoreload_checkbox = self.auto_reload_checkbox
        self.reload_checkbox = self.auto_reload_checkbox
        status.addWidget(self.auto_reload_checkbox)
        status.addStretch(1)
        controls.addLayout(status)
        body.addLayout(controls)

        if console_panel is None:
            console_panel = ConsolePanel(self.content_widget)
        self.console_panel = console_panel
        self.console = console_panel
        if self.manager is not None:
            try:
                console_panel.set_manager(self.manager)
            except Exception:
                pass
        body.addWidget(console_panel, 0)
        console_panel.setFixedHeight(140)
        self.content_layout.addLayout(body)

        self.open_files_popup = FileListPopup("Open file", self.content_widget)
        self.open_files_popup.setObjectName("open_files_popup")
        self.open_files_popup.file_chosen.connect(self._on_open_popup_chosen)
        self.open_files_popup.hide()
        self.restore_deleted_popup = FileListPopup("Restore deleted", self.content_widget)
        self.restore_deleted_popup.setObjectName("restore_deleted_popup")
        self.restore_deleted_popup.file_chosen.connect(self._on_restore_popup_chosen)
        self.restore_deleted_popup.hide()

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(AUTOSAVE_MS)
        self._autosave_timer.timeout.connect(self._autosave_current_editor)
        self._indicator_timer = QTimer(self)
        self._indicator_timer.setInterval(500)
        self._indicator_timer.timeout.connect(self._refresh_tab_indicators)
        self._indicator_timer.start()

        self._close_tab_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        self._close_tab_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._close_tab_shortcut.activated.connect(self.close_current_tab)
        self._reopen_tab_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self)
        self._reopen_tab_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._reopen_tab_shortcut.activated.connect(self.reopen_last_closed_tab)

        self.watcher = QFileSystemWatcher(self)
        self.filesystem_watcher = self.watcher
        self.file_watcher = self.watcher
        if self.scripts_dir is not None:
            try:
                self.watcher.addPath(str(self.scripts_dir))
            except Exception:
                pass
        self.watcher.directoryChanged.connect(self._on_directory_changed)
        self.watcher.fileChanged.connect(self._on_file_changed)

        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        try:
            self.tabs.tabBar().tabMoved.connect(lambda *_args: self._save_tab_state())
        except Exception:
            pass
        try:
            self.tabs.tabBar().installEventFilter(self)
        except Exception:
            pass
        self._restore_open_tabs()
        self.refresh_examples_menu()
        self._sync_current_editor()
        self._subscribe_events()
        self._sync_state()
        self._refresh_tab_indicators()

    # -- host / state -----------------------------------------------------------

    def set_host(self, host: Any) -> None:
        """Attach a ScriptHost."""
        self.host = host
        self.script_host = host
        self._subscribe_events()
        self._sync_state()

    def attach_host(self, host: Any) -> None:
        """Alias for :meth:`set_host`."""
        self.set_host(host)

    def set_manager(self, manager: Any) -> None:
        """Attach a ScriptManager and use its host for miner 0."""
        self.manager = manager
        self.script_manager = manager
        host = None
        if manager is not None:
            try:
                host = manager.host(0) or manager.ensure_host(0)
            except Exception:
                host = None
        if host is not None:
            self.set_host(host)
        try:
            self.console_panel.set_manager(manager)
        except Exception:
            pass
        self._sync_state()

    def set_game(self, game: Any) -> None:
        """Attach a game, rebinding the manager or creating a host."""
        self.game = game
        self.engine = _get(game, "engine")
        content = _get(game, "content")
        if content is not None:
            self.content_data = content
        self.progression = _get(game, "progression_service") or _get(game, "progression")
        if self.manager is not None:
            self.manager.set_game(game)
            self.set_manager(self.manager)
        elif self.host is None or _get(self.host, "engine") is None:
            try:
                from minesim.scripting.host import ScriptHost

                self.set_host(
                    ScriptHost(self.engine, self.content_data, self.progression, self.scripts_dir)
                )
            except Exception:
                pass
        self._subscribe_events()
        self.refresh_examples_menu()

    def _subscribe_events(self) -> None:
        if self.game is None:
            return
        bus = _get(self.game, "events") or _get(self.game, "event_bus")
        if bus is None or not hasattr(bus, "subscribe"):
            return
        try:
            from minesim.core.events import ScriptFailed, ScriptFinished, ScriptStarted

            bus.subscribe(ScriptStarted, lambda _e: self._on_script_started())
            bus.subscribe(ScriptFinished, lambda _e: self._on_script_stopped("Finished"))
            bus.subscribe(
                ScriptFailed,
                lambda _e: self._on_script_failed(_e),
            )
        except Exception:
            pass

    def _on_script_started(self) -> None:
        self._sync_state("Running")
        self._refresh_tab_indicators()

    def _on_script_stopped(self, label: str) -> None:
        self._sync_state(label)
        self._refresh_tab_indicators()

    # -- settings / file actions -------------------------------------------------

    def _build_file_actions_menu(self) -> None:
        menu = getattr(self, "file_actions_menu", None)
        if menu is None:
            return
        menu.clear()
        rename_action = menu.addAction("Rename…")
        rename_action.triggered.connect(lambda: self.rename_current_file())
        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self.duplicate_current_file())
        delete_action = menu.addAction("Delete…")
        delete_action.triggered.connect(lambda: self.delete_current_file())
        menu.addSeparator()
        restore_action = menu.addAction("Restore deleted…")
        restore_action.triggered.connect(lambda: self.restore_deleted())

    @property
    def trash_dir(self) -> Path:
        """Return the per-project trash folder (``scripts_dir/.trash``)."""
        return self.scripts_dir / TRASH_DIR_NAME

    def _save_tab_state(self) -> None:
        if getattr(self, "_restoring", False) or self.scripts_dir is None:
            return
        try:
            settings = ensure_settings_names()
            names = [self._tab_name(index) for index in range(self.tabs.count())]
            settings.setValue(OPEN_TABS_KEY, names)
            index = self.tabs.currentIndex()
            settings.setValue(ACTIVE_TAB_KEY, self._tab_name(index) if index >= 0 else "")
            settings.sync()
        except Exception:
            pass

    def _load_tab_names(self) -> list[str]:
        try:
            value = ensure_settings_names().value(OPEN_TABS_KEY)
        except Exception:
            return []
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        try:
            return [str(item) for item in value]
        except TypeError:
            return []

    def _load_active_tab(self) -> str:
        try:
            value = ensure_settings_names().value(ACTIVE_TAB_KEY)
        except Exception:
            return ""
        return "" if value is None else str(value)

    def _restore_open_tabs(self) -> None:
        self._restoring = True
        try:
            names = self._load_tab_names()
            active = self._load_active_tab()
            opened: list[tuple[str, int]] = []
            for saved_name in names:
                name = Path(str(saved_name)).name
                path = self.scripts_dir / name
                if not path.is_file():
                    continue
                opened.append((name, int(self.add_file(path))))
            if not names:
                main_py = self.scripts_dir / "main.py"
                if main_py.is_file():
                    opened.append(("main.py", int(self.add_file(main_py))))
            if opened:
                target = active or opened[0][0]
                index = next((idx for name, idx in opened if name == target), opened[0][1])
                self.tabs.setCurrentIndex(index)
        finally:
            self._restoring = False
        self._save_tab_state()

    def _tab_name(self, index: int) -> str:
        if index < 0 or index >= self.tabs.count():
            return ""
        widget = self.tabs.widget(index)
        for name, editor in self._editors.items():
            if editor is widget:
                return name
        text = self.tabs.tabText(index)
        return text.split(_DIRTY_MARK.strip())[0].strip()

    def tab_index(self, name: Any) -> int:
        """Return the tab index for ``name`` (or -1 when closed)."""
        editor = self._editors.get(Path(str(name)).name)
        return self.tabs.indexOf(editor) if editor is not None else -1

    def tab_running_miners(self, name: Any) -> list[int]:
        """Return the ids of miners currently running ``name``."""
        filename = Path(str(name)).name
        ids: list[int] = []
        manager = self.manager
        if manager is not None:
            hosts = getattr(manager, "hosts", {}) or {}
            for miner_id, host in sorted(hosts.items()):
                if not bool(_get(host, "is_running", False)):
                    continue
                active = Path(str(_get(host, "filename", "") or "")).name
                if active == filename:
                    ids.append(int(miner_id))
            return ids
        host = self.host
        if host is not None and bool(_get(host, "is_running", False)):
            active = Path(str(_get(host, "filename", "") or "")).name
            if active == filename:
                ids.append(int(_get(host, "miner_id", 0) or 0))
        return ids

    def tab_running_color(self, name: Any) -> str | None:
        """Return the running-dot colour of ``name`` or None when idle."""
        ids = self.tab_running_miners(name)
        return miner_badge_color(ids[0]) if ids else None

    def tab_running_color_by_index(self, index: int) -> str | None:
        return self.tab_running_color(self._tab_name(index))

    def _update_tab_indicator(self, editor: CodeEditor) -> None:
        index = self.tabs.indexOf(editor)
        if index < 0:
            return
        name = self._tab_name(index)
        if not name:
            return
        dirty = bool(editor.document().isModified())
        self.tabs.setTabText(index, name + (_DIRTY_MARK if dirty else ""))
        running = self.tab_running_miners(name)
        tip = name
        if dirty:
            tip += "\nUnsaved changes"
        if running:
            tip += "\nRunning on " + ", ".join(f"Miner {miner_id}" for miner_id in running)
        self.tabs.setTabToolTip(index, tip)

    def _refresh_tab_indicators(self) -> None:
        for editor in list(self._editors.values()):
            self._update_tab_indicator(editor)
        try:
            self.tab_bar.update()
        except Exception:
            pass
        self._update_miner_label()

    def refresh_tab_indicators(self) -> None:
        """Public alias for :meth:`_refresh_tab_indicators`."""
        self._refresh_tab_indicators()

    def _on_editor_text_changed(self, editor: CodeEditor) -> None:
        if not (self._saving or self._changing or self._restoring):
            try:
                if not editor.document().isModified():
                    editor.document().setModified(True)
            except Exception:
                pass
        self._update_tab_indicator(editor)
        if self._saving or self._changing or self._restoring:
            return
        self._autosave_editor = editor
        try:
            self._autosave_timer.start(AUTOSAVE_MS)
        except Exception:
            pass

    def _on_editor_modified_changed(self, editor: CodeEditor, _modified: bool) -> None:
        self._update_tab_indicator(editor)

    def _autosave_current_editor(self) -> None:
        editor = self._autosave_editor
        if editor is None or self.tabs.indexOf(editor) < 0:
            return
        if editor.document().isModified():
            self._save_editor(editor)

    def _on_script_failed(self, _event: Any) -> None:
        self._sync_state("Error")
        editor = self.current_editor
        host = self.host
        if editor is not None and host is not None:
            error = getattr(host, "last_error", None)
            line = error.get("line") if isinstance(error, dict) else None
            if isinstance(line, int):
                editor.set_error_line(line)

    def state_label_text(self, state: Any) -> str:
        """Map a host state to the panel state label."""
        text = str(state).upper()
        if "RUNNING" in text:
            return "Running"
        if "FINISHED" in text:
            return "Finished"
        if "FAILED" in text or "ERROR" in text:
            return "Error"
        if "STOPPED" in text:
            return "Idle"
        return "Idle"

    def set_state(self, state: Any) -> None:
        """Set the state label from a host state or label text."""
        if isinstance(state, str) and state in ("Idle", "Running", "Finished", "Error", "Stopped"):
            self.state_label.setText("Idle" if state == "Stopped" else state)
        else:
            self.state_label.setText(self.state_label_text(state))

    def update_state(self) -> None:
        """Alias for :meth:`_sync_state`."""
        self._sync_state()

    def refresh_state(self) -> None:
        """Alias for :meth:`_sync_state`."""
        self._sync_state()

    def _sync_state(self, label: str | None = None) -> None:
        if label is not None:
            self.state_label.setText(label)
            self._update_miner_label()
            return
        host = self.host
        if host is None:
            self.state_label.setText("Idle")
            self._update_miner_label()
            return
        state = getattr(host, "state", None)
        self.state_label.setText(self.state_label_text(state if state is not None else "IDLE"))
        if str(state).upper().endswith("FAILED") or str(state) == "FAILED":
            self._on_script_failed(None)
        self._update_miner_label()

    def _miner_running_file(self, filename: str) -> int | None:
        """Return the id of a miner whose assigned script is ``filename``."""
        engine = self.engine or _get(self.game, "engine")
        miners = _get(engine, "miners") or {}
        if not isinstance(miners, dict):
            return None
        for miner_id in sorted(int(key) for key in miners):
            script = Path(str(_get(miners[miner_id], "script", "") or "")).name
            if script == filename:
                return miner_id
        return None

    def _update_miner_label(self) -> None:
        label = getattr(self, "miner_name_label", None)
        if label is None:
            return
        filename = self.current_filename()
        miner_id = self._miner_running_file(filename)
        if miner_id is None:
            label.setText("No miner running this file")
        else:
            label.setText(f"Running on Miner {miner_id} · {filename}")

    # -- files / tabs -------------------------------------------------------------

    def _py_files(self) -> list[Path]:
        if self.scripts_dir is None:
            return []
        try:
            files = sorted(self.scripts_dir.glob("*.py"), key=lambda p: p.name.lower())
        except Exception:
            return []
        files.sort(key=lambda p: (0 if p.name == "main.py" else 1, p.name.lower()))
        return files

    def _create_editor(self, text: str, filename: str) -> CodeEditor:
        editor = CodeEditor(self.tabs, content=self.content_data)
        editor.setPlainText(text)
        editor.setWindowTitle(filename)
        editor.run_requested.connect(self.run)
        editor.stop_requested.connect(self.stop)
        editor.textChanged.connect(lambda ed=editor: self._on_editor_text_changed(ed))
        editor.document().modificationChanged.connect(
            lambda modified, ed=editor: self._on_editor_modified_changed(ed, modified)
        )
        editor.installEventFilter(self)
        return editor

    def add_file(self, path: Any, text: str | None = None) -> int:
        """Add ``path`` as a tab and return its index."""
        file_path = Path(path)
        name = file_path.name
        if name in self._editors:
            return self.tabs.indexOf(self._editors[name])
        if text is None:
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception:
                text = ""
        editor = self._create_editor(text, name)
        self._editors[name] = editor
        self._paths[name] = file_path
        index = self.tabs.addTab(editor, name)
        self._closed_stack = [item for item in self._closed_stack if item != file_path]
        try:
            self.watcher.addPath(str(file_path))
        except Exception:
            pass
        self._update_tab_indicator(editor)
        self._save_tab_state()
        return index

    def add_tab(self, path: Any, text: str | None = None) -> int:
        """Alias for :meth:`add_file`."""
        return self.add_file(path, text)

    def open_file(self, path: Any) -> int:
        """Open ``path`` in a tab (alias for :meth:`add_file`)."""
        return self.add_file(path)

    def open_path(self, path: Any) -> int:
        """Alias for :meth:`add_file`."""
        return self.add_file(path)

    def open_named_file(self, name: Any) -> int:
        """Open ``scripts_dir/name`` in a tab when it exists."""
        file_path = self.scripts_dir / Path(str(name)).name
        if not file_path.is_file():
            return -1
        return self.add_file(file_path)

    def closed_files(self) -> list[Path]:
        """Return every ``.py`` file in the scripts folder that is not open.

        Files are sorted by last-modified time (newest first), and the
        ``.trash`` folder is never included.
        """
        open_names = set(self._editors)
        try:
            files = [
                path
                for path in self.scripts_dir.glob("*.py")
                if path.is_file() and path.name not in open_names
            ]
        except Exception:
            return []

        def modified(path: Path) -> float:
            try:
                return float(path.stat().st_mtime)
            except OSError:
                return 0.0

        files.sort(key=lambda path: (modified(path), path.name.lower()), reverse=True)
        return files

    def available_files(self) -> list[Path]:
        """Alias for :meth:`closed_files`."""
        return self.closed_files()

    def open_dialog(self) -> FileListPopup:
        """Show the searchable list of closed scripts and return it."""
        self._refresh_open_popup()
        self.open_files_popup.show_popup()
        return self.open_files_popup

    def show_open_dialog(self) -> FileListPopup:
        """Alias for :meth:`open_dialog`."""
        return self.open_dialog()

    def open_files_dialog(self) -> FileListPopup:
        """Alias for :meth:`open_dialog`."""
        return self.open_dialog()

    def _refresh_open_popup(self) -> None:
        entries = [(path.name, path) for path in self.closed_files()]
        self.open_files_popup.set_entries(entries)

    def _on_open_popup_chosen(self, path: str) -> None:
        file_path = Path(path)
        if not file_path.is_file():
            return
        index = self.add_file(file_path)
        if index >= 0:
            self.tabs.setCurrentIndex(index)
            self._sync_current_editor()
            self._save_tab_state()

    def _refresh_restore_popup(self) -> None:
        entries = [
            (f"{self._trash_original_name(path.name)}  ·  {path.name}", path)
            for path in self.trashed_files()
        ]
        self.restore_deleted_popup.set_entries(entries)

    def _on_restore_popup_chosen(self, path: str) -> None:
        self.restore_deleted_file(path)

    def refresh_files(self) -> None:
        """Close tabs for files removed on disk and refresh file lists."""
        if self._saving or self._changing:
            return
        self._check_external_removals()
        self._refresh_tab_indicators()
        if self.open_files_popup.isVisible():
            self._refresh_open_popup()
        if self.restore_deleted_popup.isVisible():
            self._refresh_restore_popup()

    def reload_files(self) -> None:
        """Alias for :meth:`refresh_files`."""
        self.refresh_files()

    def refresh_tabs(self) -> None:
        """Alias for :meth:`refresh_files`."""
        self.refresh_files()

    def discover_files(self) -> list[Path]:
        """Return the discovered ``*.py`` files."""
        return self._py_files()

    # -- closing / reopening tabs ------------------------------------------------

    def close_tab(
        self,
        index: Any = None,
        *,
        save: bool = True,
        remember: bool = True,
    ) -> bool:
        """Save (when requested) and close one tab without deleting its file."""
        if isinstance(index, str):
            tab_index = self.tab_index(index)
        elif index is None:
            tab_index = self.tabs.currentIndex()
        else:
            try:
                tab_index = int(index)
            except (TypeError, ValueError):
                return False
        if tab_index < 0 or tab_index >= self.tabs.count():
            return False
        editor = self.tabs.widget(tab_index)
        name = self._tab_name(tab_index)
        file_path = self._paths.get(name)
        if save and isinstance(editor, CodeEditor):
            self._save_editor(editor)
        self.tabs.removeTab(tab_index)
        self._editors.pop(name, None)
        self._paths.pop(name, None)
        if file_path is not None:
            try:
                self.watcher.removePath(str(file_path))
            except Exception:
                pass
            if remember:
                self._closed_stack.append(file_path)
        if isinstance(editor, QWidget):
            editor.deleteLater()
        self._sync_current_editor()
        self._save_tab_state()
        self._update_miner_label()
        self._refresh_tab_indicators()
        return True

    def close_current_tab(self) -> bool:
        """Close the current tab (Ctrl+W)."""
        return self.close_tab(self.tabs.currentIndex())

    def close_tab_by_name(self, name: Any) -> bool:
        """Close the tab for ``name``."""
        return self.close_tab(self.tab_index(name))

    def close_all_tabs(self, *, save: bool = True, remember: bool = False) -> None:
        """Close every tab, optionally saving unsaved edits first."""
        while self.tabs.count():
            self.close_tab(self.tabs.count() - 1, save=save, remember=remember)

    def reopen_last_closed_tab(self) -> bool:
        """Reopen the most recently closed tab (Ctrl+Shift+T)."""
        while self._closed_stack:
            file_path = self._closed_stack.pop()
            if not file_path.is_file():
                continue
            index = self.add_file(file_path)
            self.tabs.setCurrentIndex(index)
            self._sync_current_editor()
            self._save_tab_state()
            return True
        return False

    def reopen_last_closed(self) -> bool:
        """Alias for :meth:`reopen_last_closed_tab`."""
        return self.reopen_last_closed_tab()

    def reopen_closed_tab(self) -> bool:
        """Alias for :meth:`reopen_last_closed_tab`."""
        return self.reopen_last_closed_tab()

    # -- rename / duplicate / delete / restore -------------------------------------

    def _resolve_file(self, value: Any = None) -> tuple[str, Path]:
        if value is None:
            name = self.current_filename()
        else:
            name = Path(str(value)).name
        return name, self._paths.get(name) or (self.scripts_dir / name)

    def _unique_sibling(self, stem: str, suffix: str = ".py") -> Path:
        candidate = self.scripts_dir / f"{stem}{suffix}"
        counter = 2
        while candidate.exists():
            candidate = self.scripts_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        return candidate

    def rename_current_file(self, new_name: Any = None) -> bool:
        """Rename the current script (asks for a name when omitted)."""
        if new_name is None:
            current = self.current_filename()
            text, accepted = QInputDialog.getText(
                self, "Rename file", "New module name:", text=current
            )
            if not accepted:
                return False
            new_name = text
        return self.rename_file(None, new_name)

    def rename_file(self, old: Any = None, new: Any = None) -> bool:
        """Rename a script after validating both the source and module name."""
        if new is None:
            return self.rename_current_file()
        old_name, old_path = self._resolve_file(old)
        try:
            new_name = validate_module_name(new)
        except ValueError:
            return False
        if not old_path.is_file():
            return False
        target = self.scripts_dir / new_name
        if target == old_path:
            return True
        if target.exists():
            return False
        editor = self._editors.get(old_name)
        if editor is not None:
            self._save_editor(editor)
        self._changing = True
        try:
            old_path.rename(target)
        except OSError:
            self._changing = False
            return False
        finally:
            self._changing = False
        if editor is not None:
            try:
                self.watcher.removePath(str(old_path))
            except Exception:
                pass
            try:
                self.watcher.addPath(str(target))
            except Exception:
                pass
            self._editors.pop(old_name, None)
            self._editors[new_name] = editor
            self._paths.pop(old_name, None)
            self._paths[new_name] = target
            index = self.tabs.indexOf(editor)
            if index >= 0:
                self.tabs.setTabText(index, new_name)
                self._update_tab_indicator(editor)
        self._closed_stack = [target if path == old_path else path for path in self._closed_stack]
        self._save_tab_state()
        self._update_miner_label()
        return True

    def duplicate_current_file(self) -> int | None:
        """Duplicate the current script and open the copy in a new tab."""
        return self.duplicate_file(None)

    def duplicate_file(self, source: Any = None) -> int | None:
        """Copy a script to ``<name>_copy.py`` (or the next free name)."""
        name, source_path = self._resolve_file(source)
        editor = self._editors.get(name)
        if editor is not None:
            self._save_editor(editor)
        if not source_path.is_file():
            return None
        target = self._unique_sibling(f"{source_path.stem}_copy", source_path.suffix)
        try:
            target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            return None
        index = self.add_file(target)
        self.tabs.setCurrentIndex(index)
        self._sync_current_editor()
        self._save_tab_state()
        return index

    def delete_current_file(self, confirm: bool = True) -> bool:
        """Move the current script to the trash (asks for confirmation)."""
        return self.delete_file(None, confirm=confirm)

    def delete_file(self, target: Any = None, *, confirm: bool = True) -> bool:
        """Move a script to ``scripts_dir/.trash`` with a timestamp."""
        name, file_path = self._resolve_file(target)
        if not file_path.is_file():
            return False
        if confirm:
            answer = QMessageBox.question(
                self,
                "Delete script",
                f"Move {name} to the trash?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        index = self.tab_index(name)
        if index >= 0:
            self.close_tab(index, save=True, remember=False)
        self._changing = True
        try:
            trash_path = self._move_to_trash(file_path)
        except OSError:
            trash_path = None
        finally:
            self._changing = False
        if trash_path is None:
            return False
        try:
            self.console_panel.append_line(f"Moved {name} to the trash", "info")
        except Exception:
            pass
        self.refresh_files()
        return True

    def _move_to_trash(self, file_path: Path) -> Path:
        trash = self.trash_dir
        trash.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        candidate = trash / f"{stamp}_{file_path.name}"
        counter = 2
        while candidate.exists():
            candidate = trash / f"{stamp}_{counter}_{file_path.name}"
            counter += 1
        file_path.replace(candidate)
        return candidate

    def trashed_files(self) -> list[Path]:
        """Return the files currently in the trash folder (newest first)."""
        try:
            files = [path for path in self.trash_dir.glob("*.py") if path.is_file()]
        except Exception:
            return []

        def modified(path: Path) -> float:
            try:
                return float(path.stat().st_mtime)
            except OSError:
                return 0.0

        files.sort(key=lambda path: (modified(path), path.name), reverse=True)
        return files

    def _trash_original_name(self, trash_name: str) -> str:
        match = _TRASH_STAMP_RE.match(str(trash_name))
        if match:
            return match.group(1)
        parts = str(trash_name).split("_", 1)
        return parts[1] if len(parts) == 2 else str(trash_name)

    def restore_deleted(self) -> bool:
        """Show the searchable list of trashed scripts."""
        files = self.trashed_files()
        if not files:
            try:
                self.console_panel.append_line("No deleted scripts to restore", "info")
            except Exception:
                pass
            return False
        self._refresh_restore_popup()
        self.restore_deleted_popup.show_popup()
        return True

    def restore_deleted_file(self, trash: Any = None) -> int | None:
        """Restore one trashed script and open it in a tab."""
        if trash is None:
            self.restore_deleted()
            return None
        candidate = Path(str(trash))
        if not candidate.is_absolute():
            candidate = self.trash_dir / candidate.name
        if not candidate.is_file():
            return None
        original = Path(self._trash_original_name(candidate.name)).name
        target = self.scripts_dir / original
        if target.exists():
            target = self._unique_sibling(Path(original).stem, Path(original).suffix)
        self._changing = True
        try:
            candidate.replace(target)
        except OSError:
            self._changing = False
            return None
        finally:
            self._changing = False
        index = self.add_file(target)
        self.tabs.setCurrentIndex(index)
        self._sync_current_editor()
        self._save_tab_state()
        return index

    def _sync_current_editor(self) -> None:
        index = self.tabs.currentIndex()
        editor: CodeEditor | None = None
        if 0 <= index < self.tabs.count():
            widget = self.tabs.widget(index)
            if isinstance(widget, CodeEditor):
                editor = widget
        self.editor = editor
        self.code_editor = editor
        self.current_editor = editor
        if editor is not None:
            try:
                self.console_panel.set_editor(editor)
            except Exception:
                pass
        try:
            self.editor_changed.emit(editor)
        except Exception:
            pass

    def _on_tab_changed(self, _index: int) -> None:
        self._sync_current_editor()
        self._update_miner_label()
        self._save_tab_state()

    def current_filename(self) -> str:
        """Return the current tab file name (``main.py`` by default)."""
        if self.editor is not None:
            index = self.tabs.currentIndex()
            if index >= 0:
                name = self._tab_name(index)
                if name:
                    return name
        return "main.py"

    def current_file(self) -> Path:
        """Return the current tab file path."""
        name = self.current_filename()
        return self._paths.get(name) or (self.scripts_dir / name)

    def current_path(self) -> Path:
        """Alias for :meth:`current_file`."""
        return self.current_file()

    def _check_external_removals(self) -> None:
        for name, path in list(self._paths.items()):
            if path.exists():
                continue
            index = self.tab_index(name)
            if index < 0:
                continue
            self.close_tab(index, save=False, remember=False)
            try:
                self.console_panel.append_line(
                    f"{name} was removed on disk; its tab was closed", "info"
                )
            except Exception:
                pass

    def _content_examples(self) -> list[Any]:
        content = _get(getattr(self, "game", None), "content") or self.content_data
        if content is None or not hasattr(content, "examples"):
            try:
                from minesim.core.content import load_content

                content = load_content()
            except Exception:
                return []
        examples = _get(content, "examples", []) or []
        if isinstance(examples, dict):
            return list(examples.values())
        return list(examples)

    def _example_unlocked(self, example: Any) -> bool:
        required = _get(example, "unlocked_by")
        if required is None:
            return True
        view = self.progression
        checker = _get(view, "is_example_unlocked")
        if callable(checker):
            return bool(checker(_get(example, "id", "")))
        return False

    def _achievement_title(self, achievement_id: str) -> str:
        content = _get(getattr(self, "game", None), "content") or self.content_data
        achievements = _get(content, "achievements", {}) or {}
        if isinstance(achievements, dict):
            achievement = achievements.get(achievement_id)
        else:
            achievement = next(
                (item for item in achievements if _get(item, "id") == achievement_id), None
            )
        return str(_get(achievement, "title", achievement_id))

    def refresh_examples_menu(self) -> None:
        """Rebuild the Examples menu from the content pack."""
        menu = getattr(self, "examples_menu", None)
        if menu is None:
            return
        menu.clear()
        self._example_actions = {}
        for example in self._content_examples():
            example_id = str(_get(example, "id", ""))
            title = str(_get(example, "title", example_id))
            action = menu.addAction(title)
            unlocked = self._example_unlocked(example)
            action.setEnabled(unlocked)
            if unlocked:
                action.triggered.connect(
                    lambda _checked=False, ident=example_id: self.open_example(ident)
                )
            else:
                required = str(_get(example, "unlocked_by", ""))
                action.setToolTip(f"Locked: unlock with {self._achievement_title(required)}")
            self._example_actions[example_id] = action

    def _unique_example_path(self, file_name: str) -> Path:
        base = Path(file_name)
        directory = Path(self.scripts_dir)
        candidate = directory / base.name
        counter = 2
        while candidate.exists():
            candidate = directory / f"{base.stem}_{counter}{base.suffix}"
            counter += 1
        return candidate

    def open_example(self, example_id: str) -> bool:
        """Copy example ``example_id`` into the scripts folder and open it."""
        example = next(
            (item for item in self._content_examples() if _get(item, "id") == example_id),
            None,
        )
        if example is None or not self._example_unlocked(example):
            return False
        file_name = str(_get(example, "file", ""))
        source_path = Path(__file__).resolve().parents[1] / "examples" / file_name
        try:
            source = source_path.read_text(encoding="utf-8")
        except OSError:
            return False
        target = self._unique_example_path(source_path.name)
        try:
            target.write_text(source, encoding="utf-8")
        except OSError:
            return False
        index = self.add_file(target, source)
        self.tabs.setCurrentIndex(index)
        self._sync_current_editor()
        return True

    def current_source(self) -> str:
        """Return the current editor text."""
        return self.editor.toPlainText() if self.editor is not None else ""

    def get_source(self) -> str:
        """Alias for :meth:`current_source`."""
        return self.current_source()

    def source(self) -> str:
        """Alias for :meth:`current_source`."""
        return self.current_source()

    def get_editor(self, filename: str | None = None) -> CodeEditor | None:
        """Return the editor for ``filename`` (or the current one)."""
        if filename is None:
            return self.editor
        return self._editors.get(Path(str(filename)).name)

    # -- saving ---------------------------------------------------------------------

    def save(self, path: Any = None) -> bool:
        """Save the current (or given) file to disk."""
        if path is not None:
            name = Path(str(path)).name
            editor = self._editors.get(name)
            if editor is None:
                return False
            file_path = self._paths.get(name) or self.scripts_dir / name
        else:
            editor = self.editor
            if editor is None:
                return False
            file_path = self.current_file()
        self._saving = True
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(editor.toPlainText(), encoding="utf-8")
            doc = editor.document()
            try:
                doc.setModified(False)
            except Exception:
                pass
            try:
                self.watcher.addPath(str(file_path))
            except Exception:
                pass
            return True
        except Exception:
            return False
        finally:
            self._saving = False

    def save_current(self) -> bool:
        """Alias for :meth:`save`."""
        return self.save()

    def save_file(self, path: Any = None) -> bool:
        """Alias for :meth:`save`."""
        return self.save(path)

    def save_all(self) -> None:
        """Save every open tab."""
        for name in list(self._editors):
            self.save(name)

    def _save_editor(self, editor: CodeEditor) -> None:
        index = self.tabs.indexOf(editor)
        if index < 0:
            return
        name = self._tab_name(index)
        file_path = self._paths.get(name) or (self.scripts_dir / name)
        self._saving = True
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(editor.toPlainText(), encoding="utf-8")
            try:
                editor.document().setModified(False)
            except Exception:
                pass
            try:
                self.watcher.addPath(str(file_path))
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._saving = False
        self._update_tab_indicator(editor)

    # -- new file / folder ----------------------------------------------------------------

    def new_file(self, name: Any = None) -> int:
        """Create a new ``.py`` file and open it in a new tab."""
        if name is None:
            candidate = self.scripts_dir / "new_file.py"
            counter = 1
            while candidate.exists():
                candidate = self.scripts_dir / f"new_file_{counter}.py"
                counter += 1
            file_path = candidate
        else:
            file_name = Path(str(name)).name
            if not file_name.endswith(".py"):
                file_name += ".py"
            file_path = self.scripts_dir / file_name
        if file_path.name in self._editors:
            index = self.tabs.indexOf(self._editors[file_path.name])
            self.tabs.setCurrentIndex(index)
            return index
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if not file_path.exists():
                file_path.write_text("", encoding="utf-8")
        except Exception:
            pass
        index = self.add_file(file_path, "")
        self.tabs.setCurrentIndex(index)
        self._sync_current_editor()
        return index

    def create_new_file(self, name: Any = None) -> int:
        """Alias for :meth:`new_file`."""
        return self.new_file(name)

    def open_scripts_folder(self) -> None:
        """Open the scripts folder in the OS file manager."""
        try:
            self.scripts_dir.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.scripts_dir)))
        except Exception:
            pass

    def open_folder(self) -> None:
        """Alias for :meth:`open_scripts_folder`."""
        self.open_scripts_folder()

    def open_scripts_dir(self) -> None:
        """Alias for :meth:`open_scripts_folder`."""
        self.open_scripts_folder()

    # -- auto-reload ---------------------------------------------------------------------

    def set_auto_reload(self, value: bool) -> None:
        """Enable/disable auto-reload from disk."""
        self.auto_reload_checkbox.setChecked(bool(value))

    def _reload_file(self, path_str: str) -> None:
        file_path = Path(path_str)
        if file_path.suffix != ".py":
            return
        name = file_path.name
        editor = self._editors.get(name)
        if editor is None:
            return
        if editor.document().isModified():
            return
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            return
        if editor.toPlainText() != text:
            self._changing = True
            try:
                editor.setPlainText(text)
                editor.document().setModified(False)
            finally:
                self._changing = False
            self._update_tab_indicator(editor)

    def reload_from_disk(self) -> None:
        """Reload open files from disk (when auto-reload is on)."""
        if not self.auto_reload_checkbox.isChecked():
            return
        for file_path in list(self._paths.values()):
            self._reload_file(str(file_path))

    def _on_directory_changed(self, _path: str) -> None:
        if self._saving or self._changing:
            return
        self.refresh_files()
        if self.auto_reload_checkbox.isChecked():
            self.reload_from_disk()

    def _on_file_changed(self, path: str) -> None:
        if self._saving or self._changing:
            return
        file_path = Path(path)
        if not file_path.exists():
            self._check_external_removals()
            return
        try:
            self.watcher.addPath(path)
        except Exception:
            pass
        if not self.auto_reload_checkbox.isChecked():
            return
        self._reload_file(path)

    # -- running -----------------------------------------------------------------------------

    def run(self) -> None:
        """Save and run the current script (stopping a running one first)."""
        self.save()
        editor = self.editor
        if editor is None:
            return
        editor.set_error_line(None)
        host = self.host
        if host is None:
            self.state_label.setText("Error")
            return
        try:
            if getattr(host, "is_running", False):
                host.stop()
        except Exception:
            pass
        try:
            self.console_panel.clear()
        except Exception:
            pass
        filename = self.current_filename()
        source = editor.toPlainText()
        try:
            if self.manager is not None:
                self.manager.start(0, filename, source)
            else:
                host.start(filename, source)
        except Exception:
            self.state_label.setText("Error")
            return
        self._sync_state("Running")
        self._refresh_tab_indicators()

    def _spawn_miner_with_file(self, filename: str) -> int | None:
        """Spawn one miner and start ``filename`` on it; None on failure."""
        engine = self.engine or _get(self.game, "engine")
        if engine is None:
            return None
        manager = self.manager
        if manager is None and getattr(self, "game", None) is not None:
            try:
                from minesim.scripting.manager import ScriptManager

                manager = ScriptManager(self.game, self.scripts_dir)
                self.set_manager(manager)
            except Exception:
                manager = None
        if manager is not None:
            try:
                error = manager.spawn_error(filename)
            except Exception:
                error = {"reason": "process_limit"}
            if error is not None:
                return None
        miners = _get(engine, "miners") or {}
        max_miners = int(_get(engine, "max_miners", 1) or 1)
        if len(miners) >= max_miners:
            return None
        config = _get(self.content_data, "config")
        costs = list(_get(config, "miner_costs", []) or [])
        extra = max(0, len(miners) - 1)
        if extra >= len(costs):
            return None
        player = _get(self.game, "player_stats") or _get(engine, "player_stats")
        if int(_get(player, "money", 0) or 0) < int(costs[extra]):
            return None
        from minesim.core.commands import SpawnMiner

        result = SpawnMiner().execute(engine)
        if not result.get("ok"):
            return None
        miner_id = int(result["miner_id"])
        if manager is not None:
            try:
                manager.start_spawned(miner_id, filename)
            except Exception:
                engine.remove_miner(miner_id)
                return None
        else:
            engine.miner_by_id(miner_id).script = filename
        return miner_id

    def run_on_new_miner(self) -> bool:
        """Save the current file and spawn a miner that runs it."""
        self.save()
        editor = self.editor
        if editor is None:
            return False
        filename = self.current_filename()
        if self._spawn_miner_with_file(filename) is None:
            self.state_label.setText("No free miner slot")
            self._update_miner_label()
            return False
        self.state_label.setText("Running")
        self._update_miner_label()
        self._refresh_tab_indicators()
        return True

    def run_current(self) -> None:
        """Alias for :meth:`run`."""
        self.run()

    def run_script(self) -> None:
        """Alias for :meth:`run`."""
        self.run()

    def start(self) -> None:
        """Alias for :meth:`run`."""
        self.run()

    def stop(self) -> None:
        """Stop the running script."""
        if self.manager is not None:
            try:
                self.manager.stop(0)
            except Exception:
                pass
        else:
            host = self.host
            if host is not None:
                try:
                    host.stop()
                except Exception:
                    pass
        self._sync_state()

    def stop_script(self) -> None:
        """Alias for :meth:`stop`."""
        self.stop()

    # -- pump / console ---------------------------------------------------------------------------

    def pump(self) -> list[Any]:
        """Pump the scripts once, feeding console/state/error highlight."""
        if self.manager is not None:
            try:
                events = self.manager.pump()
            except Exception:
                return []
            self.handle_host_events(events)
            return list(events or [])
        host = self.host
        if host is None:
            return []
        try:
            events = host.pump()
        except Exception:
            return []
        self.handle_host_events(events)
        return list(events or [])

    def handle_host_events(self, events: Any, append: bool = True) -> None:
        """Feed host ``events`` to the console and update state."""
        if events and append:
            try:
                self.console_panel.append_events(events)
            except Exception:
                pass
        host = self.host
        if host is not None:
            state = str(getattr(host, "state", ""))
            if "FAILED" in state:
                self._on_script_failed(None)
            elif state:
                self._sync_state()
        else:
            self._sync_state()
        self._refresh_tab_indicators()

    def sync_from_host(self, events: Any = None) -> None:
        """Alias for :meth:`handle_host_events` (or pump when no events)."""
        if events is None:
            self.pump()
        else:
            self.handle_host_events(events)

    # -- focus loss saving / panel events ---------------------------------------

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        editors = getattr(self, "_editors", {})
        if event.type() == QEvent.Type.FocusOut and obj in editors.values():
            self._save_editor(obj)  # type: ignore[arg-type]
        tab_bar = getattr(self, "tabs", None)
        if tab_bar is not None and event.type() == QEvent.Type.MouseButtonPress:
            if obj is tab_bar.tabBar() and event.button() == Qt.MouseButton.MiddleButton:
                index = tab_bar.tabBar().tabAt(event.position().toPoint())
                if index >= 0:
                    self.close_tab(index)
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def save_geometry(self) -> None:
        """Persist the panel geometry and the open tabs."""
        self._save_tab_state()
        super().save_geometry()

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        self.save_all()
        self._save_tab_state()
        super().closeEvent(event)


DEFAULT_SCRIPTS_DIR = default_scripts_dir()
