# Prompt 33 of 36 (v0.4): library for layers, energy, climate and the dock

Follow AGENTS.md. Goal: helpers, modules and examples for the new systems, and energy-aware versions of the old helpers. First read src/minesim/runner/minerlib.py, content/functions.json, content/modules.json, content/examples.json and src/minesim/examples/. New items have unlocked_by null for now.

1. Rule for helpers: they must work when optional functions are still locked. Wrap calls to battery(), temperature(), climate() and dock_free() in a helper that catches NotUnlockedError and falls back to reacting to the 'low_energy', 'overheated' and 'queued' results of the always-available calls.
2. Existing helpers become energy-aware: goto, goto_route, sweep, spiral, ring, mine_until, farm, haul and the route cost. They return False or stop cleanly when the miner cannot continue, and haul() charges after selling.
3. New minerlib helpers (docstrings with examples):
   - Energy: energy_to(x, y) (energy needed to walk there on this layer), can_return(margin=0.1) (enough energy to go home from here), charge_full(), safe_farm(ore, max_tiles=200) (a farm that always keeps the energy to return and charges at home).
   - Layers: to_station(), go_down(n=1), go_up(n=1), dive(layer) (go there and leave the caller on that layer).
   - Climate: cool_down(target=30), heat_budget() (rough ticks of work left before overheating, from temperature() when unlocked, otherwise from the overheated results).
   - Dock: smart_unload() (unload when the dock is free, otherwise wait with a small staggered backoff by miner id; returns the ticks waited), stagger(miner_id).
   - OOP: class EnergyAwareWorker(Worker) with needs_rest(), rest() and a run() loop that works, rests and unloads; subclasses override work().
   - Fleet: Fleet.assign_layers({miner_id: layer}) and Fleet.balance_load(max_in_hot_layers).
4. modules.json: add json and copy.
5. Examples 17 to 24 in src/minesim/examples/ with header comments and entries in examples.json: 17_energy_budget, 18_go_deep, 19_climate_watch, 20_dock_etiquette, 21_night_shift (EnergyAwareWorker), 22_layer_prospector, 23_vent_manager, 24_full_automation (several miners on different layers, charging, unloading and refining).
6. API panel, stubs and docs (tools/gen_stubs.py, tools/gen_docs.py) include everything new with tick and energy costs.
7. Tests: each helper headless; helpers work with the optional functions locked and unlocked; every example (old and new) runs through the real subprocess in lockstep for 3000 ticks with everything unlocked and raises no error; stubs and docs are up to date; the old examples still behave under the energy rules.

ACCEPTANCE: uv run python tools/gen_docs.py updates docs/API.md and all tests pass.
COMMIT: feat: v0.4 library (energy, layers, climate, dock and OOP helpers)
