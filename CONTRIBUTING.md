# Contributing to DigScript

DigScript is an open-source 2D top-down programming game. Contributions are
welcome: bug fixes, features, content, documentation and translations.

## Setup

1. Clone the repository:
   ```sh
   git clone <repo-url>
   cd digscript
   ```
2. Install [uv](https://astral.sh/) and sync the project:
   ```sh
   uv sync
   ```
3. Run the game:
   ```sh
   uv run digscript
   ```
   Linux note: `sudo apt install libxcb-cursor0`

## Checks

Before finishing any change, run:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Tests use `QT_QPA_PLATFORM=offscreen`. UI changes must also save a PNG with
`tools/screenshot.py` into `artifacts/` (and describe what it shows in the
commit).

## Architecture

DigScript follows strict architecture rules (enforced by
`tests/test_architecture.py` and described in `AGENTS.md`):

- `core/` is pure Python: no PySide6, no threads, no subprocess, no wall-clock
  time. Deterministic and runnable headless.
- `scripting/` and `runner/` never import PySide6 or `ui/`. `ui/` may import
  `core/` and `scripting/`, never the reverse. `runner/` imports only the
  standard library and itself.
- The game process never executes player code. Only the subprocess started by
  `scripting/host.py` does.
- World and miner are separate: `core/world` knows nothing about the miner. The
  miner acts only through commands processed by `core/engine.py`.
- No global mutable state or singletons. Pass dependencies through constructors.
  Systems talk through the typed `EventBus` in `core/events.py`.

## Data-driven content

All gameplay numbers and content live in `src/digscript/content/*.json`,
validated by pydantic models in `core/schemas.py`. Invalid data raises
`ContentError` with the file name and JSON path. Randomness only through
`core/rng.py` (seeded pure functions).

## Submitting changes

1. Create a branch from `main`.
2. Make your change with tests.
3. Run the checks above.
4. Open a pull request. The pull request template contains the final release
   checklist.

See `AGENTS.md` for the full code style and workflow rules.
