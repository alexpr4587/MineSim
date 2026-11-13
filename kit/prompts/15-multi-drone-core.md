# Prompt 15 of 25 (v0.3): fleet of drones (core refactor)

Follow AGENTS.md. Goal: turn the single miner into a fleet of drones that share money, upgrades and the world, without changing the behavior of a single-drone game. This is a refactor: protect it with tests first. First read core/miner.py, core/engine.py, core/commands.py, core/events.py, core/game.py, core/save.py, scripting/host.py, ui/world_view.py and the existing tests.

0. Before touching anything: add a golden regression test that runs a fixed scripted session (fixed seed, a long list of commands: moves, mines, sells, upgrades) on the current code and stores the final state and event log as a fixture. After the refactor the same session on drone 0 must produce exactly the same result.
1. Split Miner into Drone (id, x, y, facing, inventory, its own command queue and busy timer) and PlayerStats (money, capacity, tool_power, tool_tier, move_ticks, scan_radius and the aggregate stats counters), shared by all drones. Drone 0 is the main drone and always exists.
2. Fleet: engine.drones (dict by id), engine.drone(id), engine.spawn_drone() (new drone on the base, next free id) and engine.remove_drone(id) (never drone 0; the inventory of a removed drone is lost for now).
3. Commands: cost_ticks(engine, drone) and execute(engine, drone). The engine keeps one FIFO queue and one active command per drone; engine.submit(cmd, drone_id=0). step() advances one tick and processes the drones in increasing id order. The mining dice must include the drone id in the hash, but for drone 0 keep the old hash exactly (mix the id in only when it is not 0) so the golden test still passes.
4. New command SpawnDrone: cost from config drone_costs [300, 800, 2000, 5000] indexed by the number of extra drones alive; allowed only while the number of drones is below max_drones, where max_drones = 1 + the drone_bay upgrade level (new upgrade drone_bay in upgrades.json: +1 drone slot per level, 4 levels, costs 200 600 1500 4000, unlocked_by null for now). Result {ok, drone_id} or {ok: False, reason: 'no_slot' | 'not_enough_money'}. New command RemoveDrone(id).
5. Events: add drone_id to Moved, MineAttempted, OreMined, Sold and UpgradeBought; new DroneSpawned(id) and DroneRemoved(id).
6. Save version 4: fleet (each drone with position, facing, inventory) and the player stats; migrate version 3 saves (the old single miner becomes drone 0). Keep a version-3 fixture.
7. Plumbing: ScriptHost gets a drone_id parameter (default 0) and submits to that drone. Nothing else changes in scripting yet.
8. UI: the world view draws every drone (drone 0 with the selected skin; the others with the same sprite plus a small colored id badge from an 8-color palette); the HUD shows the number of drones.
9. AGENTS.md: append two rules: 'numpy is allowed only in ui/ (never in core/)' and 'floating-point math in core/ uses only + - * / comparisons, min, max, abs, ceil, floor and sqrt (no sin, cos, exp, log or fractional powers) so results are identical on every OS'. Extend tests/test_architecture.py: core/ must not import numpy, and must not call those math functions.
10. Tests: the golden regression passes; two drones with fixed command lists give identical state and event logs across runs; processing order by id; spawn limits and costs; removal; migration from version 3; the UI renders several drones (offscreen).

ACCEPTANCE: all earlier tests pass unchanged and the new fleet tests pass.
COMMIT: refactor(core): fleet of drones
