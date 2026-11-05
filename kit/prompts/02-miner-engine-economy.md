# Prompt 2 of 8: miner, tick engine and economy (core)

Follow AGENTS.md. Add the miner, the tick engine and the economy to core/ (still no Qt, no scripting).

CONTENT: extend config.json with move_ticks 4, mine_tick_base 3, sell_ticks 2, scan_ticks_per_radius 1, start_capacity 10, start_tool_power 1, start_tool_tier 0, start_scan_radius 0, free_calls_before_forced_tick 200, script_idle_timeout_s 5, console_max_lines 500. Add upgrades.json: list of {id, name, description, stat, per_level, max_level, costs, unlocked_by}:
  backpack: capacity +10 per level, 5 levels, costs 25 60 140 300 700, unlocked_by first_sale
  pickaxe: tool_power +1 and tool_tier +1 per level, 5 levels, costs 50 150 400 1000 2500, unlocked_by pocket_change
  motor: move_ticks -1 per level (never below 1), 3 levels, costs 100 400 1500, unlocked_by investor
  scanner: scan_radius +1 per level, 4 levels, costs 150 500 1500 4000, unlocked_by investor

CODE:
1. core/events.py: tiny typed EventBus (subscribe(event_type, fn), publish(event)) and frozen dataclass events: Moved, MineAttempted(ore_id, success), OreMined(ore_id, amount), Sold(money, items), UpgradeBought(id, level), ScriptStarted(defines_function), ScriptFinished, ScriptFailed(error_type), AchievementUnlocked(id), TickAdvanced(tick).
2. core/direction.py: enum Direction NORTH/EAST/SOUTH/WEST with dx, dy (y grows southwards, i.e. down on screen) and parse() accepting names like 'north' or 'n'.
3. core/miner.py: Miner dataclass: x, y, facing, inventory (ore -> count), capacity, money, tool_power, tool_tier, move_ticks, scan_radius, and stats (attempts and successes per ore, total_mined, total_earned, tiles_moved, sales).
4. core/commands.py: frozen dataclasses Move(direction), Mine(), Peek(), Scan(radius), Sell(), BuyUpgrade(id), Wait(ticks), Position(), Inventory(), Stats(). Each has cost_ticks(...) and execute(engine) -> JSON-serializable result dict. Peek, Position, Inventory and Stats cost 0 ticks. Rules:
   - Move: always allowed, cost = miner.move_ticks.
   - Mine works on the tile the miner stands on (like harvesting in The Farmer Was Replaced). Failure results: {ok: False, reason: 'locked_ore'} if the ore is not unlocked yet, 'tool_too_weak' if tool_tier < ore.tier, 'inventory_full', 'nothing_to_mine' (base or depleted tile). Otherwise cost = ceil(ore.hardness * mine_tick_base / tool_power) and success happens when unit(mix64(seed, tick, x, y, attempt_counter)) < ore.mine_probability. Success: +1 item and the world tile becomes depleted. Failure: the tile stays and the attempt is counted.
   - Peek returns the ore id of the current tile, None if empty, or 'unknown' when the ore is locked.
   - Scan(radius): cost = 1 + scan_ticks_per_radius * radius; radius is capped by miner.scan_radius; returns (dx, dy, ore_id or 'unknown') for non-empty tiles.
   - Sell only works on base tiles: converts the whole inventory to money using base_value; cost sell_ticks.
   - BuyUpgrade needs the upgrade unlocked, enough money and level < max_level; applies the stat change.
5. core/engine.py: GameEngine(world, miner, content, events, progression_view). Tick counter; submit(cmd) -> Ticket (done, result); step() advances one tick. Commands run FIFO; one command occupies the miner for its cost and executes on its last tick; zero-cost commands execute immediately on submit. run_until_idle(max_ticks) for tests. Publishes events. progression_view is a Protocol (is_ore_unlocked, is_function_unlocked, is_upgrade_unlocked, is_module_unlocked); provide AllUnlocked for tests (the real one arrives in a later prompt).
6. Tests: same seed + same commands gives an identical final state and event log; tick costs; mining probability over 5000 attempts matches p within 3 sigma for two ores; capacity limit; sell only on base; upgrades apply and respect cost and max_level; locked ore and weak tool results.

ACCEPTANCE: a headless test creates an engine, submits Move/Mine/Sell and reads the results.
COMMIT: feat(core): miner, engine and economy
