# Changelog

## [0.4.0] - 2026-11-24

### Added

- Underground layers: the surface, the old galleries, the deep level and the
  abyssal rock, reached through the new shaft and its stations (`layers`,
  `layer`, `descend` and `ascend`, plus `PageUp`/`PageDown` in the world view).
- Energy and rescue: every miner has a battery, charges at the base or a
  station (`battery`, `charge`, `energy_cost`) and is towed back to the
  station when it runs dry, losing its inventory.
- Heat and shared ventilation: hot layers warm miners, ventilation limits how
  many can work there without overloading the airflow (`temperature`, `cool`,
  `climate`), and overheated miners shut down until they cool.
- The shared dock: a queued, tick-based unloading point (`dock_free`,
  `dock_rate`) that serves the whole fleet.
- The expanded `minerlib` library with energy-aware helpers for energy budgets,
  charging, layers, shafts, cooling, climate and dock staggering; the existing
  helpers now account for the battery.
- Eight new example scripts: energy budget, going deep, climate watching, dock
  etiquette, night shift, layer prospecting, vent management and full
  automation.
- 17 new achievements in the new Depths and Engineering tabs, for 86
  achievements in 10 tabs in total.
- Save format version 13, with automatic migration of v0.3.0 and v0.3.1
  saves; layers, batteries, temperature and the new counters are persisted.

## [0.3.1] - 2026-11-17

### Added

- Closable editor tabs: every tab has a close button, middle-click closes a tab,
  `Ctrl+W` closes the current tab and `Ctrl+Shift+T` reopens the last closed one.
  Closing never deletes a script and running scripts keep running.
- A searchable **Open…** list of closed scripts, sorted by last modified time.
- File actions menu with Rename (validated Python module names), Duplicate,
  Delete to a timestamped `.trash` folder and Restore deleted.
- Open tabs, their order and the active tab are remembered between runs.
- A dirty dot in the tab title, two-second autosave and running-script dots in
  the colour of the miner that runs each script.
- Tabs close automatically with a console note when their file is deleted or
  renamed outside the game.

### Changed

- Renamed drones to miners throughout the game: UI text, player API, content
  ids and save data. The old API names remain as deprecated aliases, and old
  saves migrate automatically.

### Fixed

- The selected speed button in the HUD now uses a high-contrast label.

## [0.3.0] - 2026-11-16

### Added

- A fleet of miners: every miner runs its own script and the fleet shares a
  typed key/value memory (`spawn_miner`, `assign`, `kill_miner`, `miners`,
  `miner_id`, `shared_get` and `shared_set`).
- A base warehouse with per-miner unloading, capacity and warehouse stock
  (`unload`, `stock`, `sell_stock`).
- A dynamic market with an index, per-item prices and price history
  (`price`, `prices`, `price_history`), plus the market chart panel (`M`).
- A refinery with six recipes and timed jobs (`recipes`, `refine`, `refinery`)
  in the new base panel (`B`).
- Delivery contracts generated at the base (`contracts`, `deliver`).
- World events: rich veins, slow zones and market news.
- The new `minerlib` library with route, trading, data and OOP helpers.
- Eight new example scripts: market watching, refining, contracts, two miners,
  worker classes, event hunting, price forecasting and fleet management.
- 28 new achievements across three new tabs (Trading, Industry and Fleet), for
  69 achievements in eight tabs in total.
- Miners panel and fleet view (`T`), with per-miner scripts and consoles.
- Save format version 8, with automatic migration of v0.1.0, v0.2.0 and later
  saves; the fleet, per-miner scripts, shared memory, warehouse, market,
  refinery and contracts are persisted.

## [0.2.0] - 2026-11-12

### Added

- Lit 2.5D terrain renderer with posterized slope lighting, toggled with `H`.
- Miner skins and pixel-art sprites, selectable in the new wardrobe panel (`K`).
- 41 achievements across five tabs: Code, Mining, Business, Explorer and Data.
- Seven new player API functions: `wait`, `tick`, `distance`, `biome`, `ore_info`,
  `inspect` and `submit_estimate`.
- New `minerlib` helpers: `ring`, `nearest`, `goto_nearest`, `mine_until`,
  `haul`, `farm` and the `Samples` recorder.
- Four new Python modules: `itertools`, `functools`, `dataclasses` and `typing`.
- Eight example scripts, unlocked through the achievement chain.
- Save format version 3, with automatic migration of v0.1.0 saves.

## [0.1.0] - 2026-11-08

### Added

- First public release of MineSim, a 2D top-down programming game.
- Infinite procedurally generated, regenerating grid with per-ore mining
  probabilities.
- Player API (`move`, `mine`, `peek`, `position`, `sell`, `inventory`, `scan`,
  `stats`, `buy_upgrade`) executed in a separate subprocess.
- `minerlib` helper module (`goto`, `go_home`, `sweep`, `spiral`, `mine_here`).
- Achievements (key `L`) that unlock API functions, ores, upgrades and Python
  modules.
- Floating script editor (Ctrl+R run, Ctrl+. stop), API panel, achievements
  panel, upgrades panel and HUD.
- Game speed controls (Space pause, 1–5 speed) and world hotkeys (E, F, L, U,
  C, G, F10).
- Autosave / load progression and PyInstaller one-dir builds for Windows and
  Linux.

## [Unreleased]

- Bootstrap repository.
