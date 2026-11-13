# Prompt 17 of 25 (v0.3): refinery and contracts (core)

Follow AGENTS.md. Goal: turn ore into more valuable products and add delivery contracts. First read core/warehouse.py, core/market.py, core/engine.py, core/commands.py, core/game.py, core/progression/* and the tests from prompt 16.

CONTENT:
- recipes.json: list of {id, name, inputs, outputs, ticks, unlocked_by} (unlocked_by null for now):
  copper_bar: 3 copper -> 1 copper_bar, 60 ticks
  iron_bar: 3 iron + 1 coal -> 1 iron_bar, 80 ticks
  steel_bar: 2 iron_bar + 2 coal -> 1 steel_bar, 120 ticks
  silver_bar: 3 silver -> 1 silver_bar, 100 ticks
  gold_bar: 3 gold + 1 coal -> 1 gold_bar, 140 ticks
  cut_ruby: 2 ruby -> 1 cut_ruby, 200 ticks
- config.json: furnace_start_slots 1, contract_interval_ticks 3000, contract_start_slots 3, contract_deadline_min 4000, contract_deadline_max 12000, contract_premium_min 1.3, contract_premium_max 2.0, contract_value_min 500, contract_value_max 4000.
- upgrades.json: furnace (+1 furnace slot per level, 3 levels, costs 300 900 2500) and contract_board (+1 contract slot per level, 2 levels, costs 500 1500); both unlocked_by null for now.

CORE:
1. core/refinery.py: Refinery(recipes, slots). start(recipe_id, times, warehouse, tick) validates that the recipe is unlocked, a slot is free and the warehouse holds times * inputs; it takes the inputs out immediately and creates a job lasting ticks * times. advance(tick) finishes jobs and puts the outputs into the warehouse; if there is no room the job stays 'blocked' until there is. status() lists the jobs with progress. to_dict() / from_dict().
2. core/contracts.py: ContractBoard(seed, catalog, config). Every contract_interval_ticks a new contract is generated if there is a free slot: item (weighted choice among the items that are available at that moment: unlocked ores, plus products whose recipe is unlocked), quantity = ceil(target_value / base_value) with target_value in [contract_value_min, contract_value_max] scaled by how many ores are unlocked, a deadline in [min, max], reward = floor(quantity * base_value * premium) with premium in [premium_min, premium_max]. All randomness through mix64(seed, slot_number, k). advance(tick) expires late contracts. deliver(contract_id, warehouse) needs the full quantity in the warehouse, removes it and pays the reward. to_dict() / from_dict().
3. ProgressionView gets is_recipe_unlocked (until prompt 23 it simply returns True when unlocked_by is null). Validate recipes.json against the item catalog.
4. Commands (0 ticks unless noted): Recipes(), Refine(recipe_id, times=1) (on the base; 2 ticks), RefineryStatus(), Contracts(), Deliver(contract_id) (on the base; 2 ticks). The engine advances the refinery and the board every tick.
5. Events: RefineStarted(recipe, times), RefineFinished(recipe, times, outputs), ContractGenerated(id), ContractDelivered(id, reward), ContractExpired(id).
6. API (functions.json, proxies, stubs, docs; unlocked_by null for now): recipes(), refine(recipe_id, times=1), refinery(), contracts(), deliver(contract_id).
7. Game facade methods for the UI (instant, no position or tick rules): game.start_refine(recipe_id, times), game.deliver_contract(id), game.sell_stock(item, amount).
8. Save version 6 with refinery and board state; migrate version 5. Keep a fixture.
9. Tests: recipe validation (inputs and outputs are known items); job lifecycle, blocked outputs, slot limits; contract determinism for a seed, expiry, partial stock refuses delivery, reward paid; save/load round trip; API results are JSON friendly; earlier tests pass.

ACCEPTANCE: a headless session mines copper, unloads, refines a bar, sells it and delivers a contract.
COMMIT: feat(core): refinery and contracts
