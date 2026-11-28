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


def _setup_audio(window: Any) -> None:
    """Create the audio manager and warm the cache in the background."""
    try:
        from minesim.audio.backend import select_backend
        from minesim.audio.cache import AudioCache
        from minesim.audio.manager import AudioManager
        from minesim.audio.settings import AudioSettings

        cache = AudioCache()
        backend = select_backend(cache)
        manager = AudioManager(AudioSettings.load(), backend, cache)
        window.audio = manager
        window.audio_cache = cache
        setter = getattr(window, "set_audio", None)
        if callable(setter):
            setter(manager, cache)
        else:
            window.audio = manager
            window.audio_cache = cache

        def _on_warm() -> None:
            bridge = getattr(window, "audio_bridge", None)
            if bridge is not None:
                bridge.sync_music(force=True)
            else:
                manager.set_mood("surface", fade_ms=1500)

        window.audio_warm_thread = cache.warm_async(_on_warm)
    except Exception:
        logger.warning("Could not start audio", exc_info=True)


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
    _setup_audio(window)
    window.show()
    return app.exec()


def run() -> int:
    """Alias for :func:`main` (entry point used by ``__main__``)."""
    return main()


if __name__ == "__main__":
    raise SystemExit(main())
