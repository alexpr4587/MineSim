# DigScript API

DigScript exposes a small, deterministic API to player scripts. The game process never executes player code; scripts run in a separate subprocess started by `digscript.scripting.host`. See the README for the safety note.

## Player API functions

Functions are called directly, e.g. `move(East)`, `mine()`, `sell()`. Locked functions raise `NotUnlockedError` until the required achievement is unlocked.

| Function | Signature | Description | Cost | Example | Unlocked by |
|---|---|---|---|---|---|
| `move` | `move(direction)` | Move one tile in the given direction. | 4 ticks (less with the motor upgrade) | `move(East)` | available from the start |
| `mine` | `mine()` | Mine the tile the miner stands on. Returns a dict with ok, and reason or ore when relevant. | ceil(hardness * 3 / tool power) ticks | `result = mine()` | available from the start |
| `peek` | `peek()` | Return the ore on the current tile, None if empty, or 'unknown' if the ore is locked. | 0 ticks | `ore = peek()` | available from the start |
| `position` | `position()` | Return the miner position as (x, y). | 0 ticks | `x, y = position()` | available from the start |
| `sell` | `sell()` | Sell the whole inventory at the base and return the money gained. | 2 ticks at the base | `earned = sell()` | unlocks with the **First Dig** achievement |
| `inventory` | `inventory()` | Return the inventory as a dict of ore id to count. | 0 ticks | `items = inventory()` | unlocks with the **Hello, Miner** achievement |
| `scan` | `scan(radius)` | Scan for ore within radius tiles. Returns a list of (dx, dy, ore_id) for non-empty tiles. | 1 + radius ticks (radius capped by the scanner) | `for dx, dy, ore in scan(2): ...` | unlocks with the **Scout** achievement |
| `stats` | `stats()` | Return per-ore mining statistics as {ore: {'attempts': n, 'successes': m}}. | 0 ticks | `stats()['stone']` | unlocks with the **Data Driven** achievement |
| `buy_upgrade` | `buy_upgrade(upgrade_id)` | Buy the next level of the given upgrade and return the new level. | 0 ticks | `buy_upgrade('backpack')` | unlocks with the **First Sale** achievement |
| `wait` | `wait(ticks)` | Wait for ticks (1 to 600) without doing anything else. | as many ticks as requested (1-600) | `wait(20)` | available from the start |
| `tick` | `tick()` | Return the current game tick. | 0 ticks | `now = tick()` | available from the start |
| `distance` | `distance()` | Return the Chebyshev distance from the base at (0, 0). | 0 ticks | `d = distance()` | available from the start |
| `biome` | `biome()` | Return the id of the biome under the miner. | 0 ticks | `here = biome()` | available from the start |
| `ore_info` | `ore_info(ore_id)` | Return {id, name, tier, hardness, base_value, regen_ticks} for a known ore, or None when it is unknown or locked. The mining probability is never included. | 0 ticks | `info = ore_info('coal')` | available from the start |
| `inspect` | `inspect()` | Return {ore, mineable, reason, regrows_in} for the current tile. | 0 ticks | `seen = inspect()` | available from the start |
| `submit_estimate` | `submit_estimate(ore_id, p)` | Submit an estimate p for the mining probability of an ore after at least 100 attempts. Allows three submissions per ore and returns {ok, close}. | 0 ticks | `submit_estimate('coal', 0.9)` | available from the start |

### `move`

**Signature:** `move(direction)`

**Category:** movement

**Description:** Move one tile in the given direction.

**Cost:** 4 ticks (less with the motor upgrade)

**Example:**

```python
move(East)
```

**Unlocked by:** available from the start

### `mine`

**Signature:** `mine()`

**Category:** mining

**Description:** Mine the tile the miner stands on. Returns a dict with ok, and reason or ore when relevant.

**Cost:** ceil(hardness * 3 / tool power) ticks

**Example:**

```python
result = mine()
```

**Unlocked by:** available from the start

### `peek`

**Signature:** `peek()`

**Category:** mining

**Description:** Return the ore on the current tile, None if empty, or 'unknown' if the ore is locked.

**Cost:** 0 ticks

**Example:**

```python
ore = peek()
```

**Unlocked by:** available from the start

### `position`

**Signature:** `position()`

**Category:** movement

**Description:** Return the miner position as (x, y).

**Cost:** 0 ticks

**Example:**

```python
x, y = position()
```

**Unlocked by:** available from the start

### `sell`

**Signature:** `sell()`

**Category:** business

**Description:** Sell the whole inventory at the base and return the money gained.

**Cost:** 2 ticks at the base

**Example:**

```python
earned = sell()
```

**Unlocked by:** unlocks with the **First Dig** achievement

### `inventory`

**Signature:** `inventory()`

**Category:** business

**Description:** Return the inventory as a dict of ore id to count.

**Cost:** 0 ticks

**Example:**

```python
items = inventory()
```

**Unlocked by:** unlocks with the **Hello, Miner** achievement

### `scan`

**Signature:** `scan(radius)`

**Category:** mining

**Description:** Scan for ore within radius tiles. Returns a list of (dx, dy, ore_id) for non-empty tiles.

**Cost:** 1 + radius ticks (radius capped by the scanner)

**Example:**

```python
for dx, dy, ore in scan(2): ...
```

**Unlocked by:** unlocks with the **Scout** achievement

### `stats`

**Signature:** `stats()`

**Category:** mining

**Description:** Return per-ore mining statistics as {ore: {'attempts': n, 'successes': m}}.

**Cost:** 0 ticks

**Example:**

```python
stats()['stone']
```

**Unlocked by:** unlocks with the **Data Driven** achievement

### `buy_upgrade`

**Signature:** `buy_upgrade(upgrade_id)`

**Category:** business

**Description:** Buy the next level of the given upgrade and return the new level.

**Cost:** 0 ticks

**Example:**

```python
buy_upgrade('backpack')
```

**Unlocked by:** unlocks with the **First Sale** achievement

### `wait`

**Signature:** `wait(ticks)`

**Category:** timing

**Description:** Wait for ticks (1 to 600) without doing anything else.

**Cost:** as many ticks as requested (1-600)

**Example:**

```python
wait(20)
```

**Unlocked by:** available from the start

### `tick`

**Signature:** `tick()`

**Category:** timing

**Description:** Return the current game tick.

**Cost:** 0 ticks

**Example:**

```python
now = tick()
```

**Unlocked by:** available from the start

### `distance`

**Signature:** `distance()`

**Category:** movement

**Description:** Return the Chebyshev distance from the base at (0, 0).

**Cost:** 0 ticks

**Example:**

```python
d = distance()
```

**Unlocked by:** available from the start

### `biome`

**Signature:** `biome()`

**Category:** world

**Description:** Return the id of the biome under the miner.

**Cost:** 0 ticks

**Example:**

```python
here = biome()
```

**Unlocked by:** available from the start

### `ore_info`

**Signature:** `ore_info(ore_id)`

**Category:** mining

**Description:** Return {id, name, tier, hardness, base_value, regen_ticks} for a known ore, or None when it is unknown or locked. The mining probability is never included.

**Cost:** 0 ticks

**Example:**

```python
info = ore_info('coal')
```

**Unlocked by:** available from the start

### `inspect`

**Signature:** `inspect()`

**Category:** mining

**Description:** Return {ore, mineable, reason, regrows_in} for the current tile.

**Cost:** 0 ticks

**Example:**

```python
seen = inspect()
```

**Unlocked by:** available from the start

### `submit_estimate`

**Signature:** `submit_estimate(ore_id, p)`

**Category:** data

**Description:** Submit an estimate p for the mining probability of an ore after at least 100 attempts. Allows three submissions per ore and returns {ok, close}.

**Cost:** 0 ticks

**Example:**

```python
submit_estimate('coal', 0.9)
```

**Unlocked by:** available from the start

## minerlib helper module

`minerlib` is a pure-Python helper module importable by player scripts. The primitive API functions (`move`, `mine`, `peek`, `position`) are injected by the runner; the helpers below are implemented in `src/digscript/runner/minerlib.py`.

### `minerlib.goto`

Move the miner to ``(x, y)``, one tile at a time.

Example::

goto(start_x + 3, start_y)

### `minerlib.go_home`

Move the miner back to the base at ``(0, 0)``.

Example::

go_home()

### `minerlib.sweep`

Yield positions in serpentine (boustrophedon) order.

Yields ``(x, y)`` for ``y`` in ``range(height)``; even rows go
left-to-right (``x`` in ``range(width)``) and odd rows go
right-to-left, so consecutive positions are always adjacent.

Example::

for dx, dy in sweep(3, 2):
        print(dx, dy)

### `minerlib.spiral`

Yield positions in an infinite square spiral from ``(0, 0)``.

Starts at ``(0, 0)`` and spirals outwards (east, south, west,
north, ...) with segment lengths 1, 1, 2, 2, 3, 3, ... so the
first positions are ``(0, 0)``, ``(1, 0)``, ``(1, 1)``,
``(0, 1)``, ``(-1, 1)``, ... The generator never ends.

Example::

for dx, dy in spiral():
        print(dx, dy)

### `minerlib.ring`

Yield the offsets on the square ring of Chebyshev radius ``radius``.

The offsets are relative to the miner's starting point (``(0, 0)``
when used with :func:`goto`). ``ring(0)`` yields just ``(0, 0)``;
``ring(1)`` yields the eight surrounding tiles.

Example::

start_x, start_y = position()
    for dx, dy in ring(2):
        goto(start_x + dx, start_y + dy)

### `minerlib.nearest`

Return the nearest ``(dx, dy)`` offset of ``ore`` via :func:`scan`.

``radius`` defaults to the whole scan area (the engine caps it to
the miner's scanner). Ties are broken deterministically by
Chebyshev distance, then Manhattan distance, then ``(dy, dx)``.
Returns ``None`` when the ore is not in range.

Example::

offset = nearest("coal")
    if offset is not None:
        print("coal at", offset)

### `minerlib.goto_nearest`

Walk to the nearest tile of ``ore``; return ``True`` when found.

Example::

if goto_nearest("stone"):
        mine()

### `minerlib.mine_here`

Mine the current tile if it holds a known ore.

Peeks at the current tile first; if :func:`peek` returns an ore
id (not ``None`` and not ``'unknown'``), calls :func:`mine` and
returns its result. Otherwise returns ``None`` without mining.

Example::

result = mine_here()

### `minerlib.mine_until`

Mine the current tile until ``n`` successes or it is exhausted.

Returns the number of successful mines. A miss keeps trying; an
empty, locked, too-hard or full-inventory tile stops the loop.

Example::

successes = mine_until(3)

### `minerlib.haul`

Go home, sell the inventory, return to the previous spot, return money.

Example::

earned = haul()

### `minerlib.farm`

Sweep outward mining only ``ore`` and hauling when the bag is full.

Visits at most ``max_tiles`` positions of a square spiral around the
starting point and returns the number of mined items. The miner
ends back on the last visited tile.

Example::

mined = farm("coal", max_tiles=50)
    print("mined", mined)

### `minerlib.Samples`

A tiny tally for mining attempts. `add(ore, success)` records an attempt, `count(ore)` returns attempts, `rate(ore)` returns the observed success rate and `summary()` returns attempts, successes and rates per ore.

```python
samples = minerlib.Samples()
samples.add("stone", True)
print(samples.rate("stone"))
```

## Standard library modules

Player scripts may import the standard-library modules below once the required achievement is unlocked. All other imports are blocked.

| Module | Unlocked by |
|---|---|
| `math` | available from the start |
| `random` | unlocks with the **Wanderer** achievement |
| `statistics` | unlocks with the **Data Driven** achievement |
| `collections` | unlocks with the **Your Own Function** achievement |
| `heapq` | unlocks with the **Your Own Function** achievement |
| `itertools` | available from the start |
| `functools` | available from the start |
| `dataclasses` | available from the start |
| `typing` | available from the start |

## Safety

Player scripts run in a separate subprocess with a restricted namespace. This is **not** a security sandbox: only run scripts you trust.
