"""Load sound effect recipes and render their variants."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import ValidationError

from minesim.audio import synth
from minesim.audio.content import read_content_json
from minesim.core.schemas import AudioSfxRecipe, ContentError

__all__ = [
    "build_sfx_buffers",
    "estimated_duration",
    "load_sfx_recipes",
    "render_sfx",
]

_SAMPLE_RATE = synth.SAMPLE_RATE

_DEFAULT_FREQUENCY = {
    "thunk": 150.0,
    "pluck": 440.0,
    "bell": 660.0,
    "chime": 660.0,
    "coin": 1046.0,
    "click": 1300.0,
    "whoosh": 400.0,
    "pad": 220.0,
    "drip": 900.0,
    "hum": 60.0,
    "crackle": 1200.0,
    "notes": 440.0,
    "cascade": 1046.0,
    "sparkle": 1200.0,
    "tsk": 320.0,
    "pop": 700.0,
    "elevator": 260.0,
    "rise": 110.0,
    "bonk": 140.0,
}

_DEFAULT_DURATION = {
    "thunk": 0.24,
    "pluck": 0.7,
    "bell": 1.6,
    "chime": 1.2,
    "coin": 0.35,
    "click": 0.06,
    "whoosh": 0.6,
    "pad": 2.0,
    "drip": 0.4,
    "hum": 1.6,
    "crackle": 1.0,
    "notes": 0.5,
    "cascade": 0.5,
    "sparkle": 0.5,
    "tsk": 0.09,
    "pop": 0.12,
    "elevator": 0.8,
    "rise": 1.0,
    "bonk": 0.25,
}


def _stable_seed(*parts: object) -> int:
    text = ":".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(text, digest_size=8).digest(), "big")


def _count(duration: float) -> int:
    return max(1, int(round(float(duration) * _SAMPLE_RATE)))


def _time(duration: float) -> np.ndarray:
    return np.arange(_count(duration), dtype=np.float32) / np.float32(_SAMPLE_RATE)


def _noise_seed(rng: np.random.Generator) -> int:
    return int(rng.integers(0, 2**31 - 1))


def _thunk(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["thunk"]))
    base = float(params.get("freq", _DEFAULT_FREQUENCY["thunk"]))
    time = _time(duration)
    start = base * 2.2
    end = base * 0.8
    frequency = end + (start - end) * np.exp(-time / 0.035).astype(np.float32)
    phase = 2.0 * np.pi * np.cumsum(frequency) / _SAMPLE_RATE
    tone = np.sin(phase).astype(np.float32)
    noise = synth.one_pole_lowpass(synth.seeded_noise(duration, _noise_seed(rng)), 900.0)
    envelope = synth.adsr(duration, attack=0.004, decay=0.06, sustain=0.25, release=0.14)
    return synth.one_pole_lowpass((tone * 0.85 + noise * 0.45) * envelope, 1800.0)


def _pluck(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["pluck"]))
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["pluck"]))
    time = _time(duration)
    body = synth.triangle(frequency, duration) + 0.25 * synth.sine(frequency * 2.0, duration)
    decay = np.exp(-time * float(params.get("decay", 6.0))).astype(np.float32)
    envelope = synth.adsr(duration, attack=0.005, decay=0.15, sustain=0.5, release=0.25)
    return synth.one_pole_lowpass(body * envelope * decay, 3200.0)


def _bell_note(frequency: float, duration: float) -> np.ndarray:
    time = _time(duration)
    output = np.zeros_like(time)
    for ratio, amplitude, decay in (
        (1.0, 1.0, 1.8),
        (2.01, 0.6, 2.6),
        (2.76, 0.42, 3.2),
        (4.07, 0.25, 4.0),
        (5.43, 0.16, 5.0),
    ):
        partial = frequency * ratio
        if partial >= synth.MAX_FREQUENCY:
            continue
        envelope = np.exp(-time * decay).astype(np.float32)
        output += amplitude * synth.sine(partial, duration) * envelope
    return synth.fade(output, fade_in=0.003)


def _bell(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["bell"]))
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["bell"]))
    return _bell_note(frequency, duration)


def _chime(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["chime"]))
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["chime"]))
    count = max(2, min(6, int(params.get("notes", 4))))
    note_duration = max(0.2, duration * 0.65)
    spacing = max(0.02, duration / (count * 2.0))
    buffers: list[np.ndarray] = []
    offsets: list[int] = []
    for index in range(count):
        ratio = 1.0 + index * 0.25
        timing = index * spacing + float(rng.uniform(-0.02, 0.02))
        buffers.append(_bell_note(frequency * ratio, note_duration))
        offsets.append(max(0, int(round(timing * _SAMPLE_RATE))))
    return synth.echo(synth.mix(buffers, offsets), delay=0.16, feedback=0.2, mix=0.18)


def _coin(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["coin"]))
    scale = max(0.25, duration / _DEFAULT_DURATION["coin"])
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["coin"]))
    first_duration = 0.12 * scale
    first_time = _time(first_duration)
    first = synth.sine(frequency, first_duration) * np.exp(-first_time / 0.035).astype(np.float32)
    second_duration = 0.14 * scale
    second_time = _time(second_duration)
    second = synth.sine(frequency * 1.5, second_duration) * np.exp(-second_time / 0.045).astype(
        np.float32
    )
    sparkle_duration = 0.09 * scale
    sparkle_time = _time(sparkle_duration)
    sparkle = (
        0.2
        * synth.sine(frequency * 2.5, sparkle_duration)
        * np.exp(-sparkle_time / 0.02).astype(np.float32)
    )
    mixed = synth.mix(
        [first, second, sparkle],
        [
            0,
            int(round(0.045 * scale * _SAMPLE_RATE)),
            int(round(0.08 * scale * _SAMPLE_RATE)),
        ],
    )
    return synth.one_pole_lowpass(mixed, 5000.0)


def _click(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["click"]))
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["click"]))
    time = _time(duration)
    noise = synth.one_pole_lowpass(synth.seeded_noise(duration, _noise_seed(rng)), 2500.0)
    tone = synth.sine(frequency, duration)
    envelope = np.exp(-time / 0.012).astype(np.float32)
    return synth.one_pole_lowpass((noise * 0.6 + tone * 0.5) * envelope, 4000.0)


def _whoosh(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["whoosh"]))
    time = _time(duration)
    noise = synth.seeded_noise(duration, _noise_seed(rng))
    sweep = 400.0 + 3600.0 * np.sin(np.pi * time / duration)
    filtered = synth.variable_lowpass(noise, sweep)
    envelope = synth.adsr(duration, attack=0.08, decay=0.08, sustain=0.7, release=0.25)
    return synth.one_pole_lowpass(
        (filtered + 0.12 * synth.sine(180.0, duration)) * envelope, 5000.0
    )


def _pad(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["pad"]))
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["pad"]))
    output = np.zeros(_count(duration), dtype=np.float32)
    for ratio, detune in ((1.0, 0.997), (1.5, 1.0), (2.0, 1.003)):
        output += synth.triangle(frequency * ratio * detune, duration) / ratio
    envelope = synth.adsr(duration, attack=0.5, decay=0.2, sustain=0.8, release=0.7)
    return synth.one_pole_lowpass(output * envelope, 1800.0)


def _drip(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["drip"]))
    base = float(params.get("freq", _DEFAULT_FREQUENCY["drip"]))
    time = _time(duration)
    start = base * 1.4
    end = base * 0.35
    frequency = end + (start - end) * np.exp(-time / 0.05).astype(np.float32)
    phase = 2.0 * np.pi * np.cumsum(frequency) / _SAMPLE_RATE
    envelope = synth.adsr(duration, attack=0.002, decay=0.05, sustain=0.2, release=0.18)
    tone = np.sin(phase).astype(np.float32) * envelope
    return synth.one_pole_lowpass(synth.echo(tone, delay=0.12, feedback=0.25, mix=0.2), 4000.0)


def _hum(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["hum"]))
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["hum"]))
    time = _time(duration)
    tremolo = 1.0 + 0.08 * np.sin(2.0 * np.pi * 5.0 * time)
    body = (
        synth.sine(frequency, duration) * 0.6
        + synth.sine(frequency * 2.0, duration) * 0.25
        + synth.sine(frequency * 3.0, duration) * 0.12
    )
    envelope = synth.adsr(duration, attack=0.3, decay=0.1, sustain=1.0, release=0.3)
    return synth.one_pole_lowpass(body * tremolo * envelope, 700.0)


def _crackle(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", _DEFAULT_DURATION["crackle"]))
    base = synth.one_pole_lowpass(synth.seeded_noise(duration, _noise_seed(rng)) * 0.06, 1500.0)
    buffers: list[np.ndarray] = [base]
    offsets: list[int] = [0]
    for _ in range(12):
        start = float(rng.uniform(0.03, 0.9))
        burst_duration = 0.018
        burst = synth.one_pole_lowpass(synth.seeded_noise(burst_duration, _noise_seed(rng)), 3000.0)
        burst_time = _time(burst_duration)
        burst = burst * np.exp(-burst_time / 0.004).astype(np.float32)
        buffers.append(burst * float(rng.uniform(0.15, 0.5)))
        offsets.append(int(round(start * _SAMPLE_RATE)))
    envelope = synth.adsr(duration, attack=0.05, decay=0.1, sustain=0.8, release=0.2)
    mixed = synth.mix(buffers, offsets) * envelope
    low_note = float(params.get("freq", 0.0))
    if low_note > 0.0:
        mixed = mixed + synth.sine(low_note, duration) * envelope * 0.18
    return synth.one_pole_lowpass(mixed, 3500.0)


def _gentle_note(frequency: float, duration: float) -> np.ndarray:
    """Return a soft plucked triangle note used by the note sequences."""
    time = _time(duration)
    body = synth.triangle(frequency, duration) + 0.18 * synth.sine(frequency * 2.0, duration)
    envelope = synth.adsr(duration, attack=0.006, decay=0.12, sustain=0.35, release=0.3)
    decay = np.exp(-time * 4.5).astype(np.float32)
    return synth.one_pole_lowpass(body * envelope * decay, 3200.0)


def _notes(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 0.5))
    base = float(params.get("freq", 440.0))
    count = max(2, min(6, int(params.get("notes", 2))))
    ratios = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
    frequencies = [
        float(params.get(f"freq{index + 1}", base * ratios[index])) for index in range(count)
    ]
    spacing = float(params.get("spacing", duration / (count + 1.0)))
    note_duration = max(0.08, duration * 0.7)
    buffers: list[np.ndarray] = []
    offsets: list[int] = []
    for index, frequency in enumerate(frequencies):
        jitter = float(rng.uniform(-0.01, 0.01))
        buffers.append(_gentle_note(frequency, note_duration))
        offsets.append(max(0, int(round((index * spacing + jitter) * _SAMPLE_RATE))))
    return synth.echo(synth.mix(buffers, offsets), delay=0.14, feedback=0.18, mix=0.16)


def _cascade(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 0.5))
    frequency = float(params.get("freq", _DEFAULT_FREQUENCY["coin"]))
    count = max(2, min(12, int(params.get("count", 4))))
    spacing = max(0.02, duration / (count + 1.0))
    buffers: list[np.ndarray] = []
    offsets: list[int] = []
    for index in range(count):
        note_duration = max(0.06, spacing * 1.8)
        time = _time(note_duration)
        ping = synth.sine(frequency * (1.0 + index * 0.08), note_duration) * np.exp(
            -time / 0.035
        ).astype(np.float32)
        buffers.append(ping * (0.9 - index * 0.04))
        offsets.append(max(0, int(round(index * spacing * _SAMPLE_RATE))))
    return synth.echo(synth.mix(buffers, offsets), delay=0.09, feedback=0.22, mix=0.2)


def _sparkle(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 0.5))
    frequency = float(params.get("freq", 1200.0))
    buffers: list[np.ndarray] = []
    offsets: list[int] = []
    for index in range(5):
        note_duration = 0.08 + float(rng.uniform(0.0, 0.04))
        time = _time(note_duration)
        note_frequency = frequency * (1.0 + index * 0.16) * float(rng.uniform(0.98, 1.02))
        note = synth.sine(note_frequency, note_duration) * np.exp(-time / 0.025).astype(np.float32)
        buffers.append(note * float(rng.uniform(0.2, 0.45)))
        offsets.append(max(0, int(round(float(rng.uniform(0.0, duration * 0.7)) * _SAMPLE_RATE))))
    return synth.echo(synth.mix(buffers, offsets), delay=0.11, feedback=0.2, mix=0.24)


def _tsk(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 0.09))
    frequency = float(params.get("freq", 320.0))
    time = _time(duration)
    noise = synth.one_pole_lowpass(synth.seeded_noise(duration, _noise_seed(rng)), 1600.0)
    envelope = np.exp(-time / 0.018).astype(np.float32)
    body = synth.sine(frequency, duration) * 0.35
    return synth.one_pole_lowpass((noise * 0.8 + body) * envelope, 2200.0)


def _pop(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 0.12))
    base = float(params.get("freq", 700.0))
    time = _time(duration)
    start = base * 1.45
    end = base * 0.85
    frequency = end + (start - end) * np.exp(-time / 0.02).astype(np.float32)
    phase = 2.0 * np.pi * np.cumsum(frequency) / _SAMPLE_RATE
    envelope = synth.adsr(duration, attack=0.003, decay=0.03, sustain=0.2, release=0.08)
    return synth.one_pole_lowpass(np.sin(phase).astype(np.float32) * envelope, 3000.0)


def _elevator(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 0.8))
    whoosh = _whoosh({"duration": duration * 0.8, "freq": 260.0}, rng)
    thunk = _thunk({"duration": 0.24, "freq": 110.0}, rng)
    return synth.mix(
        [whoosh, thunk],
        [0, max(0, int(round(duration * 0.55 * _SAMPLE_RATE)))],
    )


def _rise(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 1.0))
    base = float(params.get("freq", 110.0))
    time = _time(duration)
    frequency = base * (1.0 + time / max(0.01, duration))
    phase = 2.0 * np.pi * np.cumsum(frequency) / _SAMPLE_RATE
    tremolo = 1.0 + 0.06 * np.sin(2.0 * np.pi * 6.0 * time)
    body = np.sin(phase).astype(np.float32) * 0.6 + synth.sine(base * 2.0, duration) * 0.2
    envelope = synth.adsr(duration, attack=0.2, decay=0.1, sustain=0.9, release=0.3)
    return synth.one_pole_lowpass(body * tremolo * envelope, 900.0)


def _bonk(params: dict[str, float], rng: np.random.Generator) -> np.ndarray:
    duration = float(params.get("duration", 0.25))
    base = float(params.get("freq", 140.0))
    time = _time(duration)
    frequency = base * (0.7 + 0.5 * np.exp(-time / 0.03).astype(np.float32))
    phase = 2.0 * np.pi * np.cumsum(frequency) / _SAMPLE_RATE
    envelope = synth.adsr(duration, attack=0.005, decay=0.05, sustain=0.3, release=0.15)
    return synth.one_pole_lowpass(np.sin(phase).astype(np.float32) * envelope, 700.0)


_RENDERERS = {
    "thunk": _thunk,
    "pluck": _pluck,
    "bell": _bell,
    "chime": _chime,
    "coin": _coin,
    "click": _click,
    "whoosh": _whoosh,
    "pad": _pad,
    "drip": _drip,
    "hum": _hum,
    "crackle": _crackle,
    "notes": _notes,
    "cascade": _cascade,
    "sparkle": _sparkle,
    "tsk": _tsk,
    "pop": _pop,
    "elevator": _elevator,
    "rise": _rise,
    "bonk": _bonk,
}


def estimated_duration(recipe: AudioSfxRecipe) -> float:
    """Return a conservative duration for voice bookkeeping."""
    return float(recipe.params.get("duration", _DEFAULT_DURATION.get(recipe.kind, 0.5)))


PENTATONIC_SEMITONES: tuple[int, ...] = (0, 2, 4, 7, 9, 12, 14, 16)


def pitch_ratio(pitch_steps: int) -> float:
    """Return the frequency ratio for a pentatonic step (0 to +7)."""
    step = max(0, min(len(PENTATONIC_SEMITONES) - 1, int(pitch_steps)))
    return float(2.0 ** (PENTATONIC_SEMITONES[step] / 12.0))


def render_sfx(
    recipe: AudioSfxRecipe,
    variant: int = 0,
    seed: int = 0,
    pitch_steps: int = 0,
) -> np.ndarray:
    """Render one deterministic stereo variant of ``recipe``.

    ``pitch_steps`` shifts the base frequency by a pentatonic step; it is
    used for the mining combo pop.
    """
    generator = np.random.default_rng(_stable_seed(recipe.id, int(variant), int(seed)))
    jitter = 1.0 + (float(generator.random()) * 2.0 - 1.0) * float(recipe.pitch_jitter)
    pitch = jitter * pitch_ratio(pitch_steps)
    params = dict(recipe.params)
    params["freq"] = float(params.get("freq", _DEFAULT_FREQUENCY[recipe.kind])) * pitch
    renderer = _RENDERERS[recipe.kind]
    mono = renderer(params, generator)
    stereo = synth.pan(mono, float(generator.uniform(-0.08, 0.08)))
    return synth.finalize(stereo, recipe.gain)


def build_sfx_buffers(
    recipes: dict[str, AudioSfxRecipe],
    seed: int = 0,
) -> dict[str, list[np.ndarray]]:
    """Render every variant of every recipe."""
    return {
        sound_id: [render_sfx(recipe, variant, seed) for variant in range(recipe.variants)]
        for sound_id, recipe in recipes.items()
    }


def load_sfx_recipes(content_dir: str | Path | None = None) -> dict[str, AudioSfxRecipe]:
    """Load and validate ``audio_sfx.json``.

    Errors always name the file and, when possible, the recipe id.
    """
    data: Any = read_content_json("audio_sfx.json", content_dir)
    if isinstance(data, dict):
        data = data.get("sfx", data)
    if not isinstance(data, list):
        raise ContentError("audio_sfx.json: $: expected a list of sound recipes")
    recipes: dict[str, AudioSfxRecipe] = {}
    for index, item in enumerate(data):
        identifier = item.get("id") if isinstance(item, dict) else None
        label = f" (id '{identifier}')" if identifier else ""
        try:
            recipe = AudioSfxRecipe.model_validate(item)
        except ValidationError as exc:
            errors = exc.errors(include_url=False)
            first = errors[0] if errors else {}
            location = ".".join(str(part) for part in first.get("loc", ()))
            path = f"$.{index}" + (f".{location}" if location else "")
            message = str(first.get("msg", "invalid value"))
            raise ContentError(f"audio_sfx.json: {path}{label}: {message}") from None
        if recipe.id in recipes:
            raise ContentError(f"audio_sfx.json: $.{index}.id: duplicate sound id '{recipe.id}'")
        recipes[recipe.id] = recipe
    return recipes
