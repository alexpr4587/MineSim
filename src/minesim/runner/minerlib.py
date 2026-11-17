"""Helper library importable by player scripts (pure Python).

The primitive API functions (``move``, ``mine``, ``peek`` and the
others) are injected into this module by the runner before player code
runs. They are declared here so the module is importable and testable
on its own; calling them without the runner raises ``RuntimeError``.
"""

from __future__ import annotations

import heapq
from collections.abc import Iterator, Sequence
from typing import Any

__all__ = [
    "Fleet",
    "Forecast",
    "HaulerWorker",
    "MinerWorker",
    "Samples",
    "Worker",
    "best_contract",
    "best_item_to_sell",
    "farm",
    "fulfill",
    "go_home",
    "goto",
    "goto_nearest",
    "goto_route",
    "haul",
    "linear_fit",
    "mine_here",
    "mine_until",
    "moving_average",
    "nearest",
    "ore_map",
    "refine_all",
    "ring",
    "route",
    "sell_if",
    "sma",
    "spiral",
    "sweep",
    "trend",
    "wait_for_refinery",
]

_DIRECTIONS: tuple[tuple[str, int, int], ...] = (
    ("north", 0, -1),
    ("east", 1, 0),
    ("south", 0, 1),
    ("west", -1, 0),
)

_ROUTE_MARGIN = 4
_SLOW_TILE_COST = 10
_DEFAULT_ALPHA = 0.3


def move(direction: str) -> None:
    """Move one tile in ``direction`` (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def mine() -> Any:
    """Mine the current tile (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def peek() -> Any:
    """Look at the current tile (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def position() -> tuple[int, int]:
    """Return the miner position (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def scan(radius: int) -> Any:
    """Scan for ore (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def inventory() -> Any:
    """Return the inventory (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def sell() -> int:
    """Sell the inventory (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def unload() -> Any:
    """Move the inventory into the base warehouse (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def stock() -> Any:
    """Return the warehouse contents and capacity (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def sell_stock(item: str, amount: int | None = None) -> int:
    """Sell warehouse stock at market prices (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def price(item: str) -> float | None:
    """Return the current market price of ``item`` (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def prices() -> Any:
    """Return every unlocked item price (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def price_history(item: str, n: int = 50) -> list[float] | None:
    """Return recent price samples (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def recipes() -> Any:
    """Return every refinery recipe (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def refine(recipe_id: str, times: int = 1) -> Any:
    """Start a refinery job (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def refinery() -> Any:
    """Return the running refinery jobs (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def contracts() -> Any:
    """Return the open delivery contracts (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def deliver(contract_id: int) -> int:
    """Deliver a contract at the base (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def events() -> Any:
    """Return the active world events (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def miner_id() -> int:
    """Return the id of this miner (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def miners() -> Any:
    """Return the fleet (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def spawn_miner(script_name: str) -> Any:
    """Buy a miner and start its script (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def kill_miner(miner_id: int) -> bool:
    """Remove a miner from the fleet (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def assign(miner_id: int, script_name: str) -> None:
    """Assign a script to a miner (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def shared_get(key: str, default: Any = None) -> Any:
    """Read a value from shared memory (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def shared_set(key: str, value: Any) -> None:
    """Write a value to shared memory (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def wait(ticks: int) -> None:
    """Wait for ``ticks`` ticks (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def ore_info(ore_id: str) -> Any:
    """Return public ore information (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def goto(x: int, y: int) -> None:
    """Move the miner to ``(x, y)``, one tile at a time.

    Example::

        goto(start_x + 3, start_y)
    """
    while True:
        cx, cy = position()
        if cx == x and cy == y:
            return
        if cx < x:
            move("east")
        elif cx > x:
            move("west")
        elif cy < y:
            move("south")
        else:
            move("north")


def go_home() -> None:
    """Move the miner back to the base at ``(0, 0)``.

    Example::

        go_home()
    """
    goto(0, 0)


def sweep(width: int, height: int) -> Iterator[tuple[int, int]]:
    """Yield positions in serpentine (boustrophedon) order.

    Yields ``(x, y)`` for ``y`` in ``range(height)``; even rows go
    left-to-right (``x`` in ``range(width)``) and odd rows go
    right-to-left, so consecutive positions are always adjacent.

    Example::

        for dx, dy in sweep(3, 2):
            print(dx, dy)
    """
    for y in range(height):
        if y % 2 == 0:
            xs = range(width)
        else:
            xs = range(width - 1, -1, -1)
        for x in xs:
            yield (x, y)


def spiral() -> Iterator[tuple[int, int]]:
    """Yield positions in an infinite square spiral from ``(0, 0)``.

    Starts at ``(0, 0)`` and spirals outwards (east, south, west,
    north, ...) with segment lengths 1, 1, 2, 2, 3, 3, ... so the
    first positions are ``(0, 0)``, ``(1, 0)``, ``(1, 1)``,
    ``(0, 1)``, ``(-1, 1)``, ... The generator never ends.

    Example::

        for dx, dy in spiral():
            print(dx, dy)
    """
    x = 0
    y = 0
    yield (x, y)
    directions = ((1, 0), (0, 1), (-1, 0), (0, -1))
    index = 0
    length = 1
    while True:
        for _ in range(2):
            dx, dy = directions[index % 4]
            index += 1
            for _step in range(length):
                x += dx
                y += dy
                yield (x, y)
        length += 1


def ring(radius: int) -> Iterator[tuple[int, int]]:
    """Yield the offsets on the square ring of Chebyshev radius ``radius``.

    The offsets are relative to the miner's starting point (``(0, 0)``
    when used with :func:`goto`). ``ring(0)`` yields just ``(0, 0)``;
    ``ring(1)`` yields the eight surrounding tiles.

    Example::

        start_x, start_y = position()
        for dx, dy in ring(2):
            goto(start_x + dx, start_y + dy)
    """
    radius = max(0, int(radius))
    if radius == 0:
        yield (0, 0)
        return
    for dx in range(-radius, radius + 1):
        yield (dx, -radius)
    for dy in range(-radius + 1, radius + 1):
        yield (radius, dy)
    for dx in range(radius - 1, -radius - 1, -1):
        yield (dx, radius)
    for dy in range(radius - 1, -radius, -1):
        yield (-radius, dy)


def mine_here() -> Any:
    """Mine the current tile if it holds a known ore.

    Peeks at the current tile first; if :func:`peek` returns an ore
    id (not ``None`` and not ``'unknown'``), calls :func:`mine` and
    returns its result. Otherwise returns ``None`` without mining.

    Example::

        result = mine_here()
    """
    ore = peek()
    if ore is None or ore == "unknown":
        return None
    return mine()


def nearest(ore: str, radius: int | None = None) -> tuple[int, int] | None:
    """Return the nearest ``(dx, dy)`` offset of ``ore`` via :func:`scan`.

    ``radius`` defaults to the whole scan area (the engine caps it to
    the miner's scanner). Ties are broken deterministically by
    Chebyshev distance, then Manhattan distance, then ``(dy, dx)``.
    Returns ``None`` when the ore is not in range.

    Example::

        offset = nearest("coal")
        if offset is not None:
            print("coal at", offset)
    """
    effective = 10**6 if radius is None else max(0, int(radius))
    best: tuple[int, int] | None = None
    best_key: tuple[int, int, int, int] | None = None
    for dx, dy, label in scan(effective):
        if label != ore:
            continue
        key = (max(abs(int(dx)), abs(int(dy))), abs(int(dx)) + abs(int(dy)), int(dy), int(dx))
        if best_key is None or key < best_key:
            best_key = key
            best = (int(dx), int(dy))
    return best


def goto_nearest(ore: str, radius: int | None = None) -> bool:
    """Walk to the nearest tile of ``ore``; return ``True`` when found.

    Example::

        if goto_nearest("stone"):
            mine()
    """
    offset = nearest(ore, radius)
    if offset is None:
        return False
    x, y = position()
    goto(x + offset[0], y + offset[1])
    return True


def mine_until(n: int = 1) -> int:
    """Mine the current tile until ``n`` successes or it is exhausted.

    Returns the number of successful mines. A miss keeps trying; an
    empty, locked, too-hard or full-inventory tile stops the loop.

    Example::

        successes = mine_until(3)
    """
    target = max(0, int(n))
    successes = 0
    while successes < target:
        result = mine()
        if isinstance(result, dict) and result.get("ok"):
            successes += 1
            continue
        reason = result.get("reason") if isinstance(result, dict) else None
        if reason == "miss":
            continue
        break
    return successes


def haul() -> int:
    """Go home, sell the inventory, return to the previous spot, return money.

    Example::

        earned = haul()
    """
    previous = position()
    go_home()
    earned = sell()
    goto(previous[0], previous[1])
    return int(earned or 0)


def farm(ore: str, max_tiles: int = 200) -> int:
    """Sweep outward mining only ``ore`` and hauling when the bag is full.

    Visits at most ``max_tiles`` positions of a square spiral around the
    starting point and returns the number of mined items. The miner
    ends back on the last visited tile.

    Example::

        mined = farm("coal", max_tiles=50)
        print("mined", mined)
    """
    start_x, start_y = position()
    limit = max(0, int(max_tiles))
    mined = 0
    visited = 0
    for dx, dy in spiral():
        if visited >= limit:
            break
        visited += 1
        goto(start_x + dx, start_y + dy)
        while peek() == ore:
            result = mine()
            if isinstance(result, dict) and result.get("ok"):
                mined += 1
                continue
            reason = result.get("reason") if isinstance(result, dict) else None
            if reason == "miss":
                continue
            if reason == "inventory_full":
                haul()
                continue
            break
    return mined


def _field(entry: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a dict or object."""
    if isinstance(entry, dict):
        return entry.get(name, default)
    return getattr(entry, name, default)


def _active_slow_zones() -> list[tuple[int, int, int]]:
    """Return the active slow-zone circles as ``(x, y, radius)``."""
    zones: list[tuple[int, int, int]] = []
    for event in events() or []:
        if _field(event, "kind") != "slow_zone":
            continue
        x = _field(event, "x")
        y = _field(event, "y")
        if x is None or y is None:
            continue
        radius = max(0, int(_field(event, "radius", 0) or 0))
        zones.append((int(x), int(y), radius))
    return zones


def _inside_zone(x: int, y: int, zones: Sequence[tuple[int, int, int]]) -> bool:
    """Return True when ``(x, y)`` lies inside a slow zone."""
    for zone_x, zone_y, radius in zones:
        dx = int(x) - zone_x
        dy = int(y) - zone_y
        if dx * dx + dy * dy <= radius * radius:
            return True
    return False


def route(x: int, y: int) -> list[str]:
    """Return an A* route from the miner to ``(x, y)`` as direction names.

    The search covers the rectangle between the miner and the target
    plus a safety margin. Tiles inside a slow zone reported by
    :func:`events` cost more, so the route goes around them when a
    detour is shorter. Returned values can be passed straight to
    :func:`move` (for example ``"east"``).

    Tick cost: one :func:`move` per returned step (4 ticks per tile by
    default, more inside slow zones).

    Example::

        for direction in route(4, 0):
            move(direction)
    """
    start_x, start_y = position()
    target_x, target_y = int(x), int(y)
    if (start_x, start_y) == (target_x, target_y):
        return []
    zones = _active_slow_zones()
    margin = _ROUTE_MARGIN
    if zones:
        margin = max(margin, max(radius for _zx, _zy, radius in zones) + 2)
    min_x = min(start_x, target_x) - margin
    max_x = max(start_x, target_x) + margin
    min_y = min(start_y, target_y) - margin
    max_y = max(start_y, target_y) + margin

    def heuristic(cx: int, cy: int) -> int:
        return abs(cx - target_x) + abs(cy - target_y)

    def step_cost(cx: int, cy: int) -> int:
        return _SLOW_TILE_COST if _inside_zone(cx, cy, zones) else 1

    start = (start_x, start_y)
    goal = (target_x, target_y)
    open_heap: list[tuple[int, int, int, int]] = [(heuristic(*start), 0, start_x, start_y)]
    counter = 1
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    cost_so_far: dict[tuple[int, int], int] = {start: 0}

    while open_heap:
        _estimate, _order, cx, cy = heapq.heappop(open_heap)
        if (cx, cy) == goal:
            break
        for _name, dx, dy in _DIRECTIONS:
            nx, ny = cx + dx, cy + dy
            if nx < min_x or nx > max_x or ny < min_y or ny > max_y:
                continue
            new_cost = cost_so_far[(cx, cy)] + step_cost(nx, ny)
            node = (nx, ny)
            if node in cost_so_far and new_cost >= cost_so_far[node]:
                continue
            cost_so_far[node] = new_cost
            came_from[node] = (cx, cy)
            heapq.heappush(open_heap, (new_cost + heuristic(nx, ny), counter, nx, ny))
            counter += 1

    if goal not in came_from:
        return []
    path: list[tuple[int, int]] = [goal]
    while path[-1] != start:
        path.append(came_from[path[-1]])
    path.reverse()

    directions: list[str] = []
    for (cx, cy), (nx, ny) in zip(path, path[1:], strict=False):
        dx, dy = nx - cx, ny - cy
        for name, step_x, step_y in _DIRECTIONS:
            if (step_x, step_y) == (dx, dy):
                directions.append(name)
                break
    return directions


def goto_route(x: int, y: int) -> None:
    """Walk to ``(x, y)`` using the slow-zone aware :func:`route`.

    Tick cost: one :func:`move` per route step.

    Example::

        goto_route(10, -4)
    """
    for direction in route(x, y):
        move(direction)


def ore_map(radius: int) -> dict[tuple[int, int], str]:
    """Return ``{(dx, dy): ore}`` for every ore in scanner range.

    Offsets are relative to the miner. Locked ores appear as
    ``"unknown"``. Tick cost: the cost of :func:`scan` (1 + radius
    ticks).

    Example::

        for offset, ore in ore_map(2).items():
            print(offset, ore)
    """
    result: dict[tuple[int, int], str] = {}
    for tile in scan(int(radius)) or []:
        dx, dy, label = tile[0], tile[1], tile[2]
        result[(int(dx), int(dy))] = str(label)
    return result


def moving_average(values: Sequence[float], n: int) -> list[float]:
    """Return the simple moving average for every full window of ``n``.

    Tick cost: 0 ticks (pure Python).

    Example::

        moving_average([1, 2, 3, 4], 2)  # [1.5, 2.5, 3.5]
    """
    window = max(1, int(n))
    data = [float(value) for value in values]
    if len(data) < window:
        return []
    return [sum(data[index : index + window]) / window for index in range(len(data) - window + 1)]


def linear_fit(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float]:
    """Fit ``y = slope * x + intercept`` by least squares.

    Mismatched lengths are truncated to the shorter sequence. Returns
    ``(0.0, 0.0)`` when there are fewer than two points or all ``x``
    values are equal. Tick cost: 0 ticks (pure Python).

    Example::

        slope, intercept = linear_fit([0, 1, 2], [1, 3, 5])  # (2.0, 1.0)
    """
    pairs = list(zip(xs, ys, strict=False))
    count = len(pairs)
    if count < 2:
        return (0.0, 0.0)
    xs_float = [float(x) for x, _y in pairs]
    ys_float = [float(y) for _x, y in pairs]
    mean_x = sum(xs_float) / count
    mean_y = sum(ys_float) / count
    numerator = 0.0
    denominator = 0.0
    for x_value, y_value in zip(xs_float, ys_float, strict=False):
        dx = x_value - mean_x
        numerator += dx * (y_value - mean_y)
        denominator += dx * dx
    if denominator == 0.0:
        return (0.0, 0.0)
    slope = numerator / denominator
    return (slope, mean_y - slope * mean_x)


def sma(item: str, n: int = 10) -> float:
    """Return the simple moving average of the last ``n`` prices of ``item``.

    Returns ``0.0`` when no price samples are available. Tick cost: 0
    ticks.

    Example::

        average = sma("stone", 10)
    """
    history = price_history(item, max(1, int(n))) or []
    values = [float(value) for value in history if value is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def trend(item: str, n: int = 20) -> float:
    """Return the least-squares slope of the last ``n`` prices of ``item``.

    A positive value means prices are rising, a negative value means
    they are falling and ``0.0`` means flat or not enough samples.
    Tick cost: 0 ticks.

    Example::

        if trend("stone", 12) > 0:
            print("prices are rising")
    """
    history = price_history(item, max(2, int(n))) or []
    values = [float(value) for value in history if value is not None]
    if len(values) < 2:
        return 0.0
    slope, _intercept = linear_fit(range(len(values)), values)
    return slope


def _base_value(item: str) -> float | None:
    """Return the base value of ``item`` when one is exposed."""
    try:
        info = ore_info(item)
    except Exception:
        info = None
    if isinstance(info, dict):
        value = info.get("base_value")
        if value is not None:
            return float(value)
    try:
        board = contracts() or []
    except Exception:
        board = []
    for contract in board:
        if str(_field(contract, "item", "")) != str(item):
            continue
        value = _field(contract, "base_value")
        if value is not None:
            return float(value)
    return None


def _price_index(item: str) -> float | None:
    """Return ``price / base value`` (or a recent-price ratio fallback)."""
    current = price(item)
    if current is None:
        return None
    base = _base_value(item)
    if base is not None and base > 0:
        return float(current) / base
    history = price_history(item, 20) or []
    values = [float(value) for value in history if value is not None]
    if not values:
        return None
    average = sum(values) / len(values)
    if average <= 0:
        return None
    return float(current) / average


def _stock_items() -> dict[str, int]:
    """Return the warehouse contents as ``{item: count}``."""
    result = _field(stock(), "items", {})
    if not isinstance(result, dict):
        return {}
    return {str(item): int(count) for item, count in result.items()}


def _stock_count(item: str) -> int:
    """Return how many units of ``item`` the warehouse holds."""
    return int(_stock_items().get(str(item), 0))


def sell_if(item: str, min_index: float) -> int:
    """Sell all warehouse stock of ``item`` when its price index is high.

    The price index is ``price(item) / base value``. When the base
    value is not exposed (for example for an unfamiliar product), the
    current price divided by its recent average is used instead. The
    sale only happens at the base. Returns the money gained (``0`` when
    the threshold is not met or there is no stock).

    Tick cost: 2 ticks when a sale happens.

    Example::

        earned = sell_if("stone", 1.2)
    """
    index = _price_index(item)
    if index is None or index < float(min_index):
        return 0
    amount = _stock_count(item)
    if amount <= 0:
        return 0
    return int(sell_stock(item, amount) or 0)


def best_item_to_sell() -> str | None:
    """Return the stocked item with the highest price / base value.

    Ties are broken by item id. Returns ``None`` when the warehouse is
    empty or no stocked item has a usable price. Tick cost: 0 ticks.

    Example::

        item = best_item_to_sell()
        if item is not None:
            sell_stock(item)
    """
    best_item: str | None = None
    best_index: float | None = None
    for item in sorted(_stock_items()):
        index = _price_index(item)
        if index is None:
            continue
        if best_index is None or index > best_index:
            best_index = index
            best_item = item
    return best_item


class Forecast:
    """Simple exponential smoothing for one price series.

    ``alpha`` controls how quickly the forecast follows new samples
    (0 < alpha <= 1). ``update(x)`` feeds one sample and ``predict()``
    returns the current smoothed level. Tick cost: 0 ticks.

    Example::

        forecast = Forecast(alpha=0.5)
        for sample in price_history("stone", 10) or []:
            forecast.update(sample)
        print(forecast.predict())
    """

    def __init__(self, alpha: float = _DEFAULT_ALPHA) -> None:
        value = float(alpha)
        if value <= 0.0 or value > 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = value
        self._level: float | None = None

    def update(self, x: float) -> float:
        """Feed one sample and return the new smoothed level."""
        sample = float(x)
        if self._level is None:
            self._level = sample
        else:
            self._level = self.alpha * sample + (1.0 - self.alpha) * self._level
        return self._level

    def predict(self) -> float:
        """Return the current smoothed level (``0.0`` before any update)."""
        return 0.0 if self._level is None else float(self._level)


def refine_all(recipe_id: str) -> int:
    """Start as many runs of ``recipe_id`` as the warehouse inputs allow.

    At most one refinery job can be started per call, so the returned
    count is the number of runs packed into the free furnace slot.
    Returns ``0`` when there is no free slot or not enough input.

    Tick cost: 2 ticks at the base, plus the normal refinery duration.

    Example::

        runs = refine_all("copper_bar")
    """
    recipe = (recipes() or {}).get(str(recipe_id))
    if not isinstance(recipe, dict):
        return 0
    if recipe.get("unlocked") is False:
        return 0
    inputs = recipe.get("inputs") or {}
    if not isinstance(inputs, dict) or not inputs:
        return 0
    items = _stock_items()
    runs: int | None = None
    for item, count in inputs.items():
        need = max(1, int(count))
        available = int(items.get(str(item), 0))
        possible = available // need
        runs = possible if runs is None else min(runs, possible)
    if not runs or runs <= 0:
        return 0
    result = refine(str(recipe_id), runs)
    if not isinstance(result, dict) or not result.get("ok"):
        return 0
    return max(0, int(result.get("times", runs) or 0))


def wait_for_refinery() -> None:
    """Wait until every running refinery job has finished.

    Jobs that are blocked because the warehouse is full stop the wait,
    so the helper never spins forever. Tick cost: the remaining job
    time (through :func:`wait`).

    Example::

        refine_all("copper_bar")
        wait_for_refinery()
    """
    while True:
        jobs = refinery() or []
        if not jobs:
            return
        active = [job for job in jobs if not bool(_field(job, "blocked", False))]
        if not active:
            return
        remaining = min(max(1, int(_field(job, "ticks_left", 1) or 1)) for job in active)
        wait(min(600, remaining))


def best_contract() -> dict[str, Any] | None:
    """Return the contract with the best reward per base value in stock.

    Only contracts whose quantity is already in the warehouse are
    considered. The score is ``reward / (quantity * base_value)`` (the
    premium paid per unit of base value); ties are broken by contract
    id. Returns ``None`` when nothing can be delivered right now.

    Tick cost: 0 ticks.

    Example::

        contract = best_contract()
        if contract is not None:
            deliver(contract["id"])
    """
    items = _stock_items()
    best: dict[str, Any] | None = None
    best_score: float | None = None
    for entry in contracts() or []:
        item = str(_field(entry, "item", ""))
        quantity = int(_field(entry, "quantity", 0) or 0)
        reward = int(_field(entry, "reward", 0) or 0)
        if quantity <= 0 or int(items.get(item, 0)) < quantity:
            continue
        base = _field(entry, "base_value")
        base_value = float(base) if base is not None else _base_value(item)
        if base_value is None or base_value <= 0:
            score = float(reward) / quantity
        else:
            score = float(reward) / (quantity * base_value)
        contract_id = int(_field(entry, "id", 0) or 0)
        if (
            best is None
            or best_score is None
            or score > best_score
            or (score == best_score and contract_id < int(_field(best, "id", 0) or 0))
        ):
            best = dict(entry) if isinstance(entry, dict) else {"id": contract_id}
            best_score = score
    return best


def _recipe_for_item(item: str) -> tuple[str | None, dict[str, Any] | None]:
    """Return the first recipe that outputs ``item``."""
    for recipe_id, recipe in (recipes() or {}).items():
        if not isinstance(recipe, dict):
            continue
        outputs = recipe.get("outputs") or {}
        if isinstance(outputs, dict) and str(item) in outputs:
            return str(recipe_id), recipe
    return (None, None)


def _mine_missing(item: str, target: int) -> bool:
    """Mine ``item`` until the warehouse holds ``target`` units."""
    attempts = 0
    limit = max(8, min(400, (int(target) - _stock_count(item)) * 3))
    while attempts < limit and _stock_count(item) < target:
        attempts += 1
        offset = nearest(item)
        if offset is None:
            break
        cx, cy = position()
        goto(cx + int(offset[0]), cy + int(offset[1]))
        result = mine()
        if isinstance(result, dict) and result.get("ok"):
            go_home()
            unload()
    return _stock_count(item) >= target


def fulfill(contract_id: int) -> int:
    """Fetch or refine what a contract is missing, then deliver it.

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
    """
    target_id = int(contract_id)
    contract: Any = None
    for entry in contracts() or []:
        if int(_field(entry, "id", -1) or -1) == target_id:
            contract = entry
            break
    if contract is None:
        return 0
    item = str(_field(contract, "item", ""))
    quantity = int(_field(contract, "quantity", 0) or 0)
    if not item or quantity <= 0:
        return 0

    go_home()
    unload()
    if _stock_count(item) < quantity:
        try:
            is_ore = ore_info(item) is not None
        except Exception:
            is_ore = False
        if is_ore:
            _mine_missing(item, quantity)
        else:
            recipe_id, _recipe = _recipe_for_item(item)
            while recipe_id is not None and _stock_count(item) < quantity:
                started = refine_all(recipe_id)
                if started <= 0:
                    break
                wait_for_refinery()
                go_home()
                unload()
    go_home()
    unload()
    if _stock_count(item) < quantity:
        return 0
    return int(deliver(target_id) or 0)


class Worker:
    """Base class for fleet workers driven step by step.

    Subclasses override :meth:`step`; :meth:`run` calls it repeatedly
    until it returns ``False`` or the step budget is spent. Tick cost:
    whatever the overridden step uses.

    Example::

        class Counter(Worker):
            def step(self):
                print("at", position())
                return True

        Counter("counter").run(3)
    """

    def __init__(self, name: str = "worker") -> None:
        self.name = str(name)
        self.steps = 0

    def goto(self, x: int, y: int) -> None:
        """Walk to ``(x, y)`` using the primitive :func:`goto`."""
        goto(int(x), int(y))

    def haul(self) -> int:
        """Sell the inventory through the primitive :func:`haul`."""
        return int(haul() or 0)

    def step(self) -> bool:
        """Perform one unit of work; return False to stop :meth:`run`."""
        return False

    def run(self, steps: int = 100) -> int:
        """Run :meth:`step` up to ``steps`` times and return the count."""
        limit = max(0, int(steps))
        done = 0
        while done < limit:
            done += 1
            self.steps += 1
            if not self.step():
                break
        return done


class MinerWorker(Worker):
    """A worker that mines one ore type until the bag is full, then hauls.

    Tick cost: scanning, moving and mining through the primitives.

    Example::

        digger = MinerWorker("digger", "stone")
        digger.run(50)
    """

    def __init__(self, name: str = "miner", ore: str = "stone") -> None:
        super().__init__(name)
        self.ore = str(ore)
        self.mined = 0
        self.hauls = 0
        self.earned = 0

    def step(self) -> bool:
        """Move to the ore if needed and mine once."""
        if peek() != self.ore:
            offset = nearest(self.ore)
            if offset is None:
                return False
            x, y = position()
            self.goto(x + int(offset[0]), y + int(offset[1]))
        result = mine()
        if not isinstance(result, dict):
            return True
        if result.get("ok"):
            self.mined += int(result.get("amount", 1) or 1)
            return True
        reason = result.get("reason")
        if reason == "inventory_full":
            self.earned += self.haul()
            self.hauls += 1
            return True
        if reason == "miss":
            return True
        return False


class HaulerWorker(Worker):
    """A worker that waits for work published in shared memory.

    The work value is read from ``shared_get(key)``. When it is a dict
    with ``x`` and ``y`` the worker walks there, mines the optional
    ``item`` when present and hauls when ``haul`` is true. With no work
    published it waits one tick. Tick cost: 1 wait tick when idle.

    Example::

        shared_set("work", {"x": 4, "y": 0, "item": "stone"})
        HaulerWorker("hauler").run(20)
    """

    def __init__(self, name: str = "hauler", key: str = "work") -> None:
        super().__init__(name)
        self.key = str(key)
        self.carried = 0

    def step(self) -> bool:
        """Handle the current shared-memory work item."""
        work = shared_get(self.key, None)
        if not work:
            wait(1)
            return True
        if isinstance(work, dict):
            x = work.get("x")
            y = work.get("y")
            if x is not None and y is not None:
                self.goto(int(x), int(y))
            item = work.get("item")
            if item is not None and peek() == item:
                mine()
            if work.get("haul"):
                self.carried += self.haul()
        return True


class Fleet:
    """Convenience wrapper around the fleet primitives.

    Tick cost: the normal cost of each underlying call.

    Example::

        fleet = Fleet()
        fleet.broadcast("goal", 10)
        fleet.gather("goal")
    """

    def spawn(self, script: str) -> Any:
        """Buy a miner running ``script``; return its id or an error dict."""
        return spawn_miner(str(script))

    def kill_all(self) -> list[int]:
        """Remove every miner except miner 0 and the calling miner."""
        me = int(miner_id() or 0)
        killed: list[int] = []
        for entry in miners() or []:
            target = int(_field(entry, "id", 0) or 0)
            if target == 0 or target == me:
                continue
            try:
                removed = bool(kill_miner(target))
            except Exception:
                removed = False
            if removed:
                killed.append(target)
        return killed

    def broadcast(self, key: str, value: Any) -> None:
        """Publish ``value`` under ``key`` for every miner."""
        shared_set(str(key), value)

    def gather(self, key: str) -> Any:
        """Read the value stored under ``key`` (or ``None``)."""
        return shared_get(str(key), None)


class Samples:
    """A tiny pure-Python tally of mining attempts per ore.

    Example::

        samples = Samples()
        samples.add("stone", True)
        samples.add("stone", False)
        print(samples.rate("stone"))  # 0.5
    """

    def __init__(self) -> None:
        self._attempts: dict[str, int] = {}
        self._successes: dict[str, int] = {}

    def add(self, ore: str, success: bool) -> None:
        """Record one attempt on ``ore`` (``success`` or a miss)."""
        ore = str(ore)
        self._attempts[ore] = self._attempts.get(ore, 0) + 1
        if success:
            self._successes[ore] = self._successes.get(ore, 0) + 1

    def count(self, ore: str) -> int:
        """Return the number of recorded attempts on ``ore``."""
        return int(self._attempts.get(str(ore), 0))

    def rate(self, ore: str) -> float:
        """Return the observed success rate on ``ore`` (``0.0`` if none)."""
        attempts = self.count(ore)
        if attempts <= 0:
            return 0.0
        return self._successes.get(str(ore), 0) / attempts

    def summary(self) -> dict[str, dict[str, float | int]]:
        """Return ``{ore: {'attempts', 'successes', 'rate'}}`` for every ore."""
        return {
            ore: {
                "attempts": attempts,
                "successes": int(self._successes.get(ore, 0)),
                "rate": self.rate(ore),
            }
            for ore, attempts in sorted(self._attempts.items())
        }
