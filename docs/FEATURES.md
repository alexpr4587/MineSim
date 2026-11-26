# MineSim features

This page keeps the long version of the feature list. The README is the short
tour for someone who has just found the project.

## The world

- Infinite, procedurally generated and regenerating grid with biomes and a
  separate mining probability for every ore.
- Four underground layers: the surface, the old galleries, the deep level and
  the abyssal rock. A shaft and a station on every layer connect them, and the
  view fades softly while changing layers.
- A lit 2.5D terrain renderer with posterized slope lighting, toggled with `H`.
- World events: rich veins, slow zones and market news.
- Deterministic seeded worlds. The same seed and the same commands always
  produce the same world.

## The fleet

- A fleet of miners, each running its own Python script.
- Typed key/value shared memory so scripts can coordinate without a server.
- Per-miner batteries, charging at the base or a station, and rescue towing
  when a miner runs dry.
- Heat and shared ventilation. Hot layers warm miners, airflow limits how many
  can work there, and overheated miners shut down until they cool.
- A shared dock with a tick-based queue for fleet-wide unloading.
- Miner skins and pixel-art sprites, selected in the wardrobe panel (`K`).

## The economy

- A base warehouse with per-miner unloading, capacity and stock.
- A dynamic market with an index, per-item prices and price history, plus a
  live chart (`M`).
- A refinery with six recipes and timed jobs (`B`).
- Delivery contracts generated at the base, with deadlines and premiums.
- Market news events that move prices for a limited time.

## Progression

- 86 achievements in ten tabs (Code, Mining, Business, Trading, Industry,
  Fleet, Explorer, Data, Depths and Engineering).
- Achievements unlock API functions, ores, upgrades, Python modules, features,
  recipes and example scripts.
- 47 player API functions and the `minerlib` helper module, including route,
  trading, data, OOP, energy, layer and dock helpers.
- 24 example scripts that are unlocked as the player progresses.

## Writing code

- A floating script editor with syntax highlighting, closable tabs, a
  searchable **Open…** list, rename/duplicate/delete with a recoverable trash,
  per-tab autosave and running-script indicators.
- `Ctrl+R` runs the current script and `Ctrl+.` stops it. `Ctrl+W` closes a tab
  and `Ctrl+Shift+T` reopens the last closed one.
- An API reference panel (`F`), a coloured console, a HUD, fleet consoles and
  achievement toasts.
- The Python standard library modules that the game unlocks are `math`,
  `random`, `itertools`, `functools`, `dataclasses` and `typing`.

## Data and saves

- All gameplay numbers and content live in `src/minesim/content/*.json` and are
  validated by pydantic models.
- Save format v13, with autosave and automatic migration of v0.1.0, v0.2.0,
  v0.3.0 and v0.3.1 saves.
- One-dir PyInstaller builds for Windows and Linux. Multi-miner scripts on
  several layers are supported in the frozen build.

## Safety

Player scripts run in a separate subprocess with a restricted namespace. This
is **not** a security sandbox: only run scripts you trust.
