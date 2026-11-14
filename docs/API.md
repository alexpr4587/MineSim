# MineSim API

MineSim exposes a small, deterministic API to player scripts. The game process never executes player code; scripts run in a separate subprocess started by `minesim.scripting.host`. See the README for the safety note.

## Player API functions

Functions are called directly, e.g. `move(East)`, `mine()`, `sell()`. Locked functions raise `NotUnlockedError` until the required achievement is unlocked.

| Function | Signature | Description | Cost | Example | Unlocked by |
|---|---|---|---|---|---|
| `move` | `move(direction)` | Move one tile in the given direction. | 4 ticks (less with the motor upgrade) | `move(East)` | available from the start |
| `mine` | `mine()` | Mine the tile the miner stands on. Returns a dict with ok, and reason or ore when relevant. | ceil(hardness * 3 / tool power) ticks | `result = mine()` | available from the start |
| `peek` | `peek()` | Return the ore on the current tile, None if empty, or 'unknown' if the ore is locked. | 0 ticks | `ore = peek()` | available from the start |
| `position` | `position()` | Return the miner position as (x, y). | 0 ticks | `x, y = position()` | available from the start |
| `sell` | `sell()` | Sell the whole inventory at the base and return the money gained. | 2 ticks at the base | `earned = sell()` | unlocks with the **First Dig** achievement |
| `unload` | `unload()` | Move the drone inventory into the base warehouse and return {moved, left}. | 1 tick at the base | `result = unload()` | available from the start |
| `stock` | `stock()` | Return the warehouse contents and capacity as {items, capacity, used, free}. | 0 ticks | `stock()['items']` | available from the start |
| `sell_stock` | `sell_stock(item, amount=None)` | Sell items from the warehouse at market prices and return the money gained. | 2 ticks at the base | `earned = sell_stock('stone', 10)` | available from the start |
| `price` | `price(item)` | Return the current market price of an unlocked item, or None. | 0 ticks | `price('stone')` | available from the start |
| `prices` | `prices()` | Return a dict of current market prices for every unlocked item. | 0 ticks | `prices()['stone']` | available from the start |
| `price_history` | `price_history(item, n=50)` | Return up to n recent price samples for an unlocked item, or None. | 0 ticks | `price_history('stone', 20)` | available from the start |
| `inventory` | `inventory()` | Return the inventory as a dict of ore id to count. | 0 ticks | `items = inventory()` | unlocks with the **Hello, Miner** achievement |
| `scan` | `scan(radius)` | Scan for ore within radius tiles. Returns a list of (dx, dy, ore_id) for non-empty tiles. | 1 + radius ticks (radius capped by the scanner) | `for dx, dy, ore in scan(2): ...` | unlocks with the **Scout** achievement |
| `stats` | `stats()` | Return per-ore mining statistics as {ore: {'attempts': n, 'successes': m}}. | 0 ticks | `stats()['stone']` | unlocks with the **Data Driven** achievement |
| `buy_upgrade` | `buy_upgrade(upgrade_id)` | Buy the next level of the given upgrade and return the new level. | 0 ticks | `buy_upgrade('backpack')` | unlocks with the **First Sale** achievement |
| `wait` | `wait(ticks)` | Wait for ticks (1 to 600) without doing anything else. | as many ticks as requested (1-600) | `wait(20)` | unlocks with the **Patience** achievement |
| `tick` | `tick()` | Return the current game tick. | 0 ticks | `now = tick()` | unlocks with the **Clockwork** achievement |
| `distance` | `distance()` | Return the Chebyshev distance from the base at (0, 0). | 0 ticks | `d = distance()` | unlocks with the **Far From Home** achievement |
| `biome` | `biome()` | Return the id of the biome under the miner. | 0 ticks | `here = biome()` | unlocks with the **Deep Diver** achievement |
| `ore_info` | `ore_info(ore_id)` | Return {id, name, tier, hardness, base_value, regen_ticks} for a known ore, or None when it is unknown or locked. The mining probability is never included. | 0 ticks | `info = ore_info('coal')` | unlocks with the **Appraiser** achievement |
| `inspect` | `inspect()` | Return {ore, mineable, reason, regrows_in} for the current tile. | 0 ticks | `seen = inspect()` | unlocks with the **Know Your Limits** achievement |
| `submit_estimate` | `submit_estimate(ore_id, p)` | Submit an estimate p for the mining probability of an ore after at least 100 attempts. Allows three submissions per ore and returns {ok, close}. | 0 ticks | `submit_estimate('coal', 0.9)` | unlocks with the **Sampler** achievement |
| `recipes` | `recipes()` | Return {recipe_id: {id, name, inputs, outputs, ticks, unlocked, unlocked_by}} for every refinery recipe. | 0 ticks | `bars = recipes()` | available from the start |
| `refine` | `refine(recipe_id, times=1)` | Start a refinery job at the base. The inputs are consumed immediately; returns {ok, recipe, times, duration, finish_tick}. | 2 ticks | `refine('copper_bar', 2)` | available from the start |
| `refinery` | `refinery()` | Return the running refinery jobs as a list of {recipe, times, ticks_left, progress, blocked, outputs}. | 0 ticks | `jobs = refinery()` | available from the start |
| `contracts` | `contracts()` | Return the open delivery contracts as a list of {id, item, quantity, reward, deadline, ticks_left}. | 0 ticks | `board = contracts()` | available from the start |
| `deliver` | `deliver(contract_id)` | Deliver a contract from the warehouse at the base and return the reward money. | 2 ticks | `paid = deliver(cid)` | available from the start |

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

### `unload`

**Signature:** `unload()`

**Category:** business

**Description:** Move the drone inventory into the base warehouse and return {moved, left}.

**Cost:** 1 tick at the base

**Example:**

```python
result = unload()
```

**Unlocked by:** available from the start

### `stock`

**Signature:** `stock()`

**Category:** business

**Description:** Return the warehouse contents and capacity as {items, capacity, used, free}.

**Cost:** 0 ticks

**Example:**

```python
stock()['items']
```

**Unlocked by:** available from the start

### `sell_stock`

**Signature:** `sell_stock(item, amount=None)`

**Category:** business

**Description:** Sell items from the warehouse at market prices and return the money gained.

**Cost:** 2 ticks at the base

**Example:**

```python
earned = sell_stock('stone', 10)
```

**Unlocked by:** available from the start

### `price`

**Signature:** `price(item)`

**Category:** market

**Description:** Return the current market price of an unlocked item, or None.

**Cost:** 0 ticks

**Example:**

```python
price('stone')
```

**Unlocked by:** available from the start

### `prices`

**Signature:** `prices()`

**Category:** market

**Description:** Return a dict of current market prices for every unlocked item.

**Cost:** 0 ticks

**Example:**

```python
prices()['stone']
```

**Unlocked by:** available from the start

### `price_history`

**Signature:** `price_history(item, n=50)`

**Category:** market

**Description:** Return up to n recent price samples for an unlocked item, or None.

**Cost:** 0 ticks

**Example:**

```python
price_history('stone', 20)
```

**Unlocked by:** available from the start

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

**Unlocked by:** unlocks with the **Patience** achievement

### `tick`

**Signature:** `tick()`

**Category:** timing

**Description:** Return the current game tick.

**Cost:** 0 ticks

**Example:**

```python
now = tick()
```

**Unlocked by:** unlocks with the **Clockwork** achievement

### `distance`

**Signature:** `distance()`

**Category:** movement

**Description:** Return the Chebyshev distance from the base at (0, 0).

**Cost:** 0 ticks

**Example:**

```python
d = distance()
```

**Unlocked by:** unlocks with the **Far From Home** achievement

### `biome`

**Signature:** `biome()`

**Category:** world

**Description:** Return the id of the biome under the miner.

**Cost:** 0 ticks

**Example:**

```python
here = biome()
```

**Unlocked by:** unlocks with the **Deep Diver** achievement

### `ore_info`

**Signature:** `ore_info(ore_id)`

**Category:** mining

**Description:** Return {id, name, tier, hardness, base_value, regen_ticks} for a known ore, or None when it is unknown or locked. The mining probability is never included.

**Cost:** 0 ticks

**Example:**

```python
info = ore_info('coal')
```

**Unlocked by:** unlocks with the **Appraiser** achievement

### `inspect`

**Signature:** `inspect()`

**Category:** mining

**Description:** Return {ore, mineable, reason, regrows_in} for the current tile.

**Cost:** 0 ticks

**Example:**

```python
seen = inspect()
```

**Unlocked by:** unlocks with the **Know Your Limits** achievement

### `submit_estimate`

**Signature:** `submit_estimate(ore_id, p)`

**Category:** data

**Description:** Submit an estimate p for the mining probability of an ore after at least 100 attempts. Allows three submissions per ore and returns {ok, close}.

**Cost:** 0 ticks

**Example:**

```python
submit_estimate('coal', 0.9)
```

**Unlocked by:** unlocks with the **Sampler** achievement

### `recipes`

**Signature:** `recipes()`

**Category:** business

**Description:** Return {recipe_id: {id, name, inputs, outputs, ticks, unlocked, unlocked_by}} for every refinery recipe.

**Cost:** 0 ticks

**Example:**

```python
bars = recipes()
```

**Unlocked by:** available from the start

### `refine`

**Signature:** `refine(recipe_id, times=1)`

**Category:** business

**Description:** Start a refinery job at the base. The inputs are consumed immediately; returns {ok, recipe, times, duration, finish_tick}.

**Cost:** 2 ticks

**Example:**

```python
refine('copper_bar', 2)
```

**Unlocked by:** available from the start

### `refinery`

**Signature:** `refinery()`

**Category:** business

**Description:** Return the running refinery jobs as a list of {recipe, times, ticks_left, progress, blocked, outputs}.

**Cost:** 0 ticks

**Example:**

```python
jobs = refinery()
```

**Unlocked by:** available from the start

### `contracts`

**Signature:** `contracts()`

**Category:** business

**Description:** Return the open delivery contracts as a list of {id, item, quantity, reward, deadline, ticks_left}.

**Cost:** 0 ticks

**Example:**

```python
board = contracts()
```

**Unlocked by:** available from the start

### `deliver`

**Signature:** `deliver(contract_id)`

**Category:** business

**Description:** Deliver a contract from the warehouse at the base and return the reward money.

**Cost:** 2 ticks

**Example:**

```python
paid = deliver(cid)
```

**Unlocked by:** available from the start

## minerlib helper module

`minerlib` is a pure-Python helper module importable by player scripts. The primitive API functions (`move`, `mine`, `peek`, `position`) are injected by the runner; the helpers below are implemented in `src/minesim/runner/minerlib.py`.

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
| `itertools` | unlocks with the **Bring Your Tools** achievement |
| `functools` | unlocks with the **One-Liner** achievement |
| `dataclasses` | unlocks with the **Object Oriented** achievement |
| `typing` | unlocks with the **Safe Hands** achievement |

## Safety

Player scripts run in a separate subprocess with a restricted namespace. This is **not** a security sandbox: only run scripts you trust.
