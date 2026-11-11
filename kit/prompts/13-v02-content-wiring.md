# Prompt 13 of 14 (v0.2): content wiring (new achievements, unlock chain, balance report)

Follow AGENTS.md. Goal: add the 26 new achievements, two new tabs (explorer and data) and connect the new functions, modules, skins and examples to the unlock chain. This is data plus tests and a balance report. First read content/achievements.json, functions.json, modules.json, skins.json, examples.json and ui/achievements_panel.py.

1. achievements.json: add the tabs 'explorer' and 'data' (the achievements panel must show 5 tabs and still lay out without overlaps). New achievements (id | tab | parent | criteria | rewards | title):
  clockwork | code | hello_miner | scripts_finished >= 5 | function tick | Clockwork
  import_it | code | custom_function | script_feature uses_import | module itertools | Bring Your Tools
  one_liner | code | import_it | script_feature uses_comprehension | module functools | One-Liner
  own_class | code | one_liner | script_feature uses_class | module dataclasses, example 08_dataclass_logbook | Object Oriented
  safe_hands | code | own_class | script_feature uses_try | module typing | Safe Hands
  recursion | code | custom_function | script_feature uses_recursion | money 200 | Down the Rabbit Hole
  know_your_limits | mining | coal_miner | fail:tool_too_weak >= 1 | function inspect | Know Your Limits
  appraiser | mining | coal_miner | unique_ores_mined >= 3 | function ore_info | Appraiser
  patience | mining | first_dig | regens >= 1 | function wait, example 07_regen_cycle | Patience
  lucky_strike | mining | copper_age | streak >= 5 | money 150 | Lucky Strike
  unlucky | mining | copper_age | fail_streak >= 8 | money 25 | Better Luck Next Time
  ruby_hunter | mining | gold_rush | mined:ruby >= 1 | skin ruby_runner, money 1000 | Ruby Hunter
  completionist | mining | ruby_hunter | unique_ores_mined >= 7 | money 2000 | Completionist
  big_haul | business | first_sale | largest_sale >= 100 | money 100 | Big Haul
  wholesale | business | big_haul | largest_sale >= 1000 | money 500 | Wholesale
  diversified | business | first_sale | ores_in_one_sale >= 4 | money 200 | Diversified Portfolio
  upgrader | business | pocket_change | upgrades_bought >= 5 | money 300 | Upgrade Addict
  far_from_home | explorer | - | max_distance >= 20 | function distance | Far From Home
  deep_diver | explorer | far_from_home | max_distance >= 40 | function biome, example 04_explorer_spiral | Deep Diver
  crystal_hunter | explorer | deep_diver | biome:crystal_caverns >= 1 | money 500 | Crystal Hunter
  cartographer | explorer | deep_diver | biomes_visited >= 3 | money 300 | Cartographer
  marathon | explorer | far_from_home | tiles_moved >= 2000 | money 300 | Marathon
  sampler | data | - | attempts:coal >= 100 | function submit_estimate, example 05_probability_lab | Sampler
  calibrated | data | sampler | good_estimates >= 1 | money 250 | Calibrated
  well_calibrated | data | calibrated | good_estimates >= 4 | money 1000 | Well Calibrated
  big_numbers | data | sampler | attempts:any >= 2000 | money 400 | Law of Large Numbers
2. Extra rewards on EXISTING achievements: copper_age += skin copper_core; iron_will += skin steel_walker; gold_rush += skin golden_hauler and example 06_farm_ruby; first_sale += example 02_sweep_and_sell; scout += example 03_ore_hunter.
3. unlocked_by wiring (replace the nulls from prompts 10 and 12): functions wait <- patience, tick <- clockwork, distance <- far_from_home, biome <- deep_diver, ore_info <- appraiser, inspect <- know_your_limits, submit_estimate <- sampler; modules itertools <- import_it, functools <- one_liner, dataclasses <- own_class, typing <- safe_hands; skins copper_core <- copper_age, steel_walker <- iron_will, golden_hauler <- gold_rush, ruby_runner <- ruby_hunter (rusty_bot stays null); examples 01_hello null, 02_sweep_and_sell <- first_sale, 03_ore_hunter <- scout, 04_explorer_spiral <- deep_diver, 05_probability_lab <- sampler, 06_farm_ruby <- gold_rush, 07_regen_cycle <- patience, 08_dataclass_logbook <- own_class.
4. tools/balance_sim.py: a headless simulation of two simple strategies (a random walker, and a serpentine sweeper that goes home and sells when the inventory is full and buys upgrades greedily) for 200000 ticks. It prints and saves docs/BALANCE.md with the tick at which each achievement completes (or 'never'). Do NOT retune any number in this prompt; only report.
5. tools/gen_docs.py also generates docs/GUIDE.md: every achievement grouped by tab with its criteria, rewards and what it unlocks.
6. Tests: content validation passes (all ids exist, no cycles, parents in the same tab, every unlockable thing has exactly one unlocking achievement); the initial unlock sets are the expected ones; a scripted headless session unlocks a chain of achievements; the achievements panel lays out all 5 tabs without overlaps.

ACCEPTANCE: docs/GUIDE.md and docs/BALANCE.md exist and all tests pass.
COMMIT: feat(content): 26 new achievements and the v0.2 unlock chain
