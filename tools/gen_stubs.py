"""Generate ``minesim_api.pyi`` from functions.json and minerlib.

Usage: ``python tools/gen_stubs.py [output]``
The default output is ``minesim_api.pyi`` in the current directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the src layout importable when run as a plain script.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from minesim.scripting.stubs import generate_stub_text, write_stubs  # noqa: E402

__all__ = ["generate_stubs", "generate_stub_text", "main"]


def generate_stubs(output: str | Path | None = None) -> Path:
    """Generate ``minesim_api.pyi`` and return its path."""
    if output is None:
        path = Path("minesim_api.pyi")
        path.write_text(generate_stub_text(), encoding="utf-8")
        return path
    # write_stubs expects a directory; handle the file-path case here.
    path = Path(output)
    if path.suffix == ".pyi":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generate_stub_text(), encoding="utf-8")
        return path
    return write_stubs(path)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the stub generator."""
    args = list(sys.argv[1:] if argv is None else argv)
    output: str | None = None
    if args:
        output = args[0]
    result = generate_stubs(output)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
