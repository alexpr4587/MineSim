"""Persistent audio settings backed by :class:`QSettings`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["AudioSettings", "SETTINGS_PREFIX"]

SETTINGS_PREFIX = "audio"


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _to_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return bool(default)


@dataclass(slots=True)
class AudioSettings:
    """User audio preferences with sane, quiet defaults."""

    master: float = 0.8
    music: float = 0.25
    sfx: float = 0.6
    music_enabled: bool = True
    sfx_enabled: bool = True
    muted: bool = False

    def clamped(self) -> AudioSettings:
        """Return a copy with all volumes clamped to ``[0, 1]``."""
        return AudioSettings(
            master=max(0.0, min(1.0, float(self.master))),
            music=max(0.0, min(1.0, float(self.music))),
            sfx=max(0.0, min(1.0, float(self.sfx))),
            music_enabled=bool(self.music_enabled),
            sfx_enabled=bool(self.sfx_enabled),
            muted=bool(self.muted),
        )

    @classmethod
    def load(cls, settings: Any = None) -> AudioSettings:
        """Load settings from ``settings`` (a QSettings) or the app defaults."""
        if settings is None:
            from PySide6.QtCore import QSettings

            settings = QSettings("MineSim", "MineSim")
        prefix = SETTINGS_PREFIX
        return cls(
            master=_to_float(settings.value(f"{prefix}/master", 0.8), 0.8),
            music=_to_float(settings.value(f"{prefix}/music", 0.25), 0.25),
            sfx=_to_float(settings.value(f"{prefix}/sfx", 0.6), 0.6),
            music_enabled=_to_bool(settings.value(f"{prefix}/music_enabled", True), True),
            sfx_enabled=_to_bool(settings.value(f"{prefix}/sfx_enabled", True), True),
            muted=_to_bool(settings.value(f"{prefix}/muted", False), False),
        ).clamped()

    def save(self, settings: Any = None) -> None:
        """Persist the settings to ``settings`` (a QSettings) or the app defaults."""
        if settings is None:
            from PySide6.QtCore import QSettings

            settings = QSettings("MineSim", "MineSim")
        values = self.clamped()
        prefix = SETTINGS_PREFIX
        settings.setValue(f"{prefix}/master", values.master)
        settings.setValue(f"{prefix}/music", values.music)
        settings.setValue(f"{prefix}/sfx", values.sfx)
        settings.setValue(f"{prefix}/music_enabled", values.music_enabled)
        settings.setValue(f"{prefix}/sfx_enabled", values.sfx_enabled)
        settings.setValue(f"{prefix}/muted", values.muted)
        sync = getattr(settings, "sync", None)
        if callable(sync):
            sync()
