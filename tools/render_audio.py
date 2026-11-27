"""Render one synthesized sound or music loop into ``artifacts/``.

Usage::

    uv run python tools/render_audio.py mine_thunk
    uv run python tools/render_audio.py surface --bars 8
    uv run python tools/render_audio.py --list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from minesim.audio.music import load_music_moods, render_loop
from minesim.audio.recipes import load_sfx_recipes, render_sfx
from minesim.audio.synth import write_wav

__all__ = ["main"]


def main(argv: list[str] | None = None) -> int:
    """Render ``name`` and print the written path."""
    parser = argparse.ArgumentParser(prog="render_audio.py")
    parser.add_argument("name", nargs="?", help="sound id or music mood id")
    parser.add_argument("--list", action="store_true", help="list sounds and moods")
    parser.add_argument("--bars", type=int, default=8, help="music loop bars")
    parser.add_argument("--seed", type=int, default=0, help="rendering seed")
    parser.add_argument("--variant", type=int, default=0, help="sound variant index")
    parser.add_argument("--output", type=Path, default=None, help="output WAV path")
    args = parser.parse_args(argv)

    recipes = load_sfx_recipes()
    moods = load_music_moods()
    if args.list or not args.name:
        print("sounds:", ", ".join(sorted(recipes)))
        print("moods:", ", ".join(sorted(moods)))
        return 0 if args.list else 2

    root = Path(__file__).resolve().parents[1]
    artifacts = root / "artifacts"
    if args.name in recipes:
        buffer = render_sfx(recipes[args.name], args.variant, args.seed)
        output = args.output or artifacts / f"sfx_{args.name}.wav"
    elif args.name in moods:
        buffer = render_loop(moods[args.name], seed=args.seed, bars=args.bars)
        output = args.output or artifacts / f"music_{args.name}.wav"
    else:
        print(f"unknown sound or mood: {args.name}", file=sys.stderr)
        return 2
    write_wav(output, buffer)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
