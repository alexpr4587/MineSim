# Prompt 32 of 36 (v0.4): dock throughput

Follow AGENTS.md. Goal: the surface dock is a shared bottleneck for the whole fleet. First read core/commands.py, core/engine.py, core/warehouse.py, ui/world_view.py, ui/base_panel.py, ui/hud.py and the dock-related tests.

CONTENT: config.json dock_rate 4 (units per tick). upgrades.json: dock (+2 units per tick per level, 4 levels, costs 400 1200 3000 8000; unlocked_by null for now).

CORE:
1. The dock is a single shared server on the surface base. Unload and the inventory Sell use it: a command that moves n units occupies the dock for max(1, ceil(n / dock_rate)) ticks. If the dock is busy the miner waits in a FIFO queue (ties by arrival tick, then miner id) and shows the state 'queued'. Selling stock from the warehouse and the other base commands do not use the dock.
2. Command DockStatus() -> {free, queue_length, eta_ticks, rate} (0 ticks). API dock_free() -> {free, queue, eta} and dock_rate() (functions.json, proxies, stubs, docs; unlocked_by null for now).
3. Events: DockQueued(miner_id, units) and DockServed(miner_id, units, waited_ticks).
4. Save: the dock state follows the same rule as in-flight commands today; the dock upgrade level is saved with the upgrades.
5. UI: a small queue badge over the base sprite, 'Dock: busy (2 queued)' in the HUD and the dock rate in the base panel; the miners panel shows 'queued'.
6. Tests: occupancy math; FIFO and tie breaks; upgrade effect; selling stock does not use the dock; several miners unloading at once finish in the expected tick order; determinism; the UI badge renders; earlier tests pass.

ACCEPTANCE: a headless session with five miners unloading at the same time shows the queue and the waiting ticks.
COMMIT: feat(core): shared dock with queueing
