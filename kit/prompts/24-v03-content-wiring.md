# Prompt 24 of 25 (v0.3): content wiring (achievements and unlock chain)

Follow AGENTS.md. Goal: add the v0.3 achievements and wire everything new to the unlock chain. Data, tests and a balance report. First read content/achievements.json and all the content files from prompts 15 to 22.

1. New tabs: trading, industry, fleet (explorer already exists). The achievements panel must show 8 tabs without overlaps (make the tab bar scrollable if needed). New achievements (id | tab | parent | criteria | rewards | title):
  storage_unit | trading | - | sales >= 5 | feature warehouse, functions unload stock sell_stock, upgrade warehouse | Storage Unit
  market_watcher | trading | storage_unit | unloads >= 3 | feature market, functions price prices | Market Watcher
  chartist | trading | market_watcher | api:price >= 25 | function price_history, module bisect | Chartist
  sell_high | trading | market_watcher | sold_high >= 20 | money 500 | Sell High
  hoarder | trading | storage_unit | warehouse_peak >= 300 | money 300 | Hoarder
  trend_follower | trading | chartist | api:price_history >= 20 | module operator, examples 09_market_watcher and 15_price_forecast | Trend Follower
  first_order | trading | storage_unit | money_earned >= 2000 | feature contracts, functions contracts deliver, upgrade contract_board | First Order
  contract_runner | trading | first_order | contracts_done >= 3 | example 11_contract_runner | Contract Runner
  big_client | trading | contract_runner | contract_reward_total >= 20000 | money 2500 | Big Client
  corporate_favorite | trading | contract_runner | contracts_done >= 15 | money 4000 | Corporate Favorite
  market_master | trading | sell_high | money_earned >= 50000 | money 5000 | Market Master
  smelter | industry | - | mined:copper >= 30 | feature refinery, functions recipes refine refinery, recipe copper_bar, upgrade furnace | Smelter
  iron_works | industry | smelter | recipe:copper_bar >= 5 | recipe iron_bar | Iron Works
  steel_age | industry | iron_works | recipe:iron_bar >= 5 | recipe steel_bar | Steel Age
  silversmith | industry | iron_works | mined:silver >= 10 | recipe silver_bar | Silversmith
  goldsmith | industry | silversmith | mined:gold >= 10 | recipe gold_bar | Goldsmith
  lapidary | industry | goldsmith | mined:ruby >= 5 | recipe cut_ruby | Lapidary
  bar_factory | industry | steel_age | bars_made >= 50 | money 1500 | Bar Factory
  production_line | industry | steel_age | api:refine >= 30 | example 10_refine_everything | Production Line
  second_pair_of_hands | fleet | - | money_earned >= 3000 | feature drones, functions drone_id drones spawn_drone kill_drone assign, upgrade drone_bay | Second Pair of Hands
  first_drone | fleet | second_pair_of_hands | drones_spawned >= 1 | functions shared_get shared_set, example 12_two_drones | Teamwork
  small_fleet | fleet | first_drone | max_drones_alive >= 3 | money 1000 | Small Fleet
  swarm | fleet | small_fleet | max_drones_alive >= 5 | money 3000 | Swarm
  message_board | fleet | first_drone | api:shared_set >= 50 | example 16_fleet_manager | Message Board
  inheritance | fleet | first_drone | script_feature uses_inheritance | modules abc enum, example 13_worker_classes | Inheritance
  news_reader | explorer | far_from_home | events_started >= 3 | function events | News Reader
  prospector | explorer | news_reader | rich_vein_mined >= 10 | example 14_event_hunter, money 400 | Prospector
  stuck_in_the_mud | explorer | news_reader | slow_zone_moves >= 20 | money 200 | Stuck in the Mud
2. unlocked_by wiring (replace the nulls from prompts 15 to 22): every new function, module, recipe, upgrade, feature and example gets exactly the achievement that rewards it in the table above. Products need no unlock.
3. Extend tools/balance_sim.py: strategies that use the warehouse, the market (sell when the index is >= 1.1), the refinery and one extra drone, in lockstep for 300000 ticks; update docs/BALANCE.md with the completion tick of every achievement (or 'never'). Do NOT retune numbers in this prompt.
4. tools/gen_docs.py regenerates docs/GUIDE.md with the new tabs.
5. Tests: content validation (ids exist, no cycles, parents in the same tab, every unlockable thing has exactly one unlocking achievement); the initial unlock sets; a scripted headless session unlocks a chain across tabs (storage_unit, market_watcher, smelter); the panel lays out 8 tabs.

ACCEPTANCE: docs/GUIDE.md and docs/BALANCE.md are updated and all tests pass.
COMMIT: feat(content): v0.3 achievements and unlock chain
