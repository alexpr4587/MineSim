"""Tests for the procedural audio engine (prompt 38)."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from minesim.audio import synth
from minesim.audio.backend import NullBackend, select_backend
from minesim.audio.cache import AudioCache
from minesim.audio.manager import AudioManager
from minesim.audio.music import load_music_moods, loop_length, render_loop
from minesim.audio.recipes import load_sfx_recipes, render_sfx
from minesim.audio.settings import AudioSettings
from minesim.core.schemas import AudioProtections, ContentError


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class _FakeCache:
    def sfx_duration(self, sound_id: str) -> float:
        return 1.0


def test_synthesis_is_finite_bounded_and_deterministic() -> None:
    for buffer in (
        synth.sine(440.0, 0.05),
        synth.triangle(220.0, 0.05),
        synth.soft_saw(110.0, 0.05),
    ):
        assert buffer.dtype == np.float32
        assert buffer.shape == (2205,)
        assert np.isfinite(buffer).all()
        assert float(np.max(np.abs(buffer))) <= 1.0
    noise = synth.seeded_noise(0.02, 123)
    again = synth.seeded_noise(0.02, 123)
    assert np.array_equal(noise, again)
    assert not np.array_equal(noise, synth.seeded_noise(0.02, 124))


def test_adsr_has_minimum_attack_and_expected_length() -> None:
    envelope = synth.adsr(0.1, attack=0.0, release=0.2)
    assert envelope.dtype == np.float32
    assert envelope.shape == (4410,)
    assert float(envelope[0]) == 0.0
    assert float(envelope[-1]) == 0.0


def test_filters_and_normalization() -> None:
    high = synth.sine(15000.0, 0.1)
    filtered = synth.one_pole_lowpass(high, 6000.0)
    assert float(np.sqrt(np.mean(filtered**2))) < float(np.sqrt(np.mean(high**2)))
    normalized = synth.normalize(np.full((100, 2), 0.1, dtype=np.float32))
    target = 10.0 ** (-8.0 / 20.0)
    assert float(np.max(np.abs(normalized))) == pytest.approx(target, rel=1e-6)


def test_write_wav_is_stereo_16_bit(tmp_path: Path) -> None:
    path = synth.write_wav(tmp_path / "test.wav", np.zeros((100, 2), dtype=np.float32))
    with wave.open(str(path), "rb") as handle:
        assert handle.getnchannels() == 2
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == synth.SAMPLE_RATE
        assert handle.getnframes() == 100


def test_audio_content_validates() -> None:
    recipes = load_sfx_recipes()
    assert {"ui_click", "mine_stone", "sell_small", "achievement", "step"} <= set(recipes)
    moods = load_music_moods()
    assert set(moods) == {"surface", "galleries", "deep", "abyss"}
    assert moods["surface"].bpm == 72
    assert moods["abyss"].bpm == 48
    cache = AudioCache()
    assert cache.protections().max_voices == 12


def test_recipe_validation_error_names_file_and_id(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "audio_sfx.json").write_text(
        json.dumps([{"id": "bad_sound", "kind": "not_a_kind"}]),
        encoding="utf-8",
    )
    with pytest.raises(ContentError) as info:
        load_sfx_recipes(content)
    message = str(info.value)
    assert "audio_sfx.json" in message
    assert "bad_sound" in message


def test_sfx_rendering_is_deterministic_bounded_and_varied() -> None:
    recipes = load_sfx_recipes()
    recipe = recipes["ui_click"]
    first = render_sfx(recipe, variant=0, seed=7)
    again = render_sfx(recipe, variant=0, seed=7)
    assert np.array_equal(first, again)
    assert first.dtype == np.float32
    assert first.ndim == 2
    assert first.shape[1] == 2
    assert np.isfinite(first).all()
    assert float(np.max(np.abs(first))) <= 1.0
    assert not np.array_equal(first, render_sfx(recipe, variant=1, seed=7))
    for item in recipes.values():
        buffer = render_sfx(item, variant=0, seed=1)
        assert buffer.shape[0] > 0
        assert np.isfinite(buffer).all()
        assert float(np.max(np.abs(buffer))) <= 1.0


def test_music_loop_length_seam_and_determinism() -> None:
    moods = load_music_moods()
    mood = moods["surface"]
    loop = render_loop(mood, seed=3, bars=1)
    assert loop.dtype == np.float32
    assert loop.shape == (loop_length(mood, 1), 2)
    assert np.isfinite(loop).all()
    assert float(np.max(np.abs(loop))) <= 1.0
    assert abs(float(loop[0, 0]) - float(loop[-1, 0])) < 1e-6
    assert abs(float(loop[0, 1]) - float(loop[-1, 1])) < 1e-6
    assert np.array_equal(loop, render_loop(mood, seed=3, bars=1))


def test_cache_key_changes_when_a_recipe_changes(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()

    def write(gain: float) -> None:
        (content / "audio_sfx.json").write_text(
            json.dumps([{"id": "ui_click", "kind": "click", "gain": gain}]),
            encoding="utf-8",
        )

    write(0.5)
    first = AudioCache(
        content_dir=content, cache_dir=tmp_path / "cache", data_dir=tmp_path / "data"
    )
    first_key = first.key
    write(0.8)
    second = AudioCache(
        content_dir=content,
        cache_dir=tmp_path / "cache",
        data_dir=tmp_path / "data",
    )
    assert second.key != first_key


def test_cache_override_paths(tmp_path: Path) -> None:
    data = tmp_path / "data"
    override = data / "audio" / "override"
    override.mkdir(parents=True)
    sound = override / "mine_stone.wav"
    sound.write_bytes(b"RIFF")
    music = override / "music"
    music.mkdir()
    track = music / "surface.ogg"
    track.write_bytes(b"OggS")
    cache = AudioCache(cache_dir=tmp_path / "cache", data_dir=data)
    assert cache.sfx_path("mine_stone", 0) == sound
    assert cache.music_path("surface") == track


def test_manager_applies_volume_math_voice_cap_and_interval() -> None:
    clock = _Clock()
    settings = AudioSettings(master=0.5, music=0.4, sfx=0.5)
    backend = NullBackend()
    protections = AudioProtections(max_voices=2, min_interval_ms={"a": 100})
    manager = AudioManager(
        settings,
        backend,
        _FakeCache(),
        protections,
        clock=clock,
    )
    assert manager.play("a", volume=0.5, pan=0.4)
    call = backend.sfx_calls[-1]
    assert call.volume == pytest.approx(0.125)
    assert call.pan == pytest.approx(0.4)
    assert not manager.play("a")
    assert manager.play("b")
    assert not manager.play("c")
    clock.advance(1.1)
    assert manager.play("c")


def test_manager_ducking_and_music_calls() -> None:
    clock = _Clock()
    settings = AudioSettings(master=1.0, music=1.0, sfx=1.0)
    backend = NullBackend()
    protections = AudioProtections(max_voices=12, min_interval_ms={})
    manager = AudioManager(settings, backend, _FakeCache(), protections, clock=clock)
    manager.duck(0.5, 1000)
    assert backend.volumes == pytest.approx((1.0, 0.5, 0.5))
    assert manager.play("quiet")
    assert backend.sfx_calls[-1].volume == pytest.approx(0.5)
    clock.advance(1.1)
    assert manager.play("loud")
    assert backend.sfx_calls[-1].volume == pytest.approx(1.0)
    assert manager.set_mood("surface", fade_ms=250)
    assert backend.music_calls[-1].sound_id == "surface"
    assert backend.music_calls[-1].fade_ms == 250


def test_audio_settings_persist(tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    settings_file = tmp_path / "audio.ini"
    storage = QSettings(str(settings_file), QSettings.Format.IniFormat)
    storage.clear()
    AudioSettings(
        master=0.42,
        music=0.12,
        sfx=0.34,
        music_enabled=False,
        sfx_enabled=True,
        muted=True,
    ).save(storage)
    loaded = AudioSettings.load(storage)
    assert loaded.master == pytest.approx(0.42)
    assert loaded.music == pytest.approx(0.12)
    assert loaded.sfx == pytest.approx(0.34)
    assert loaded.music_enabled is False
    assert loaded.sfx_enabled is True
    assert loaded.muted is True


def test_backend_selection_rules() -> None:
    class _DummyBackend:
        available = True

    assert isinstance(
        select_backend(environ={"MINESIM_AUDIO": "off"}, platform="xcb", has_device=lambda: True),
        NullBackend,
    )
    assert isinstance(
        select_backend(environ={}, platform="offscreen", has_device=lambda: True),
        NullBackend,
    )
    assert isinstance(
        select_backend(
            environ={"MINESIM_AUDIO": "on"},
            platform="offscreen",
            has_device=lambda: False,
        ),
        NullBackend,
    )
    result = select_backend(
        environ={"MINESIM_AUDIO": "on"},
        platform="offscreen",
        has_device=lambda: True,
        backend_factory=lambda cache: _DummyBackend(),
    )
    assert isinstance(result, _DummyBackend)
