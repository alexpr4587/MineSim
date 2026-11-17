# Prompt 26 of 36 (v0.3.1): rename drones to miners

Follow AGENTS.md. Goal: everything that is called a drone becomes a miner (they mine, so 'drone' makes no sense). Behavior does not change. First run `grep -rniI drone` over src, tests, tools, docs, README.md and kit to see the full list.

1. User-facing text: every title, label, button, toast, tooltip, console message, HUD text, panel name and docstring. Examples: panel 'Drones' -> 'Miners'; 'Drone 0' -> 'Miner 0'; 'Run on new drone' -> 'Run on new miner'; HUD 'Drones: 4 alive' -> 'Miners: 4 alive'; upgrade 'Drone Bay' -> 'Miner Bay'. The main miner is 'Miner 0'.
2. Key: the miners panel moves from D to T (for Team) in the keymap, the View menu, Ctrl+T, the README and the docs.
3. Player API (functions.json, proxies, stubs, docs, examples): spawn_drone -> spawn_miner, kill_drone -> kill_miner, drone_id -> miner_id, drones -> miners (the list entries keep their fields). The old names stay as deprecated aliases that still work and print one console info line per script run (for example 'spawn_drone is now spawn_miner'); they are listed only in a 'Deprecated' section of docs/API.md and in the stubs. minerlib (Fleet, Worker and the others) uses the new names.
4. Content ids (migrate them in saves): feature drones -> miners; upgrade drone_bay -> miner_bay; achievement first_drone -> first_miner (title 'Teamwork' stays); example file 12_two_drones -> 12_two_miners; counters drones_spawned -> miners_spawned and max_drones_alive -> max_miners_alive; counters api:spawn_drone, api:kill_drone, api:drone_id, api:drones -> api:spawn_miner, api:kill_miner, api:miner_id, api:miners; config key drone_costs -> miner_costs.
5. Code: class Drone -> Miner, events DroneSpawned and DroneRemoved -> MinerSpawned and MinerRemoved, fields and parameters drone_id -> miner_id, modules and files (ui/drones_panel.py -> ui/miners_panel.py and so on; use git mv), the tools/screenshot.py flag --drones -> --miners, test names and fixtures.
6. Save: a new version (current + 1) that renames the keys and ids above; migration from every older version; keep fixtures of the previous versions and test that their scripts, achievements, counters, upgrades and fleet survive the rename.
7. A test that scans the sources, content, docs and README for the word 'drone' (case-insensitive) and fails unless the match is in the alias and migration modules, their tests, or CHANGELOG.md.
8. Old user scripts that call the old names keep running (alias test).

ACCEPTANCE: all tests pass; `grep -rniI drone` only finds the allowed places.
COMMIT: refactor: rename drones to miners
