# Optional prompt R: rename the project to MineSim

Run this only if the game should be called MineSim (the README title already says so). Run it BEFORE prompt 15, after unzipping the v0.3 kit. Follow AGENTS.md. Rename MineSim to MineSim everywhere in one commit, without changing behavior.

1. Package minesim -> minesim (src/minesim), console script `minesim`, `python -m minesim`, all imports, pyproject, the PyInstaller spec and output names, GitHub workflows, window title, platformdirs app name ('MineSim'), QSettings organization and application names, the stub file name (minesim_api.pyi), docs, README, CHANGELOG, AGENTS.md and every file in kit/prompts (replace MineSim and minesim).
2. User data migration: on first start, if the old MineSim user data folder exists and the MineSim one does not, move it (saves, scripts, settings) and log it. Add a test with temporary directories.
3. Use git mv so the history stays readable.

VERIFY: uv run ruff check . && uv run ruff format --check . && uv run pytest -q && uv run minesim --selftest
COMMIT: refactor: rename project to MineSim
