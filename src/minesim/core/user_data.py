"""One-time migration of user data from the legacy DigScript folder to MineSim."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["APP_NAME", "LEGACY_APP_NAME", "migrate_legacy_user_data"]

APP_NAME = "MineSim"
LEGACY_APP_NAME = "DigScript"


def _rename_settings_file(directory: Path) -> None:
    for path in directory.iterdir():
        if not path.is_file() or path.stem != LEGACY_APP_NAME:
            continue
        if path.suffix not in {".conf", ".ini"}:
            continue
        target = path.with_name(f"{APP_NAME}{path.suffix}")
        if target.exists():
            continue
        try:
            path.rename(target)
        except OSError as exc:
            logger.warning("Could not rename %s to %s: %s", path, target, exc)


def _migrate_tree(root: Path, moved: list[Path], *, settings: bool = False) -> None:
    legacy = root / LEGACY_APP_NAME
    current = root / APP_NAME
    if not legacy.is_dir() or current.exists():
        return
    try:
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy), str(current))
    except OSError as exc:
        logger.warning("Could not migrate %s to %s: %s", legacy, current, exc)
        return
    if settings:
        _rename_settings_file(current)
    logger.info("Migrated user data from %s to %s", legacy, current)
    moved.append(current)


def migrate_legacy_user_data(
    *,
    data_root: Path | None = None,
    config_root: Path | None = None,
) -> list[Path]:
    """Move legacy user data to the MineSim folders on first start.

    Saves and scripts live in the platform data directory; settings live in
    the platform configuration directory. A folder is moved only when the
    legacy folder exists and the MineSim folder does not. Returns the target
    directories that were moved.
    """
    if data_root is None:
        from platformdirs import user_data_dir

        data_root = Path(user_data_dir())
    if config_root is None:
        from platformdirs import user_config_dir

        config_root = Path(user_config_dir())
    moved: list[Path] = []
    _migrate_tree(Path(data_root), moved)
    _migrate_tree(Path(config_root), moved, settings=True)
    return moved
