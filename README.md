# DigScript

DigScript is an open-source 2D top-down programming game. You write real Python
in an in-game floating editor to control a mining robot on an infinite,
procedurally generated, regenerating grid. Every ore has its own mining
probability. Achievements (key **L**, like Minecraft advancements) unlock API
functions, ores, upgrades and Python modules.

## Screenshot

![DigScript main window](docs/screenshot.png)

## Controls

| Key | Action |
|-----|--------|
| `E` | Toggle the script editor |
| `F` | Toggle the API functions panel |
| `L` | Toggle the achievements panel |
| `U` | Toggle the upgrades panel |
| `C` | Recenter the world on the miner |
| `G` | Toggle the world grid |
| `F10` | Open the File menu |
| `Space` | Toggle pause |
| `1`–`5` | Set game speed (slowest to fastest) |
| `Ctrl+R` | Run the current script |
| `Ctrl+.` | Stop the running script |

## Your first script

Open the editor with `E`, replace the starter script and press `Ctrl+R`:

```python
for _ in range(10):
    if peek() is not None:
        mine()
    move(East)
```

Run it to completion to unlock the **Hello, Miner** achievement, then sell your
ore with `sell()` and buy the **Backpack** upgrade with `buy_upgrade("backpack")`.

## Install from source

```sh
uv sync && uv run digscript
```

Linux note: `sudo apt install libxcb-cursor0`

## Safety

Player scripts run in a separate subprocess with a restricted namespace. This is
**not** a security sandbox: only run scripts you trust.
