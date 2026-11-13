# Prompt 22 of 25 (v0.3): library expansion for the new systems

Follow AGENTS.md. Goal: helpers, modules and examples for trading, refining, contracts, events and fleets. First read runner/minerlib.py, content/functions.json, content/modules.json, content/examples.json and src/minesim/examples/. All new items have unlocked_by null for now.

1. minerlib (pure Python on top of the primitives, each with a docstring and a short example):
   - Navigation: route(x, y) -> list of Directions (A* with heapq over the area between the two points plus a margin; tiles inside slow zones from events() cost more); goto_route(x, y); ore_map(radius) -> {(dx, dy): ore}.
   - Trading: sma(item, n=10); trend(item, n=20) (slope of a least-squares line in plain Python); sell_if(item, min_index) (sell stock only when price / base value >= min_index, return the money); best_item_to_sell() (highest price / base value among the stocked items).
   - Data: moving_average(values, n); linear_fit(xs, ys) -> (slope, intercept); class Forecast (simple exponential smoothing with update(x) and predict()).
   - Refinery and contracts: refine_all(recipe_id) (as many runs as the warehouse allows); wait_for_refinery(); best_contract() (best reward per base value that the stock can already cover, or None); fulfill(contract_id) (fetch or refine what is missing when possible, then deliver).
   - Fleet and OOP: class Worker (base class with name, run(), step(), goto(), haul()); MinerWorker(Worker) (mines an ore until full, then hauls); HaulerWorker(Worker) (waits for work published in shared memory); class Fleet (spawn(script), kill_all(), broadcast(key, value), gather(key)).
2. modules.json: add abc, enum, bisect and operator.
3. Examples 09 to 16 in src/minesim/examples/ with header comments and entries in examples.json: 09_market_watcher, 10_refine_everything, 11_contract_runner, 12_two_drones, 13_worker_classes (inheritance), 14_event_hunter (rich veins and slow zones), 15_price_forecast (moving average and linear fit), 16_fleet_manager (shared memory).
4. API panel, stubs and docs (tools/gen_stubs.py, tools/gen_docs.py) include everything new, with tick costs.
5. Tests: each helper against a headless engine (route avoids a slow zone; trend and linear_fit on known data; sell_if thresholds; refine_all with limited stock; Worker subclasses run); every example runs through the real subprocess in lockstep for 3000 ticks with everything unlocked and raises no error; stubs and docs are up to date.

ACCEPTANCE: uv run python tools/gen_docs.py updates docs/API.md and all tests pass.
COMMIT: feat: v0.3 library (navigation, trading, data, fleet and OOP helpers)
