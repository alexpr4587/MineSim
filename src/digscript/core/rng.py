"""Seeded pure random helpers.

All randomness in core/ flows through this module. Everything here is
pure integer arithmetic (splitmix64 style), so results are identical
on every OS and Python version -- no ``random``, ``hash()`` or
wall-clock time is ever used.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

__all__ = ["MASK64", "mix64", "unit", "weighted_choice"]

MASK64 = (1 << 64) - 1

_GOLDEN = 0x9E3779B97F4A7C15
_MIX_MULTIPLIER_1 = 0xBF58476D1CE4E5B9
_MIX_MULTIPLIER_2 = 0x94D049BB133111EB
_TWO_POW_53 = 9007199254740992.0


def _splitmix64(value: int) -> int:
    """One splitmix64 mixing step, masked to 64 bits."""
    z = (value + _GOLDEN) & MASK64
    z = ((z ^ (z >> 30)) * _MIX_MULTIPLIER_1) & MASK64
    z = ((z ^ (z >> 27)) * _MIX_MULTIPLIER_2) & MASK64
    return z ^ (z >> 31)


def mix64(*ints: int) -> int:
    """Mix integers into a 64-bit hash (splitmix64 style).

    The result is always in ``[0, 2**64)`` and is a pure function of
    the inputs: negative inputs are masked to 64 bits first, so the
    result does not depend on the platform or Python version.
    """
    state = 0
    for value in ints:
        state = _splitmix64(state ^ (value & MASK64))
    return state


def unit(h: int) -> float:
    """Map a 64-bit hash ``h`` to a float in ``[0, 1)``.

    Uses the top 53 bits so the result is always strictly below 1.0.
    """
    return ((h & MASK64) >> 11) * (1.0 / _TWO_POW_53)


def weighted_choice[T](h: int, items: Mapping[T, float] | Iterable[tuple[T, float]]) -> T:
    """Pick a key from ``items`` weighted by its value, using hash ``h``.

    ``items`` may be a mapping of key -> weight or an iterable of
    ``(key, weight)`` pairs. Iteration order is preserved, which keeps
    the choice deterministic for a given ``h`` and input order.
    """
    if isinstance(items, Mapping):
        pairs: list[tuple[T, float]] = list(items.items())  # type: ignore[assignment]
    else:
        pairs = []
        for index, item in enumerate(items):
            if isinstance(item, (tuple, list)):
                pairs.append(item)  # type: ignore[arg-type]
            elif isinstance(item, (int, float)):
                pairs.append((index, float(item)))  # type: ignore[arg-type]
            elif hasattr(item, "weight"):
                key = getattr(item, "id", item)
                pairs.append((key, float(item.weight)))  # type: ignore[attr-defined]
            else:
                raise TypeError(f"unsupported weighted_choice item: {item!r}")
    if not pairs:
        raise ValueError("weighted_choice requires at least one item")
    total = 0.0
    for _, weight in pairs:
        if weight < 0:
            raise ValueError("weights must be >= 0")
        total += weight
    if total <= 0:
        raise ValueError("weights must have a positive total")
    threshold = unit(h) * total
    cumulative = 0.0
    last_positive: T | None = None
    for key, weight in pairs:
        if weight > 0:
            last_positive = key
        cumulative += weight
        if threshold < cumulative:
            return key
    # Rounding at the very top of the range: fall back to the last
    # key with a positive weight.
    assert last_positive is not None
    return last_positive
