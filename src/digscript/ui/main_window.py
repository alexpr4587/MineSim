"""Main window: HUD on top, world view as the central widget."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from digscript.ui.game_loop import GameLoop
from digscript.ui.hud import HUD
from digscript.ui.world_view import WorldView

__all__ = ["MainWindow"]


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
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget):
                if parent is None:
                    parent = arg
            elif game is None:
                game = arg
        if game is None:
            from digscript.core.game import Game

            game = Game.new()
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("DigScript")
        self.world_view = WorldView(game)
        self.hud = HUD(game)
        self.game_loop = GameLoop(game, hud=self.hud, world_view=self.world_view)
        self.hud.set_game_loop(self.game_loop)
        self.loop = self.game_loop
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.hud)
        layout.addWidget(self.world_view, 1)
        self.setCentralWidget(container)
        self.resize(1024, 768)
        self.game_loop.start()

    def refresh(self) -> None:
        """Refresh the HUD and world view."""
        self.hud.refresh()
        self.world_view.update()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Stop the game loop when the window closes."""
        self.game_loop.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override name
        """Space toggles pause; keys 1 to 5 set the speed."""
        if self.game_loop.handle_key(event.key()):
            event.accept()
            return
        if event.key() in (Qt.Key.Key_C, Qt.Key.Key_c, Qt.Key.Key_G, Qt.Key.Key_g):
            self.world_view.keyPressEvent(event)
            return
        super().keyPressEvent(event)
