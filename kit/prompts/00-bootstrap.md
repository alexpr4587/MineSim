# Prompt 0 of 8: repository bootstrap

You are starting a new open-source Python game called DigScript (working title; the package is `digscript`). AGENTS.md in the project root describes the game and the rules: read it first and follow it.

TASK 0: set up the repository. Do not write game logic yet.
1. Make sure uv and Python 3.12 are available (install uv if missing, then `uv python pin 3.12`).
2. Create the project in the CURRENT directory with a src layout (`uv init --package --name digscript .` or equivalent). The directory already contains AGENTS.md and kit/: keep them untouched. Dependencies: PySide6>=6.7, pydantic>=2.7, platformdirs. Dev group: pytest, ruff, pyinstaller. Console script: `digscript = digscript.__main__:main`. Configure ruff (line length 100, rules E,F,I,UP,B) and pytest (testpaths = tests, marker `integration`). Make sure the git repository exists on branch main (`git init -b main` if needed).
3. Create this skeleton (empty modules, each with a docstring):
   src/digscript/__main__.py   main(): calls multiprocessing.freeze_support() first, supports a --selftest flag (stub for now), then starts the UI
   src/digscript/core/         pure game logic: schemas.py, content.py, rng.py, events.py, world/, progression/
   src/digscript/scripting/    parent-side bridge to the player-script subprocess
   src/digscript/runner/       code that runs INSIDE the subprocess
   src/digscript/ui/           PySide6 only
   src/digscript/content/      JSON game data (ores, biomes, achievements, functions, modules, upgrades, config)
   tests/  tools/  docs/  artifacts/ (git-ignored)
   README.md  LICENSE (MIT, copyright holder: DigScript contributors)  CHANGELOG.md  .gitignore
4. AGENTS.md already exists in the project root. Do not rewrite it.
5. CI in .github/workflows/ci.yml, matrix ubuntu-latest + windows-latest: checkout, astral-sh/setup-uv, `uv sync`; on Linux `sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libxcb-cursor0 fonts-dejavu-core`; then ruff check, ruff format --check and pytest -q with QT_QPA_PLATFORM=offscreen.
6. tests/test_architecture.py: parse every .py under core/, scripting/ and runner/ with `ast`. Fail if any of them imports PySide6 or digscript.ui; fail if core/ imports scripting or runner; fail if runner/ imports anything except the standard library and digscript.runner.
7. tools/screenshot.py: creates a QApplication on the offscreen platform, shows a placeholder window with a label, grabs it and saves artifacts/smoke.png.
8. README.md, about 10 lines: what it is, pre-alpha status, `uv sync && uv run digscript`, Linux note (`sudo apt install libxcb-cursor0`).

VERIFY: uv run ruff check . && uv run ruff format --check . && uv run pytest -q && QT_QPA_PLATFORM=offscreen uv run python tools/screenshot.py
COMMIT: chore: bootstrap repository (include AGENTS.md and kit/ in this commit)
