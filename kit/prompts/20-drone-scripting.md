# Prompt 20 of 25 (v0.3): drone scripting (manager, spawn, shared memory)

Follow AGENTS.md. Goal: every drone runs its own script in its own subprocess. First read scripting/host.py, runner/main.py, core/engine.py, core/commands.py, core/game.py, ui/game_loop.py, ui/editor_panel.py, ui/console_panel.py and the scripting tests.

1. scripting/manager.py: ScriptManager(game, scripts_dir) owns one ScriptHost per drone. start(drone_id, filename, source), stop(drone_id), stop_all(), pump() (all hosts, in drone id order), states(), console(drone_id). The main drone (0) is started by the editor Run button as today. At most max_script_processes hosts at the same time (config, default 8).
2. New primitives (commands where the engine is involved, handled by the manager where a process is involved; functions.json, proxies, stubs, docs; unlocked_by null for now):
   - spawn_drone(script_name): script_name is a .py file in scripts_dir. It charges the SpawnDrone cost from prompt 15 (5 ticks), creates the drone on the base and starts its script; it returns the drone id or {ok: False, reason}.
   - kill_drone(drone_id): stops its script and removes it (never drone 0). assign(drone_id, script_name): stops the current script of that drone and starts the new one.
   - drone_id(): the own id. drones(): [{id, x, y, state, script, inventory_used}] (0 ticks).
   - shared_get(key, default=None) and shared_set(key, value): a JSON key-value store shared by all drones and kept in the save (max 64 keys, keys up to 40 characters, values up to 4 KB serialized; violations raise a clear exception inside the player script).
3. Each host binds to its drone: requests from that script go to that drone's queue. When a script ends or fails, the drone stays where it is, idle; ScriptFailed marks that drone as failed (console line with the traceback). Scripts can spawn drones (recursion is limited by the slots and the money).
4. Lockstep driver for headless use: manager.run_lockstep(max_ticks) advances the engine only when every running script is blocked on a reply or finished, so results are deterministic (used by tests, --selftest and the balance tool). The UI keeps its non-blocking loop; ui/game_loop.py now calls manager.pump().
5. UI wiring (minimal): the console panel gets a drone selector (dropdown) that shows the console of the chosen drone; closing the window stops all scripts.
6. The --selftest now spawns a second drone from a script and checks that both scripts cooperate through shared memory, also in the frozen build.
7. Save: shared memory and the script name of each drone (so the UI can show it; scripts are not restarted automatically after loading). Bump the version and migrate.
8. Tests (real subprocess, integration, deterministic in lockstep): spawn, kill and assign; slot, money and process limits; shared memory between two drones; a failing drone does not stop the others; two identical lockstep runs give identical engine states; the watchdog still kills a runaway drone script.

ACCEPTANCE: uv run minesim --selftest prints OK (Linux and Windows CI) with two cooperating drones.
COMMIT: feat(scripting): multi-drone script manager and shared memory
