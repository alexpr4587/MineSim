"""Architecture invariants enforced by AST inspection."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "digscript"


def _python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def _imports(path: Path) -> list[tuple[str | None, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: list[tuple[str | None, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.append((alias.name, 0))
        elif isinstance(node, ast.ImportFrom):
            result.append((node.module, node.level))
    return result


def test_no_forbidden_imports_in_core_scripting_runner() -> None:
    for directory in (SRC / "core", SRC / "scripting", SRC / "runner"):
        for path in _python_files(directory):
            for module, _level in _imports(path):
                if module is None:
                    continue
                assert not module.split(".")[0] == "PySide6", f"{path}: imports PySide6"
                assert not module.startswith("digscript.ui"), f"{path}: imports digscript.ui"
                assert module.split(".")[0] != "ui", f"{path}: imports ui"


def test_core_does_not_import_scripting_or_runner() -> None:
    for path in _python_files(SRC / "core"):
        for module, _level in _imports(path):
            if module is None:
                continue
            assert not module.startswith("digscript.scripting"), f"{path}: core imports scripting"
            assert not module.startswith("digscript.runner"), f"{path}: core imports runner"
            assert module.split(".")[0] not in {"scripting", "runner"}, (
                f"{path}: core imports scripting/runner"
            )


def test_runner_only_stdlib_and_itself() -> None:
    stdlib = set(sys.stdlib_module_names)
    for path in _python_files(SRC / "runner"):
        for module, level in _imports(path):
            if level and level > 0:
                # relative import inside runner package
                continue
            if module is None:
                continue
            top = module.split(".")[0]
            if top == "digscript":
                # only digscript.runner allowed
                assert module.startswith("digscript.runner"), f"{path}: runner imports {module}"
                continue
            assert top in stdlib, f"{path}: runner imports non-stdlib {module}"
