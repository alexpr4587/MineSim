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
| `battery` | `battery()` | Return the miner battery as (energy, capacity). | 0 ticks | `energy, capacity = battery()` | unlocks with the **Out of Juice** achievement |
| `charge` | `charge()` | Recharge the battery on a base or shaft station and return {ok, energy, capacity, charged}. | ceil(missing energy / charge rate) ticks | `charge()` | unlocks with the **Out of Juice** achievement |
| `energy_cost` | `energy_cost(action, arg=None)` | Return the energy an action would cost right now. For 'scan', arg is the radius; for 'mine' the ore under the miner is used. | 0 ticks | `energy_cost('mine')` | unlocks with the **Out of Juice** achievement |
| `temperature` | `temperature()` | Return the miner temperature as {ok, temperature, overheated, cooldown, layer, heat}. | 0 ticks | `temperature()['temperature']` | unlocks with the **Feel the Heat** achievement |
| `cool` | `cool(target=30)` | Cool down on a base or shaft station until the temperature reaches target. | ceil((temperature - target) / cool rate) ticks | `cool(30)` | unlocks with the **Feel the Heat** achievement |
| `climate` | `climate()` | Return the layer climate as {layer, heat, airflow, miners_in_hot_layers, overload}. | 0 ticks | `climate()['airflow']` | unlocks with the **Feel the Heat** achievement |
| `sell` | `sell()` | Sell the whole inventory at the base and return the money gained. Waits for the shared surface dock. | ceil(units / dock rate) ticks at the base | `earned = sell()` | unlocks with the **First Dig** achievement |
| `unload` | `unload()` | Move the miner inventory into the base warehouse and return {moved, left}. Waits for the shared surface dock. | ceil(units / dock rate) ticks at the base | `result = unload()` | unlocks with the **Storage Unit** achievement |
| `dock_free` | `dock_free()` | Return the surface dock status as {free, queue, eta}. | 0 ticks | `status = dock_free()` | unlocks with the **Traffic Jam** achievement |
| `dock_rate` | `dock_rate()` | Return how many inventory units the surface dock services per tick. | 0 ticks | `rate = dock_rate()` | unlocks with the **Traffic Jam** achievement |
| `stock` | `stock()` | Return the warehouse contents and capacity as {items, capacity, used, free}. | 0 ticks | `stock()['items']` | unlocks with the **Storage Unit** achievement |
| `sell_stock` | `sell_stock(item, amount=None)` | Sell items from the warehouse at market prices and return the money gained. | 2 ticks at the base | `earned = sell_stock('stone', 10)` | unlocks with the **Storage Unit** achievement |
| `price` | `price(item)` | Return the current market price of an unlocked item, or None. | 0 ticks | `price('stone')` | unlocks with the **Market Watcher** achievement |
| `prices` | `prices()` | Return a dict of current market prices for every unlocked item. | 0 ticks | `prices()['stone']` | unlocks with the **Market Watcher** achievement |
| `price_history` | `price_history(item, n=50)` | Return up to n recent price samples for an unlocked item, or None. | 0 ticks | `price_history('stone', 20)` | unlocks with the **Chartist** achievement |
| `inventory` | `inventory()` | Return the inventory as a dict of ore id to count. | 0 ticks | `items = inventory()` | unlocks with the **Hello, Miner** achievement |
| `scan` | `scan(radius)` | Scan for ore within radius tiles. Returns a list of (dx, dy, ore_id) for non-empty tiles. | 1 + radius ticks (radius capped by the scanner) | `for dx, dy, ore in scan(2): ...` | unlocks with the **Scout** achievement |
| `stats` | `stats()` | Return per-ore mining statistics as {ore: {'attempts': n, 'successes': m}}. | 0 ticks | `stats()['stone']` | unlocks with the **Data Driven** achievement |
| `buy_upgrade` | `buy_upgrade(upgrade_id)` | Buy the next level of the given upgrade and return the new level. | 0 ticks | `buy_upgrade('backpack')` | unlocks with the **First Sale** achievement |
| `wait` | `wait(ticks)` | Wait for ticks (1 to 600) without doing anything else. | as many ticks as requested (1-600) | `wait(20)` | unlocks with the **Patience** achievement |
| `tick` | `tick()` | Return the current game tick. | 0 ticks | `now = tick()` | unlocks with the **Clockwork** achievement |
| `events` | `events()` | Return the active world events as dicts with kind, x, y, radius, ends_in, item and direction ('shortage' or 'glut' for market news). The exact price factor is never included. | 0 ticks | `for event in events(): print(event['kind'])` | unlocks with the **News Reader** achievement |
| `distance` | `distance()` | Return the Chebyshev distance from the base at (0, 0). | 0 ticks | `d = distance()` | unlocks with the **Far From Home** achievement |
| `layer` | `layer()` | Return the index of the layer the miner is on (0 is the surface). | 0 ticks | `here = layer()` | unlocks with the **Deep Ambition** achievement |
| `layers` | `layers()` | Return the underground layers as a list of {index, name, accessible} dicts. | 0 ticks | `for level in layers(): print(level['name'])` | unlocks with the **Deep Ambition** achievement |
| `descend` | `descend()` | Descend one layer from a shaft station. Requires a deep enough shaft upgrade and returns {ok, layer, reason}. | 20 ticks | `result = descend()` | unlocks with the **Deep Ambition** achievement |
| `ascend` | `ascend()` | Ascend one layer from a shaft station and return {ok, layer, reason}. | 20 ticks | `result = ascend()` | unlocks with the **Deep Ambition** achievement |
| `biome` | `biome()` | Return the id of the biome under the miner. | 0 ticks | `here = biome()` | unlocks with the **Deep Diver** achievement |
| `ore_info` | `ore_info(ore_id)` | Return {id, name, tier, hardness, base_value, regen_ticks} for a known ore, or None when it is unknown or locked. The mining probability is never included. | 0 ticks | `info = ore_info('coal')` | unlocks with the **Appraiser** achievement |
| `inspect` | `inspect()` | Return {ore, mineable, reason, regrows_in} for the current tile. | 0 ticks | `seen = inspect()` | unlocks with the **Know Your Limits** achievement |
| `submit_estimate` | `submit_estimate(ore_id, p)` | Submit an estimate p for the mining probability of an ore after at least 100 attempts. Allows three submissions per ore and returns {ok, close}. | 0 ticks | `submit_estimate('coal', 0.9)` | unlocks with the **Sampler** achievement |
| `recipes` | `recipes()` | Return {recipe_id: {id, name, inputs, outputs, ticks, unlocked, unlocked_by}} for every refinery recipe. | 0 ticks | `bars = recipes()` | unlocks with the **Smelter** achievement |
| `refine` | `refine(recipe_id, times=1)` | Start a refinery job at the base. The inputs are consumed immediately; returns {ok, recipe, times, duration, finish_tick}. | 2 ticks | `refine('copper_bar', 2)` | unlocks with the **Smelter** achievement |
| `refinery` | `refinery()` | Return the running refinery jobs as a list of {recipe, times, ticks_left, progress, blocked, outputs}. | 0 ticks | `jobs = refinery()` | unlocks with the **Smelter** achievement |
| `contracts` | `contracts()` | Return the open delivery contracts as a list of {id, item, quantity, reward, deadline, ticks_left}. | 0 ticks | `board = contracts()` | unlocks with the **First Order** achievement |
| `deliver` | `deliver(contract_id)` | Deliver a contract from the warehouse at the base and return the reward money. | 2 ticks | `paid = deliver(cid)` | unlocks with the **First Order** achievement |
| `miner_id` | `miner_id()` | Return the id of the miner running this script. | 0 ticks | `me = miner_id()` | unlocks with the **Second Pair of Hands** achievement |
| `miners` | `miners()` | Return the fleet as a list of {id, x, y, state, script, inventory_used} dicts. | 0 ticks | `for miner in miners(): print(miner['id'], miner['state'])` | unlocks with the **Second Pair of Hands** achievement |
| `spawn_miner` | `spawn_miner(script_name)` | Buy a miner on the base and start script_name (a .py file in the scripts folder). Returns the new miner id or {ok: False, reason}. | 5 ticks plus the next miner cost | `worker = spawn_miner('worker.py')` | unlocks with the **Second Pair of Hands** achievement |
| `kill_miner` | `kill_miner(miner_id)` | Stop the script of miner_id and remove that miner. Never removes miner 0. Returns True on success. | 0 ticks | `kill_miner(worker)` | unlocks with the **Second Pair of Hands** achievement |
| `assign` | `assign(miner_id, script_name)` | Stop the current script of miner_id and start script_name instead. | 0 ticks | `assign(1, 'hauler.py')` | unlocks with the **Second Pair of Hands** achievement |
| `shared_get` | `shared_get(key, default=None)` | Return the JSON value stored under key in the fleet-wide shared store, or default. | 0 ticks | `goal = shared_get('goal', 0)` | unlocks with the **Teamwork** achievement |
| `shared_set` | `shared_set(key, value)` | Store a JSON value under key in the fleet-wide shared store (max 64 keys, 40-character keys, 4 KB values). | 0 ticks | `shared_set('goal', 20)` | unlocks with the **Teamwork** achievement |

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

### `battery`

**Signature:** `battery()`

**Category:** energy

**Description:** Return the miner battery as (energy, capacity).

**Cost:** 0 ticks

**Example:**

```python
energy, capacity = battery()
```

**Unlocked by:** unlocks with the **Out of Juice** achievement

### `charge`

**Signature:** `charge()`

**Category:** energy

**Description:** Recharge the battery on a base or shaft station and return {ok, energy, capacity, charged}.

**Cost:** ceil(missing energy / charge rate) ticks

**Example:**

```python
charge()
```

**Unlocked by:** unlocks with the **Out of Juice** achievement

### `energy_cost`

**Signature:** `energy_cost(action, arg=None)`

**Category:** energy

**Description:** Return the energy an action would cost right now. For 'scan', arg is the radius; for 'mine' the ore under the miner is used.

**Cost:** 0 ticks

**Example:**

```python
energy_cost('mine')
```

**Unlocked by:** unlocks with the **Out of Juice** achievement

### `temperature`

**Signature:** `temperature()`

**Category:** climate

**Description:** Return the miner temperature as {ok, temperature, overheated, cooldown, layer, heat}.

**Cost:** 0 ticks

**Example:**

```python
temperature()['temperature']
```

**Unlocked by:** unlocks with the **Feel the Heat** achievement

### `cool`

**Signature:** `cool(target=30)`

**Category:** climate

**Description:** Cool down on a base or shaft station until the temperature reaches target.

**Cost:** ceil((temperature - target) / cool rate) ticks

**Example:**

```python
cool(30)
```

**Unlocked by:** unlocks with the **Feel the Heat** achievement

### `climate`

**Signature:** `climate()`

**Category:** climate

**Description:** Return the layer climate as {layer, heat, airflow, miners_in_hot_layers, overload}.

**Cost:** 0 ticks

**Example:**

```python
climate()['airflow']
```

**Unlocked by:** unlocks with the **Feel the Heat** achievement

### `sell`

**Signature:** `sell()`

**Category:** business

**Description:** Sell the whole inventory at the base and return the money gained. Waits for the shared surface dock.

**Cost:** ceil(units / dock rate) ticks at the base

**Example:**

```python
earned = sell()
```

**Unlocked by:** unlocks with the **First Dig** achievement

### `unload`

**Signature:** `unload()`

**Category:** business

**Description:** Move the miner inventory into the base warehouse and return {moved, left}. Waits for the shared surface dock.

**Cost:** ceil(units / dock rate) ticks at the base

**Example:**

```python
result = unload()
```

**Unlocked by:** unlocks with the **Storage Unit** achievement

### `dock_free`

**Signature:** `dock_free()`

**Category:** business

**Description:** Return the surface dock status as {free, queue, eta}.

**Cost:** 0 ticks

**Example:**

```python
status = dock_free()
```

**Unlocked by:** unlocks with the **Traffic Jam** achievement

### `dock_rate`

**Signature:** `dock_rate()`

**Category:** business

**Description:** Return how many inventory units the surface dock services per tick.

**Cost:** 0 ticks

**Example:**

```python
rate = dock_rate()
```

**Unlocked by:** unlocks with the **Traffic Jam** achievement

### `stock`

**Signature:** `stock()`

**Category:** business

**Description:** Return the warehouse contents and capacity as {items, capacity, used, free}.

**Cost:** 0 ticks

**Example:**

```python
stock()['items']
```

**Unlocked by:** unlocks with the **Storage Unit** achievement

### `sell_stock`

**Signature:** `sell_stock(item, amount=None)`

**Category:** business

**Description:** Sell items from the warehouse at market prices and return the money gained.

**Cost:** 2 ticks at the base

**Example:**

```python
earned = sell_stock('stone', 10)
```

**Unlocked by:** unlocks with the **Storage Unit** achievement

### `price`

**Signature:** `price(item)`

**Category:** market

**Description:** Return the current market price of an unlocked item, or None.

**Cost:** 0 ticks

**Example:**

```python
price('stone')
```

**Unlocked by:** unlocks with the **Market Watcher** achievement

### `prices`

**Signature:** `prices()`

**Category:** market

**Description:** Return a dict of current market prices for every unlocked item.

**Cost:** 0 ticks

**Example:**

```python
prices()['stone']
```

**Unlocked by:** unlocks with the **Market Watcher** achievement

### `price_history`

**Signature:** `price_history(item, n=50)`

**Category:** market

**Description:** Return up to n recent price samples for an unlocked item, or None.

**Cost:** 0 ticks

**Example:**

```python
price_history('stone', 20)
```

**Unlocked by:** unlocks with the **Chartist** achievement

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

### `events`

**Signature:** `events()`

**Category:** world

**Description:** Return the active world events as dicts with kind, x, y, radius, ends_in, item and direction ('shortage' or 'glut' for market news). The exact price factor is never included.

**Cost:** 0 ticks

**Example:**

```python
for event in events(): print(event['kind'])
```

**Unlocked by:** unlocks with the **News Reader** achievement

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

### `layer`

**Signature:** `layer()`

**Category:** world

**Description:** Return the index of the layer the miner is on (0 is the surface).

**Cost:** 0 ticks

**Example:**

```python
here = layer()
```

**Unlocked by:** unlocks with the **Deep Ambition** achievement

### `layers`

**Signature:** `layers()`

**Category:** world

**Description:** Return the underground layers as a list of {index, name, accessible} dicts.

**Cost:** 0 ticks

**Example:**

```python
for level in layers(): print(level['name'])
```

**Unlocked by:** unlocks with the **Deep Ambition** achievement

### `descend`

**Signature:** `descend()`

**Category:** movement

**Description:** Descend one layer from a shaft station. Requires a deep enough shaft upgrade and returns {ok, layer, reason}.

**Cost:** 20 ticks

**Example:**

```python
result = descend()
```

**Unlocked by:** unlocks with the **Deep Ambition** achievement

### `ascend`

**Signature:** `ascend()`

**Category:** movement

**Description:** Ascend one layer from a shaft station and return {ok, layer, reason}.

**Cost:** 20 ticks

**Example:**

```python
result = ascend()
```

**Unlocked by:** unlocks with the **Deep Ambition** achievement

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

**Unlocked by:** unlocks with the **Smelter** achievement

### `refine`

**Signature:** `refine(recipe_id, times=1)`

**Category:** business

**Description:** Start a refinery job at the base. The inputs are consumed immediately; returns {ok, recipe, times, duration, finish_tick}.

**Cost:** 2 ticks

**Example:**

```python
refine('copper_bar', 2)
```

**Unlocked by:** unlocks with the **Smelter** achievement

### `refinery`

**Signature:** `refinery()`

**Category:** business

**Description:** Return the running refinery jobs as a list of {recipe, times, ticks_left, progress, blocked, outputs}.

**Cost:** 0 ticks

**Example:**

```python
jobs = refinery()
```

**Unlocked by:** unlocks with the **Smelter** achievement

### `contracts`

**Signature:** `contracts()`

**Category:** business

**Description:** Return the open delivery contracts as a list of {id, item, quantity, reward, deadline, ticks_left}.

**Cost:** 0 ticks

**Example:**

```python
board = contracts()
```

**Unlocked by:** unlocks with the **First Order** achievement

### `deliver`

**Signature:** `deliver(contract_id)`

**Category:** business

**Description:** Deliver a contract from the warehouse at the base and return the reward money.

**Cost:** 2 ticks

**Example:**

```python
paid = deliver(cid)
```

**Unlocked by:** unlocks with the **First Order** achievement

### `miner_id`

**Signature:** `miner_id()`

**Category:** fleet

**Description:** Return the id of the miner running this script.

**Cost:** 0 ticks

**Example:**

```python
me = miner_id()
```

**Unlocked by:** unlocks with the **Second Pair of Hands** achievement

### `miners`

**Signature:** `miners()`

**Category:** fleet

**Description:** Return the fleet as a list of {id, x, y, state, script, inventory_used} dicts.

**Cost:** 0 ticks

**Example:**

```python
for miner in miners(): print(miner['id'], miner['state'])
```

**Unlocked by:** unlocks with the **Second Pair of Hands** achievement

### `spawn_miner`

**Signature:** `spawn_miner(script_name)`

**Category:** fleet

**Description:** Buy a miner on the base and start script_name (a .py file in the scripts folder). Returns the new miner id or {ok: False, reason}.

**Cost:** 5 ticks plus the next miner cost

**Example:**

```python
worker = spawn_miner('worker.py')
```

**Unlocked by:** unlocks with the **Second Pair of Hands** achievement

### `kill_miner`

**Signature:** `kill_miner(miner_id)`

**Category:** fleet

**Description:** Stop the script of miner_id and remove that miner. Never removes miner 0. Returns True on success.

**Cost:** 0 ticks

**Example:**

```python
kill_miner(worker)
```

**Unlocked by:** unlocks with the **Second Pair of Hands** achievement

### `assign`

**Signature:** `assign(miner_id, script_name)`

**Category:** fleet

**Description:** Stop the current script of miner_id and start script_name instead.

**Cost:** 0 ticks

**Example:**

```python
assign(1, 'hauler.py')
```

**Unlocked by:** unlocks with the **Second Pair of Hands** achievement

### `shared_get`

**Signature:** `shared_get(key, default=None)`

**Category:** fleet

**Description:** Return the JSON value stored under key in the fleet-wide shared store, or default.

**Cost:** 0 ticks

**Example:**

```python
goal = shared_get('goal', 0)
```

**Unlocked by:** unlocks with the **Teamwork** achievement

### `shared_set`

**Signature:** `shared_set(key, value)`

**Category:** fleet

**Description:** Store a JSON value under key in the fleet-wide shared store (max 64 keys, 40-character keys, 4 KB values).

**Cost:** 0 ticks

**Example:**

```python
shared_set('goal', 20)
```

**Unlocked by:** unlocks with the **Teamwork** achievement

## minerlib helper module

`minerlib` is a pure-Python helper module importable by player scripts. The primitive API functions (`move`, `mine`, `peek`, `position`) are injected by the runner; the helpers below are implemented in `src/minesim/runner/minerlib.py`.

### `minerlib.goto`

Move the miner to ``(x, y)``, one tile at a time.

The helper stops cleanly when the miner cannot continue (for
example because the battery is empty). Low-energy refusals are
retried once after a charge on a station.

Tick cost: one :func:`move` per tile.
Energy cost: the per-move energy of the current layer per tile.

Example::

if goto(start_x + 3, start_y):
        print("arrived")

### `minerlib.go_home`

Move the miner back to the base at ``(0, 0)``.

Tick cost: one :func:`move` per tile.
Energy cost: the per-move energy of the current layer per tile.

Example::

go_home()

### `minerlib.sweep`

Yield positions in serpentine (boustrophedon) order.

Yields ``(x, y)`` for ``y`` in ``range(height)``; even rows go
left-to-right (``x`` in ``range(width)``) and odd rows go
right-to-left, so consecutive positions are always adjacent. The
generator stops early when the known battery is empty.

Tick cost: 0 ticks (pure Python).
Energy cost: 0 energy.

Example::

for dx, dy in sweep(3, 2):
        print(dx, dy)

### `minerlib.spiral`

Yield positions in an infinite square spiral from ``(0, 0)``.

Starts at ``(0, 0)`` and spirals outwards (east, south, west,
north, ...) with segment lengths 1, 1, 2, 2, 3, 3, ... so the
first positions are ``(0, 0)``, ``(1, 0)``, ``(1, 1)``,
``(0, 1)``, ``(-1, 1)``, ... The generator stops early when the
known battery is empty, otherwise it never ends.

Tick cost: 0 ticks (pure Python).
Energy cost: 0 energy.

Example::

for dx, dy in spiral():
        print(dx, dy)

### `minerlib.ring`

Yield the offsets on the square ring of Chebyshev radius ``radius``.

The offsets are relative to the miner's starting point (``(0, 0)``
when used with :func:`goto`). ``ring(0)`` yields just ``(0, 0)``;
``ring(1)`` yields the eight surrounding tiles. The generator stops
early when the known battery is empty.

Tick cost: 0 ticks (pure Python).
Energy cost: 0 energy.

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
empty, locked, too-hard, full-inventory, low-energy or overheated
tile stops the loop cleanly.

Tick cost: the normal :func:`mine` cost per attempt.
Energy cost: the normal :func:`mine` energy per attempt.

Example::

successes = mine_until(3)

### `minerlib.haul`

Go home, sell the inventory, charge, then return to the previous spot.

The sale is skipped (but the trip still happens) when :func:`sell`
is locked; the helper then tries :func:`unload`. Charging happens
after selling, as the station is only left afterwards.

Tick cost: walking plus the normal :func:`sell` cost.
Energy cost: the per-move energy of the current layer per tile.

Example::

earned = haul()

### `minerlib.farm`

Sweep outward mining only ``ore`` and hauling when the bag is full.

Visits at most ``max_tiles`` positions of a square spiral around the
starting point and returns the number of mined items. The helper
stops cleanly when there is not enough energy left to return home.
The miner ends back on the last visited tile.

Tick cost: moving plus the normal :func:`mine` cost per attempt.
Energy cost: the per-move and per-mine energy of the current layer.

Example::

mined = farm("coal", max_tiles=50)
    print("mined", mined)

### `minerlib.route`

Return an A* route from the miner to ``(x, y)`` as direction names.

The search covers the rectangle between the miner and the target
plus a safety margin. Tiles inside a slow zone reported by
:func:`events` cost more, so the route goes around them when a
detour is shorter. Returned values can be passed straight to
:func:`move` (for example ``"east"``).

Tick cost: one :func:`move` per returned step (4 ticks per tile by
default, more inside slow zones).
Energy cost: the per-move energy of the current layer per step.

Example::

for direction in route(4, 0):
        move(direction)

### `minerlib.goto_route`

Walk to ``(x, y)`` using the slow-zone aware :func:`route`.

Stops cleanly and returns False when a move is refused or the
battery cannot pay for the next step.

Tick cost: one :func:`move` per route step.
Energy cost: the per-move energy of the current layer per step.

Example::

goto_route(10, -4)

### `minerlib.ore_map`

Return ``{(dx, dy): ore}`` for every ore in scanner range.

Offsets are relative to the miner. Locked ores appear as
``"unknown"``. Tick cost: the cost of :func:`scan` (1 + radius
ticks).

Example::

for offset, ore in ore_map(2).items():
        print(offset, ore)

### `minerlib.energy_to`

Return the energy needed to walk to ``(x, y)`` on this layer.

The value comes from the length of :func:`route` multiplied by the
current per-move energy cost. A miner on the target already needs
no energy.

Tick cost: 0 ticks (path planning only).
Energy cost: 0 energy (this is a query).

Example::

need = energy_to(10, 0)
    energy, capacity = battery()
    if energy >= need:
        goto(10, 0)

### `minerlib.can_return`

Return True when the battery can still carry the miner home.

``margin`` is a fraction of the trip energy kept as a safety
buffer (``0.1`` means ten percent). When :func:`battery` is locked
the helper assumes the miner can continue.

Tick cost: 0 ticks.
Energy cost: 0 energy (this is a query).

Example::

while can_return():
        mine_until(1)
    haul()

### `minerlib.charge_full`

Charge the battery fully on the current station.

Returns False when the miner is not on a station or :func:`charge`
is locked.

Tick cost: the normal :func:`charge` duration.
Energy cost: 0 energy.

Example::

go_home()
    charge_full()

### `minerlib.safe_farm`

Farm ``ore`` while always keeping enough energy to return home.

Before each tile the helper checks that the round trip fits in the
battery. When it does not, the miner returns to the station, charges
(and cools) and tries again. A full inventory is hauled first.

Tick cost: moving, mining, hauling and charging as needed.
Energy cost: the per-move and per-mine energy of the current layer.

Example::

mined = safe_farm("stone", max_tiles=60)
    print("mined", mined)

### `minerlib.to_station`

Walk to the station of the current layer at ``(0, 0)``.

Tick cost: one :func:`move` per tile.
Energy cost: the per-move energy of the current layer per tile.

Example::

if to_station():
        charge_full()

### `minerlib.go_down`

Descend ``n`` layers from shaft stations.

The miner walks to the station of its layer, charges when the shaft
ride would not fit in the battery and then descends. Returns False
when the shaft is too shallow or a station cannot be reached.

Tick cost: walking plus 20 ticks per shaft ride.
Energy cost: the per-move energy plus 15 energy per shaft ride.

Example::

go_down(2)

### `minerlib.go_up`

Ascend ``n`` layers from shaft stations.

Already being on the surface counts as success.

Tick cost: walking plus 20 ticks per shaft ride.
Energy cost: the per-move energy plus 15 energy per shaft ride.

Example::

go_up(1)

### `minerlib.dive`

Travel to ``layer`` and leave the caller standing on its station.

Layers above the current one use :func:`go_down`; layers below use
:func:`go_up`. Returns False when the target is not reachable.

Tick cost: walking plus 20 ticks per shaft ride.
Energy cost: the per-move energy plus 15 energy per shaft ride.

Example::

dive(2)
    print("now on layer", layer())

### `minerlib.cool_down`

Walk to the station and cool down to ``target`` temperature.

Tick cost: walking plus the normal :func:`cool` duration.
Energy cost: the per-move energy per tile.

Example::

cool_down(30)

### `minerlib.heat_budget`

Return a rough number of work ticks left before overheating.

With :func:`temperature` unlocked the estimate uses the current
temperature, the layer heat and the airflow overload. Without it
the helper returns ``1`` as a conservative one-tick budget.

Tick cost: 0 ticks.
Energy cost: 0 energy.

Example::

if heat_budget() < 20:
        cool_down(30)

### `minerlib.smart_unload`

Unload when the dock is free, otherwise wait with a stagger.

The wait before each retry is :func:`stagger` of the own miner id.
The helper returns the number of ticks it waited; when
:func:`dock_free` is locked it unloads immediately.

Tick cost: the wait ticks plus the normal :func:`unload` duration.
Energy cost: 0 energy.

Example::

waited = smart_unload()
    print("waited", waited, "ticks for the dock")

### `minerlib.stagger`

Return a small deterministic backoff for a miner id.

The values cycle between 1 and 4 ticks, so several miners do not
all knock on the dock in the same tick.

Tick cost: 0 ticks.
Energy cost: 0 energy.

Example::

wait(stagger(miner_id()))

### `minerlib.sma`

Return the simple moving average of the last ``n`` prices of ``item``.

Returns ``0.0`` when no price samples are available. Tick cost: 0
ticks.

Example::

average = sma("stone", 10)

### `minerlib.trend`

Return the least-squares slope of the last ``n`` prices of ``item``.

A positive value means prices are rising, a negative value means
they are falling and ``0.0`` means flat or not enough samples.
Tick cost: 0 ticks.

Example::

if trend("stone", 12) > 0:
        print("prices are rising")

### `minerlib.sell_if`

Sell all warehouse stock of ``item`` when its price index is high.

The price index is ``price(item) / base value``. When the base
value is not exposed (for example for an unfamiliar product), the
current price divided by its recent average is used instead. The
sale only happens at the base. Returns the money gained (``0`` when
the threshold is not met or there is no stock).

Tick cost: 2 ticks when a sale happens.

Example::

earned = sell_if("stone", 1.2)

### `minerlib.best_item_to_sell`

Return the stocked item with the highest price / base value.

Ties are broken by item id. Returns ``None`` when the warehouse is
empty or no stocked item has a usable price. Tick cost: 0 ticks.

Example::

item = best_item_to_sell()
    if item is not None:
        sell_stock(item)

### `minerlib.moving_average`

Return the simple moving average for every full window of ``n``.

Tick cost: 0 ticks (pure Python).

Example::

moving_average([1, 2, 3, 4], 2)  # [1.5, 2.5, 3.5]

### `minerlib.linear_fit`

Fit ``y = slope * x + intercept`` by least squares.

Mismatched lengths are truncated to the shorter sequence. Returns
``(0.0, 0.0)`` when there are fewer than two points or all ``x``
values are equal. Tick cost: 0 ticks (pure Python).

Example::

slope, intercept = linear_fit([0, 1, 2], [1, 3, 5])  # (2.0, 1.0)

### `minerlib.refine_all`

Start as many runs of ``recipe_id`` as the warehouse inputs allow.

At most one refinery job can be started per call, so the returned
count is the number of runs packed into the free furnace slot.
Returns ``0`` when there is no free slot or not enough input.

Tick cost: 2 ticks at the base, plus the normal refinery duration.

Example::

runs = refine_all("copper_bar")

### `minerlib.wait_for_refinery`

Wait until every running refinery job has finished.

Jobs that are blocked because the warehouse is full stop the wait,
so the helper never spins forever. Tick cost: the remaining job
time (through :func:`wait`).

Example::

refine_all("copper_bar")
    wait_for_refinery()

### `minerlib.best_contract`

Return the contract with the best reward per base value in stock.

Only contracts whose quantity is already in the warehouse are
considered. The score is ``reward / (quantity * base_value)`` (the
premium paid per unit of base value); ties are broken by contract
id. Returns ``None`` when nothing can be delivered right now.

Tick cost: 0 ticks.

Example::

contract = best_contract()
    if contract is not None:
        deliver(contract["id"])

### `minerlib.fulfill`

Fetch or refine what a contract is missing, then deliver it.

The helper first unloads the current inventory at the base. Missing
ore is mined; missing products are refined from the first recipe
that outputs them. Refining and mining are skipped when the inputs
or reachable ore are not available. Returns the reward money, or
``0`` when the contract could not be completed.

Tick cost: 2 ticks to deliver plus the mining, moving and refining
work needed for the missing items.

Example::

contract = best_contract()
    if contract is not None:
        earned = fulfill(contract["id"])

### `minerlib.Forecast`

Simple exponential smoothing for one price series.

``alpha`` controls how quickly the forecast follows new samples
(0 < alpha <= 1). ``update(x)`` feeds one sample and ``predict()``
returns the current smoothed level. Tick cost: 0 ticks.

Example::

forecast = Forecast(alpha=0.5)
    for sample in price_history("stone", 10) or []:
        forecast.update(sample)
    print(forecast.predict())

### `minerlib.Worker`

Base class for fleet workers driven step by step.

Subclasses override :meth:`step`; :meth:`run` calls it repeatedly
until it returns ``False`` or the step budget is spent. Tick cost:
whatever the overridden step uses.

Example::

class Counter(Worker):
        def step(self):
            print("at", position())
            return True

Counter("counter").run(3)

### `minerlib.EnergyAwareWorker`

A worker loop that works, rests, unloads and keeps energy in reserve.

Subclasses override :meth:`work` (return ``False`` to stop, or a
``mine()`` result to trigger an unload on ``inventory_full``).
:meth:`run` checks :meth:`needs_rest` before each step, calls
:meth:`rest` when needed and unloads at the dock when the bag fills.

Tick cost: whatever :meth:`work`, :meth:`rest` and unloading use.
Energy cost: whatever :meth:`work` and walking use.

Example::

class Digger(EnergyAwareWorker):
        def work(self):
            return mine()

Digger("digger").run(50)

### `minerlib.MinerWorker`

A worker that mines one ore type until the bag is full, then hauls.

Tick cost: scanning, moving and mining through the primitives.

Example::

digger = MinerWorker("digger", "stone")
    digger.run(50)

### `minerlib.HaulerWorker`

A worker that waits for work published in shared memory.

The work value is read from ``shared_get(key)``. When it is a dict
with ``x`` and ``y`` the worker walks there, mines the optional
``item`` when present and hauls when ``haul`` is true. With no work
published it waits one tick. Tick cost: 1 wait tick when idle.

Example::

shared_set("work", {"x": 4, "y": 0, "item": "stone"})
    HaulerWorker("hauler").run(20)

### `minerlib.Fleet`

Convenience wrapper around the fleet primitives.

Tick cost: the normal cost of each underlying call.

Example::

fleet = Fleet()
    fleet.broadcast("goal", 10)
    fleet.gather("goal")

### `minerlib.Samples`

A tiny pure-Python tally of mining attempts per ore.

Example::

samples = Samples()
    samples.add("stone", True)
    samples.add("stone", False)
    print(samples.rate("stone"))  # 0.5

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
| `abc` | unlocks with the **Inheritance** achievement |
| `enum` | unlocks with the **Inheritance** achievement |
| `bisect` | unlocks with the **Chartist** achievement |
| `operator` | unlocks with the **Trend Follower** achievement |
| `json` | unlocks with the **Power User** achievement |
| `copy` | unlocks with the **Gallery Veteran** achievement |

## Deprecated

These old function names still work as aliases, print one console notice per script run and will be removed in a future release.

- `drone_id` -> `miner_id`
- `drones` -> `miners`
- `spawn_drone` -> `spawn_miner`
- `kill_drone` -> `kill_miner`

## Safety

Player scripts run in a separate subprocess with a restricted namespace. This is **not** a security sandbox: only run scripts you trust.
