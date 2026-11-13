# Prompt 4 of 8: progression (achievements, unlocks) and saves (core)

Follow AGENTS.md. Add progression (achievements and unlocks) and saving to core/. From this prompt on, every unlocked_by id in ores, functions, modules and upgrades must be validated at load time against achievements.json, and every reward id must point to an existing function, ore, upgrade or module.

CONTENT: achievements.json with schema {id, tab ('code' | 'mining' | 'business'), parent (id or null), title, description, criteria, rewards}. criteria is {type: 'counter', counter, target} or {type: 'script_defines_function'}. Counters: mined:any, mined:<ore_id>, attempts:any, tiles_moved, sales (only sales that gave money), money_earned (money from selling only), scripts_finished (normal completion only). rewards is a list of {type: unlock_function | unlock_ore | unlock_upgrade | unlock_module, id} or {type: money, amount}.
The 15 starter achievements (id | tab | parent | criteria | rewards | title):
  hello_miner | code | - | scripts_finished >= 1 | function inventory | Hello, Miner
  wanderer | code | hello_miner | tiles_moved >= 200 | module random | Wanderer
  scout | code | wanderer | attempts:any >= 50 | function scan | Scout
  data_driven | code | scout | attempts:any >= 200 | function stats, module statistics | Data Driven
  custom_function | code | hello_miner | script defines a function | modules collections and heapq | Your Own Function
  first_dig | mining | - | mined:any >= 1 | ore coal, function sell | First Dig
  coal_miner | mining | first_dig | mined:coal >= 20 | ore copper | Coal Miner
  copper_age | mining | coal_miner | mined:copper >= 20 | ore iron | Copper Age
  iron_will | mining | copper_age | mined:iron >= 20 | ore silver | Iron Will
  silver_lining | mining | iron_will | mined:silver >= 20 | ore gold | Silver Lining
  gold_rush | mining | silver_lining | mined:gold >= 10 | ore ruby | Gold Rush
  first_sale | business | - | sales >= 1 | function buy_upgrade, upgrade backpack | First Sale
  pocket_change | business | first_sale | money_earned >= 100 | upgrade pickaxe | Pocket Change
  investor | business | pocket_change | money_earned >= 1000 | upgrades motor and scanner | Investor
  tycoon | business | investor | money_earned >= 10000 | money 500 | Tycoon

CODE:
1. core/progression/state.py: ProgressionState (counters, completed {id: tick}, unlocked sets for functions, ores, upgrades, modules). At the start everything with unlocked_by null is unlocked.
2. core/progression/service.py: ProgressionService subscribes to the engine and script events and updates counters. An achievement is available once its parent is completed (roots are always available) and only available achievements can complete. It applies rewards and publishes AchievementUnlocked. It implements the ProgressionView protocol (is_*_unlocked) plus requirement_title(kind, id) (the title of the achievement that unlocks something, used in error messages) and progress(id) -> (current, target) for the UI.
3. core/save.py: SaveGame pydantic model {version: 1, seed, tick, miner, world_delta, progression}; save(path) and load(path) with an atomic write (temp file + os.replace) and a migrate(data) hook keyed by version; default file platformdirs user_data_dir('MineSim')/saves/slot1.json. A corrupted or newer save raises SaveError and never crashes the app.
4. core/game.py: Game facade that wires content, world, miner, engine, events and progression: Game.new(seed=None), Game.load(path), game.save(path). It is the single entry point for ui/ and scripting/.
5. Tests: each criteria type fires on the right events; children are not available before their parent; each reward type applies; locked things report the right achievement title; a save/load round trip gives the same state and the same next 500 ticks for a scripted session; corrupted and wrong-version saves are handled; content validation catches an unknown achievement id in unlocked_by.

ACCEPTANCE: a headless test plays: mine -> first_dig unlocks coal and sell; sell -> first_sale unlocks buy_upgrade and the backpack upgrade.
COMMIT: feat(core): achievements, unlocks and saves
