# Prompt 23 of 25 (v0.3): progression extension (counters, features, recipes)

Follow AGENTS.md. Goal: building blocks for the v0.3 achievements. No new achievements yet (prompt 24). First read core/progression/*, core/events.py, core/save.py, scripting/manager.py and ui/*panel.py.

1. New counters from events, documented in docs/PROGRESSION.md: unloads (Unloaded with something moved); warehouse_peak (max units stored); sold_high (units sold when the sale avg_index >= 1.25); recipe:<id> (finished jobs of a recipe); bars_made (product units produced); contracts_done; contract_reward_total; drones_spawned; max_drones_alive; events_started (all world events); rich_vein_mined (OreMined with in_rich_vein); slow_zone_moves (Moved with in_slow_zone); and api:<function> (successful script calls of each API function; the manager publishes ApiCalled(function, drone_id)).
2. New script feature uses_inheritance (a class with at least one base other than object), detected with ast in the host.
3. New reward types unlock_recipe and unlock_feature (features: warehouse, market, refinery, contracts, drones). ProgressionState gets unlocked_recipes and unlocked_features (starting with everything whose unlocked_by is null); is_recipe_unlocked now uses the real state; the ProgressionView gets is_feature_unlocked. recipes.json unlocked_by is validated against achievements.json.
4. UI gating: the base panel tabs (warehouse, refinery, contracts), the market panel and the drones panel show a lock overlay 'Unlocks with: <achievement title>' while their feature is locked; the keys still open the panel. Game methods that act on locked features refuse with a clear result.
5. Save: bump the version and migrate older saves (new counters 0; features and recipes start from the null unlocked_by rule).
6. Tests: each counter with synthetic events; uses_inheritance positive and negative snippets; the new reward types; the gating in the UI (offscreen); migration; earlier tests pass.

ACCEPTANCE: a headless scripted session moves every new counter as documented.
COMMIT: feat(core): v0.3 counters, features and recipe unlocks
