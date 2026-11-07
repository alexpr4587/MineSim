# AGENTS.md: rules for every task in this repo

## Project
DigScript (working title; the package is `digscript`) is an open-source 2D top-down programming game. The player writes real Python in an in-game floating editor to control a mining robot on an infinite, procedurally generated, regenerating grid. Every ore has its own mining probability. Achievements (key L, like Minecraft advancements) unlock API functions, ores, upgrades and Python modules. Targets: Windows and Linux. License: MIT. All code, docs and in-game text in English.
Build tasks live in kit/prompts/NN-*.md and are run one per session, in order.

## Stack and checks
- Python 3.12, uv, PySide6, pydantic v2, platformdirs, pytest, ruff.
- Before finishing ANY task run: uv run ruff check . && uv run ruff format --check . && uv run pytest -q (tests use QT_QPA_PLATFORM=offscreen).
- UI tasks must also save a PNG with tools/screenshot.py into artifacts/ and you must describe what it shows.

## Architecture (enforced by tests/test_architecture.py)
- core/ is pure Python: no PySide6, no threads, no subprocess, no wall-clock time. Deterministic and runnable headless.
- scripting/ and runner/ never import PySide6 or ui/. ui/ may import core/ and scripting/, never the reverse. runner/ imports only the standard library and itself.
- The game process NEVER executes player code. Only the subprocess started by scripting/host.py does.
- World and miner are separate: core/world knows nothing about the miner. The miner acts only through commands processed by core/engine.py.
- No global mutable state or singletons. Pass dependencies through constructors. Systems talk through the typed EventBus in core/events.py.

## Data-driven
- All gameplay numbers and content live in src/digscript/content/*.json, validated by pydantic models in core/schemas.py. No magic numbers in code. Invalid data raises ContentError with the file name and JSON path.
- Randomness only through core/rng.py (seeded pure functions). Never use random, hash() or time inside core/.

## Code style
- Type hints everywhere, from __future__ import annotations, dataclasses(slots=True) or pydantic models for data, pathlib for paths, platformdirs for user folders, logging instead of print (CLI tools excepted).
- Small functions. Docstrings on public classes and functions (the player API docstrings are user-facing documentation).
- UI is written in Python code (no Qt Designer files). Colors and fonts only in ui/theme.py. Widgets contain no game logic.
- Everything must work on Windows and Linux: no shell-specific code, CI runs both.

## Workflow
- Small steps, tests written together with the code. Do not add dependencies the task does not list unless you justify them in the commit message.
- Do not rename public APIs or change the architecture unless asked. If a requirement is ambiguous choose the simplest option, say so in the commit message and continue.
- If unsure about a PySide6 or pydantic API, inspect the installed package (for example uv run python -c 'import PySide6.QtWidgets as m; help(m.QPlainTextEdit)') instead of guessing.
- End every task with a short report: what changed, commands run and their results, known limitations. Use Conventional Commits.
- Player scripts run in a subprocess with a restricted namespace. This is NOT a security sandbox; never claim it is.
