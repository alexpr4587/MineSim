"""Audio backends: a recording null backend and a QtMultimedia backend."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

__all__ = [
    "AudioBackend",
    "AudioCall",
    "NullBackend",
    "QtBackend",
    "audio_output_available",
    "select_backend",
]

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AudioCall:
    """One call recorded by :class:`NullBackend`."""

    kind: str
    sound_id: str = ""
    volume: float = 1.0
    pan: float = 0.0
    fade_ms: int = 0
    pitch_steps: int = 0
    pitch: float = 1.0


class AudioBackend(ABC):
    """The playback interface used by :class:`~minesim.audio.manager.AudioManager`."""

    @property
    def available(self) -> bool:
        """Whether this backend can make sound."""
        return False

    @abstractmethod
    def play_sfx(
        self,
        sound_id: str,
        volume: float = 1.0,
        pan: float = 0.0,
        pitch_steps: int = 0,
    ) -> None:
        """Play a one-shot sound effect, optionally shifted by pentatonic steps."""

    @abstractmethod
    def play_music(self, track_id: str, fade_ms: int = 0) -> None:
        """Start a music track, crossfading from the current one."""

    @abstractmethod
    def stop_music(self, fade_ms: int = 0) -> None:
        """Stop the music, optionally fading out."""

    @abstractmethod
    def play_ambience(self, loop_id: str, volume: float = 1.0, fade_ms: int = 0) -> None:
        """Start a looping ambience track."""

    @abstractmethod
    def set_volumes(self, master: float, music: float, sfx: float) -> None:
        """Set the global volume levels."""


class NullBackend(AudioBackend):
    """A silent backend that records every call (used by tests and CI)."""

    def __init__(self) -> None:
        self.calls: list[AudioCall] = []
        self.volumes: tuple[float, float, float] = (1.0, 1.0, 1.0)

    @property
    def available(self) -> bool:
        return True

    @property
    def sfx_calls(self) -> list[AudioCall]:
        """Only the sound effect calls."""
        return [call for call in self.calls if call.kind == "sfx"]

    @property
    def music_calls(self) -> list[AudioCall]:
        """Only the music calls."""
        return [call for call in self.calls if call.kind == "music"]

    def play_sfx(
        self,
        sound_id: str,
        volume: float = 1.0,
        pan: float = 0.0,
        pitch_steps: int = 0,
    ) -> None:
        steps = max(0, min(7, int(pitch_steps)))
        semitones = (0, 2, 4, 7, 9, 12, 14, 16)[steps]
        pitch = 2.0 ** (semitones / 12.0)
        self.calls.append(
            AudioCall(
                "sfx",
                sound_id,
                float(volume),
                float(pan),
                pitch_steps=steps,
                pitch=pitch,
            )
        )

    def play_music(self, track_id: str, fade_ms: int = 0) -> None:
        self.calls.append(AudioCall("music", track_id, fade_ms=int(fade_ms)))

    def stop_music(self, fade_ms: int = 0) -> None:
        self.calls.append(AudioCall("stop_music", fade_ms=int(fade_ms)))

    def play_ambience(self, loop_id: str, volume: float = 1.0, fade_ms: int = 0) -> None:
        self.calls.append(AudioCall("ambience", loop_id, float(volume), fade_ms=int(fade_ms)))

    def set_volumes(self, master: float, music: float, sfx: float) -> None:
        self.volumes = (float(master), float(music), float(sfx))
        self.calls.append(AudioCall("volumes", volume=float(master)))


class QtBackend(AudioBackend):
    """QtMultimedia playback with an overlapping SFX pool and music crossfades."""

    POOL_SIZE = 6

    def __init__(self, cache: Any = None, parent: Any = None) -> None:
        from PySide6.QtCore import QPropertyAnimation, QUrl
        from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect

        self._cache = cache
        self._parent = parent
        self._QUrl = QUrl
        self._QSoundEffect = QSoundEffect
        self._QMediaPlayer = QMediaPlayer
        self._QAudioOutput = QAudioOutput
        self._QPropertyAnimation = QPropertyAnimation
        self._sfx_pool: dict[str, list[Any]] = {}
        self._sfx_index: dict[str, int] = {}
        self._variant_index: dict[str, int] = {}
        self._animations: list[Any] = []
        self._master = 1.0
        self._music = 1.0
        self._sfx = 1.0
        self._ambience_volume = 1.0
        self._music_track: str | None = None
        self._music_index = 0
        self._music_players = [self._make_player(), self._make_player()]
        self._ambience_player = self._make_player()

    @property
    def available(self) -> bool:
        return True

    def _make_player(self) -> tuple[Any, Any]:
        player = self._QMediaPlayer(self._parent)
        output = self._QAudioOutput(self._parent)
        player.setAudioOutput(output)
        output.setVolume(0.0)
        return player, output

    def _music_level(self) -> float:
        return max(0.0, min(1.0, self._master * self._music))

    def _fade(
        self,
        output: Any,
        start: float,
        end: float,
        duration_ms: int,
        finished: Any = None,
    ) -> Any:
        if duration_ms <= 0:
            output.setVolume(float(end))
            if finished is not None:
                finished()
            return None
        animation = self._QPropertyAnimation(output, b"volume")
        animation.setDuration(int(duration_ms))
        animation.setStartValue(float(start))
        animation.setEndValue(float(end))
        if finished is not None:
            animation.finished.connect(finished)
        animation.start()
        self._animations.append(animation)
        return animation

    def play_sfx(
        self,
        sound_id: str,
        volume: float = 1.0,
        pan: float = 0.0,
        pitch_steps: int = 0,
    ) -> None:
        if self._cache is None:
            return
        variant_count = max(1, int(self._cache.sfx_variant_count(sound_id)))
        variant = self._variant_index.get(sound_id, 0) % variant_count
        self._variant_index[sound_id] = variant + 1
        steps = max(0, min(7, int(pitch_steps)))
        path = None
        pitched = getattr(self._cache, "pitched_sfx_path", None)
        if steps and callable(pitched):
            try:
                candidate = pitched(sound_id, variant, steps)
                if candidate.is_file():
                    path = candidate
            except Exception:
                path = None
        if path is None:
            path = self._cache.sfx_path(sound_id, variant)
        if not path.is_file():
            return
        pool = self._sfx_pool.setdefault(sound_id, [])
        if len(pool) < self.POOL_SIZE:
            effect = self._QSoundEffect()
            pool.append(effect)
        index = self._sfx_index.get(sound_id, 0) % len(pool)
        self._sfx_index[sound_id] = index + 1
        effect = pool[index]
        effect.setSource(self._QUrl.fromLocalFile(str(path)))
        effect.setVolume(max(0.0, min(1.0, float(volume))))
        effect.play()

    def play_music(self, track_id: str, fade_ms: int = 0) -> None:
        if self._cache is None:
            return
        path = self._cache.music_path(track_id)
        if not path.is_file():
            return
        if self._music_track == track_id:
            return
        current = self._music_index
        next_index = 1 - current
        player, output = self._music_players[next_index]
        player.stop()
        player.setSource(self._QUrl.fromLocalFile(str(path)))
        player.setLoops(self._QMediaPlayer.Loops.Infinite)
        output.setVolume(0.0)
        player.play()
        old_player, old_output = self._music_players[current]
        old_volume = float(old_output.volume())
        self._fade(output, 0.0, self._music_level(), fade_ms)
        self._fade(old_output, old_volume, 0.0, fade_ms, old_player.stop)
        self._music_index = next_index
        self._music_track = track_id

    def stop_music(self, fade_ms: int = 0) -> None:
        player, output = self._music_players[self._music_index]
        self._fade(output, float(output.volume()), 0.0, fade_ms, player.stop)
        self._music_track = None

    def play_ambience(self, loop_id: str, volume: float = 1.0, fade_ms: int = 0) -> None:
        if self._cache is None:
            return
        path = self._cache.ambience_path(loop_id)
        if not path.is_file():
            path = self._cache.music_path(loop_id)
        if not path.is_file():
            return
        player, output = self._ambience_player
        player.stop()
        player.setSource(self._QUrl.fromLocalFile(str(path)))
        player.setLoops(self._QMediaPlayer.Loops.Infinite)
        output.setVolume(0.0)
        player.play()
        self._ambience_volume = max(0.0, min(1.0, float(volume)))
        self._fade(output, 0.0, self._master * self._ambience_volume, fade_ms)

    def set_volumes(self, master: float, music: float, sfx: float) -> None:
        self._master = max(0.0, min(1.0, float(master)))
        self._music = max(0.0, min(1.0, float(music)))
        self._sfx = max(0.0, min(1.0, float(sfx)))
        level = self._music_level()
        for _player, output in self._music_players:
            output.setVolume(level)
        self._ambience_player[1].setVolume(self._master * self._ambience_volume)


def audio_output_available() -> bool:
    """Return True when Qt reports at least one audio output device."""
    try:
        from PySide6.QtMultimedia import QMediaDevices

        return bool(QMediaDevices.audioOutputs())
    except Exception:
        return False


def select_backend(
    cache: Any = None,
    *,
    environ: Any = None,
    platform: str | None = None,
    has_device: Any = None,
    backend_factory: Any = None,
) -> AudioBackend:
    """Choose the Qt backend when it can work, else the silent backend.

    ``MINESIM_AUDIO=off`` forces silence. An offscreen Qt platform also
    forces silence unless ``MINESIM_AUDIO=on``. Without an audio output
    device the null backend is always used.
    """
    environment = os.environ if environ is None else environ
    mode = str(environment.get("MINESIM_AUDIO", "")).strip().lower()
    if mode in {"off", "0", "false", "no", "disabled"}:
        return NullBackend()
    current_platform = os.environ.get("QT_QPA_PLATFORM", "") if platform is None else str(platform)
    forced = mode in {"on", "1", "true", "yes"}
    if current_platform.strip().lower() == "offscreen" and not forced:
        return NullBackend()
    device_check = has_device or audio_output_available
    try:
        device_available = bool(device_check())
    except Exception:
        device_available = False
    if not device_available:
        return NullBackend()
    factory = backend_factory or QtBackend
    try:
        return factory(cache)
    except Exception:
        logger.warning("Could not start the Qt audio backend", exc_info=True)
        return NullBackend()
