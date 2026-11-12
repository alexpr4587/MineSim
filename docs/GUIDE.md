# DigScript Achievement Guide

Every achievement belongs to one of five tabs: Code, Mining, Business, Explorer and Data. An achievement becomes available once its parent is completed. Completing it grants the rewards and unlocks listed below.

## Code

### Hello, Miner (`hello_miner`)

Run a script to completion.

**Criteria:** `scripts_finished` reaches 1.

**Rewards:** function `inventory`

**Unlocks:** function `inventory`

### Wanderer (`wanderer`)

Move 200 tiles.

**Requires:** Hello, Miner

**Criteria:** `tiles_moved` reaches 200.

**Rewards:** module `random`

**Unlocks:** module `random`

### Scout (`scout`)

Make 50 mining attempts.

**Requires:** Wanderer

**Criteria:** `attempts:any` reaches 50.

**Rewards:** function `scan`; example `03_ore_hunter`

**Unlocks:** function `scan`; example `03_ore_hunter`

### Data Driven (`data_driven`)

Make 200 mining attempts.

**Requires:** Scout

**Criteria:** `attempts:any` reaches 200.

**Rewards:** function `stats`; module `statistics`

**Unlocks:** function `stats`; module `statistics`

### Your Own Function (`custom_function`)

Write a script that defines a function.

**Requires:** Hello, Miner

**Criteria:** A script defines a function.

**Rewards:** module `collections`; module `heapq`

**Unlocks:** module `collections`; module `heapq`

### Clockwork (`clockwork`)

Finish five scripts.

**Requires:** Hello, Miner

**Criteria:** `scripts_finished` reaches 5.

**Rewards:** function `tick`

**Unlocks:** function `tick`

### Bring Your Tools (`import_it`)

Use an import in a script.

**Requires:** Your Own Function

**Criteria:** A script uses `uses_import`.

**Rewards:** module `itertools`

**Unlocks:** module `itertools`

### One-Liner (`one_liner`)

Use a comprehension in a script.

**Requires:** Bring Your Tools

**Criteria:** A script uses `uses_comprehension`.

**Rewards:** module `functools`

**Unlocks:** module `functools`

### Object Oriented (`own_class`)

Define a class in a script.

**Requires:** One-Liner

**Criteria:** A script uses `uses_class`.

**Rewards:** module `dataclasses`; example `08_dataclass_logbook`

**Unlocks:** module `dataclasses`; example `08_dataclass_logbook`

### Safe Hands (`safe_hands`)

Use try/except in a script.

**Requires:** Object Oriented

**Criteria:** A script uses `uses_try`.

**Rewards:** module `typing`

**Unlocks:** module `typing`

### Down the Rabbit Hole (`recursion`)

Write a recursive function.

**Requires:** Your Own Function

**Criteria:** A script uses `uses_recursion`.

**Rewards:** +200 money

**Unlocks:** Nothing.

## Mining

### First Dig (`first_dig`)

Mine your first ore.

**Criteria:** `mined:any` reaches 1.

**Rewards:** ore `coal`; function `sell`

**Unlocks:** ore `coal`; function `sell`

### Coal Miner (`coal_miner`)

Mine 20 coal.

**Requires:** First Dig

**Criteria:** `mined:coal` reaches 20.

**Rewards:** ore `copper`

**Unlocks:** ore `copper`

### Copper Age (`copper_age`)

Mine 20 copper.

**Requires:** Coal Miner

**Criteria:** `mined:copper` reaches 20.

**Rewards:** ore `iron`; skin `copper_core`

**Unlocks:** ore `iron`; skin `copper_core`

### Iron Will (`iron_will`)

Mine 20 iron.

**Requires:** Copper Age

**Criteria:** `mined:iron` reaches 20.

**Rewards:** ore `silver`; skin `steel_walker`

**Unlocks:** ore `silver`; skin `steel_walker`

### Silver Lining (`silver_lining`)

Mine 20 silver.

**Requires:** Iron Will

**Criteria:** `mined:silver` reaches 20.

**Rewards:** ore `gold`

**Unlocks:** ore `gold`

### Gold Rush (`gold_rush`)

Mine 10 gold.

**Requires:** Silver Lining

**Criteria:** `mined:gold` reaches 10.

**Rewards:** ore `ruby`; skin `golden_hauler`; example `06_farm_ruby`

**Unlocks:** ore `ruby`; skin `golden_hauler`; example `06_farm_ruby`

### Know Your Limits (`know_your_limits`)

Try to mine an ore that is too hard.

**Requires:** Coal Miner

**Criteria:** `fail:tool_too_weak` reaches 1.

**Rewards:** function `inspect`

**Unlocks:** function `inspect`

### Appraiser (`appraiser`)

Mine three different ores.

**Requires:** Coal Miner

**Criteria:** `unique_ores_mined` reaches 3.

**Rewards:** function `ore_info`

**Unlocks:** function `ore_info`

### Patience (`patience`)

See a mined tile regenerate.

**Requires:** First Dig

**Criteria:** `regens` reaches 1.

**Rewards:** function `wait`; example `07_regen_cycle`

**Unlocks:** function `wait`; example `07_regen_cycle`

### Lucky Strike (`lucky_strike`)

Succeed five mining attempts in a row.

**Requires:** Copper Age

**Criteria:** `streak` reaches 5.

**Rewards:** +150 money

**Unlocks:** Nothing.

### Better Luck Next Time (`unlucky`)

Miss eight mining attempts in a row.

**Requires:** Copper Age

**Criteria:** `fail_streak` reaches 8.

**Rewards:** +25 money

**Unlocks:** Nothing.

### Ruby Hunter (`ruby_hunter`)

Mine a ruby.

**Requires:** Gold Rush

**Criteria:** `mined:ruby` reaches 1.

**Rewards:** skin `ruby_runner`; +1000 money

**Unlocks:** skin `ruby_runner`

### Completionist (`completionist`)

Mine all seven ores.

**Requires:** Ruby Hunter

**Criteria:** `unique_ores_mined` reaches 7.

**Rewards:** +2000 money

**Unlocks:** Nothing.

## Business

### First Sale (`first_sale`)

Sell ore for money.

**Criteria:** `sales` reaches 1.

**Rewards:** function `buy_upgrade`; upgrade `backpack`; example `02_sweep_and_sell`

**Unlocks:** function `buy_upgrade`; upgrade `backpack`; example `02_sweep_and_sell`

### Pocket Change (`pocket_change`)

Earn 100 money from selling ore.

**Requires:** First Sale

**Criteria:** `money_earned` reaches 100.

**Rewards:** upgrade `pickaxe`

**Unlocks:** upgrade `pickaxe`

### Investor (`investor`)

Earn 1000 money from selling ore.

**Requires:** Pocket Change

**Criteria:** `money_earned` reaches 1000.

**Rewards:** upgrade `motor`; upgrade `scanner`

**Unlocks:** upgrade `motor`; upgrade `scanner`

### Tycoon (`tycoon`)

Earn 10000 money from selling ore.

**Requires:** Investor

**Criteria:** `money_earned` reaches 10000.

**Rewards:** +500 money

**Unlocks:** Nothing.

### Big Haul (`big_haul`)

Earn 100 money in a single sale.

**Requires:** First Sale

**Criteria:** `largest_sale` reaches 100.

**Rewards:** +100 money

**Unlocks:** Nothing.

### Wholesale (`wholesale`)

Earn 1000 money in a single sale.

**Requires:** Big Haul

**Criteria:** `largest_sale` reaches 1000.

**Rewards:** +500 money

**Unlocks:** Nothing.

### Diversified Portfolio (`diversified`)

Sell four different ores at once.

**Requires:** First Sale

**Criteria:** `ores_in_one_sale` reaches 4.

**Rewards:** +200 money

**Unlocks:** Nothing.

### Upgrade Addict (`upgrader`)

Buy five upgrade levels.

**Requires:** Pocket Change

**Criteria:** `upgrades_bought` reaches 5.

**Rewards:** +300 money

**Unlocks:** Nothing.

## Explorer

### Far From Home (`far_from_home`)

Reach distance 20 from the base.

**Criteria:** `max_distance` reaches 20.

**Rewards:** function `distance`

**Unlocks:** function `distance`

### Deep Diver (`deep_diver`)

Reach distance 40 from the base.

**Requires:** Far From Home

**Criteria:** `max_distance` reaches 40.

**Rewards:** function `biome`; example `04_explorer_spiral`

**Unlocks:** function `biome`; example `04_explorer_spiral`

### Crystal Hunter (`crystal_hunter`)

Visit the Crystal Caverns.

**Requires:** Deep Diver

**Criteria:** `biome:crystal_caverns` reaches 1.

**Rewards:** +500 money

**Unlocks:** Nothing.

### Cartographer (`cartographer`)

Visit three different biomes.

**Requires:** Deep Diver

**Criteria:** `biomes_visited` reaches 3.

**Rewards:** +300 money

**Unlocks:** Nothing.

### Marathon (`marathon`)

Move 2000 tiles.

**Requires:** Far From Home

**Criteria:** `tiles_moved` reaches 2000.

**Rewards:** +300 money

**Unlocks:** Nothing.

## Data

### Sampler (`sampler`)

Make 100 attempts on coal.

**Criteria:** `attempts:coal` reaches 100.

**Rewards:** function `submit_estimate`; example `05_probability_lab`

**Unlocks:** function `submit_estimate`; example `05_probability_lab`

### Calibrated (`calibrated`)

Submit a good estimate.

**Requires:** Sampler

**Criteria:** `good_estimates` reaches 1.

**Rewards:** +250 money

**Unlocks:** Nothing.

### Well Calibrated (`well_calibrated`)

Submit four good estimates.

**Requires:** Calibrated

**Criteria:** `good_estimates` reaches 4.

**Rewards:** +1000 money

**Unlocks:** Nothing.

### Law of Large Numbers (`big_numbers`)

Make 2000 mining attempts.

**Requires:** Sampler

**Criteria:** `attempts:any` reaches 2000.

**Rewards:** +400 money

**Unlocks:** Nothing.
