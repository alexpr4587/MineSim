"""Editor panel: script tabs, run/stop controls and the console."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QFileSystemWatcher, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from digscript.ui.code_editor import CodeEditor
from digscript.ui.console_panel import ConsolePanel
from digscript.ui.floating_panel import FloatingPanel

__all__ = [
    "DEFAULT_SCRIPTS_DIR",
    "STARTER_SCRIPT",
    "STARTER_SOURCE",
    "EditorPanel",
    "default_scripts_dir",
    "get_scripts_dir",
]

STARTER_SCRIPT = (
    "# Welcome! Edit this script and press Run (Ctrl+R).\n"
    "for _ in range(10):\n"
    "    if peek() is not None:\n"
    "        mine()\n"
    "    move(East)\n"
)
STARTER_SOURCE = STARTER_SCRIPT


def default_scripts_dir() -> Path:
    """Return ``user_data_dir('DigScript')/scripts`` as a Path."""
    try:
        from platformdirs import user_data_dir

        base = user_data_dir("DigScript")
    except Exception:
        base = str(Path.home() / ".local" / "share" / "DigScript")
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Editor"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        host = kwargs.pop("host", None) or kwargs.pop("script_host", None)
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
                from digscript.core.game import Game

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
        if host is None:
            try:
                from digscript.scripting.host import ScriptHost

                host = ScriptHost(engine, content, progression, self.scripts_dir)
            except Exception:
                host = None
        self.host = host
        self.script_host = host
        self.engine = engine
        self.content = content
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
        self.editor: CodeEditor | None = None
        self.code_editor: CodeEditor | None = None
        self.current_editor: CodeEditor | None = None

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(4)

        self.tabs = QTabWidget(self.content_widget)
        self.tab_widget = self.tabs
        self.file_tabs = self.tabs
        self.tabWidget = self.tabs
        body.addWidget(self.tabs, 1)

        controls = QHBoxLayout()
        self.new_file_button = QPushButton("New file", self.content_widget)
        self.run_button = QPushButton("Run", self.content_widget)
        self.stop_button = QPushButton("Stop", self.content_widget)
        self.open_folder_button = QPushButton("Open scripts folder", self.content_widget)
        self.examples_button = QPushButton("Examples", self.content_widget)
        self.examples_menu = QMenu(self.examples_button)
        self.examples_button.setMenu(self.examples_menu)
        self._example_actions: dict[str, Any] = {}
        self.new_button = self.new_file_button
        self.open_scripts_folder_button = self.open_folder_button
        self.open_button = self.open_folder_button
        self.new_file_button.clicked.connect(lambda: self.new_file())
        self.run_button.clicked.connect(self.run)
        self.stop_button.clicked.connect(self.stop)
        self.open_folder_button.clicked.connect(self.open_scripts_folder)
        self.examples_button.setToolTip("Open an example script in a new tab")
        for button in (
            self.new_file_button,
            self.run_button,
            self.stop_button,
            self.open_folder_button,
            self.examples_button,
        ):
            button.setToolTip(button.toolTip() or button.text())
            controls.addWidget(button)
        self.state_label = QLabel("Idle", self.content_widget)
        self.status_label = self.state_label
        self.stateLabel = self.state_label
        controls.addWidget(self.state_label)
        self.auto_reload_checkbox = QCheckBox("Auto-reload", self.content_widget)
        self.auto_reload_checkbox.setObjectName("auto_reload_checkbox")
        self.auto_reload_checkbox.setChecked(True)
        self.autoreload_checkbox = self.auto_reload_checkbox
        self.reload_checkbox = self.auto_reload_checkbox
        controls.addWidget(self.auto_reload_checkbox)
        controls.addStretch(1)
        body.addLayout(controls)

        if console_panel is None:
            console_panel = ConsolePanel(self.content_widget)
        self.console_panel = console_panel
        self.console = console_panel
        body.addWidget(console_panel, 0)
        console_panel.setFixedHeight(140)
        self.content_layout.addLayout(body)

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

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.refresh_files()
        self.refresh_examples_menu()
        main_index = (
            self.tabs.indexOf(self._editors["main.py"]) if "main.py" in self._editors else 0
        )
        if self.tabs.count() > 0:
            self.tabs.setCurrentIndex(main_index)
        self._sync_current_editor()
        self._subscribe_events()
        self._sync_state()

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

    def set_game(self, game: Any) -> None:
        """Attach a game, creating a host if needed."""
        self.game = game
        self.engine = _get(game, "engine")
        self.content = _get(game, "content")
        self.progression = _get(game, "progression_service") or _get(game, "progression")
        if self.host is None or _get(self.host, "engine") is None:
            try:
                from digscript.scripting.host import ScriptHost

                self.set_host(
                    ScriptHost(self.engine, self.content, self.progression, self.scripts_dir)
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
            from digscript.core.events import ScriptFailed, ScriptFinished, ScriptStarted

            bus.subscribe(ScriptStarted, lambda _e: self._sync_state("Running"))
            bus.subscribe(ScriptFinished, lambda _e: self._sync_state("Finished"))
            bus.subscribe(
                ScriptFailed,
                lambda _e: self._on_script_failed(_e),
            )
        except Exception:
            pass

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
            return
        host = self.host
        if host is None:
            self.state_label.setText("Idle")
            return
        state = getattr(host, "state", None)
        self.state_label.setText(self.state_label_text(state if state is not None else "IDLE"))
        if str(state).upper().endswith("FAILED") or str(state) == "FAILED":
            self._on_script_failed(None)

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
        editor = CodeEditor(self.tabs, content=self.content)
        editor.setPlainText(text)
        editor.setWindowTitle(filename)
        editor.run_requested.connect(self.run)
        editor.stop_requested.connect(self.stop)
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
        try:
            self.watcher.addPath(str(file_path))
        except Exception:
            pass
        return index

    def add_tab(self, path: Any, text: str | None = None) -> int:
        """Alias for :meth:`add_file`."""
        return self.add_file(path, text)

    def open_file(self, path: Any) -> int:
        """Alias for :meth:`add_file`."""
        return self.add_file(path)

    def refresh_files(self) -> None:
        """(Re)discover ``*.py`` files, adding tabs for new files."""
        for file_path in self._py_files():
            self.add_file(file_path)
        self._sync_current_editor()

    def reload_files(self) -> None:
        """Alias for :meth:`refresh_files`."""
        self.refresh_files()

    def refresh_tabs(self) -> None:
        """Alias for :meth:`refresh_files`."""
        self.refresh_files()

    def discover_files(self) -> list[Path]:
        """Return the discovered ``*.py`` files."""
        return self._py_files()

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

    def _on_tab_changed(self, _index: int) -> None:
        self._sync_current_editor()

    def current_filename(self) -> str:
        """Return the current tab file name (``main.py`` by default)."""
        if self.editor is not None:
            index = self.tabs.currentIndex()
            if index >= 0:
                return self.tabs.tabText(index)
        return "main.py"

    def current_file(self) -> Path:
        """Return the current tab file path."""
        return self.scripts_dir / self.current_filename()

    def current_path(self) -> Path:
        """Alias for :meth:`current_file`."""
        return self.current_file()

    def _content_examples(self) -> list[Any]:
        content = _get(getattr(self, "game", None), "content") or self.content
        if content is None or not hasattr(content, "examples"):
            try:
                from digscript.core.content import load_content

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
        content = _get(getattr(self, "game", None), "content") or self.content
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
        name = self.tabs.tabText(index)
        self._saving = True
        try:
            file_path = self.scripts_dir / name
            file_path.write_text(editor.toPlainText(), encoding="utf-8")
            try:
                editor.document().setModified(False)
            except Exception:
                pass
        except Exception:
            pass
        finally:
            self._saving = False

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
            self.add_file(file_path)
            return
        if editor.document().isModified():
            return
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            return
        if editor.toPlainText() != text:
            editor.setPlainText(text)
            try:
                editor.document().setModified(False)
            except Exception:
                pass

    def reload_from_disk(self) -> None:
        """Reload open files from disk (when auto-reload is on)."""
        if not self.auto_reload_checkbox.isChecked():
            return
        for file_path in self._py_files():
            self._reload_file(str(file_path))

    def _on_directory_changed(self, _path: str) -> None:
        if self._saving or not self.auto_reload_checkbox.isChecked():
            return
        self.refresh_files()
        self.reload_from_disk()

    def _on_file_changed(self, path: str) -> None:
        try:
            self.watcher.addPath(path)
        except Exception:
            pass
        if self._saving or not self.auto_reload_checkbox.isChecked():
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
            host.start(filename, source)
        except Exception:
            self.state_label.setText("Error")
            return
        self._sync_state("Running")

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
        """Pump the host once, feeding console/state/error highlight."""
        host = self.host
        if host is None:
            return []
        try:
            events = host.pump()
        except Exception:
            return []
        self.handle_host_events(events)
        return list(events or [])

    def handle_host_events(self, events: Any) -> None:
        """Feed host ``events`` to the console and update state."""
        if events:
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
        return super().eventFilter(obj, event)

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        self.save_all()
        super().closeEvent(event)


DEFAULT_SCRIPTS_DIR = default_scripts_dir()
