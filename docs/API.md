# DigScript API

DigScript exposes a small, deterministic API to player scripts. The game process never executes player code; scripts run in a separate subprocess started by `digscript.scripting.host`. See the README for the safety note.

## Player API functions

Functions are called directly, e.g. `move(East)`, `mine()`, `sell()`. Locked functions raise `NotUnlockedError` until the required achievement is unlocked.

| Function | Signature | Description | Unlocked by |
|---|---|---|---|
| `move` | `move(direction)` | Move one tile in the given direction. | available from the start |
| `mine` | `mine()` | Mine the tile the miner stands on. Returns a dict with ok, and reason or ore when relevant. | available from the start |
| `peek` | `peek()` | Return the ore on the current tile, None if empty, or 'unknown' if the ore is locked. | available from the start |
| `position` | `position()` | Return the miner position as (x, y). | available from the start |
| `sell` | `sell()` | Sell the whole inventory at the base and return the money gained. | unlocks with the **First Dig** achievement |
| `inventory` | `inventory()` | Return the inventory as a dict of ore id to count. | unlocks with the **Hello, Miner** achievement |
| `scan` | `scan(radius)` | Scan for ore within radius tiles. Returns a list of (dx, dy, ore_id) for non-empty tiles. | unlocks with the **Scout** achievement |
| `stats` | `stats()` | Return per-ore mining statistics as {ore: {'attempts': n, 'successes': m}}. | unlocks with the **Data Driven** achievement |
| `buy_upgrade` | `buy_upgrade(upgrade_id)` | Buy the next level of the given upgrade and return the new level. | unlocks with the **First Sale** achievement |

### `move`

**Signature:** `move(direction)`

**Category:** movement

**Description:** Move one tile in the given direction.

**Unlocked by:** available from the start

### `mine`

**Signature:** `mine()`

**Category:** mining

**Description:** Mine the tile the miner stands on. Returns a dict with ok, and reason or ore when relevant.

**Unlocked by:** available from the start

### `peek`

**Signature:** `peek()`

**Category:** mining

**Description:** Return the ore on the current tile, None if empty, or 'unknown' if the ore is locked.

**Unlocked by:** available from the start

### `position`

**Signature:** `position()`

**Category:** movement

**Description:** Return the miner position as (x, y).

**Unlocked by:** available from the start

### `sell`

**Signature:** `sell()`

**Category:** business

**Description:** Sell the whole inventory at the base and return the money gained.

**Unlocked by:** unlocks with the **First Dig** achievement

### `inventory`

**Signature:** `inventory()`

**Category:** business

**Description:** Return the inventory as a dict of ore id to count.

**Unlocked by:** unlocks with the **Hello, Miner** achievement

### `scan`

**Signature:** `scan(radius)`

**Category:** mining

**Description:** Scan for ore within radius tiles. Returns a list of (dx, dy, ore_id) for non-empty tiles.

**Unlocked by:** unlocks with the **Scout** achievement

### `stats`

**Signature:** `stats()`

**Category:** mining

**Description:** Return per-ore mining statistics as {ore: {'attempts': n, 'successes': m}}.

**Unlocked by:** unlocks with the **Data Driven** achievement

### `buy_upgrade`

**Signature:** `buy_upgrade(upgrade_id)`

**Category:** business

**Description:** Buy the next level of the given upgrade and return the new level.

**Unlocked by:** unlocks with the **First Sale** achievement

## minerlib helper module

`minerlib` is a pure-Python helper module importable by player scripts. The primitive API functions (`move`, `mine`, `peek`, `position`) are injected by the runner; the helpers below are implemented in `src/digscript/runner/minerlib.py`.

### `minerlib.goto`

Move the miner to ``(x, y)``, one tile at a time.

Moves horizontally first (east/west), then vertically
(south/north), until ``position() == (x, y)``.

### `minerlib.go_home`

Move the miner back to the base at ``(0, 0)``.

### `minerlib.sweep`

Yield positions in serpentine (boustrophedon) order.

Yields ``(x, y)`` for ``y`` in ``range(height)``; even rows go
left-to-right (``x`` in ``range(width)``) and odd rows go
right-to-left, so consecutive positions are always adjacent.

### `minerlib.spiral`

Yield positions in an infinite square spiral from ``(0, 0)``.

Starts at ``(0, 0)`` and spirals outwards (east, south, west,
north, ...) with segment lengths 1, 1, 2, 2, 3, 3, ... so the
first positions are ``(0, 0)``, ``(1, 0)``, ``(1, 1)``,
``(0, 1)``, ``(-1, 1)``, ... The generator never ends.

### `minerlib.mine_here`

Mine the current tile if it holds a known ore.

Peeks at the current tile first; if :func:`peek` returns an ore
id (not ``None`` and not ``'unknown'``), calls :func:`mine` and
returns its result. Otherwise returns ``None`` without mining.

## Standard library modules

Player scripts may import the standard-library modules below once the required achievement is unlocked. All other imports are blocked.

| Module | Unlocked by |
|---|---|
| `math` | available from the start |
| `random` | unlocks with the **Wanderer** achievement |
| `statistics` | unlocks with the **Data Driven** achievement |
| `collections` | unlocks with the **Your Own Function** achievement |
| `heapq` | unlocks with the **Your Own Function** achievement |

## Safety

Player scripts run in a separate subprocess with a restricted namespace. This is **not** a security sandbox: only run scripts you trust.
