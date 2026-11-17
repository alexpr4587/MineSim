# Prompt 35 of 36 (v0.4): content wiring (achievements and unlock chain)

Follow AGENTS.md. Goal: add the v0.4 achievements and wire everything new to the unlock chain. Data, tests and a balance report. First read content/achievements.json and all the content files from prompts 28 to 33.

1. New tabs: depths and engineering (10 tabs in total; the achievements panel must still lay out without overlaps and keep a scrollable tab bar). New achievements (id | tab | parent | criteria | rewards | title):
  out_of_juice | engineering | - | fail:low_energy >= 1 | functions battery charge energy_cost, upgrade battery | Out of Juice
  power_user | engineering | out_of_juice | energy_used >= 5000 | module json, example 17_energy_budget | Power User
  first_charge | engineering | out_of_juice | charges >= 5 | upgrade charger | Plugged In
  rescued | engineering | out_of_juice | rescues >= 1 | money 100 | Call a Tow
  efficiency_expert | engineering | power_user | api:energy_cost >= 50 | example 21_night_shift | Efficiency Expert
  traffic_jam | engineering | - | dock_wait_ticks >= 50 | functions dock_free dock_rate, upgrade dock | Traffic Jam
  dock_master | engineering | traffic_jam | dock_units >= 2000 | example 20_dock_etiquette, money 500 | Dock Master
  deep_ambition | depths | - | money_earned >= 8000 | functions layer layers descend ascend, upgrade shaft | Deep Ambition
  first_descent | depths | deep_ambition | max_layer >= 1 | example 18_go_deep, money 300 | First Descent
  galleries_veteran | depths | first_descent | mined_layer:1 >= 100 | module copy, money 500 | Gallery Veteran
  feel_the_heat | depths | first_descent | max_layer >= 2 | functions temperature cool climate, upgrades cooling ventilation | Feel the Heat
  cool_head | depths | feel_the_heat | peak_temp >= 80 | example 19_climate_watch | Cool Head
  meltdown | depths | feel_the_heat | overheats >= 1 | money 150 | Meltdown
  deep_miner | depths | feel_the_heat | mined_layer:2 >= 200 | money 1500 | Deep Miner
  fresh_air | depths | feel_the_heat | peak_deep_miners >= 3 | example 23_vent_manager | Fresh Air
  abyss_gazer | depths | deep_miner | max_layer >= 3 | example 22_layer_prospector | Into the Abyss
  abyssal_haul | depths | abyss_gazer | mined_layer:3 >= 100 | example 24_full_automation, money 5000 | Abyssal Haul
2. unlocked_by wiring (replace the nulls from prompts 28 to 33): every new function, module, upgrade and example gets exactly the achievement that rewards it above.
3. Extend tools/balance_sim.py: strategies that charge, go down the shaft and use several miners with the dock and the airflow, in lockstep for 400000 ticks; update docs/BALANCE.md with the completion tick of every achievement (or 'never'). Do NOT retune numbers in this prompt.
4. tools/gen_docs.py regenerates docs/GUIDE.md with the new tabs.
5. Tests: content validation (ids exist, no cycles, parents in the same tab, every unlockable thing has exactly one unlocking achievement); the initial unlock sets; a scripted headless session unlocks out_of_juice, deep_ambition and first_descent; the panel lays out 10 tabs.

ACCEPTANCE: docs/GUIDE.md and docs/BALANCE.md are updated and all tests pass.
COMMIT: feat(content): v0.4 achievements and unlock chain
