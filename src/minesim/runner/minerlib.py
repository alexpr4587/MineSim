"""Helper library importable by player scripts (pure Python).

The primitive API functions (``move``, ``mine``, ``peek`` and the
others) are injected into this module by the runner before player code
runs. They are declared here so the module is importable and testable
on its own; calling them without the runner raises ``RuntimeError``.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Iterator, Sequence
from typing import Any

__all__ = [
    "EnergyAwareWorker",
    "Fleet",
    "Forecast",
    "HaulerWorker",
    "MinerWorker",
    "Samples",
    "Worker",
    "best_contract",
    "best_item_to_sell",
    "can_return",
    "charge_full",
    "cool_down",
    "dive",
    "energy_to",
    "farm",
    "fulfill",
    "go_down",
    "go_home",
    "go_up",
    "goto",
    "goto_nearest",
    "goto_route",
    "haul",
    "heat_budget",
    "linear_fit",
    "mine_here",
    "mine_until",
    "moving_average",
    "nearest",
    "ore_map",
    "refine_all",
    "ring",
    "route",
    "safe_farm",
    "sell_if",
    "sma",
    "smart_unload",
    "spiral",
    "stagger",
    "sweep",
    "to_station",
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
_HEAT_GAIN_PER_LEVEL = 0.12
_OVERHEAT_AT = 100.0
_IDLE_HEAT_BUDGET = 999_999
_HOT_LAYER_FROM = 2
_DEFAULT_REST_MARGIN = 0.2
_DOCK_BACKOFF_MODULUS = 4


class NotUnlockedError(Exception):
    """Fallback class replaced by the runner's real error type at runtime."""


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


def battery() -> Any:
    """Return the battery state (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def charge() -> Any:
    """Recharge on a station (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def energy_cost(action: str, arg: int | None = None) -> Any:
    """Return an action's energy cost (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def temperature() -> Any:
    """Return the temperature state (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def cool(target: float = 30) -> Any:
    """Cool down on a station (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def climate() -> Any:
    """Return the layer climate (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def layer() -> int:
    """Return the current layer (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def layers() -> Any:
    """Return the layers (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def descend() -> Any:
    """Descend one layer (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def ascend() -> Any:
    """Ascend one layer (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def dock_free() -> Any:
    """Return the dock status (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def dock_rate() -> int:
    """Return the dock rate (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def tick() -> int:
    """Return the current tick (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def distance() -> int:
    """Return the distance from the base (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def biome() -> str:
    """Return the current biome (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def stats() -> Any:
    """Return mining stats (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def buy_upgrade(upgrade_id: str) -> Any:
    """Buy an upgrade (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def inspect() -> Any:
    """Describe the current tile (injected by the runner)."""
    raise RuntimeError("minerlib is only available inside a player script")


def submit_estimate(ore_id: str, p: float) -> Any:
    """Submit a probability estimate (injected by the runner)."""
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


def _optional_call(name: str, *args: Any, **kwargs: Any) -> Any:
    """Call an optional injected API function, returning None when locked."""
    function = globals().get(name)
    if not callable(function):
        return None
    try:
        return function(*args, **kwargs)
    except NotUnlockedError:
        return None
    except RuntimeError:
        return None


def _battery_state() -> tuple[int, int] | None:
    """Return ``(energy, capacity)`` when :func:`battery` is available."""
    result = _optional_call("battery")
    if isinstance(result, dict):
        return (int(result.get("energy", 0) or 0), int(result.get("capacity", 0) or 0))
    if isinstance(result, (tuple, list)) and len(result) >= 2:
        return (int(result[0]), int(result[1]))
    return None


def _move_energy_cost() -> int:
    """Return the energy needed for one move (fallback 1)."""
    result = _optional_call("energy_cost", "move")
    if isinstance(result, dict):
        result = result.get("cost")
    try:
        return max(0, int(result))
    except (TypeError, ValueError):
        return 1


def _action_energy_cost(action: str) -> int:
    """Return the energy needed for ``action`` (fallback 0)."""
    result = _optional_call("energy_cost", action)
    if isinstance(result, dict):
        result = result.get("cost")
    try:
        return max(0, int(result))
    except (TypeError, ValueError):
        return 0


def _try_charge() -> bool:
    """Charge the battery when possible; return True on success."""
    result = _optional_call("charge")
    if isinstance(result, dict):
        return bool(result.get("ok"))
    return bool(result)


def _try_wait(ticks: int) -> bool:
    """Wait ``ticks`` ticks when :func:`wait` is unlocked."""
    function = globals().get("wait")
    if not callable(function):
        return False
    try:
        function(max(1, int(ticks)))
        return True
    except (NotUnlockedError, RuntimeError):
        return False


def _try_sell() -> int | None:
    """Sell the inventory when possible, else return None."""
    function = globals().get("sell")
    if not callable(function):
        return None
    try:
        return int(function() or 0)
    except (NotUnlockedError, RuntimeError):
        return None


def _try_unload() -> Any:
    """Unload into the warehouse when possible, else return None."""
    result = _optional_call("unload")
    return result


def _current_layer() -> int:
    """Return the current layer, or 0 when :func:`layer` is locked."""
    result = _optional_call("layer")
    try:
        return int(result)
    except (TypeError, ValueError):
        return 0


def _dock_status() -> dict[str, Any] | None:
    """Return the dock status when :func:`dock_free` is available."""
    result = _optional_call("dock_free")
    return result if isinstance(result, dict) else None


def _temperature_state() -> dict[str, Any] | None:
    """Return the temperature state when :func:`temperature` is available."""
    result = _optional_call("temperature")
    return result if isinstance(result, dict) else None


def _climate_state() -> dict[str, Any] | None:
    """Return the climate state when :func:`climate` is available."""
    result = _optional_call("climate")
    return result if isinstance(result, dict) else None


def _miner_identity() -> int:
    """Return the own miner id, or 0 when :func:`miner_id` is locked."""
    result = _optional_call("miner_id")
    try:
        return int(result)
    except (TypeError, ValueError):
        return 0


def _generator_has_energy() -> bool:
    """Return False only when the battery is known to be empty."""
    state = _battery_state()
    if state is None:
        return True
    return state[0] > 0


def _move_failed(result: Any) -> bool:
    """Return True when a :func:`move` result reports a refusal."""
    if result is False:
        return True
    return isinstance(result, dict) and result.get("ok") is False


def _ensure_energy(reserve: int = 0) -> bool:
    """Make sure one move plus ``reserve`` energy is available."""
    state = _battery_state()
    if state is None:
        return True
    needed = _move_energy_cost() + max(0, int(reserve))
    if state[0] >= needed:
        return True
    if not _try_charge():
        return False
    state = _battery_state()
    return state is None or state[0] >= needed


def _manhattan(x: int, y: int) -> int:
    """Return Manhattan distance from the miner to ``(x, y)``."""
    cx, cy = position()
    return abs(int(x) - int(cx)) + abs(int(y) - int(cy))


def _return_home_and_charge() -> bool:
    """Go home, charge and cool when that is possible."""
    if can_return(0.0):
        if not go_home():
            return False
    elif not _try_charge():
        return False
    charge_full()
    _optional_call("cool", 30)
    return True


def _shaft_action(name: str) -> tuple[bool, Any]:
    """Run a descend/ascend action and return ``(ok, result)``."""
    result = _optional_call(name)
    if isinstance(result, dict):
        return (bool(result.get("ok")), result)
    return (bool(result), result)


def goto(x: int, y: int) -> bool:
    """Move the miner to ``(x, y)``, one tile at a time.

    The helper stops cleanly when the miner cannot continue (for
    example because the battery is empty). Low-energy refusals are
    retried once after a charge on a station.

    Tick cost: one :func:`move` per tile.
    Energy cost: the per-move energy of the current layer per tile.

    Example::

        if goto(start_x + 3, start_y):
            print("arrived")
    """
    target_x, target_y = int(x), int(y)
    while True:
        cx, cy = position()
        if cx == target_x and cy == target_y:
            return True
        if not _ensure_energy():
            return False
        if cx < target_x:
            direction = "east"
        elif cx > target_x:
            direction = "west"
        elif cy < target_y:
            direction = "south"
        else:
            direction = "north"
        if not _move_failed(move(direction)):
            continue
        if not _try_charge():
            return False
        if _move_failed(move(direction)):
            return False


def go_home() -> bool:
    """Move the miner back to the base at ``(0, 0)``.

    Tick cost: one :func:`move` per tile.
    Energy cost: the per-move energy of the current layer per tile.

    Example::

        go_home()
    """
    return goto(0, 0)


def sweep(width: int, height: int) -> Iterator[tuple[int, int]]:
    """Yield positions in serpentine (boustrophedon) order.

    Yields ``(x, y)`` for ``y`` in ``range(height)``; even rows go
    left-to-right (``x`` in ``range(width)``) and odd rows go
    right-to-left, so consecutive positions are always adjacent. The
    generator stops early when the known battery is empty.

    Tick cost: 0 ticks (pure Python).
    Energy cost: 0 energy.

    Example::

        for dx, dy in sweep(3, 2):
            print(dx, dy)
    """
    for y in range(height):
        if not _generator_has_energy():
            return
        if y % 2 == 0:
            xs = range(width)
        else:
            xs = range(width - 1, -1, -1)
        for x in xs:
            if not _generator_has_energy():
                return
            yield (x, y)


def spiral() -> Iterator[tuple[int, int]]:
    """Yield positions in an infinite square spiral from ``(0, 0)``.

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
    """
    x = 0
    y = 0
    if not _generator_has_energy():
        return
    yield (x, y)
    directions = ((1, 0), (0, 1), (-1, 0), (0, -1))
    index = 0
    length = 1
    while _generator_has_energy():
        for _ in range(2):
            dx, dy = directions[index % 4]
            index += 1
            for _step in range(length):
                if not _generator_has_energy():
                    return
                x += dx
                y += dy
                yield (x, y)
        length += 1


def ring(radius: int) -> Iterator[tuple[int, int]]:
    """Yield the offsets on the square ring of Chebyshev radius ``radius``.

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
    """
    radius = max(0, int(radius))
    if radius == 0:
        if _generator_has_energy():
            yield (0, 0)
        return
    for dx in range(-radius, radius + 1):
        if not _generator_has_energy():
            return
        yield (dx, -radius)
    for dy in range(-radius + 1, radius + 1):
        if not _generator_has_energy():
            return
        yield (radius, dy)
    for dx in range(radius - 1, -radius - 1, -1):
        if not _generator_has_energy():
            return
        yield (dx, radius)
    for dy in range(radius - 1, -radius, -1):
        if not _generator_has_energy():
            return
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
    return goto(x + offset[0], y + offset[1])


def mine_until(n: int = 1) -> int:
    """Mine the current tile until ``n`` successes or it is exhausted.

    Returns the number of successful mines. A miss keeps trying; an
    empty, locked, too-hard, full-inventory, low-energy or overheated
    tile stops the loop cleanly.

    Tick cost: the normal :func:`mine` cost per attempt.
    Energy cost: the normal :func:`mine` energy per attempt.

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
    """Go home, sell the inventory, charge, then return to the previous spot.

    The sale is skipped (but the trip still happens) when :func:`sell`
    is locked; the helper then tries :func:`unload`. Charging happens
    after selling, as the station is only left afterwards.

    Tick cost: walking plus the normal :func:`sell` cost.
    Energy cost: the per-move energy of the current layer per tile.

    Example::

        earned = haul()
    """
    previous = position()
    if not go_home():
        return 0
    earned = _try_sell()
    if earned is None:
        _try_unload()
        earned = 0
    charge_full()
    goto(previous[0], previous[1])
    return int(earned or 0)


def farm(ore: str, max_tiles: int = 200) -> int:
    """Sweep outward mining only ``ore`` and hauling when the bag is full.

    Visits at most ``max_tiles`` positions of a square spiral around the
    starting point and returns the number of mined items. The helper
    stops cleanly when there is not enough energy left to return home.
    The miner ends back on the last visited tile.

    Tick cost: moving plus the normal :func:`mine` cost per attempt.
    Energy cost: the per-move and per-mine energy of the current layer.

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
        if not can_return():
            break
        if not goto(start_x + dx, start_y + dy):
            break
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


def energy_to(x: int, y: int) -> int:
    """Return the energy needed to walk to ``(x, y)`` on this layer.

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
    """
    target_x, target_y = int(x), int(y)
    if position() == (target_x, target_y):
        return 0
    steps = route(target_x, target_y)
    distance = len(steps) if steps else _manhattan(target_x, target_y)
    return int(distance) * _move_energy_cost()


def can_return(margin: float = 0.1) -> bool:
    """Return True when the battery can still carry the miner home.

    ``margin`` is a fraction of the trip energy kept as a safety
    buffer (``0.1`` means ten percent). When :func:`battery` is locked
    the helper assumes the miner can continue.

    Tick cost: 0 ticks.
    Energy cost: 0 energy (this is a query).

    Example::

        while can_return():
            mine_until(1)
        haul()
    """
    state = _battery_state()
    if state is None:
        return True
    energy, _capacity = state
    needed = energy_to(0, 0)
    buffer = int(math.ceil(float(needed) * max(0.0, float(margin))))
    return energy >= needed + buffer


def charge_full() -> bool:
    """Charge the battery fully on the current station.

    Returns False when the miner is not on a station or :func:`charge`
    is locked.

    Tick cost: the normal :func:`charge` duration.
    Energy cost: 0 energy.

    Example::

        go_home()
        charge_full()
    """
    return _try_charge()


def _trip_energy(x: int, y: int) -> int:
    """Return a conservative energy estimate for target plus return."""
    cx, cy = position()
    there = abs(int(x) - cx) + abs(int(y) - cy)
    back = abs(int(x)) + abs(int(y))
    return (there + back) * _move_energy_cost()


def safe_farm(ore: str, max_tiles: int = 200) -> int:
    """Farm ``ore`` while always keeping enough energy to return home.

    Before each tile the helper checks that the round trip fits in the
    battery. When it does not, the miner returns to the station, charges
    (and cools) and tries again. A full inventory is hauled first.

    Tick cost: moving, mining, hauling and charging as needed.
    Energy cost: the per-move and per-mine energy of the current layer.

    Example::

        mined = safe_farm("stone", max_tiles=60)
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
        target_x, target_y = start_x + dx, start_y + dy
        attempts = 0
        while True:
            state = _battery_state()
            energy = state[0] if state is not None else 10**9
            if can_return() and _trip_energy(target_x, target_y) <= energy:
                break
            attempts += 1
            if attempts > 2 or not _return_home_and_charge():
                return mined
        if not goto(target_x, target_y):
            return mined
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


def _shaft_step(name: str) -> bool:
    """Charge for and perform one descend/ascend transition."""
    if not _ensure_energy(_action_energy_cost(name)):
        return False
    ok, _result = _shaft_action(name)
    return ok


def to_station() -> bool:
    """Walk to the station of the current layer at ``(0, 0)``.

    Tick cost: one :func:`move` per tile.
    Energy cost: the per-move energy of the current layer per tile.

    Example::

        if to_station():
            charge_full()
    """
    return goto(0, 0)


def go_down(n: int = 1) -> bool:
    """Descend ``n`` layers from shaft stations.

    The miner walks to the station of its layer, charges when the shaft
    ride would not fit in the battery and then descends. Returns False
    when the shaft is too shallow or a station cannot be reached.

    Tick cost: walking plus 20 ticks per shaft ride.
    Energy cost: the per-move energy plus 15 energy per shaft ride.

    Example::

        go_down(2)
    """
    for _ in range(max(0, int(n))):
        if not to_station():
            return False
        if not _shaft_step("descend"):
            return False
    return True


def go_up(n: int = 1) -> bool:
    """Ascend ``n`` layers from shaft stations.

    Already being on the surface counts as success.

    Tick cost: walking plus 20 ticks per shaft ride.
    Energy cost: the per-move energy plus 15 energy per shaft ride.

    Example::

        go_up(1)
    """
    for _ in range(max(0, int(n))):
        if _current_layer() <= 0:
            return True
        if not to_station():
            return False
        if not _shaft_step("ascend"):
            return False
    return True


def dive(layer: int) -> bool:
    """Travel to ``layer`` and leave the caller standing on its station.

    Layers above the current one use :func:`go_down`; layers below use
    :func:`go_up`. Returns False when the target is not reachable.

    Tick cost: walking plus 20 ticks per shaft ride.
    Energy cost: the per-move energy plus 15 energy per shaft ride.

    Example::

        dive(2)
        print("now on layer", layer())
    """
    target = max(0, int(layer))
    current = _current_layer()
    if target == current:
        return True
    if target > current:
        return go_down(target - current)
    return go_up(current - target)


def cool_down(target: float = 30) -> bool:
    """Walk to the station and cool down to ``target`` temperature.

    Tick cost: walking plus the normal :func:`cool` duration.
    Energy cost: the per-move energy per tile.

    Example::

        cool_down(30)
    """
    if not to_station():
        return False
    result = _optional_call("cool", float(target))
    if isinstance(result, dict):
        return bool(result.get("ok"))
    return bool(result)


def heat_budget() -> int:
    """Return a rough number of work ticks left before overheating.

    With :func:`temperature` unlocked the estimate uses the current
    temperature, the layer heat and the airflow overload. Without it
    the helper returns ``1`` as a conservative one-tick budget.

    Tick cost: 0 ticks.
    Energy cost: 0 energy.

    Example::

        if heat_budget() < 20:
            cool_down(30)
    """
    state = _temperature_state()
    if state is None:
        return 1
    if state.get("overheated") or int(state.get("cooldown", 0) or 0) > 0:
        return 0
    temperature = max(0.0, float(state.get("temperature", 0.0) or 0.0))
    climate_state = _climate_state() or {}
    heat = max(0.0, float(climate_state.get("heat", state.get("heat", 0.0)) or 0.0))
    if heat <= 0.0:
        return _IDLE_HEAT_BUDGET
    overload = max(0.0, float(climate_state.get("overload", 0.0) or 0.0))
    gain = _HEAT_GAIN_PER_LEVEL * heat * (1.0 + overload)
    if gain <= 0.0:
        return _IDLE_HEAT_BUDGET
    return max(0, int((_OVERHEAT_AT - temperature) / gain))


def stagger(miner_id: int) -> int:
    """Return a small deterministic backoff for a miner id.

    The values cycle between 1 and 4 ticks, so several miners do not
    all knock on the dock in the same tick.

    Tick cost: 0 ticks.
    Energy cost: 0 energy.

    Example::

        wait(stagger(miner_id()))
    """
    return 1 + (max(0, int(miner_id)) % _DOCK_BACKOFF_MODULUS)


def smart_unload() -> int:
    """Unload when the dock is free, otherwise wait with a stagger.

    The wait before each retry is :func:`stagger` of the own miner id.
    The helper returns the number of ticks it waited; when
    :func:`dock_free` is locked it unloads immediately.

    Tick cost: the wait ticks plus the normal :func:`unload` duration.
    Energy cost: 0 energy.

    Example::

        waited = smart_unload()
        print("waited", waited, "ticks for the dock")
    """
    waited = 0
    me = _miner_identity()
    while True:
        status = _dock_status()
        if status is None or bool(status.get("free", True)):
            _try_unload()
            return waited
        if not _try_wait(stagger(me)):
            _try_unload()
            return waited
        waited += stagger(me)


def _field(entry: Any, name: str, default: Any = None) -> Any:
    """Read ``name`` from a dict or object."""
    if isinstance(entry, dict):
        return entry.get(name, default)
    return getattr(entry, name, default)


def _active_slow_zones() -> list[tuple[int, int, int]]:
    """Return the active slow-zone circles as ``(x, y, radius)``."""
    zones: list[tuple[int, int, int]] = []
    for event in _optional_call("events") or []:
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
    Energy cost: the per-move energy of the current layer per step.

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


def goto_route(x: int, y: int) -> bool:
    """Walk to ``(x, y)`` using the slow-zone aware :func:`route`.

    Stops cleanly and returns False when a move is refused or the
    battery cannot pay for the next step.

    Tick cost: one :func:`move` per route step.
    Energy cost: the per-move energy of the current layer per step.

    Example::

        goto_route(10, -4)
    """
    target_x, target_y = int(x), int(y)
    steps = route(target_x, target_y)
    if not steps:
        return position() == (target_x, target_y)
    for direction in steps:
        if not _ensure_energy():
            return False
        if _move_failed(move(direction)):
            return False
    return True


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

    def goto(self, x: int, y: int) -> bool:
        """Walk to ``(x, y)`` using the primitive :func:`goto`."""
        return goto(int(x), int(y))

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


class EnergyAwareWorker(Worker):
    """A worker loop that works, rests, unloads and keeps energy in reserve.

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
    """

    def __init__(self, name: str = "worker", rest_margin: float = _DEFAULT_REST_MARGIN) -> None:
        super().__init__(name)
        self.rest_margin = max(0.0, min(1.0, float(rest_margin)))
        self.rests = 0
        self.unloads = 0

    def work(self) -> Any:
        """Perform one unit of work; subclasses override this."""
        return False

    def needs_rest(self) -> bool:
        """Return True when the battery, heat or trip home needs a rest."""
        state = _temperature_state()
        if state is not None:
            if state.get("overheated") or int(state.get("cooldown", 0) or 0) > 0:
                return True
            if heat_budget() <= 1:
                return True
        if not can_return(0.1):
            return True
        battery_state = _battery_state()
        if battery_state is not None:
            energy, capacity = battery_state
            if capacity > 0 and energy <= capacity * self.rest_margin:
                return True
        return False

    def rest(self) -> bool:
        """Go to the station, charge, cool and unload there."""
        self.rests += 1
        if not to_station():
            return False
        charged = charge_full()
        state = _temperature_state()
        if state is not None and float(state.get("temperature", 0.0) or 0.0) > 30.0:
            cool_down(30)
        if self._has_cargo():
            smart_unload()
            self.unloads += 1
        return charged

    def _has_cargo(self) -> bool:
        """Return True when the inventory holds at least one item."""
        items = _optional_call("inventory")
        if isinstance(items, dict):
            return any(int(count or 0) > 0 for count in items.values())
        return False

    def _should_unload(self, result: Any) -> bool:
        """Return True when ``work`` asked for an unload."""
        if result == "unload":
            return True
        if isinstance(result, dict):
            if result.get("unload"):
                return True
            return result.get("reason") == "inventory_full"
        return False

    def run(self, steps: int = 100) -> int:
        """Work, rest and unload up to ``steps`` times; return the count."""
        limit = max(0, int(steps))
        done = 0
        while done < limit:
            done += 1
            self.steps += 1
            if self.needs_rest():
                if not self.rest():
                    break
                continue
            result = self.work()
            if result is False:
                break
            if self._should_unload(result):
                smart_unload()
                self.unloads += 1
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

    def assign_layers(self, assignments: dict[int, int]) -> dict[int, int]:
        """Publish ``{miner_id: layer}`` in shared memory and return it.

        The mapping is merged into the ``fleet_layers`` shared key so
        every miner can read its target. When the calling miner appears
        in ``assignments`` it also dives to that layer.

        Tick cost: 0 ticks for the shared write plus the dive cost.
        Energy cost: the per-move energy plus 15 energy per shaft ride.

        Example::

            fleet = Fleet()
            fleet.assign_layers({0: 1, 1: 2})
        """
        stored = self.gather("fleet_layers")
        mapping: dict[str, int] = {}
        if isinstance(stored, dict):
            for key, value in stored.items():
                try:
                    mapping[str(int(key))] = int(value)
                except (TypeError, ValueError):
                    continue
        for key, value in assignments.items():
            mapping[str(int(key))] = int(value)
        self.broadcast("fleet_layers", mapping)
        me = _miner_identity()
        if me in assignments:
            dive(int(assignments[me]))
        return {int(key): int(value) for key, value in mapping.items()}

    def balance_load(self, max_in_hot_layers: int) -> dict[int, int]:
        """Spread the fleet across layers, capping the hot layers.

        ``max_in_hot_layers`` miners are assigned to hot layers
        (index 2 and deeper); the rest go to the cooler upper layers.
        The assignment is published under ``fleet_layers`` and returned
        as ``{miner_id: layer}``.

        Tick cost: 0 ticks.
        Energy cost: 0 energy.

        Example::

            Fleet().balance_load(2)
        """
        limit = max(0, int(max_in_hot_layers))
        fleet = _optional_call("miners") or []
        identifiers: list[int] = []
        for entry in fleet:
            try:
                identifiers.append(int(_field(entry, "id", 0) or 0))
            except (TypeError, ValueError):
                continue
        identifiers.sort()
        if not identifiers:
            me = _miner_identity()
            identifiers = [me]
        available = _optional_call("layers") or []
        accessible: list[int] = []
        for entry in available:
            if bool(_field(entry, "accessible", True)):
                try:
                    accessible.append(int(_field(entry, "index", 0) or 0))
                except (TypeError, ValueError):
                    continue
        if not accessible:
            accessible = [0]
        accessible = sorted(set(accessible))
        hot = [level for level in accessible if level >= _HOT_LAYER_FROM]
        cold = [level for level in accessible if level < _HOT_LAYER_FROM]
        mapping: dict[int, int] = {}
        if not hot:
            pool = cold or accessible
            for index, miner_id in enumerate(identifiers):
                mapping[miner_id] = pool[index % len(pool)]
        else:
            hot_slots = [hot[index % len(hot)] for index in range(limit)]
            hot_slots = hot_slots[: max(0, len(identifiers))]
            cold_pool = cold or hot
            cold_index = 0
            for index, miner_id in enumerate(identifiers):
                if index < len(hot_slots):
                    mapping[miner_id] = hot_slots[index]
                else:
                    mapping[miner_id] = cold_pool[cold_index % len(cold_pool)]
                    cold_index += 1
        self.broadcast("fleet_layers", {str(key): value for key, value in mapping.items()})
        return mapping


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
