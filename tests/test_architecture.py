"""Architecture boundary tests."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "minesim"


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
                assert not module.startswith("minesim.ui"), f"{path}: imports minesim.ui"


def test_core_does_not_import_scripting_or_runner() -> None:
    for path in _py_files("core"):
        for module in _imports(path):
            assert not module.startswith("minesim.scripting"), path
            assert not module.startswith("minesim.runner"), path


FORBIDDEN_MATH_CALLS = {
    "sin",
    "cos",
    "tan",
    "exp",
    "log",
    "log2",
    "log10",
    "pow",
}


def test_core_does_not_import_numpy() -> None:
    for path in _py_files("core"):
        for module in _imports(path):
            assert module.split(".")[0] != "numpy", f"{path}: imports numpy"


def test_core_has_no_forbidden_floating_point_math() -> None:
    for path in _py_files("core"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in FORBIDDEN_MATH_CALLS, (
                    f"{path}: calls math.{node.func.attr}"
                )
            if isinstance(node, ast.ImportFrom) and node.module == "math":
                for alias in node.names:
                    assert alias.name not in FORBIDDEN_MATH_CALLS, (
                        f"{path}: imports math.{alias.name}"
                    )
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                exponent = node.right
                if not (isinstance(exponent, ast.Constant) and isinstance(exponent.value, int)):
                    raise AssertionError(f"{path}: uses a fractional power")


def test_runner_imports_only_stdlib_and_runner() -> None:
    allowed = set(sys.stdlib_module_names)
    for path in _py_files("runner"):
        for module in _imports(path):
            top = module.split(".")[0]
            assert top in allowed or module.startswith("minesim.runner"), (
                f"{path}: runner imports {module}"
            )
