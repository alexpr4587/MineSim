"""Helper library importable by player scripts (pure Python).

The primitive API functions (``move``, ``mine``, ``peek`` and the
others) are injected into this module by the runner before player code
runs. They are declared here so the module is importable and testable
on its own; calling them without the runner raises ``RuntimeError``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

__all__ = [
    "Samples",
    "farm",
    "go_home",
    "goto",
    "goto_nearest",
    "haul",
    "mine_here",
    "mine_until",
    "nearest",
    "ring",
    "spiral",
    "sweep",
]


def move(direction: str) -> None:
    """Move one tile in ``direction`` (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def mine() -> Any:
    """Mine the current tile (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def peek() -> Any:
    """Look at the current tile (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def position() -> tuple[int, int]:
    """Return the miner position (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def scan(radius: int) -> Any:
    """Scan for ore (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def inventory() -> Any:
    """Return the inventory (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def sell() -> int:
    """Sell the inventory (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def goto(x: int, y: int) -> None:
    """Move the miner to ``(x, y)``, one tile at a time.

    Example::

        goto(start_x + 3, start_y)
    """
    while True:
        cx, cy = position()
        if cx == x and cy == y:
            return
        if cx < x:
            move("east")
        elif cx > x:
            move("west")
        elif cy < y:
            move("south")
        else:
            move("north")


def go_home() -> None:
    """Move the miner back to the base at ``(0, 0)``.

    Example::

        go_home()
    """
    goto(0, 0)


def sweep(width: int, height: int) -> Iterator[tuple[int, int]]:
    """Yield positions in serpentine (boustrophedon) order.

    Yields ``(x, y)`` for ``y`` in ``range(height)``; even rows go
    left-to-right (``x`` in ``range(width)``) and odd rows go
    right-to-left, so consecutive positions are always adjacent.

    Example::

        for dx, dy in sweep(3, 2):
            print(dx, dy)
    """
    for y in range(height):
        if y % 2 == 0:
            xs = range(width)
        else:
            xs = range(width - 1, -1, -1)
        for x in xs:
            yield (x, y)


def spiral() -> Iterator[tuple[int, int]]:
    """Yield positions in an infinite square spiral from ``(0, 0)``.

    Starts at ``(0, 0)`` and spirals outwards (east, south, west,
    north, ...) with segment lengths 1, 1, 2, 2, 3, 3, ... so the
    first positions are ``(0, 0)``, ``(1, 0)``, ``(1, 1)``,
    ``(0, 1)``, ``(-1, 1)``, ... The generator never ends.

    Example::

        for dx, dy in spiral():
            print(dx, dy)
    """
    x = 0
    y = 0
    yield (x, y)
    directions = ((1, 0), (0, 1), (-1, 0), (0, -1))
    index = 0
    length = 1
    while True:
        for _ in range(2):
            dx, dy = directions[index % 4]
            index += 1
            for _step in range(length):
                x += dx
                y += dy
                yield (x, y)
        length += 1


def ring(radius: int) -> Iterator[tuple[int, int]]:
    """Yield the offsets on the square ring of Chebyshev radius ``radius``.

    The offsets are relative to the miner's starting point (``(0, 0)``
    when used with :func:`goto`). ``ring(0)`` yields just ``(0, 0)``;
    ``ring(1)`` yields the eight surrounding tiles.

    Example::

        start_x, start_y = position()
        for dx, dy in ring(2):
            goto(start_x + dx, start_y + dy)
    """
    radius = max(0, int(radius))
    if radius == 0:
        yield (0, 0)
        return
    for dx in range(-radius, radius + 1):
        yield (dx, -radius)
    for dy in range(-radius + 1, radius + 1):
        yield (radius, dy)
    for dx in range(radius - 1, -radius - 1, -1):
        yield (dx, radius)
    for dy in range(radius - 1, -radius, -1):
        yield (-radius, dy)


def mine_here() -> Any:
    """Mine the current tile if it holds a known ore.

    Peeks at the current tile first; if :func:`peek` returns an ore
    id (not ``None`` and not ``'unknown'``), calls :func:`mine` and
    returns its result. Otherwise returns ``None`` without mining.

    Example::

        result = mine_here()
    """
    ore = peek()
    if ore is None or ore == "unknown":
        return None
    return mine()


def nearest(ore: str, radius: int | None = None) -> tuple[int, int] | None:
    """Return the nearest ``(dx, dy)`` offset of ``ore`` via :func:`scan`.

    ``radius`` defaults to the whole scan area (the engine caps it to
    the miner's scanner). Ties are broken deterministically by
    Chebyshev distance, then Manhattan distance, then ``(dy, dx)``.
    Returns ``None`` when the ore is not in range.

    Example::

        offset = nearest("coal")
        if offset is not None:
            print("coal at", offset)
    """
    effective = 10**6 if radius is None else max(0, int(radius))
    best: tuple[int, int] | None = None
    best_key: tuple[int, int, int, int] | None = None
    for dx, dy, label in scan(effective):
        if label != ore:
            continue
        key = (max(abs(int(dx)), abs(int(dy))), abs(int(dx)) + abs(int(dy)), int(dy), int(dx))
        if best_key is None or key < best_key:
            best_key = key
            best = (int(dx), int(dy))
    return best


def goto_nearest(ore: str, radius: int | None = None) -> bool:
    """Walk to the nearest tile of ``ore``; return ``True`` when found.

    Example::

        if goto_nearest("stone"):
            mine()
    """
    offset = nearest(ore, radius)
    if offset is None:
        return False
    x, y = position()
    goto(x + offset[0], y + offset[1])
    return True


def mine_until(n: int = 1) -> int:
    """Mine the current tile until ``n`` successes or it is exhausted.

    Returns the number of successful mines. A miss keeps trying; an
    empty, locked, too-hard or full-inventory tile stops the loop.

    Example::

        successes = mine_until(3)
    """
    target = max(0, int(n))
    successes = 0
    while successes < target:
        result = mine()
        if isinstance(result, dict) and result.get("ok"):
            successes += 1
            continue
        reason = result.get("reason") if isinstance(result, dict) else None
        if reason == "miss":
            continue
        break
    return successes


def haul() -> int:
    """Go home, sell the inventory, return to the previous spot, return money.

    Example::

        earned = haul()
    """
    previous = position()
    go_home()
    earned = sell()
    goto(previous[0], previous[1])
    return int(earned or 0)


def farm(ore: str, max_tiles: int = 200) -> int:
    """Sweep outward mining only ``ore`` and hauling when the bag is full.

    Visits at most ``max_tiles`` positions of a square spiral around the
    starting point and returns the number of mined items. The miner
    ends back on the last visited tile.

    Example::

        mined = farm("coal", max_tiles=50)
        print("mined", mined)
    """
    start_x, start_y = position()
    limit = max(0, int(max_tiles))
    mined = 0
    visited = 0
    for dx, dy in spiral():
        if visited >= limit:
            break
        visited += 1
        goto(start_x + dx, start_y + dy)
        while peek() == ore:
            result = mine()
            if isinstance(result, dict) and result.get("ok"):
                mined += 1
                continue
            reason = result.get("reason") if isinstance(result, dict) else None
            if reason == "miss":
                continue
            if reason == "inventory_full":
                haul()
                continue
            break
    return mined


class Samples:
    """A tiny pure-Python tally of mining attempts per ore.

    Example::

        samples = Samples()
        samples.add("stone", True)
        samples.add("stone", False)
        print(samples.rate("stone"))  # 0.5
    """

    def __init__(self) -> None:
        self._attempts: dict[str, int] = {}
        self._successes: dict[str, int] = {}

    def add(self, ore: str, success: bool) -> None:
        """Record one attempt on ``ore`` (``success`` or a miss)."""
        ore = str(ore)
        self._attempts[ore] = self._attempts.get(ore, 0) + 1
        if success:
            self._successes[ore] = self._successes.get(ore, 0) + 1

    def count(self, ore: str) -> int:
        """Return the number of recorded attempts on ``ore``."""
        return int(self._attempts.get(str(ore), 0))

    def rate(self, ore: str) -> float:
        """Return the observed success rate on ``ore`` (``0.0`` if none)."""
        attempts = self.count(ore)
        if attempts <= 0:
            return 0.0
        return self._successes.get(str(ore), 0) / attempts

    def summary(self) -> dict[str, dict[str, float | int]]:
        """Return ``{ore: {'attempts', 'successes', 'rate'}}`` for every ore."""
        return {
            ore: {
                "attempts": attempts,
                "successes": int(self._successes.get(ore, 0)),
                "rate": self.rate(ore),
            }
            for ore, attempts in sorted(self._attempts.items())
        }
