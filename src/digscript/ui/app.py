"""Application bootstrap: load the autosave or start a new game."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["load_game_or_new", "main", "run"]


def load_game_or_new(path: str | Path | None = None) -> Any:
    """Load the autosave at ``path`` if it exists, else start a new game."""
    from digscript.core.game import Game
    from digscript.core.save import SaveError, default_save_path

    target = Path(path) if path is not None else default_save_path()
    if target.is_file():
        try:
            return Game.load(target)
        except (SaveError, ValueError, OSError) as exc:
            logger.warning("Could not load autosave %s: %s; starting a new game", target, exc)
    return Game.new()


def main() -> int:
    """Start the UI and return the exit code."""
    from PySide6.QtWidgets import QApplication

    from digscript.ui.main_window import MainWindow
    from digscript.ui.theme import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    game = load_game_or_new()
    window = MainWindow(game)
    window.show()
    return app.exec()


def run() -> int:
    """Alias for :func:`main` (entry point used by ``__main__``)."""
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
