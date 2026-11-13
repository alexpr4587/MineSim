"""Save games: atomic writes, loading and version migration."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "CURRENT_VERSION",
    "DEFAULT_SAVE_PATH",
    "DEFAULT_SKIN",
    "MIGRATIONS",
    "SaveError",
    "SaveGame",
    "default_save_path",
    "load",
    "load_game",
    "migrate",
    "save",
    "save_game",
]

logger = logging.getLogger(__name__)

CURRENT_VERSION = 5
SAVE_VERSION = CURRENT_VERSION
DEFAULT_SKIN = "rusty_bot"


class SaveError(Exception):
    """Raised when a save file is corrupted, invalid or too new."""


def default_save_path() -> Path:
    """Return the default save file path (platformdirs user data dir)."""
    try:
        from platformdirs import user_data_dir

        base = Path(user_data_dir("MineSim"))
    except Exception:
        base = Path.home() / ".local" / "share" / "MineSim"
    return base / "saves" / "slot1.json"


DEFAULT_SAVE_PATH = default_save_path()


def _identity(data: dict[str, Any]) -> dict[str, Any]:
    return dict(data)


def _migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Add the selected skin introduced in save version 2."""
    migrated = dict(data)
    migrated.setdefault("selected_skin", DEFAULT_SKIN)
    migrated["version"] = 2
    return migrated


def _migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    """Bump to save version 3.

    Version 3 adds progression counters and the unlocked skin/example
    sets. Missing counters default to 0 and missing unlock sets are
    rebuilt from content, so the payload only needs the version bump.
    """
    migrated = dict(data)
    migrated["version"] = 3
    return migrated


def _migrate_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
    """Split the single version-3 miner into player stats and drone 0."""
    migrated = dict(data)
    miner = migrated.pop("miner", {}) or {}
    if not isinstance(miner, dict):
        miner = {}
    if "player_stats" not in migrated:
        migrated["player_stats"] = {
            "money": int(miner.get("money", 0)),
            "capacity": int(miner.get("capacity", 10)),
            "tool_power": int(miner.get("tool_power", 1)),
            "tool_tier": int(miner.get("tool_tier", 0)),
            "move_ticks": int(miner.get("move_ticks", 4)),
            "scan_radius": int(miner.get("scan_radius", 0)),
            "stats": dict(miner.get("stats", {}) or {}),
            "upgrades": dict(miner.get("upgrades", {}) or {}),
            "estimates": dict(miner.get("estimates", {}) or {}),
        }
    if "fleet" not in migrated:
        migrated["fleet"] = [
            {
                "id": 0,
                "x": int(miner.get("x", 0)),
                "y": int(miner.get("y", 0)),
                "facing": miner.get("facing", "north"),
                "inventory": dict(miner.get("inventory", {}) or {}),
            }
        ]
    migrated["version"] = 4
    return migrated


def _migrate_v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """Add the base warehouse and market state introduced in version 5."""
    migrated = dict(data)
    migrated.setdefault("warehouse", {})
    migrated.setdefault("market", {})
    migrated["version"] = 5
    return migrated


MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
    3: _migrate_v3_to_v4,
    4: _migrate_v4_to_v5,
}


def migrate(data: Any) -> dict[str, Any]:
    """Migrate save ``data`` (a dict) up to the current version.

    Raises :class:`SaveError` for corrupted data or a save from a
    newer version than this build understands.
    """
    if not isinstance(data, dict):
        raise SaveError("save data must be a JSON object")
    version = data.get("version")
    if version is None:
        raise SaveError("save data is missing 'version'")
    try:
        version_int = int(version)
    except (TypeError, ValueError):
        raise SaveError(f"save data has invalid 'version': {version!r}") from None
    if version_int > CURRENT_VERSION:
        raise SaveError(
            f"save version {version_int} is newer than the supported version {CURRENT_VERSION}"
        )
    current = dict(data)
    while version_int < CURRENT_VERSION:
        migrator = MIGRATIONS.get(version_int)
        if migrator is None:
            raise SaveError(f"no migration available from save version {version_int}")
        migrated = migrator(current)
        if not isinstance(migrated, dict):
            raise SaveError("migration did not return a save object")
        current = dict(migrated)
        next_version = current.get("version", version_int + 1)
        try:
            version_int = int(next_version)
        except (TypeError, ValueError):
            raise SaveError(f"migration produced invalid 'version': {next_version!r}") from None
    return current


class SaveGame(BaseModel):
    """A serialised game state (save file schema, version 5)."""

    model_config = ConfigDict(extra="ignore")

    version: int = Field(default=CURRENT_VERSION)
    seed: int
    tick: int = 0
    selected_skin: str = DEFAULT_SKIN
    fleet: list[dict[str, Any]] = Field(default_factory=list)
    player_stats: dict[str, Any] = Field(default_factory=dict)
    world_delta: dict[str, Any] = Field(default_factory=dict)
    progression: dict[str, Any] = Field(default_factory=dict)
    warehouse: dict[str, Any] = Field(default_factory=dict)
    market: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def migrate(cls, data: Any) -> dict[str, Any]:
        """Alias for :func:`migrate` (migration hook keyed by version)."""
        return migrate(data)

    @classmethod
    def from_dict(cls, data: Any) -> SaveGame:
        """Build a SaveGame from a raw dict, migrating if needed."""
        migrated = migrate(data)
        try:
            return cls.model_validate(migrated)
        except ValidationError as exc:
            raise SaveError(f"invalid save data: {exc}") from None

    def to_dict(self) -> dict[str, Any]:
        """Return the save as a JSON-serialisable dict."""
        return self.model_dump()

    def save(self, path: str | Path | None = None) -> Path:
        """Write this save atomically to ``path`` (default save path)."""
        target = Path(path) if path is not None else default_save_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.model_dump(), indent=2, sort_keys=True)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(target.parent),
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                tmp_path = Path(handle.name)
                handle.write(payload)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(tmp_path, target)
            tmp_path = None
        except OSError as exc:
            raise SaveError(f"could not write save to {target}: {exc}") from exc
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink(missing_ok=True)
                except OSError:
                    pass
        return target

    @classmethod
    def load(cls, path: str | Path | None = None) -> SaveGame:
        """Load a save from ``path`` (default save path).

        Raises :class:`SaveError` for a missing, corrupted, invalid or
        newer-version save; never raises anything else for bad data.
        """
        target = Path(path) if path is not None else default_save_path()
        try:
            text = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise SaveError(f"save file not found: {target}") from None
        except OSError as exc:
            raise SaveError(f"could not read save file {target}: {exc}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SaveError(f"corrupted save file {target}: invalid JSON: {exc}") from None
        except ValueError as exc:
            raise SaveError(f"corrupted save file {target}: {exc}") from None
        return cls.from_dict(data)


def save_game(savegame: Any, path: str | Path | None = None) -> Path:
    """Save ``savegame`` (a SaveGame, dict or object with ``save``) to ``path``."""
    if isinstance(savegame, SaveGame):
        return savegame.save(path)
    if isinstance(savegame, dict):
        return SaveGame.from_dict(savegame).save(path)
    save_method = getattr(savegame, "save", None)
    if callable(save_method) and path is not None:
        return Path(save_method(path))
    if callable(save_method):
        return Path(save_method())
    if hasattr(savegame, "model_dump"):
        return SaveGame(**savegame.model_dump()).save(path)
    raise SaveError(f"cannot save object of type {type(savegame).__name__}")


def load_game(path: str | Path | None = None) -> SaveGame:
    """Load a :class:`SaveGame` from ``path`` (default save path)."""
    return SaveGame.load(path)


def save(data_or_path: Any, path: str | Path | None = None) -> Path:
    """Save a SaveGame/dict to ``path`` (module-level convenience)."""
    if path is None and isinstance(data_or_path, (str, Path)):
        raise SaveError("save() requires a SaveGame or dict to save")
    return save_game(data_or_path, path)


def load(path: str | Path | None = None) -> SaveGame:
    """Load a :class:`SaveGame` (module-level convenience)."""
    return SaveGame.load(path)
