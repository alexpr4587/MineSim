"""The audio manager: volume math, voice limits, ducking and music moods."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from minesim.audio.backend import AudioBackend
from minesim.audio.settings import AudioSettings
from minesim.core.schemas import AudioProtections

__all__ = ["AudioManager"]


class AudioManager:
    """Turn gameplay events into polite, rate-limited audio calls."""

    def __init__(
        self,
        settings: AudioSettings,
        backend: AudioBackend,
        cache: Any,
        protections: AudioProtections | None = None,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.settings = settings
        self.backend = backend
        self.cache = cache
        if protections is None:
            loader = getattr(cache, "protections", None)
            if callable(loader):
                try:
                    protections = loader()
                except Exception:
                    protections = None
        self.protections = protections or AudioProtections()
        self._clock = clock or time.monotonic
        self._voices: list[float] = []
        self._last_played: dict[str, float] = {}
        self._duck_until = 0.0
        self._duck_amount = 0.0
        self._mood: str | None = None
        self._apply_volumes()

    @property
    def available(self) -> bool:
        """Whether the current backend can make sound."""
        return bool(self.backend.available)

    @property
    def mood(self) -> str | None:
        """The currently requested music mood."""
        return self._mood

    @property
    def voice_count(self) -> int:
        """The number of voices still considered active."""
        self._prune_voices(self._clock())
        return len(self._voices)

    def _duck_factor(self) -> float:
        if self._clock() >= self._duck_until:
            return 1.0
        return max(0.0, 1.0 - float(self._duck_amount))

    def _master_level(self) -> float:
        return 0.0 if self.settings.muted else float(self.settings.master)

    def _music_level(self) -> float:
        if not self.settings.music_enabled:
            return 0.0
        return float(self.settings.music) * self._duck_factor()

    def _sfx_level(self) -> float:
        if not self.settings.sfx_enabled:
            return 0.0
        return float(self.settings.sfx) * self._duck_factor()

    def _apply_volumes(self) -> None:
        self.backend.set_volumes(
            self._master_level(),
            self._music_level(),
            self._sfx_level(),
        )

    def _prune_voices(self, now: float) -> None:
        self._voices = [end for end in self._voices if end > now]

    def _voice_duration(self, sound_id: str) -> float:
        reader = getattr(self.cache, "sfx_duration", None)
        if callable(reader):
            try:
                return max(0.01, float(reader(sound_id)))
            except Exception:
                return 0.5
        return 0.5

    def play(self, sound_id: str, volume: float = 1.0, pan: float = 0.0) -> bool:
        """Play a sound effect if it passes the interval and voice limits."""
        if not self.settings.sfx_enabled or self.settings.muted:
            return False
        now = self._clock()
        interval = float(self.protections.min_interval_ms.get(sound_id, 0)) / 1000.0
        last = self._last_played.get(sound_id)
        if last is not None and now - last < interval:
            return False
        self._prune_voices(now)
        if len(self._voices) >= int(self.protections.max_voices):
            return False
        gain = self._master_level() * self._sfx_level() * float(volume)
        if gain <= 0.0:
            return False
        self.backend.play_sfx(
            sound_id,
            max(0.0, min(1.0, gain)),
            max(-1.0, min(1.0, float(pan))),
        )
        self._last_played[sound_id] = now
        self._voices.append(now + self._voice_duration(sound_id))
        return True

    def set_mood(self, mood: str, fade_ms: int = 1000) -> bool:
        """Request a music mood with a crossfade."""
        self._mood = mood
        if not self.settings.music_enabled or self.settings.muted:
            self.backend.stop_music(fade_ms)
            return False
        self.backend.play_music(mood, fade_ms)
        return True

    def stop_music(self, fade_ms: int = 500) -> None:
        """Stop the background music."""
        self._mood = None
        self.backend.stop_music(fade_ms)

    def duck(self, amount: float, ms: int) -> None:
        """Temporarily lower all audio by ``amount`` for ``ms`` milliseconds."""
        amount = max(0.0, min(1.0, float(amount)))
        milliseconds = max(0, int(ms))
        if amount <= 0.0 or milliseconds <= 0:
            self._duck_amount = 0.0
            self._duck_until = 0.0
        else:
            self._duck_amount = amount
            self._duck_until = self._clock() + milliseconds / 1000.0
        self._apply_volumes()

    def set_volumes(
        self,
        master: float | None = None,
        music: float | None = None,
        sfx: float | None = None,
    ) -> None:
        """Update one or more volume levels and apply them immediately."""
        if master is not None:
            self.settings.master = max(0.0, min(1.0, float(master)))
        if music is not None:
            self.settings.music = max(0.0, min(1.0, float(music)))
        if sfx is not None:
            self.settings.sfx = max(0.0, min(1.0, float(sfx)))
        self._apply_volumes()

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute all audio."""
        self.settings.muted = bool(muted)
        self._apply_volumes()

    def set_music_enabled(self, enabled: bool) -> None:
        """Enable or disable background music."""
        self.settings.music_enabled = bool(enabled)
        self._apply_volumes()
        if not enabled:
            self.backend.stop_music(500)

    def set_sfx_enabled(self, enabled: bool) -> None:
        """Enable or disable sound effects."""
        self.settings.sfx_enabled = bool(enabled)
        self._apply_volumes()
