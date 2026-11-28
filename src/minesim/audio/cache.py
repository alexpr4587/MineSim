"""Render the synthesized audio into a versioned on-disk cache."""

from __future__ import annotations

import hashlib
import logging
import wave
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import QObject, QThread, Signal, Slot

from minesim import __version__
from minesim.audio import synth
from minesim.audio.content import read_content_json, read_content_text
from minesim.audio.music import load_music_moods, render_loop
from minesim.audio.recipes import estimated_duration, load_sfx_recipes, render_sfx
from minesim.core.schemas import (
    AudioMood,
    AudioProtections,
    AudioSfxRecipe,
    ContentError,
)

__all__ = ["AudioCache", "AudioWarmThread"]

logger = logging.getLogger(__name__)

CACHE_VERSION = 1


def _default_cache_dir() -> Path:
    try:
        from platformdirs import user_cache_dir

        return Path(user_cache_dir("MineSim"))
    except Exception:
        return Path.home() / ".cache" / "MineSim"


def _default_data_dir() -> Path:
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir("MineSim"))
    except Exception:
        return Path.home() / ".local" / "share" / "MineSim"


class AudioCache:
    """Versioned WAV cache plus user overrides for sounds and music."""

    def __init__(
        self,
        content_dir: str | Path | None = None,
        cache_dir: str | Path | None = None,
        data_dir: str | Path | None = None,
    ) -> None:
        self.content_dir = content_dir
        self.cache_dir = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
        self.data_dir = Path(data_dir) if data_dir is not None else _default_data_dir()
        self._key: str | None = None
        self._recipes: dict[str, AudioSfxRecipe] | None = None
        self._moods: dict[str, AudioMood] | None = None
        self._protections: AudioProtections | None = None

    def _fingerprint(self) -> str:
        parts = [f"cache={CACHE_VERSION}", f"version={__version__}"]
        for filename in (
            "audio_sfx.json",
            "audio_music.json",
            "audio_events.json",
            "audio.json",
        ):
            try:
                parts.append(read_content_text(filename, self.content_dir))
            except ContentError:
                parts.append(f"<missing:{filename}>")
        joined = "\n".join(parts).encode("utf-8")
        return hashlib.sha256(joined).hexdigest()[:16]

    @property
    def key(self) -> str:
        """The content/version hash used in the cache folder name."""
        if self._key is None:
            self._key = self._fingerprint()
        return self._key

    @property
    def root(self) -> Path:
        """The cache folder for the current content and code version."""
        return self.cache_dir / "audio" / self.key

    @property
    def sfx_dir(self) -> Path:
        """Where rendered sound effects are stored."""
        return self.root / "sfx"

    @property
    def music_dir(self) -> Path:
        """Where rendered music loops are stored."""
        return self.root / "music"

    @property
    def override_dir(self) -> Path:
        """Where the user's audio overrides live."""
        return self.data_dir / "audio" / "override"

    def recipes(self) -> dict[str, AudioSfxRecipe]:
        """Return the validated sound recipes."""
        if self._recipes is None:
            self._recipes = load_sfx_recipes(self.content_dir)
        return self._recipes

    def moods(self) -> dict[str, AudioMood]:
        """Return the validated music moods."""
        if self._moods is None:
            self._moods = load_music_moods(self.content_dir)
        return self._moods

    def protections(self) -> AudioProtections:
        """Return the validated voice/interval limits."""
        if self._protections is None:
            data: Any = read_content_json("audio.json", self.content_dir)
            try:
                self._protections = AudioProtections.model_validate(data)
            except ValidationError as exc:
                errors = exc.errors(include_url=False)
                first = errors[0] if errors else {}
                location = ".".join(str(part) for part in first.get("loc", ()))
                path = "$" + (f".{location}" if location else "")
                message = str(first.get("msg", "invalid value"))
                raise ContentError(f"audio.json: {path}: {message}") from None
        return self._protections

    def sfx_variant_count(self, sound_id: str) -> int:
        """Return the number of variants for ``sound_id``."""
        recipe = self.recipes().get(sound_id)
        return int(recipe.variants) if recipe is not None else 1

    def sfx_path(self, sound_id: str, variant: int = 0) -> Path:
        """Return the WAV path for a sound, honouring user overrides."""
        override = self.override_dir / f"{sound_id}.wav"
        if override.is_file():
            return override
        return self.sfx_dir / f"{sound_id}_{int(variant)}.wav"

    def pitched_sfx_path(self, sound_id: str, variant: int, pitch_steps: int) -> Path:
        """Return the WAV path for a pitched combo variant."""
        return self.sfx_dir / f"{sound_id}_p{int(pitch_steps)}_{int(variant)}.wav"

    def music_path(self, mood_id: str) -> Path:
        """Return the path for a music mood, honouring user overrides."""
        override_dir = self.override_dir / "music"
        for suffix in (".wav", ".ogg", ".mp3"):
            candidate = override_dir / f"{mood_id}{suffix}"
            if candidate.is_file():
                return candidate
        return self.music_dir / f"{mood_id}.wav"

    def ambience_path(self, loop_id: str) -> Path:
        """Return the path for an ambience loop, honouring user overrides."""
        override_dir = self.override_dir / "ambience"
        for suffix in (".wav", ".ogg", ".mp3"):
            candidate = override_dir / f"{loop_id}{suffix}"
            if candidate.is_file():
                return candidate
        return self.music_dir / f"{loop_id}.wav"

    def sfx_duration(self, sound_id: str) -> float:
        """Return the duration of a rendered sound in seconds."""
        path = self.sfx_path(sound_id, 0)
        if path.is_file():
            try:
                with wave.open(str(path), "rb") as handle:
                    frames = handle.getnframes()
                    rate = handle.getframerate() or synth.SAMPLE_RATE
                    return float(frames) / float(rate)
            except (OSError, wave.Error):
                pass
        recipe = self.recipes().get(sound_id)
        if recipe is not None:
            return estimated_duration(recipe)
        return 0.5

    def is_ready(self) -> bool:
        """Return True when every synthesized file is already on disk."""
        try:
            recipes = self.recipes()
            moods = self.moods()
        except ContentError:
            return False
        for sound_id, recipe in recipes.items():
            if (self.override_dir / f"{sound_id}.wav").is_file():
                continue
            for variant in range(recipe.variants):
                if not (self.sfx_dir / f"{sound_id}_{variant}.wav").is_file():
                    return False
            for step in range(recipe.pitch_variants):
                for variant in range(recipe.variants):
                    if not self.pitched_sfx_path(sound_id, variant, step).is_file():
                        return False
        for mood_id in moods:
            if not self.music_path(mood_id).is_file():
                return False
        return True

    def render_sfx(self, sound_id: str, seed: int = 0) -> list[Path]:
        """Render every variant of one sound effect."""
        recipe = self.recipes().get(sound_id)
        if recipe is None:
            raise ContentError(f"audio_sfx.json: $.id: unknown sound id '{sound_id}'")
        paths: list[Path] = []
        for variant in range(recipe.variants):
            buffer = render_sfx(recipe, variant, seed)
            path = self.sfx_dir / f"{sound_id}_{variant}.wav"
            paths.append(synth.write_wav(path, buffer))
        return paths

    def render_pitched_sfx(self, sound_id: str, pitch_steps: int, seed: int = 0) -> list[Path]:
        """Render every variant of one sound at a pentatonic combo pitch."""
        recipe = self.recipes().get(sound_id)
        if recipe is None:
            raise ContentError(f"audio_sfx.json: $.id: unknown sound id '{sound_id}'")
        steps = max(0, min(7, int(pitch_steps)))
        paths: list[Path] = []
        for variant in range(recipe.variants):
            buffer = render_sfx(recipe, variant, seed, pitch_steps=steps)
            path = self.pitched_sfx_path(sound_id, variant, steps)
            paths.append(synth.write_wav(path, buffer))
        return paths

    def render_music(self, mood_id: str, seed: int = 0, bars: int = 8) -> Path:
        """Render one music mood loop."""
        mood = self.moods().get(mood_id)
        if mood is None:
            raise ContentError(f"audio_music.json: $.id: unknown mood id '{mood_id}'")
        loop = render_loop(mood, seed=seed, bars=bars)
        path = self.music_dir / f"{mood_id}.wav"
        return synth.write_wav(path, loop)

    def render_all(self, seed: int = 0, bars: int = 8) -> None:
        """Render every sound variant, combo pitch and music loop."""
        for sound_id, recipe in self.recipes().items():
            self.render_sfx(sound_id, seed)
            for step in range(recipe.pitch_variants):
                self.render_pitched_sfx(sound_id, step, seed)
        for mood_id in self.moods():
            self.render_music(mood_id, seed, bars)

    def warm_async(self, callback: Any = None, bars: int = 8) -> AudioWarmThread | None:
        """Render the cache in a background thread and call ``callback`` when ready."""
        if self.is_ready():
            if callback is not None:
                callback()
            return None
        thread = AudioWarmThread(self, bars)
        if callback is not None:
            relay = _WarmRelay(callback)
            thread.relay = relay
            thread.ready.connect(relay.invoke)
        thread.failed.connect(
            lambda message: logger.warning("Audio cache rendering failed: %s", message)
        )
        thread.start()
        return thread


class _WarmRelay(QObject):
    """Run the ready callback in the main thread that created the thread."""

    def __init__(self, callback: Any) -> None:
        super().__init__()
        self._callback = callback

    @Slot()
    def invoke(self) -> None:
        try:
            self._callback()
        except Exception:
            logger.exception("Audio ready callback failed")


class AudioWarmThread(QThread):
    """Background cache renderer used at startup."""

    ready = Signal()
    failed = Signal(str)

    def __init__(self, cache: AudioCache, bars: int = 8, parent: Any = None) -> None:
        super().__init__(parent)
        self._cache = cache
        self._bars = bars
        self.relay: Any = None

    def run(self) -> None:
        try:
            self._cache.render_all(bars=self._bars)
        except Exception as exc:
            logger.exception("Could not render the audio cache")
            self.failed.emit(str(exc))
            return
        self.ready.emit()
