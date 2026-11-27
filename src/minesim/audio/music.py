"""Generative, seamless background music loops."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

from minesim.audio import synth
from minesim.audio.content import read_content_json
from minesim.core.schemas import AudioMood, ContentError

__all__ = ["load_music_moods", "loop_length", "render_loop"]

_SAMPLE_RATE = synth.SAMPLE_RATE
_BEATS_PER_BAR = 4


def _midi_to_frequency(note: int) -> float:
    return 440.0 * (2.0 ** ((float(note) - 69.0) / 12.0))


def _scale_note(mood: AudioMood, degree: int, octave: int = 0) -> int:
    size = len(mood.scale)
    octave_shift, index = divmod(int(degree), size)
    return int(mood.root_note) + int(mood.scale[index]) + 12 * (octave_shift + octave)


def _bar_samples(mood: AudioMood) -> int:
    beat = 60.0 / float(mood.bpm)
    return max(1, int(round(beat * _BEATS_PER_BAR * _SAMPLE_RATE)))


def loop_length(mood: AudioMood, bars: int = 8) -> int:
    """Return the exact number of frames in a rendered loop."""
    return _bar_samples(mood) * max(1, int(bars))


def _add(target: np.ndarray, source: np.ndarray, offset: int) -> None:
    if offset >= target.shape[0]:
        return
    end = min(target.shape[0], offset + source.shape[0])
    target[offset:end] += source[: end - offset]


def _melody_note(frequency: float, duration: float, brightness: float) -> np.ndarray:
    time = np.arange(max(1, int(round(duration * _SAMPLE_RATE))), dtype=np.float32)
    time /= np.float32(_SAMPLE_RATE)
    body = synth.triangle(frequency, duration) + 0.2 * synth.sine(frequency * 2.0, duration)
    decay = np.exp(-time * (3.0 + float(brightness) * 2.0)).astype(np.float32)
    envelope = synth.adsr(duration, attack=0.004, decay=0.2, sustain=0.35, release=0.3)
    cutoff = 1500.0 + float(brightness) * 3500.0
    return synth.one_pole_lowpass(body * decay * envelope, cutoff)


def _render_pad(mood: AudioMood, bars: int, bar_samples: int, total: int) -> np.ndarray:
    pad = np.zeros((total, 2), dtype=np.float32)
    bar_duration = bar_samples / _SAMPLE_RATE
    for bar_index in range(bars + 1):
        chord = mood.chords[bar_index % len(mood.chords)]
        start = bar_index * bar_samples
        for note_index, degree in enumerate(chord):
            frequency = _midi_to_frequency(_scale_note(mood, degree))
            duration = bar_duration * 1.1
            note = np.zeros(max(1, int(round(duration * _SAMPLE_RATE))), dtype=np.float32)
            for detune in (0.997, 1.003):
                note += synth.triangle(frequency * detune, duration) * 0.5
            envelope = synth.adsr(
                duration,
                attack=bar_duration * 0.35,
                decay=bar_duration * 0.2,
                sustain=0.8,
                release=bar_duration * 0.5,
            )
            pan_value = -0.3 if note_index % 2 == 0 else 0.3
            _add(pad, synth.pan(note * envelope, pan_value), start)
    return pad


def _render_melody(
    mood: AudioMood,
    bars: int,
    bar_samples: int,
    beat_samples: int,
    total: int,
    generator: np.random.Generator,
) -> np.ndarray:
    melody = np.zeros((total, 2), dtype=np.float32)
    degree = 0
    maximum_degree = max(1, len(mood.scale) * 2 - 1)
    for bar_index in range(bars + 1):
        for beat_index in range(_BEATS_PER_BAR):
            if generator.random() >= float(mood.melody_density):
                continue
            degree += int(generator.integers(-2, 3))
            degree = max(0, min(maximum_degree, degree))
            note = _scale_note(mood, degree, octave=1)
            frequency = _midi_to_frequency(note)
            duration = min(1.4, beat_samples / _SAMPLE_RATE * 1.8)
            jitter = float(generator.uniform(-0.12, 0.12))
            offset = int(round((bar_index * _BEATS_PER_BAR + beat_index + jitter) * beat_samples))
            if offset < 0:
                offset = 0
            buffer = _melody_note(frequency, duration, mood.brightness)
            pan_value = float(generator.uniform(-0.25, 0.25))
            _add(melody, synth.pan(buffer, pan_value), offset)
    return synth.echo(
        melody,
        delay=beat_samples / _SAMPLE_RATE * 0.75,
        feedback=0.22,
        mix=0.2,
    )


def _render_bass(
    mood: AudioMood,
    bars: int,
    bar_samples: int,
    total: int,
    generator: np.random.Generator,
) -> np.ndarray:
    bass = np.zeros((total, 2), dtype=np.float32)
    bar_duration = bar_samples / _SAMPLE_RATE
    probability = min(0.95, 0.4 + float(mood.bass) * 0.5)
    for bar_index in range(bars + 1):
        if generator.random() > probability:
            continue
        chord = mood.chords[bar_index % len(mood.chords)]
        frequency = _midi_to_frequency(_scale_note(mood, chord[0], octave=-2))
        duration = bar_duration * 0.85
        note = synth.sine(frequency, duration) * 0.7 + synth.sine(frequency * 2.0, duration) * 0.15
        envelope = synth.adsr(duration, attack=0.05, decay=0.15, sustain=0.6, release=0.3)
        offset = bar_index * bar_samples
        if generator.random() < 0.35:
            offset += bar_samples // 2
        _add(bass, synth.pan(note * envelope, 0.0), offset)
    return bass


def render_loop(mood: AudioMood, seed: int = 0, bars: int = 8) -> np.ndarray:
    """Render a seamless stereo loop for ``mood``.

    One extra bar is rendered, its tail is folded onto the beginning,
    and the seam is smoothed so the first and last samples match.
    """
    bars = max(1, int(bars))
    bar_samples = _bar_samples(mood)
    loop_samples = bar_samples * bars
    total = loop_samples + bar_samples
    generator = np.random.default_rng(int(seed) & ((1 << 63) - 1))

    pad = _render_pad(mood, bars, bar_samples, total)
    melody = _render_melody(
        mood, bars, bar_samples, bar_samples // _BEATS_PER_BAR, total, generator
    )
    bass = _render_bass(mood, bars, bar_samples, total, generator)

    mixed = pad * float(mood.pad_gain) + melody + bass * float(mood.bass)
    mixed = synth.warm(mixed)

    attack_count = max(2, int(round(synth.MIN_ATTACK_SECONDS * _SAMPLE_RATE)))
    ramp = np.linspace(0.0, 1.0, attack_count, dtype=np.float32)[:, None]
    mixed[:attack_count] *= ramp

    loop = mixed[:loop_samples].copy()
    tail = mixed[loop_samples : loop_samples + bar_samples]
    loop[: tail.shape[0]] += tail
    loop = synth.normalize(loop)

    seam = min(loop.shape[0] // 4, max(2, int(round(0.003 * _SAMPLE_RATE))))
    if seam > 0:
        ramp = np.linspace(0.0, 1.0, seam, dtype=np.float32)[:, None]
        loop[-seam:] = loop[-seam:] * (1.0 - ramp) + loop[0] * ramp
    return loop.astype(np.float32)


def load_music_moods(content_dir: str | Path | None = None) -> dict[str, AudioMood]:
    """Load and validate ``audio_music.json``."""
    data: Any = read_content_json("audio_music.json", content_dir)
    if isinstance(data, dict):
        data = data.get("moods", data)
    if not isinstance(data, list):
        raise ContentError("audio_music.json: $: expected a list of moods")
    moods: dict[str, AudioMood] = {}
    for index, item in enumerate(data):
        identifier = item.get("id") if isinstance(item, dict) else None
        label = f" (id '{identifier}')" if identifier else ""
        try:
            mood = AudioMood.model_validate(item)
        except ValidationError as exc:
            errors = exc.errors(include_url=False)
            first = errors[0] if errors else {}
            location = ".".join(str(part) for part in first.get("loc", ()))
            path = f"$.{index}" + (f".{location}" if location else "")
            message = str(first.get("msg", "invalid value"))
            raise ContentError(f"audio_music.json: {path}{label}: {message}") from None
        if mood.id in moods:
            raise ContentError(f"audio_music.json: $.{index}.id: duplicate mood id '{mood.id}'")
        moods[mood.id] = mood
    return moods
