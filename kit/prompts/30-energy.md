# Prompt 30 of 36 (v0.4): energy and batteries

Follow AGENTS.md. Goal: every miner has a battery. The mechanic is always on; only the API functions that inspect it are gated later. First read core/commands.py, core/engine.py, the miner entity, core/progression/*, ui/hud.py, ui/miners_panel.py and the engine tests.

CONTENT:
- config.json: battery_start 300, energy_move 1, energy_mine_base 1 (plus hardness // 2), energy_scan_per_radius 1, energy_shaft 15, charge_rate 10 (energy per tick), rescue_ticks 600, rescue_energy_fraction 0.25, rescue_loses_inventory true.
- upgrades.json: battery (+100 capacity per level, 5 levels, costs 200 600 1500 4000 9000) and charger (+10 charge rate per level, 3 levels, costs 300 900 2500); unlocked_by null for now.

CORE:
1. Each miner has energy (starts full); the capacity is a shared stat (PlayerStats). Move, Mine, Scan, Descend and Ascend spend energy when they start; the amount is multiplied by the energy_multiplier of the layer (ceil). If a miner has less energy than an action costs, the action is refused with reason 'low_energy' (1 tick) and nothing is spent.
2. Stranding: a miner that cannot afford even a Move and is not on a base or station tile is stranded; after rescue_ticks it is rescued to the station (or base) of its layer with rescue_energy_fraction of its battery, losing its inventory when rescue_loses_inventory is true. Events: MinerStranded(miner_id) and MinerRescued(miner_id, lost_items).
3. New command Charge() on a base or station tile: restores the battery, lasting ceil(missing / charge_rate) ticks (1 tick minimum). Commands Battery() (energy and capacity) and EnergyCost(action) (the energy that action would cost right now at the current layer; for 'mine' it uses the ore under the miner) cost 0 ticks. Events: EnergySpent(miner_id, amount) and Charged(miner_id, amount).
4. API (functions.json, proxies, stubs, docs; unlocked_by null for now): battery() -> (energy, capacity), charge() -> {ok, energy}, energy_cost(action, arg=None). move(direction) now returns True when the miner moved and False when it was refused; mine() results can have reason 'low_energy'. Scripts that ignored the old None return keep working.
5. UI: an energy bar for the selected miner in the HUD, an energy column in the miners panel, a 'stranded' badge on the map and a toast on rescue.
6. Save: a new version with miner energy (default full); migrate. Keep a fixture.
7. Tests: costs per action and per layer; refusal without spending; the stranding and rescue timeline; charge duration and caps; upgrades change capacity and rate; move returns a bool; determinism; UI bars render; earlier tests pass (adapt expectations that assume infinite energy by giving those tests a large battery config).

ACCEPTANCE: a headless script that never checks energy eventually gets 'low_energy' and is rescued; one that charges runs forever.
COMMIT: feat(core): energy, batteries and rescue
