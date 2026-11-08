# Changelog

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
