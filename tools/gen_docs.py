"""Generate ``docs/API.md`` and ``docs/GUIDE.md`` from the content files.

Usage: ``python tools/gen_docs.py``
The default outputs are ``docs/API.md`` and ``docs/GUIDE.md`` relative to
the repository root.
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
_CONTENT = _ROOT / "src" / "minesim" / "content"
_DOCS = _ROOT / "docs"

__all__ = ["generate_api_md", "generate_guide_md", "main"]

_TAB_ORDER = ("code", "mining", "business", "explorer", "data")
_TAB_TITLES = {
    "code": "Code",
    "mining": "Mining",
    "business": "Business",
    "explorer": "Explorer",
    "data": "Data",
}


def _load_json(name: str) -> Any:
    with open(_CONTENT / name, encoding="utf-8") as handle:
        return json.load(handle)


def _minerlib_doc(name: str) -> str:
    """Return the docstring of a :mod:`minesim.runner.minerlib` function."""
    from minesim.runner import minerlib

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
    lines.append("# MineSim API")
    lines.append("")
    lines.append(
        "MineSim exposes a small, deterministic API to player scripts. "
        "The game process never executes player code; scripts run in a "
        "separate subprocess started by `minesim.scripting.host`. "
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
        "`src/minesim/runner/minerlib.py`."
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


def _criteria_label(criteria: Any) -> str:
    """Return a human-readable description of an achievement criterion."""
    if not isinstance(criteria, dict):
        return "Unknown."
    criteria_type = criteria.get("type")
    if criteria_type == "counter":
        counter = str(criteria.get("counter", ""))
        target = criteria.get("target", 1)
        return f"`{counter}` reaches {target}."
    if criteria_type == "script_feature":
        feature = str(criteria.get("feature", ""))
        return f"A script uses `{feature}`."
    if criteria_type == "script_defines_function":
        return "A script defines a function."
    return "Unknown."


def _reward_label(reward: Any) -> str:
    """Return a human-readable description of one achievement reward."""
    if not isinstance(reward, dict):
        return ""
    reward_type = reward.get("type")
    reward_id = reward.get("id")
    if reward_type == "money":
        return f"+{reward.get('amount', 0)} money"
    if not reward_id:
        return ""
    labels = {
        "unlock_function": "function",
        "unlock_ore": "ore",
        "unlock_upgrade": "upgrade",
        "unlock_module": "module",
        "unlock_skin": "skin",
        "unlock_example": "example",
    }
    kind = labels.get(str(reward_type))
    if kind is None:
        return ""
    return f"{kind} `{reward_id}`"


def _unlocked_by_entries(achievement_id: str) -> list[str]:
    """Return every content entry whose ``unlocked_by`` is the achievement."""
    collections = (
        ("ores.json", "id", "ore"),
        ("functions.json", "name", "function"),
        ("modules.json", "name", "module"),
        ("upgrades.json", "id", "upgrade"),
        ("skins.json", "id", "skin"),
        ("examples.json", "id", "example"),
    )
    entries: list[str] = []
    for filename, key, kind in collections:
        try:
            data = _load_json(filename)
        except FileNotFoundError:
            continue
        for entry in data:
            if isinstance(entry, dict) and entry.get("unlocked_by") == achievement_id:
                entries.append(f"{kind} `{entry.get(key, '')}`")
    return entries


def generate_guide_md(output: str | Path | None = None) -> Path:
    """Generate ``docs/GUIDE.md`` and return its path."""
    achievements = _load_json("achievements.json")
    titles = {
        str(entry.get("id")): str(entry.get("title", entry.get("id")))
        for entry in achievements
        if isinstance(entry, dict)
    }

    lines: list[str] = []
    lines.append("# MineSim Achievement Guide")
    lines.append("")
    lines.append(
        "Every achievement belongs to one of five tabs: Code, Mining, Business, "
        "Explorer and Data. An achievement becomes available once its parent is "
        "completed. Completing it grants the rewards and unlocks listed below."
    )
    lines.append("")

    for tab_id in _TAB_ORDER:
        tab_achievements = [
            entry
            for entry in achievements
            if isinstance(entry, dict) and entry.get("tab") == tab_id
        ]
        if not tab_achievements:
            continue
        lines.append(f"## {_TAB_TITLES[tab_id]}")
        lines.append("")
        for entry in tab_achievements:
            achievement_id = str(entry.get("id", ""))
            title = str(entry.get("title", achievement_id))
            lines.append(f"### {title} (`{achievement_id}`)")
            lines.append("")
            description = str(entry.get("description", ""))
            if description:
                lines.append(description)
                lines.append("")
            parent = entry.get("parent")
            if parent:
                lines.append(f"**Requires:** {titles.get(str(parent), str(parent))}")
                lines.append("")
            lines.append(f"**Criteria:** {_criteria_label(entry.get('criteria'))}")
            lines.append("")
            rewards = [
                label
                for label in (_reward_label(reward) for reward in entry.get("rewards", []))
                if label
            ]
            lines.append(f"**Rewards:** {'; '.join(rewards) if rewards else 'None.'}")
            lines.append("")
            unlocked = _unlocked_by_entries(achievement_id)
            lines.append(f"**Unlocks:** {'; '.join(unlocked) if unlocked else 'Nothing.'}")
            lines.append("")

    out = Path(output) if output else (_DOCS / "GUIDE.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    """Entry point for the docs generator."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        api_path = generate_api_md(args[0])
        guide_path = generate_guide_md(Path(args[0]).with_name("GUIDE.md"))
    else:
        api_path = generate_api_md()
        guide_path = generate_guide_md()
    print(str(api_path))
    print(str(guide_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
