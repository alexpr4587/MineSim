# Prompt 45 of 46 (v0.5): content (collection achievements, cozy skins)

Follow AGENTS.md. Goal: add the collection achievements and the cozy skins that reward exploring and playing. Data, counters, tests and docs. First read content/achievements.json, content/skins.json, core/progression/* and the Journal code.

1. Counters (documented in docs/PROGRESSION.md): codex_entries; codex:ores, codex:products, codex:biomes, codex:layers, codex:skins, codex:events (counts of discovered entries by category); rare_finds (units of gold or ruby mined); ticks_played (engine ticks); rain_seen (rain periods the player was present for); tutorial_done.
2. Four new skins in skins.json (palette swaps with names and short cozy descriptions): lantern_bot (warm amber glow), moss_bot (soft greens), night_owl (deep blue with a gold visor), golden_hour (peach and rose). unlocked_by as below.
3. New tab 'collection' (11 tabs in total; the achievements panel keeps a scrollable tab bar) and these achievements (id | tab | parent | criteria | rewards | title):
  welcome | code | - | tutorial_done >= 1 | money 200 | Welcome Aboard
  first_entry | collection | - | codex_entries >= 1 | skin lantern_bot | First Entry
  rock_collector | collection | first_entry | codex:ores >= 7 | skin moss_bot | Rock Collector
  bar_collector | collection | first_entry | codex:products >= 6 | money 1000 | Bar Collector
  biome_tourist | collection | first_entry | codex:biomes >= 6 | skin night_owl | Biome Tourist
  four_floors_down | collection | biome_tourist | codex:layers >= 4 | skin golden_hour | Four Floors Down
  event_witness | collection | first_entry | codex:events >= 3 | money 500 | Event Witness
  lucky_day | collection | rock_collector | rare_finds >= 25 | money 2000 | Lucky Day
  codex_complete | collection | rock_collector | codex_entries >= 25 | money 10000 | Codex Complete
  cozy_hour | collection | - | ticks_played >= 36000 | money 500 | Cozy Hour
  rainy_day | collection | cozy_hour | rain_seen >= 1 | money 300 | Rainy Day
4. Wire the new skins to their achievements (unlocked_by) and show them in the wardrobe; validate that every unlockable thing has exactly one unlocking achievement.
5. tools/gen_docs.py regenerates docs/GUIDE.md and docs/PROGRESSION.md.
6. Tests: each counter with synthetic events; content validation; the panel lays out 11 tabs; the wardrobe shows the new skins locked and then unlocked; save migration (new counters 0).

ACCEPTANCE: docs/GUIDE.md lists 97 achievements in 11 tabs and all tests pass.
COMMIT: feat(content): collection achievements and cozy skins
