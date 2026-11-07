"""Helper library importable by player scripts (pure Python).

The primitive API functions (``move``, ``mine``, ``peek`` and
``position``) are injected into this module by the runner before
player code runs. They are declared here so the module is importable
and testable on its own; calling them without the runner raises
``RuntimeError``.
"""

from __future__ import annotations

from typing import Any

__all__ = ["go_home", "goto", "mine_here", "spiral", "sweep"]


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


def goto(x: int, y: int) -> None:
    """Move the miner to ``(x, y)``, one tile at a time.

    Moves horizontally first (east/west), then vertically
    (south/north), until ``position() == (x, y)``.
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
    """Move the miner back to the base at ``(0, 0)``."""
    goto(0, 0)


def sweep(width: int, height: int) -> Any:
    """Yield positions in serpentine (boustrophedon) order.

    Yields ``(x, y)`` for ``y`` in ``range(height)``; even rows go
    left-to-right (``x`` in ``range(width)``) and odd rows go
    right-to-left, so consecutive positions are always adjacent.
    """
    for y in range(height):
        if y % 2 == 0:
            xs = range(width)
        else:
            xs = range(width - 1, -1, -1)
        for x in xs:
            yield (x, y)


def spiral() -> Any:
    """Yield positions in an infinite square spiral from ``(0, 0)``.

    Starts at ``(0, 0)`` and spirals outwards (east, south, west,
    north, ...) with segment lengths 1, 1, 2, 2, 3, 3, ... so the
    first positions are ``(0, 0)``, ``(1, 0)``, ``(1, 1)``,
    ``(0, 1)``, ``(-1, 1)``, ... The generator never ends.
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


def mine_here() -> Any:
    """Mine the current tile if it holds a known ore.

    Peeks at the current tile first; if :func:`peek` returns an ore
    id (not ``None`` and not ``'unknown'``), calls :func:`mine` and
    returns its result. Otherwise returns ``None`` without mining.
    """
    ore = peek()
    if ore is None or ore == "unknown":
        return None
    return mine()
