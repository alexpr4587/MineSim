# Changelog

## [0.3.0] - 2026-11-16

### Added

- A fleet of drones: every drone runs its own script and the fleet shares a
  typed key/value memory (`spawn_drone`, `assign`, `kill_drone`, `drones`,
  `drone_id`, `shared_get` and `shared_set`).
- A base warehouse with per-drone unloading, capacity and warehouse stock
  (`unload`, `stock`, `sell_stock`).
- A dynamic market with an index, per-item prices and price history
  (`price`, `prices`, `price_history`), plus the market chart panel (`M`).
- A refinery with six recipes and timed jobs (`recipes`, `refine`, `refinery`)
  in the new base panel (`B`).
- Delivery contracts generated at the base (`contracts`, `deliver`).
- World events: rich veins, slow zones and market news.
- The new `minerlib` library with route, trading, data and OOP helpers.
- Eight new example scripts: market watching, refining, contracts, two drones,
  worker classes, event hunting, price forecasting and fleet management.
- 28 new achievements across three new tabs (Trading, Industry and Fleet), for
  69 achievements in eight tabs in total.
- Drones panel and fleet view (`D`), with per-drone scripts and consoles.
- Save format version 8, with automatic migration of v0.1.0, v0.2.0 and later
  saves; the fleet, per-drone scripts, shared memory, warehouse, market,
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
