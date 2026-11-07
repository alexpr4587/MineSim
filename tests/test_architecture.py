"""Architecture boundary tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "digscript"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _py_files(package: str) -> list[Path]:
    return sorted((SRC / package).rglob("*.py"))


def test_no_pyside6_or_ui_in_core_scripting_runner() -> None:
    for package in ("core", "scripting", "runner"):
        for path in _py_files(package):
            for module in _imports(path):
                assert not module.startswith("PySide6"), f"{path}: imports PySide6"
                assert not module.startswith("digscript.ui"), f"{path}: imports digscript.ui"


def test_core_does_not_import_scripting_or_runner() -> None:
    for path in _py_files("core"):
        for module in _imports(path):
            assert not module.startswith("digscript.scripting"), path
            assert not module.startswith("digscript.runner"), path


def test_runner_imports_only_stdlib_and_runner() -> None:
    allowed = set(sys.stdlib_module_names)
    for path in _py_files("runner"):
        for module in _imports(path):
            top = module.split(".")[0]
            assert top in allowed or module.startswith("digscript.runner"), (
                f"{path}: runner imports {module}"
            )
