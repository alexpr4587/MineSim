# MineSim

## Tagline

Automate a mining operation by writing real Python.

## Description

MineSim is a small 2D top-down programming game about a mining robot, a real
Python editor and an operation that keeps growing.

You start on the surface with one miner. Write a loop, mine some ore, sell it
and buy your first upgrade. Then unlock a second miner, a warehouse, a refinery,
a market chart and a shaft that goes deeper. Every ore has its own mining
probability, so the best routes come from experiments, not from a walkthrough.

The Python is real: variables, lists, loops, functions, modules, classes and
shared state. Achievements unlock new API functions and Python modules, and the
in-game API reference explains every function. Scripts run in a separate
subprocess with a restricted namespace. This is **not** a security sandbox:
only run scripts you trust.

### What you can automate

- Sweep ore, return to the base and unload.
- Run a fleet where each miner has its own script and shared memory.
- Watch the battery, temperature and ventilation before a miner shuts down.
- Refine bars, deliver contracts and sell stock when the market is high.
- Explore four underground layers and keep a station supplied.

### A calm pace

There is no timer and no fail state. Pause with `Space`, change the speed with
`1`–`5`, and let the operation run while you edit the next script. The lit 2.5D
terrain, miner skins and soft layer transitions are there to make the work feel
good to watch.

## Controls

| Key | Action |
|-----|--------|
| `E` | Toggle the script editor |
| `F` | Toggle the API functions panel |
| `L` | Toggle achievements |
| `U` | Toggle upgrades |
| `K` | Toggle the wardrobe |
| `B` | Toggle the base panel |
| `M` | Toggle the market panel |
| `T` | Toggle the miners panel |
| `H` | Toggle lit terrain |
| `C` | Recenter on the miner |
| `G` | Toggle the grid |
| `PageUp` / `PageDown` | View the layer above / below |
| `Space` | Pause |
| `1`–`5` | Game speed |
| `Ctrl+R` / `Ctrl+.` | Run / stop the current script |
| `F10` | Open the File menu |

## System requirements

- Windows 10 or newer, or a modern Linux distribution.
- A 64-bit CPU and a display that can run Qt 6.
- No Python installation is required for the release build.
- Linux note: install `libxcb-cursor0` if Qt reports a missing xcb library.

## Suggested tags

`programming`, `automation`, `python`, `idle`, `mining`, `sandbox`,
`open-source`, `cozy`, `singleplayer`, `2d`

## Download

Download the Windows zip or the Linux tar.gz from the GitHub Releases page.
The page is updated with every release.

Repository and feedback: see the project README.
