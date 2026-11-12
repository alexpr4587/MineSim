"""Generate ``docs/API.md`` from ``functions.json`` and the ``minerlib`` docstrings.

Usage: ``python tools/gen_docs.py``
The default output is ``docs/API.md`` relative to the repository root.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any

# Make the src layout importable when run as a plain script.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_ROOT = Path(__file__).resolve().parents[1]
_CONTENT = _ROOT / "src" / "digscript" / "content"
_DOCS = _ROOT / "docs"

__all__ = ["generate_api_md", "main"]


def _load_json(name: str) -> Any:
    with open(_CONTENT / name, encoding="utf-8") as handle:
        return json.load(handle)


def _minerlib_doc(name: str) -> str:
    """Return the docstring of a :mod:`digscript.runner.minerlib` function."""
    from digscript.runner import minerlib

    fn = getattr(minerlib, name, None)
    if fn is None:
        return ""
    return inspect.getdoc(fn) or ""


def _achievement_titles() -> dict[str, str]:
    titles: dict[str, str] = {}
    for entry in _load_json("achievements.json"):
        if isinstance(entry, dict) and entry.get("id"):
            titles[str(entry["id"])] = str(entry.get("title", entry["id"]))
    return titles


def _unlocked_by_label(unlocked_by: Any, titles: dict[str, str]) -> str:
    if not unlocked_by:
        return "available from the start"
    title = titles.get(str(unlocked_by), str(unlocked_by))
    return f"unlocks with the **{title}** achievement"


def generate_api_md(output: str | Path | None = None) -> Path:
    """Generate ``docs/API.md`` and return its path."""
    functions = _load_json("functions.json")
    modules = _load_json("modules.json")
    titles = _achievement_titles()

    lines: list[str] = []
    lines.append("# DigScript API")
    lines.append("")
    lines.append(
        "DigScript exposes a small, deterministic API to player scripts. "
        "The game process never executes player code; scripts run in a "
        "separate subprocess started by `digscript.scripting.host`. "
        "See the README for the safety note."
    )
    lines.append("")

    lines.append("## Player API functions")
    lines.append("")
    lines.append(
        "Functions are called directly, e.g. `move(East)`, `mine()`, "
        "`sell()`. Locked functions raise `NotUnlockedError` until the "
        "required achievement is unlocked."
    )
    lines.append("")
    lines.append("| Function | Signature | Description | Cost | Example | Unlocked by |")
    lines.append("|---|---|---|---|---|---|")
    for entry in functions:
        name = str(entry.get("name", ""))
        signature = str(entry.get("signature", ""))
        doc = str(entry.get("doc", ""))
        cost = str(entry.get("cost", ""))
        example = str(entry.get("example", ""))
        unlocked_by = entry.get("unlocked_by")
        lines.append(
            f"| `{name}` | `{signature}` | {doc} | {cost} | `{example}` | "
            f"{_unlocked_by_label(unlocked_by, titles)} |"
        )
    lines.append("")

    for entry in functions:
        name = str(entry.get("name", ""))
        signature = str(entry.get("signature", ""))
        doc = str(entry.get("doc", ""))
        category = str(entry.get("category", ""))
        unlocked_by = entry.get("unlocked_by")
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append(f"**Signature:** `{signature}`")
        lines.append("")
        lines.append(f"**Category:** {category}")
        lines.append("")
        lines.append(f"**Description:** {doc}")
        lines.append("")
        lines.append(f"**Cost:** {entry.get('cost', '')}")
        lines.append("")
        lines.append("**Example:**")
        lines.append("")
        lines.append("```python")
        lines.append(str(entry.get("example", "")))
        lines.append("```")
        lines.append("")
        lines.append(f"**Unlocked by:** {_unlocked_by_label(unlocked_by, titles)}")
        lines.append("")

    lines.append("## minerlib helper module")
    lines.append("")
    lines.append(
        "`minerlib` is a pure-Python helper module importable by player scripts. "
        "The primitive API functions (`move`, `mine`, `peek`, `position`) are "
        "injected by the runner; the helpers below are implemented in "
        "`src/digscript/runner/minerlib.py`."
    )
    lines.append("")

    helper_names = (
        "goto",
        "go_home",
        "sweep",
        "spiral",
        "ring",
        "nearest",
        "goto_nearest",
        "mine_here",
        "mine_until",
        "haul",
        "farm",
    )
    for name in helper_names:
        doc = _minerlib_doc(name)
        lines.append(f"### `minerlib.{name}`")
        lines.append("")
        if doc:
            # Render the docstring, indenting continuation lines.
            for paragraph in doc.split("\n\n"):
                lines.append(paragraph.strip())
                lines.append("")
        else:
            lines.append("*No documentation.*")
            lines.append("")

    lines.append("### `minerlib.Samples`")
    lines.append("")
    lines.append(
        "A tiny tally for mining attempts. `add(ore, success)` records an "
        "attempt, `count(ore)` returns attempts, `rate(ore)` returns the "
        "observed success rate and `summary()` returns attempts, successes "
        "and rates per ore."
    )
    lines.append("")
    lines.append("```python")
    lines.append("samples = minerlib.Samples()")
    lines.append('samples.add("stone", True)')
    lines.append('print(samples.rate("stone"))')
    lines.append("```")
    lines.append("")

    lines.append("## Standard library modules")
    lines.append("")
    lines.append(
        "Player scripts may import the standard-library modules below once the "
        "required achievement is unlocked. All other imports are blocked."
    )
    lines.append("")
    lines.append("| Module | Unlocked by |")
    lines.append("|---|---|")
    for entry in modules:
        name = str(entry.get("name", ""))
        unlocked_by = entry.get("unlocked_by")
        lines.append(f"| `{name}` | {_unlocked_by_label(unlocked_by, titles)} |")
    lines.append("")

    lines.append("## Safety")
    lines.append("")
    lines.append(
        "Player scripts run in a separate subprocess with a restricted namespace. "
        "This is **not** a security sandbox: only run scripts you trust."
    )
    lines.append("")

    out = Path(output) if output else (_DOCS / "API.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    """Entry point for the docs generator."""
    args = list(sys.argv[1:] if argv is None else argv)
    output = args[0] if args else None
    path = generate_api_md(output)
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
