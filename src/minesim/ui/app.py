"""Application bootstrap: load the autosave or start a new game."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["load_game_or_new", "main", "run"]


def load_game_or_new(path: str | Path | None = None) -> Any:
    """Load the autosave at ``path`` if it exists, else start a new game."""
    from minesim.core.game import Game
    from minesim.core.save import SaveError, default_save_path

    target = Path(path) if path is not None else default_save_path()
    if target.is_file():
        try:
            return Game.load(target)
        except (SaveError, ValueError, OSError) as exc:
            logger.warning("Could not load autosave %s: %s; starting a new game", target, exc)
    return Game.new()


def _migrate_legacy_settings() -> None:
    from PySide6.QtCore import QSettings

    old = QSettings("DigScript", "DigScript")
    keys = old.allKeys()
    if not keys:
        return
    new = QSettings("MineSim", "MineSim")
    if new.allKeys():
        return
    for key in keys:
        new.setValue(key, old.value(key))
    new.sync()
    old.clear()
    old.sync()
    logger.info("Migrated settings from DigScript to MineSim")


def main() -> int:
    """Start the UI and return the exit code."""
    from PySide6.QtWidgets import QApplication

    from minesim.core.user_data import migrate_legacy_user_data
    from minesim.ui.main_window import MainWindow
    from minesim.ui.theme import apply_theme

    try:
        migrate_legacy_user_data()
        _migrate_legacy_settings()
    except Exception:
        logger.warning("Could not migrate legacy user data", exc_info=True)
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("MineSim")
    app.setApplicationName("MineSim")
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
