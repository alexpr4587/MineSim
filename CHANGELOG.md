# Changelog

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

- First public release of DigScript, a 2D top-down programming game.
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
