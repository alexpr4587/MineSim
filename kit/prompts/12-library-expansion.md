# Prompt 12 of 14 (v0.2): library expansion (API functions, minerlib, modules, examples)

Follow AGENTS.md. Goal: grow the player library. First read core/commands.py, core/engine.py, scripting/host.py, runner/main.py, runner/minerlib.py, content/functions.json, content/modules.json, ui/editor_panel.py and ui/api_panel.py. For now every new function, module and example has unlocked_by null (prompt 13 wires them to achievements).

1. New primitives (core command + functions.json entry + runner proxy + stub + docs; keep the existing cost model):
   - wait(ticks): costs that many ticks (1 to 600).
   - tick(): the current game tick (0 ticks).
   - distance(): Chebyshev distance from the base (0 ticks).
   - biome(): id of the biome under the miner (0 ticks).
   - ore_info(ore_id): {id, name, tier, hardness, base_value, regen_ticks}; None for locked or unknown ores. It must NEVER include mine_probability: players have to estimate it (0 ticks).
   - inspect(): {ore, mineable: bool, reason or None, regrows_in: ticks or None} for the current tile (0 ticks).
   - submit_estimate(ore_id, p): needs at least 100 recorded attempts on that ore, otherwise {ok: False, reason: 'not_enough_data', attempts}; at most 3 submissions per ore (kept in the save); returns {ok: True, close: bool} where close means abs(p - true probability) <= 0.05. Never return the numeric error. Publishes EstimateSubmitted with the error and whether it was good.
2. minerlib additions (pure Python on top of the primitives, with docstrings that include a short example): nearest(ore, radius=None) -> (dx, dy) or None (uses scan); goto_nearest(ore, radius=None) -> bool; ring(r), a generator of positions on a square ring around the start; mine_until(n=1), which repeats mine() on the current tile until n successes or the tile is exhausted; haul(), which goes home, sells, returns to the previous position and returns the money; farm(ore, max_tiles=200), which sweeps outward mining only that ore and hauls when the inventory is full; class Samples with add(ore, success), count(ore), rate(ore) and summary(), in plain Python.
3. modules.json: add itertools, functools, dataclasses and typing.
4. Examples: content/examples.json with {id, title, file, unlocked_by} and the scripts in src/minesim/examples/, each with a header comment that explains what it teaches and which unlocks it needs:
   01_hello (the starter script), 02_sweep_and_sell, 03_ore_hunter (scan + nearest), 04_explorer_spiral (distance + biome), 05_probability_lab (Samples + submit_estimate), 06_farm_ruby, 07_regen_cycle (wait + tick), 08_dataclass_logbook (dataclasses).
   Editor panel: an 'Examples' menu. Unlocked examples are copied into scripts_dir as a new file (never overwrite an existing file); locked ones are dimmed.
5. API panel and docs: show the tick cost and a short example for every function; tools/gen_stubs.py and tools/gen_docs.py include everything new.
6. Tests: each primitive (including the 100-attempt and 3-submission limits and the fact that ore_info never leaks mine_probability); each minerlib helper against a headless engine; every example script runs through the real subprocess for 2000 ticks with everything unlocked and raises no error (the test stops it); stubs and docs are up to date (a test regenerates them and compares).

ACCEPTANCE: uv run python tools/gen_docs.py updates docs/API.md and all tests pass.
COMMIT: feat: library expansion with new functions, helpers, modules and examples
