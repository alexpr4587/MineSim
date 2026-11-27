"""Deterministic numpy synthesis primitives used by the audio engine.

Everything is rendered at :data:`SAMPLE_RATE` as ``float32`` and kept
soft and warm: a final band limit removes energy above roughly 6 kHz
and every sound gets an attack of at least 2 ms.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

__all__ = [
    "MAX_FREQUENCY",
    "MIN_ATTACK_SECONDS",
    "PEAK_DBFS",
    "SAMPLE_RATE",
    "adsr",
    "echo",
    "enforce_attack",
    "fade",
    "finalize",
    "mix",
    "normalize",
    "one_pole_highpass",
    "one_pole_lowpass",
    "pan",
    "reverb",
    "seeded_noise",
    "sine",
    "soft_saw",
    "to_int16",
    "triangle",
    "variable_lowpass",
    "warm",
    "write_wav",
]

SAMPLE_RATE = 44100
MAX_FREQUENCY = 6000.0
MIN_ATTACK_SECONDS = 0.002
PEAK_DBFS = -8.0
_TWO_PI = 2.0 * math.pi


def _sample_count(duration: float, sample_rate: int = SAMPLE_RATE) -> int:
    return max(1, int(round(float(duration) * float(sample_rate))))


def _time_axis(duration: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    count = _sample_count(duration, sample_rate)
    return np.arange(count, dtype=np.float32) / np.float32(sample_rate)


def sine(
    frequency: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    phase: float = 0.0,
) -> np.ndarray:
    """Return a sine wave as ``float32``."""
    time = _time_axis(duration, sample_rate)
    return np.sin(_TWO_PI * float(frequency) * time + float(phase)).astype(np.float32)


def triangle(
    frequency: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
    phase: float = 0.0,
) -> np.ndarray:
    """Return a triangle wave as ``float32``."""
    time = _time_axis(duration, sample_rate)
    angle = _TWO_PI * float(frequency) * time + float(phase)
    return (2.0 / math.pi * np.arcsin(np.sin(angle))).astype(np.float32)


def soft_saw(
    frequency: float,
    duration: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Return a band-limited, soft sawtooth built from low harmonics."""
    frequency = max(1.0, float(frequency))
    time = _time_axis(duration, sample_rate)
    harmonics = max(1, min(12, int(MAX_FREQUENCY // frequency)))
    output = np.zeros_like(time)
    for harmonic in range(1, harmonics + 1):
        output += np.sin(_TWO_PI * harmonic * frequency * time) / harmonic
    return np.clip(output * (2.0 / math.pi), -1.0, 1.0).astype(np.float32)


def adsr(
    duration: float,
    attack: float = 0.01,
    decay: float = 0.1,
    sustain: float = 0.7,
    release: float = 0.2,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Return an ADSR envelope of ``duration`` seconds as ``float32``.

    The attack is never shorter than :data:`MIN_ATTACK_SECONDS`.
    """
    count = _sample_count(duration, sample_rate)
    attack = max(MIN_ATTACK_SECONDS, float(attack))
    sustain = max(0.0, min(1.0, float(sustain)))
    attack_count = min(count, int(round(attack * sample_rate)))
    release_count = min(
        count - attack_count,
        int(round(max(0.0, release) * sample_rate)),
    )
    remaining = count - attack_count - release_count
    decay_count = min(remaining, int(round(max(0.0, decay) * sample_rate)))
    sustain_count = remaining - decay_count
    parts: list[np.ndarray] = []
    if attack_count:
        parts.append(np.linspace(0.0, 1.0, attack_count, endpoint=False))
    if decay_count:
        parts.append(np.linspace(1.0, sustain, decay_count, endpoint=False))
    if sustain_count:
        parts.append(np.full(sustain_count, sustain))
    if release_count:
        parts.append(np.linspace(sustain, 0.0, release_count))
    if not parts:
        return np.zeros(count, dtype=np.float32)
    envelope = np.concatenate(parts).astype(np.float32)
    if envelope.size < count:
        envelope = np.pad(envelope, (0, count - envelope.size))
    return envelope[:count].astype(np.float32)


def _filter_channels(
    data: np.ndarray,
    cutoff: float,
    sample_rate: int,
    highpass: bool,
) -> np.ndarray:
    if data.ndim == 2:
        channels = [
            _filter_channels(data[:, index], cutoff, sample_rate, highpass)
            for index in range(data.shape[1])
        ]
        return np.stack(channels, axis=1).astype(np.float32)
    count = data.shape[0]
    if count == 0:
        return data.astype(np.float32)
    cutoff = max(1.0, min(float(cutoff), float(sample_rate) * 0.49))
    alpha = 1.0 - math.exp(-_TWO_PI * cutoff / float(sample_rate))
    frequencies = np.fft.rfftfreq(count, d=1.0 / float(sample_rate))
    omega = _TWO_PI * frequencies / float(sample_rate)
    response = alpha / (1.0 - (1.0 - alpha) * np.exp(-1j * omega))
    if highpass:
        response = 1.0 - response
    spectrum = np.fft.rfft(data.astype(np.float64))
    filtered = np.fft.irfft(spectrum * response, count)
    return filtered.astype(np.float32)


def one_pole_lowpass(
    samples: np.ndarray,
    cutoff: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Apply a one-pole low-pass filter."""
    return _filter_channels(np.asarray(samples, dtype=np.float32), cutoff, sample_rate, False)


def one_pole_highpass(
    samples: np.ndarray,
    cutoff: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Apply a one-pole high-pass filter."""
    return _filter_channels(np.asarray(samples, dtype=np.float32), cutoff, sample_rate, True)


def variable_lowpass(
    samples: np.ndarray,
    cutoff: np.ndarray | float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Apply a one-pole low-pass whose cutoff may change per sample."""
    data = np.asarray(samples, dtype=np.float32)
    cutoffs = np.asarray(cutoff, dtype=np.float32)
    if cutoffs.ndim == 0:
        cutoffs = np.full(data.shape[0], float(cutoffs), dtype=np.float32)
    output = np.empty_like(data)
    state = 0.0
    for index in range(data.shape[0]):
        frequency = max(1.0, min(float(cutoffs[index]), float(sample_rate) * 0.49))
        alpha = 1.0 - math.exp(-_TWO_PI * frequency / float(sample_rate))
        state += alpha * (float(data[index]) - state)
        output[index] = state
    return output.astype(np.float32)


def seeded_noise(
    duration: float,
    seed: int,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Return deterministic uniform noise in ``[-1, 1)`` as ``float32``."""
    count = _sample_count(duration, sample_rate)
    generator = np.random.default_rng(int(seed) & ((1 << 63) - 1))
    return generator.uniform(-1.0, 1.0, count).astype(np.float32)


def _comb(
    samples: np.ndarray,
    delay: float,
    feedback: float,
    sample_rate: int,
) -> np.ndarray:
    data = np.asarray(samples, dtype=np.float32)
    count = data.shape[0]
    delay_count = max(1, int(round(float(delay) * sample_rate)))
    wet = data.copy()
    feedback = max(0.0, min(0.95, float(feedback)))
    for start in range(delay_count, count, delay_count):
        end = min(start + delay_count, count)
        wet[start:end] += feedback * wet[start - delay_count : end - delay_count]
    return wet


def echo(
    samples: np.ndarray,
    delay: float = 0.25,
    feedback: float = 0.3,
    mix: float = 0.3,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Add a feedback echo (works on mono or stereo arrays)."""
    data = np.asarray(samples, dtype=np.float32)
    if data.ndim == 2:
        channels = [
            echo(data[:, index], delay, feedback, mix, sample_rate)
            for index in range(data.shape[1])
        ]
        return np.stack(channels, axis=1).astype(np.float32)
    wet = _comb(data, delay, feedback, sample_rate)
    mix = max(0.0, min(1.0, float(mix)))
    return ((1.0 - mix) * data + mix * wet).astype(np.float32)


def reverb(
    samples: np.ndarray,
    mix: float = 0.2,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Apply a light four-comb reverb (works on mono or stereo arrays)."""
    data = np.asarray(samples, dtype=np.float32)
    if data.ndim == 2:
        channels = [reverb(data[:, index], mix, sample_rate) for index in range(data.shape[1])]
        return np.stack(channels, axis=1).astype(np.float32)
    wet = np.zeros_like(data)
    for delay, feedback in (
        (0.0297, 0.35),
        (0.0371, 0.32),
        (0.0411, 0.30),
        (0.0437, 0.28),
    ):
        wet += _comb(data, delay, feedback, sample_rate)
    wet *= 0.25
    mix = max(0.0, min(1.0, float(mix)))
    return ((1.0 - mix) * data + mix * wet).astype(np.float32)


def fade(
    samples: np.ndarray,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Fade a mono or stereo buffer in and out."""
    data = np.asarray(samples, dtype=np.float32)
    output = data.copy()
    count = output.shape[0]
    attack = min(count, max(0, int(round(float(fade_in) * sample_rate))))
    if attack:
        ramp = np.linspace(0.0, 1.0, attack, dtype=np.float32)
        if output.ndim == 2:
            ramp = ramp[:, None]
        output[:attack] *= ramp
    release = min(count, max(0, int(round(float(fade_out) * sample_rate))))
    if release:
        ramp = np.linspace(1.0, 0.0, release, dtype=np.float32)
        if output.ndim == 2:
            ramp = ramp[:, None]
        output[-release:] *= ramp
    return output.astype(np.float32)


def enforce_attack(
    samples: np.ndarray,
    attack: float = MIN_ATTACK_SECONDS,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Make sure a buffer never starts with a hard attack."""
    return fade(samples, fade_in=max(MIN_ATTACK_SECONDS, float(attack)), sample_rate=sample_rate)


def pan(mono: np.ndarray, pan_value: float = 0.0) -> np.ndarray:
    """Return a stereo buffer using equal-power panning."""
    data = np.asarray(mono, dtype=np.float32)
    position = max(-1.0, min(1.0, float(pan_value)))
    angle = (position + 1.0) * math.pi / 4.0
    left = math.cos(angle)
    right = math.sin(angle)
    return np.stack([data * left, data * right], axis=1).astype(np.float32)


def mix(
    buffers: list[np.ndarray],
    offsets: list[int] | None = None,
) -> np.ndarray:
    """Mix mono or stereo buffers at sample offsets."""
    if not buffers:
        return np.zeros(0, dtype=np.float32)
    data = [np.asarray(buffer, dtype=np.float32) for buffer in buffers]
    starts = list(offsets) if offsets is not None else [0] * len(data)
    stereo = any(buffer.ndim == 2 for buffer in data)
    length = max(start + buffer.shape[0] for buffer, start in zip(data, starts, strict=True))
    if stereo:
        output = np.zeros((length, 2), dtype=np.float32)
    else:
        output = np.zeros(length, dtype=np.float32)
    for buffer, start in zip(data, starts, strict=True):
        if stereo and buffer.ndim == 1:
            buffer = pan(buffer)
        output[start : start + buffer.shape[0]] += buffer
    return output.astype(np.float32)


def normalize(samples: np.ndarray, peak_dbfs: float = PEAK_DBFS) -> np.ndarray:
    """Normalize the peak of a buffer to ``peak_dbfs``."""
    data = np.asarray(samples, dtype=np.float32)
    peak = float(np.max(np.abs(data))) if data.size else 0.0
    if peak <= 1e-9:
        return data.copy()
    target = 10.0 ** (float(peak_dbfs) / 20.0)
    return (data * (target / peak)).astype(np.float32)


def warm(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Remove DC and roll off everything above about 6 kHz."""
    data = one_pole_highpass(np.asarray(samples, dtype=np.float32), 30.0, sample_rate)
    data = one_pole_lowpass(data, MAX_FREQUENCY, sample_rate)
    return one_pole_lowpass(data, MAX_FREQUENCY, sample_rate)


def finalize(
    samples: np.ndarray,
    gain: float = 1.0,
    sample_rate: int = SAMPLE_RATE,
    peak_dbfs: float = PEAK_DBFS,
) -> np.ndarray:
    """Band-limit, soften the attack, fade out and normalize a sound."""
    data = warm(samples, sample_rate)
    data = enforce_attack(data, MIN_ATTACK_SECONDS, sample_rate)
    data = fade(data, fade_out=0.005, sample_rate=sample_rate)
    data = normalize(data, peak_dbfs)
    data = data * float(gain)
    return np.clip(data, -1.0, 1.0).astype(np.float32)


def to_int16(samples: np.ndarray) -> np.ndarray:
    """Convert float samples in ``[-1, 1]`` to signed 16-bit PCM."""
    data = np.asarray(samples, dtype=np.float32)
    return (np.clip(data, -1.0, 1.0) * 32767.0).astype(np.int16)


def write_wav(
    path: str | Path,
    samples: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
) -> Path:
    """Write mono or stereo float samples to a 16-bit WAV file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = to_int16(samples)
    if data.ndim == 1:
        channels = 1
    elif data.ndim == 2:
        channels = data.shape[1]
    else:
        raise ValueError("samples must be a mono or stereo array")
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(data.astype("<i2", copy=False).tobytes())
    return target
