"""Main window: HUD on top, world view central, floating panels overlaid."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from minesim import __version__
from minesim.core.game import Game
from minesim.core.save import default_save_path
from minesim.ui.achievements_panel import AchievementsPanel
from minesim.ui.api_panel import ApiPanel
from minesim.ui.base_panel import BasePanel
from minesim.ui.editor_panel import EditorPanel, default_scripts_dir
from minesim.ui.floating_panel import ensure_settings_names
from minesim.ui.game_loop import GameLoop
from minesim.ui.hud import HUD
from minesim.ui.links import (
    BUG_REPORT_URL,
    FEEDBACK_URL,
    PROJECT_PAGE_URL,
)
from minesim.ui.market_panel import MarketPanel
from minesim.ui.miners_panel import MinersPanel
from minesim.ui.options_panel import OptionsPanel
from minesim.ui.toasts import ToastManager
from minesim.ui.upgrades_panel import UpgradesPanel
from minesim.ui.wardrobe_panel import WardrobePanel
from minesim.ui.world_view import WorldView

__all__ = ["MainWindow"]

_SINGLE_KEYS = {
    Qt.Key.Key_T,
    Qt.Key.Key_E,
    Qt.Key.Key_F,
    Qt.Key.Key_L,
    Qt.Key.Key_U,
    Qt.Key.Key_K,
    Qt.Key.Key_B,
    Qt.Key.Key_M,
    Qt.Key.Key_C,
    Qt.Key.Key_G,
    Qt.Key.Key_H,
    Qt.Key.Key_O,
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
    """The main MineSim window (WorldView central, HUD on top)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        game = kwargs.pop("game", None)
        parent = kwargs.pop("parent", None)
        scripts_dir = (
            kwargs.pop("scripts_dir", None)
            or kwargs.pop("script_dir", None)
            or kwargs.pop("scripts_directory", None)
        )
        host = kwargs.pop("host", None) or kwargs.pop("script_host", None)
        manager = kwargs.pop("manager", None) or kwargs.pop("script_manager", None)
        audio = kwargs.pop("audio", None) or kwargs.pop("audio_manager", None)
        audio_cache = kwargs.pop("audio_cache", None)
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
            from minesim.core.game import Game

            game = Game.new()
        ensure_settings_names()
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("MineSim")
        self.world_view = WorldView(game)
        self.hud = HUD(game, world_view=self.world_view)
        self.scripts_dir: Path = (
            Path(scripts_dir) if scripts_dir is not None else default_scripts_dir()
        )
        if manager is None:
            try:
                from minesim.scripting.manager import ScriptManager

                manager = ScriptManager(game, self.scripts_dir)
            except Exception:
                manager = None
        if manager is not None:
            if host is not None:
                try:
                    manager.adopt_host(host)
                except Exception:
                    pass
            else:
                try:
                    host = manager.host(0) or manager.ensure_host(0)
                except Exception:
                    host = None
        elif host is None:
            try:
                from minesim.scripting.host import ScriptHost

                host = ScriptHost(
                    _get(game, "engine"),
                    _get(game, "content"),
                    _get(game, "progression_service") or _get(game, "progression"),
                    self.scripts_dir,
                )
            except Exception:
                host = None
        self.manager = manager
        self.script_manager = manager
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
            if manager is not None:
                try:
                    self.editor_panel.set_manager(manager)
                except Exception:
                    pass
            elif _get(self.editor_panel, "host") is None and host is not None:
                try:
                    self.editor_panel.set_host(host)
                except Exception:
                    pass
        else:
            self.editor_panel = EditorPanel(
                game=game,
                host=host,
                manager=manager,
                scripts_dir=self.scripts_dir,
                parent=self,
                console_panel=console_panel_arg,
            )
        self.editor = self.editor_panel
        self.code_editor = _get(self.editor_panel, "code_editor") or _get(
            self.editor_panel, "editor"
        )
        try:
            self.editor_panel.editor_changed.connect(self._on_editor_changed)
        except Exception:
            pass
        self.console_panel = _get(self.editor_panel, "console_panel") or console_panel_arg
        self.console = self.console_panel
        if self.console_panel is not None and manager is not None:
            try:
                self.console_panel.set_manager(manager)
            except Exception:
                pass
        self.miners_panel = MinersPanel(
            game=game,
            manager=manager,
            scripts_dir=self.scripts_dir,
            world_view=self.world_view,
            console_panel=self.console_panel,
            parent=self,
        )
        self._wire_miner_selection()
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
            "miners": self.miners_panel,
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
        self.wardrobe_panel = WardrobePanel(
            game=game,
            parent=self,
        )
        self.base_panel = BasePanel(
            game=game,
            parent=self,
        )
        self.market_panel = MarketPanel(
            game=game,
            parent=self,
        )
        self.floating_panels["achievements"] = self.achievements_panel
        self.floating_panels["upgrades"] = self.upgrades_panel
        self.floating_panels["wardrobe"] = self.wardrobe_panel
        self.floating_panels["base"] = self.base_panel
        self.floating_panels["market"] = self.market_panel
        self.miners_panel.hide()
        self.achievements_panel.hide()
        self.upgrades_panel.hide()
        self.wardrobe_panel.hide()
        self.base_panel.hide()
        self.market_panel.hide()
        self.wardrobe_panel.skin_selected.connect(lambda _skin: self.world_view.update())

        # Toasts for achievement unlocks.
        self.toast_manager = ToastManager(self, game)

        # Options panel (O): audio controls now, more sections later.
        self.audio = audio
        self.audio_cache = audio_cache
        self.audio_bridge = None
        self.options_panel = OptionsPanel(game=game, audio=audio, parent=self)
        self.options_panel.hide()
        self.floating_panels["options"] = self.options_panel

        self.game_loop = GameLoop(
            game,
            hud=self.hud,
            world_view=self.world_view,
            host=host,
            manager=manager,
            editor_panel=self.editor_panel,
            console_panel=self.console_panel,
        )
        self.hud.set_game_loop(self.game_loop)
        self.hud.set_audio(audio, self.show_options)
        self.loop = self.game_loop
        self.game_loop.start()
        if audio is not None:
            self.set_audio(audio, self.audio_cache)

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

    def _on_editor_changed(self, editor: Any) -> None:
        """Keep the main-window editor aliases on the active tab."""
        self.code_editor = editor
        self.editor = self.editor_panel

    def _sync_view_actions(self) -> None:
        for action, panel in (
            (getattr(self, "_editor_action", None), getattr(self, "editor_panel", None)),
            (getattr(self, "_api_action", None), getattr(self, "api_panel", None)),
            (getattr(self, "_miners_action", None), getattr(self, "miners_panel", None)),
            (
                getattr(self, "_achievements_action", None),
                getattr(self, "achievements_panel", None),
            ),
            (getattr(self, "_upgrades_action", None), getattr(self, "upgrades_panel", None)),
            (getattr(self, "_wardrobe_action", None), getattr(self, "wardrobe_panel", None)),
            (getattr(self, "_base_action", None), getattr(self, "base_panel", None)),
            (getattr(self, "_market_action", None), getattr(self, "market_panel", None)),
            (getattr(self, "_options_action", None), getattr(self, "options_panel", None)),
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

    # -- miners / selection ----------------------------------------------------

    def _wire_miner_selection(self) -> None:
        """Keep the miners panel, world view and console on one selection."""
        try:
            self.miners_panel.miner_selected.connect(
                lambda miner_id: self._sync_miner_selection(miner_id, "panel")
            )
            self.world_view.selected_miner_changed.connect(
                lambda miner_id: self._sync_miner_selection(miner_id, "world")
            )
        except Exception:
            pass
        selector = _get(self.console_panel, "miner_selector")
        if selector is not None and hasattr(selector, "currentIndexChanged"):
            try:
                selector.currentIndexChanged.connect(self._on_console_miner_changed)
            except Exception:
                pass

    def _sync_miner_selection(self, miner_id: int, source: str = "") -> None:
        """Apply ``miner_id`` to every view except the one that emitted it."""
        try:
            miner_id = int(miner_id)
        except (TypeError, ValueError):
            return
        if source != "panel" and _get(self.miners_panel, "selected_miner") != miner_id:
            try:
                self.miners_panel.select_miner(miner_id)
            except Exception:
                pass
        if source != "world" and _get(self.world_view, "selected_miner_id") != miner_id:
            try:
                self.world_view.select_miner(miner_id)
            except Exception:
                pass
        if (
            self.console_panel is not None
            and _get(self.console_panel, "selected_miner") != miner_id
        ):
            try:
                self.console_panel.set_miner(miner_id)
            except Exception:
                pass

    def _on_console_miner_changed(self, _index: int) -> None:
        selected = _get(self.console_panel, "selected_miner")
        if selected is not None:
            self._sync_miner_selection(int(selected), "console")

    def toggle_miners(self) -> None:
        """Toggle the miners panel (T)."""
        self.miners_panel.toggle()
        self._sync_view_actions()

    def show_miners(self) -> None:
        """Show the miners panel."""
        self.miners_panel.refresh()
        self.miners_panel.show_panel()
        self._sync_view_actions()

    def hide_miners(self) -> None:
        """Hide the miners panel."""
        self.miners_panel.hide_panel()
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

    def toggle_wardrobe(self) -> None:
        """Toggle the wardrobe panel (K)."""
        self.wardrobe_panel.toggle()
        self._sync_view_actions()

    def show_wardrobe(self) -> None:
        """Show the wardrobe panel."""
        self.wardrobe_panel.show_panel()
        self._sync_view_actions()

    def hide_wardrobe(self) -> None:
        """Hide the wardrobe panel."""
        self.wardrobe_panel.hide_panel()
        self._sync_view_actions()

    def toggle_base(self) -> None:
        """Toggle the base panel (B)."""
        self.base_panel.toggle()
        self._sync_view_actions()

    def show_base(self) -> None:
        """Show the base panel."""
        self.base_panel.show_panel()
        self._sync_view_actions()

    def hide_base(self) -> None:
        """Hide the base panel."""
        self.base_panel.hide_panel()
        self._sync_view_actions()

    def toggle_market(self) -> None:
        """Toggle the market panel (M)."""
        self.market_panel.toggle()
        self._sync_view_actions()

    def show_market(self) -> None:
        """Show the market panel."""
        self.market_panel.show_panel()
        self._sync_view_actions()

    def hide_market(self) -> None:
        """Hide the market panel."""
        self.market_panel.hide_panel()
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

    def _on_terrain_lighting_toggled(self, checked: bool) -> None:
        self.world_view.set_terrain_lighting(checked)

    def _sync_terrain_action(self, enabled: bool) -> None:
        action = getattr(self, "_terrain_action", None)
        if action is None:
            return
        action.blockSignals(True)
        action.setChecked(bool(enabled))
        action.blockSignals(False)

    def toggle_terrain_lighting(self) -> None:
        """Toggle the lit 2.5D terrain renderer (H in the world view)."""
        self.world_view.toggle_terrain_lighting()

    # -- audio / options ------------------------------------------------------

    def set_audio(self, audio: Any, cache: Any = None) -> None:
        """Attach the audio manager and build the event/music bridge."""
        self.audio = audio
        self.audio_cache = cache
        self.options_panel.set_audio(audio)
        self.hud.set_audio(audio, self.show_options)
        if audio is None:
            return
        try:
            from minesim.ui.audio_bridge import AudioBridge

            bridge = AudioBridge(
                self.game,
                audio,
                world_view=self.world_view,
                content=getattr(self.game, "content", None),
            )
        except Exception:
            self.audio_bridge = None
            return
        self.audio_bridge = bridge
        self.hud.set_audio_bridge(bridge)
        self.game_loop.set_audio_bridge(bridge)
        bridge.set_paused(bool(getattr(self.game_loop, "paused", False)))
        self._maybe_show_audio_hint()

    def _maybe_show_audio_hint(self) -> None:
        """Show the one-time first-run audio hint."""
        settings = getattr(self.audio, "settings", None)
        if settings is None or bool(getattr(settings, "hint_shown", True)):
            return
        settings.hint_shown = True
        saver = getattr(settings, "save", None)
        if callable(saver):
            try:
                saver()
            except Exception:
                pass
        QTimer.singleShot(
            1200,
            lambda: self.toast_manager.show_message(
                "Sound", "Music is on. Press O to change the sound."
            ),
        )

    def show_options(self) -> None:
        """Show the options panel (O)."""
        self.options_panel.show_panel()
        self._sync_view_actions()

    def toggle_options(self) -> None:
        """Toggle the options panel (O)."""
        self.options_panel.toggle()
        self._sync_view_actions()

    def _toggle_mute(self) -> None:
        """Mute or unmute all audio (Ctrl+Shift+M)."""
        self.hud.toggle_mute()

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
        self._wardrobe_action = view_menu.addAction("&Wardrobe")
        self._wardrobe_action.setCheckable(True)
        self._wardrobe_action.setShortcut(QKeySequence("Ctrl+K"))
        self._wardrobe_action.setToolTip("Toggle wardrobe (K when world focused)")
        self._wardrobe_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.wardrobe_panel, checked)
        )
        self._base_action = view_menu.addAction("&Base")
        self._base_action.setCheckable(True)
        self._base_action.setShortcut(QKeySequence("Ctrl+B"))
        self._base_action.setToolTip("Toggle base panel (B when world focused)")
        self._base_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.base_panel, checked)
        )
        self._market_action = view_menu.addAction("&Market")
        self._market_action.setCheckable(True)
        self._market_action.setShortcut(QKeySequence("Ctrl+M"))
        self._market_action.setToolTip("Toggle market panel (M when world focused)")
        self._market_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.market_panel, checked)
        )
        self._miners_action = view_menu.addAction("&Miners")
        self._miners_action.setCheckable(True)
        self._miners_action.setShortcut(QKeySequence("Ctrl+T"))
        self._miners_action.setToolTip("Toggle miners panel (T when world focused)")
        self._miners_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.miners_panel, checked)
        )
        view_menu.addSeparator()
        self._options_action = view_menu.addAction("&Options…")
        self._options_action.setShortcut(QKeySequence("Ctrl+,"))
        self._options_action.setToolTip("Audio and other options (O when world focused)")
        self._options_action.triggered.connect(
            lambda checked=False: self._on_view_action(self.options_panel, checked)
        )
        view_menu.addSeparator()
        self._terrain_action = view_menu.addAction("Terrain &lighting")
        self._terrain_action.setCheckable(True)
        self._terrain_action.setChecked(bool(self.world_view.terrain_lighting))
        self._terrain_action.setToolTip("Toggle lit 2.5D terrain (H when world focused)")
        self._terrain_action.toggled.connect(self._on_terrain_lighting_toggled)
        self.world_view.terrain_lighting_changed.connect(self._sync_terrain_action)
        menu_bar.addMenu(view_menu)
        self._view_menu = view_menu
        self._build_help_menu(menu_bar)
        self.setMenuBar(menu_bar)
        self._file_menu = file_menu
        # F10 opens the File menu.
        self._f10_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F10), self)
        self._f10_shortcut.activated.connect(self._open_file_menu)
        self._mute_shortcut = QShortcut(QKeySequence("Ctrl+Shift+M"), self)
        self._mute_shortcut.activated.connect(self._toggle_mute)
        self._sync_view_actions()

    def _build_help_menu(self, menu_bar: QMenuBar) -> None:
        """Add the Help menu with bug, feedback, project and About entries."""
        help_menu = QMenu("&Help", self)
        self._report_bug_action = help_menu.addAction("Report a bug")
        self._report_bug_action.setData(BUG_REPORT_URL)
        self._report_bug_action.triggered.connect(
            lambda _checked=False: self._open_url(BUG_REPORT_URL)
        )
        self._feedback_action = help_menu.addAction("Send feedback")
        self._feedback_action.setData(FEEDBACK_URL)
        self._feedback_action.triggered.connect(lambda _checked=False: self._open_url(FEEDBACK_URL))
        self._project_page_action = help_menu.addAction("Open the project page")
        self._project_page_action.setData(PROJECT_PAGE_URL)
        self._project_page_action.triggered.connect(
            lambda _checked=False: self._open_url(PROJECT_PAGE_URL)
        )
        help_menu.addSeparator()
        self._about_action = help_menu.addAction("About MineSim")
        self._about_action.triggered.connect(self.show_about)
        menu_bar.addMenu(help_menu)
        self._help_menu = help_menu

    def _open_url(self, url: str) -> None:
        """Open ``url`` in the user's browser."""
        QDesktopServices.openUrl(QUrl(url))

    def about_text(self) -> str:
        """Return the text shown in the About MineSim dialog."""
        seed = getattr(self.game, "seed", 0)
        return (
            f"MineSim {__version__}\n\n"
            "Automate a mining operation by writing real Python.\n\n"
            f"World seed: {seed}\n"
            "License: MIT\n\n"
            "Player scripts run in a separate subprocess with a restricted\n"
            "namespace. This is not a security sandbox: only run scripts you trust."
        )

    def show_about(self) -> None:
        """Show the About MineSim dialog with version, seed and license."""
        QMessageBox.about(self, "About MineSim", self.about_text())

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
        self.world_view.set_game(game)
        self.miners_panel.set_game(game)
        self.achievements_panel.set_game(game)
        self.upgrades_panel.set_game(game)
        self.wardrobe_panel.set_game(game)
        self.base_panel.set_game(game)
        self.market_panel.set_game(game)
        self.toast_manager.set_game(game)
        self.api_panel.set_game(game)
        if self.audio_bridge is not None:
            try:
                self.audio_bridge.set_game(game)
                self.audio_bridge.reset_combo()
            except Exception:
                pass
        if self.manager is not None:
            self.manager.set_game(game)
            try:
                self.host = self.manager.host(0) or self.manager.ensure_host(0)
            except Exception:
                self.host = None
            self.script_host = self.host
            self.editor_panel.set_manager(self.manager)
            self.miners_panel.set_manager(self.manager)
            if self.console_panel is not None:
                self.console_panel.set_manager(self.manager)
            self.game_loop.set_manager(self.manager)
            self._wire_miner_selection()
        else:
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
            getattr(self, "wardrobe_panel", None),
            getattr(self, "base_panel", None),
            getattr(self, "market_panel", None),
            getattr(self, "miners_panel", None),
        ):
            if panel is not None:
                try:
                    if panel is focused or panel.isAncestorOf(focused):
                        return False
                except Exception:
                    pass
        options = getattr(self, "options_panel", None)
        if options is not None:
            try:
                if options is focused or options.isAncestorOf(focused):
                    return True
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
        """Refresh the HUD, world view and fleet panel."""
        self.hud.refresh()
        self.world_view.update()
        try:
            self.miners_panel.refresh()
        except Exception:
            pass
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
            getattr(self, "wardrobe_panel", None),
            getattr(self, "base_panel", None),
            getattr(self, "market_panel", None),
            getattr(self, "miners_panel", None),
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
        manager = getattr(self, "manager", None) or getattr(self, "script_manager", None)
        if manager is not None:
            try:
                manager.stop_all()
            except Exception:
                pass
        else:
            host = getattr(self, "host", None) or getattr(self, "script_host", None)
            if host is not None:
                try:
                    host.stop()
                except Exception:
                    pass
        bridge = getattr(self, "audio_bridge", None)
        if bridge is not None:
            try:
                bridge.close()
            except Exception:
                pass
        self.game_loop.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Hotkeys: E editor, F functions, B base, M market, Space/1-5 speed, C/G world."""
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
        if (
            modifiers & ctrl
            and modifiers & Qt.KeyboardModifier.ShiftModifier
            and key == Qt.Key.Key_M
        ):
            self._toggle_mute()
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
        if key == Qt.Key.Key_K:
            self.toggle_wardrobe()
            event.accept()
            return
        if key == Qt.Key.Key_B:
            self.toggle_base()
            event.accept()
            return
        if key == Qt.Key.Key_M:
            self.toggle_market()
            event.accept()
            return
        if key == Qt.Key.Key_T:
            self.toggle_miners()
            event.accept()
            return
        if key == Qt.Key.Key_O:
            self.toggle_options()
            event.accept()
            return
        if key == Qt.Key.Key_F10:
            self._open_file_menu()
            event.accept()
            return
        if self.game_loop.handle_key(key):
            event.accept()
            return
        if key in (Qt.Key.Key_C, Qt.Key.Key_G, Qt.Key.Key_H):
            self.world_view.keyPressEvent(event)
            return
        super().keyPressEvent(event)
