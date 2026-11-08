"""Main window: HUD on top, world view central, floating panels overlaid."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from digscript.core.game import Game
from digscript.core.save import default_save_path
from digscript.ui.achievements_panel import AchievementsPanel
from digscript.ui.api_panel import ApiPanel
from digscript.ui.editor_panel import EditorPanel, default_scripts_dir
from digscript.ui.floating_panel import ensure_settings_names
from digscript.ui.game_loop import GameLoop
from digscript.ui.hud import HUD
from digscript.ui.toasts import ToastManager
from digscript.ui.upgrades_panel import UpgradesPanel
from digscript.ui.world_view import WorldView

__all__ = ["MainWindow"]

_SINGLE_KEYS = {
    Qt.Key.Key_E,
    Qt.Key.Key_F,
    Qt.Key.Key_L,
    Qt.Key.Key_U,
    Qt.Key.Key_C,
    Qt.Key.Key_G,
    Qt.Key.Key_Space,
    Qt.Key.Key_1,
    Qt.Key.Key_2,
    Qt.Key.Key_3,
    Qt.Key.Key_4,
    Qt.Key.Key_5,
}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class MainWindow(QMainWindow):
    """The main DigScript window (WorldView central, HUD on top)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        game = kwargs.pop("game", None)
        parent = kwargs.pop("parent", None)
        scripts_dir = (
            kwargs.pop("scripts_dir", None)
            or kwargs.pop("script_dir", None)
            or kwargs.pop("scripts_directory", None)
        )
        host = kwargs.pop("host", None) or kwargs.pop("script_host", None)
        editor_panel_arg = kwargs.pop("editor_panel", None) or kwargs.pop("editor", None)
        api_panel_arg = kwargs.pop("api_panel", None) or kwargs.pop("functions_panel", None)
        console_panel_arg = kwargs.pop("console_panel", None) or kwargs.pop("console", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget):
                if parent is None:
                    parent = arg
            elif hasattr(arg, "start") and hasattr(arg, "pump"):
                if host is None:
                    host = arg
            elif isinstance(arg, (str, Path)):
                if scripts_dir is None:
                    scripts_dir = arg
            elif game is None:
                game = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        if game is None:
            from digscript.core.game import Game

            game = Game.new()
        ensure_settings_names()
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("DigScript")
        self.world_view = WorldView(game)
        self.hud = HUD(game)
        self.scripts_dir: Path = (
            Path(scripts_dir) if scripts_dir is not None else default_scripts_dir()
        )
        if host is None:
            try:
                from digscript.scripting.host import ScriptHost

                host = ScriptHost(
                    _get(game, "engine"),
                    _get(game, "content"),
                    _get(game, "progression_service") or _get(game, "progression"),
                    self.scripts_dir,
                )
            except Exception:
                host = None
        self.host = host
        self.script_host = host

        container = QWidget(self)
        self.container = container
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.hud)
        layout.addWidget(self.world_view, 1)
        self.setCentralWidget(container)
        self.resize(1024, 768)

        if editor_panel_arg is not None:
            self.editor_panel = editor_panel_arg
            if _get(self.editor_panel, "host") is None and host is not None:
                try:
                    self.editor_panel.set_host(host)
                except Exception:
                    pass
        else:
            self.editor_panel = EditorPanel(
                game=game,
                host=host,
                scripts_dir=self.scripts_dir,
                parent=self,
                console_panel=console_panel_arg,
            )
        self.editor = self.editor_panel
        self.code_editor = _get(self.editor_panel, "code_editor") or _get(
            self.editor_panel, "editor"
        )
        self.console_panel = _get(self.editor_panel, "console_panel") or console_panel_arg
        self.console = self.console_panel
        if api_panel_arg is not None:
            self.api_panel = api_panel_arg
        else:
            self.api_panel = ApiPanel(game=game, host=host, parent=self)
        self.functions_panel = self.api_panel
        self.api_reference = self.api_panel
        self.function_panel = self.api_panel
        self.floating_panels: dict[str, Any] = {
            "editor": self.editor_panel,
            "api": self.api_panel,
            "functions": self.api_panel,
        }
        self.panels = self.floating_panels

        # Achievements (L) and upgrades (U) panels.
        self.achievements_panel = AchievementsPanel(
            game=game,
            parent=self,
        )
        self.upgrades_panel = UpgradesPanel(
            game=game,
            parent=self,
        )
        self.floating_panels["achievements"] = self.achievements_panel
        self.floating_panels["upgrades"] = self.upgrades_panel
        self.achievements_panel.hide()
        self.upgrades_panel.hide()

        # Toasts for achievement unlocks.
        self.toast_manager = ToastManager(self, game)

        self.game_loop = GameLoop(
            game,
            hud=self.hud,
            world_view=self.world_view,
            host=host,
            editor_panel=self.editor_panel,
            console_panel=self.console_panel,
        )
        self.hud.set_game_loop(self.game_loop)
        self.loop = self.game_loop
        self.game_loop.start()

        # Autosave every 30 s of wall-clock time.
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30000)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

        # Menu bar (F10): New game, Load, Save, Quit.
        self._build_menu_bar()

        # Show the editor over the world; the functions panel starts hidden.
        try:
            self.editor_panel.show_panel()
        except Exception:
            self.editor_panel.show()
        self.api_panel.hide()
        self.world_view.setFocus()

    # -- panel toggles -------------------------------------------------------------

    def _sync_view_actions(self) -> None:
        for action, panel in (
            (getattr(self, "_editor_action", None), getattr(self, "editor_panel", None)),
            (getattr(self, "_api_action", None), getattr(self, "api_panel", None)),
            (
                getattr(self, "_achievements_action", None),
                getattr(self, "achievements_panel", None),
            ),
            (getattr(self, "_upgrades_action", None), getattr(self, "upgrades_panel", None)),
        ):
            if action is not None and panel is not None:
                try:
                    action.setChecked(bool(panel.isVisible()))
                except Exception:
                    pass

    def toggle_editor(self) -> None:
        """Toggle the editor panel (E)."""
        self.editor_panel.toggle()
        self._sync_view_actions()

    def toggle_api_panel(self) -> None:
        """Toggle the functions reference panel (F)."""
        self.api_panel.toggle()
        self._sync_view_actions()

    def toggle_functions(self) -> None:
        """Alias for :meth:`toggle_api_panel`."""
        self.toggle_api_panel()

    def toggle_api(self) -> None:
        """Alias for :meth:`toggle_api_panel`."""
        self.toggle_api_panel()

    def toggle_functions_panel(self) -> None:
        """Alias for :meth:`toggle_api_panel`."""
        self.toggle_api_panel()

    def show_editor(self) -> None:
        """Show the editor panel."""
        self.editor_panel.show_panel()
        self._sync_view_actions()

    def hide_editor(self) -> None:
        """Hide the editor panel."""
        self.editor_panel.hide_panel()
        self._sync_view_actions()

    def show_api_panel(self) -> None:
        """Show the functions reference panel."""
        self.api_panel.show_panel()
        self._sync_view_actions()

    def hide_api_panel(self) -> None:
        """Hide the functions reference panel."""
        self.api_panel.hide_panel()
        self._sync_view_actions()

    # -- achievements / upgrades toggles --------------------------------------

    def toggle_achievements(self) -> None:
        """Toggle the achievements panel (L)."""
        self.achievements_panel.toggle()
        self._sync_view_actions()

    def toggle_upgrades(self) -> None:
        """Toggle the upgrades panel (U)."""
        self.upgrades_panel.toggle()
        self._sync_view_actions()

    def show_achievements(self) -> None:
        """Show the achievements panel."""
        self.achievements_panel.show_panel()
        self._sync_view_actions()

    def hide_achievements(self) -> None:
        """Hide the achievements panel."""
        self.achievements_panel.hide_panel()
        self._sync_view_actions()

    def show_upgrades(self) -> None:
        """Show the upgrades panel."""
        self.upgrades_panel.show_panel()
        self._sync_view_actions()

    def hide_upgrades(self) -> None:
        """Hide the upgrades panel."""
        self.upgrades_panel.hide_panel()
        self._sync_view_actions()

    def _on_view_action(self, panel: Any, checked: bool) -> None:
        if panel is None:
            return
        try:
            if checked:
                panel.show_panel()
            else:
                panel.hide_panel()
        except Exception:
            pass
        self._sync_view_actions()

    # -- menu bar (F10) -------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = QMenuBar(self)
        file_menu = QMenu("&File", self)
        new_action = file_menu.addAction("&New game")
        new_action.setShortcut(QKeySequence("Ctrl+N"))
        new_action.triggered.connect(self._new_game)
        load_action = file_menu.addAction("&Load…")
        load_action.setShortcut(QKeySequence("Ctrl+O"))
        load_action.triggered.connect(self._load_game)
        save_action = file_menu.addAction("&Save")
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._save_game)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("&Quit")
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        menu_bar.addMenu(file_menu)
        view_menu = QMenu("&View", self)
        self._editor_action = view_menu.addAction("&Editor")
        self._editor_action.setCheckable(True)
        self._editor_action.setShortcut(QKeySequence("Ctrl+E"))
        self._editor_action.setToolTip("Toggle editor (E when world focused, Ctrl+E anywhere)")
        self._editor_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.editor_panel, checked)
        )
        self._api_action = view_menu.addAction("&Functions / API")
        self._api_action.setCheckable(True)
        self._api_action.setShortcut(QKeySequence("Ctrl+F"))
        self._api_action.setToolTip("Toggle API panel (F when world focused)")
        self._api_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.api_panel, checked)
        )
        self._achievements_action = view_menu.addAction("&Achievements")
        self._achievements_action.setCheckable(True)
        self._achievements_action.setShortcut(QKeySequence("Ctrl+L"))
        self._achievements_action.setToolTip("Toggle achievements (L when world focused)")
        self._achievements_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.achievements_panel, checked)
        )
        self._upgrades_action = view_menu.addAction("&Upgrades")
        self._upgrades_action.setCheckable(True)
        self._upgrades_action.setShortcut(QKeySequence("Ctrl+U"))
        self._upgrades_action.setToolTip("Toggle upgrades (U when world focused)")
        self._upgrades_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.upgrades_panel, checked)
        )
        menu_bar.addMenu(view_menu)
        self._view_menu = view_menu
        self.setMenuBar(menu_bar)
        self._file_menu = file_menu
        # F10 opens the File menu.
        self._f10_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F10), self)
        self._f10_shortcut.activated.connect(self._open_file_menu)
        self._sync_view_actions()

    def _open_file_menu(self) -> None:
        menu = getattr(self, "_file_menu", None)
        if menu is not None:
            menu.menuAction().trigger()
            menu.show()

    # -- save / load / new ----------------------------------------------------

    def _autosave(self) -> None:
        """Autosave every 30 s of wall-clock time."""
        try:
            self.game.save()
        except Exception:
            pass

    def _save_game(self) -> None:
        try:
            path = self.game.save()
            self._notify(f"Saved to {path}")
        except Exception as exc:
            self._notify(f"Save failed: {exc}")

    def _load_game(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load game", str(default_save_path().parent), "JSON (*.json)"
        )
        if not path:
            return
        try:
            self._switch_game(Game.load(path))
            self._notify(f"Loaded {path}")
        except Exception as exc:
            self._notify(f"Load failed: {exc}")

    def _new_game(self) -> None:
        try:
            self._switch_game(Game.new())
            self._notify("New game started")
        except Exception as exc:
            self._notify(f"New game failed: {exc}")

    def _switch_game(self, game: Game) -> None:
        """Replace the active game and re-bind panels/toasts."""
        self.game_loop.stop()
        self.game = game
        self.game_loop.game = game
        self.game_loop.engine = game.engine
        self.hud.set_game(game)
        self.world_view.game = game
        self.world_view.world = game.world
        self.world_view.engine = game.engine
        self.achievements_panel.set_game(game)
        self.upgrades_panel.set_game(game)
        self.toast_manager.set_game(game)
        self.api_panel.set_game(game)
        self.editor_panel.set_game(game)
        self.world_view.update()
        self.hud.refresh()
        self.game_loop.start()

    def _notify(self, message: str) -> None:
        self.statusBar().showMessage(message, 3000)

    # -- hotkeys ----------------------------------------------------------------------

    def _focus_allows_hotkeys(self) -> bool:
        """Return True only when the world view or HUD (or window) has focus."""
        from PySide6.QtWidgets import QApplication

        focused = QApplication.focusWidget()
        if focused is None:
            return True
        if isinstance(focused, (QPlainTextEdit, QTextEdit, QLineEdit)):
            return False
        # Any text widget (duck-typed) also blocks single keys.
        if hasattr(focused, "toPlainText") and hasattr(focused, "textCursor"):
            return False
        if focused is self:
            return True
        for panel in (
            getattr(self, "editor_panel", None),
            getattr(self, "api_panel", None),
            getattr(self, "achievements_panel", None),
            getattr(self, "upgrades_panel", None),
        ):
            if panel is not None:
                try:
                    if panel is focused or panel.isAncestorOf(focused):
                        return False
                except Exception:
                    pass
        world_view = getattr(self, "world_view", None)
        hud = getattr(self, "hud", None)
        if world_view is not None and (focused is world_view or world_view.isAncestorOf(focused)):
            return True
        if hud is not None and (focused is hud or hud.isAncestorOf(focused)):
            return True
        if focused is getattr(self, "container", None):
            return True
        return False

    def _focus_is_text_widget(self) -> bool:
        from PySide6.QtWidgets import QApplication

        focused = QApplication.focusWidget()
        if focused is None:
            return False
        if isinstance(focused, (QPlainTextEdit, QTextEdit, QLineEdit)):
            return True
        return bool(hasattr(focused, "toPlainText") and hasattr(focused, "textCursor"))

    def _move_focus_to_world(self) -> None:
        world_view = getattr(self, "world_view", None)
        if world_view is not None:
            world_view.setFocus()

    def refresh(self) -> None:
        """Refresh the HUD and world view."""
        self.hud.refresh()
        self.world_view.update()
        try:
            self.editor_panel._sync_state()
        except Exception:
            pass
        try:
            self.api_panel.refresh()
        except Exception:
            pass

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Stop the script and game loop when the window closes; save the game."""
        for panel in (
            getattr(self, "editor_panel", None),
            getattr(self, "api_panel", None),
            getattr(self, "achievements_panel", None),
            getattr(self, "upgrades_panel", None),
        ):
            if panel is not None:
                try:
                    panel.save_geometry()
                except Exception:
                    pass
        try:
            self.game.save()
        except Exception:
            pass
        host = getattr(self, "host", None) or getattr(self, "script_host", None)
        if host is not None:
            try:
                host.stop()
            except Exception:
                pass
        self.game_loop.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Hotkeys: E editor, F functions, Space/1-5 speed, C/G world."""
        key = event.key()
        modifiers = event.modifiers()
        try:
            from PySide6.QtCore import Qt as _Qt

            ctrl = _Qt.KeyboardModifier.ControlModifier
        except Exception:
            ctrl = event.modifiers()
        if modifiers & ctrl and key == Qt.Key.Key_R:
            try:
                self.editor_panel.run()
            except Exception:
                pass
            event.accept()
            return
        if modifiers & ctrl and key == Qt.Key.Key_Period:
            try:
                self.editor_panel.stop()
            except Exception:
                pass
            event.accept()
            return
        if key == Qt.Key.Key_Escape and self._focus_is_text_widget():
            self._move_focus_to_world()
            event.accept()
            return
        if key in _SINGLE_KEYS and not self._focus_allows_hotkeys():
            super().keyPressEvent(event)
            return
        if key == Qt.Key.Key_E:
            self.toggle_editor()
            event.accept()
            return
        if key == Qt.Key.Key_F:
            self.toggle_api_panel()
            event.accept()
            return
        if key == Qt.Key.Key_L:
            self.toggle_achievements()
            event.accept()
            return
        if key == Qt.Key.Key_U:
            self.toggle_upgrades()
            event.accept()
            return
        if key == Qt.Key.Key_F10:
            self._open_file_menu()
            event.accept()
            return
        if self.game_loop.handle_key(key):
            event.accept()
            return
        if key in (Qt.Key.Key_C, Qt.Key.Key_G):
            self.world_view.keyPressEvent(event)
            return
        super().keyPressEvent(event)
