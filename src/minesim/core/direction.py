"""Cardinal directions (y grows southwards, i.e. down on screen)."""

from __future__ import annotations

from enum import Enum

__all__ = ["Direction", "parse"]


class Direction(Enum):
    """The four cardinal directions."""

    NORTH = (0, -1)
    EAST = (1, 0)
    SOUTH = (0, 1)
    WEST = (-1, 0)

    @property
    def dx(self) -> int:
        """Horizontal delta (east is positive)."""
        value: tuple[int, int] = self.value
        return value[0]

    @property
    def dy(self) -> int:
        """Vertical delta (south is positive)."""
        value: tuple[int, int] = self.value
        return value[1]

    @classmethod
    def parse(cls, value: Direction | str) -> Direction:
        """Parse a direction from a name like ``'north'`` or ``'n'``."""
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise ValueError(f"invalid direction: {value!r}")
        key = value.strip().lower()
        aliases = {
            "north": cls.NORTH,
            "n": cls.NORTH,
            "east": cls.EAST,
            "e": cls.EAST,
            "south": cls.SOUTH,
            "s": cls.SOUTH,
            "west": cls.WEST,
            "w": cls.WEST,
        }
        try:
            return aliases[key]
        except KeyError:
            raise ValueError(f"invalid direction: {value!r}") from None


def parse(value: Direction | str) -> Direction:
    """Parse a direction from a name like ``'north'`` or ``'n'``."""
    return Direction.parse(value)
