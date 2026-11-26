# Prompt 42 of 46 (v0.5): goals, journal, records and first-run guide

Follow AGENTS.md. Goal: always give the player a small next thing to chase and a place to see their progress. First read core/progression/*, ui/hud.py, ui/achievements_panel.py, ui/toasts.py, ui/options_panel.py and core/save.py.

1. Goals widget (HUD, bottom left, collapsible): up to 3 'next goals': available achievements (parent completed) sorted by progress fraction, each with a progress bar, the numbers (7/20) and a hint line about what it unlocks. Clicking one opens the achievements panel at that node. Completing a goal makes the widget pop and refresh.
2. First-run guide: content/tutorial.json, a list of steps {id, text, highlight (a widget object name), advance_on (an event or action)}: open the editor (E), press Run, watch the miner, mine something (First Dig), go home and sell, buy the first upgrade, open the achievements panel (L). A pulsing outline plus a small text bubble; every step can be skipped and the whole guide can be dismissed; it only starts on a brand new game; 'Reset tutorial' in Options. Event TutorialCompleted.
3. Journal (key J): tabs Ores, Products, Biomes, Layers, Skins and Events. Undiscovered entries are silhouettes with '???'. Discovered entries show the data the player may know, the player's own stats (units mined, observed success rate, first found) and a short cozy flavor text from content/codex.json (one or two friendly lines per entry). Discovery gives a toast, the codex_entry sound and a NEW badge until viewed. Never show hidden numbers such as the true mine_probability.
4. Records tab in the Journal: lifetime totals (ores mined by type, money earned, ticks played, scripts run), personal bests with the tick when they happened (biggest sale, best mining streak, deepest layer, most miners at once) and a small income-per-minute sparkline for the last hour.
5. Save: discovered journal entries, records and tutorial progress; a new version with migration. Keep a fixture.
6. Events: CodexDiscovered(category, id) and RecordBroken(name, value).
7. Tests: goal selection and ordering; the guide advances on the right events, can be skipped and does not start on a loaded game; discovery for each category; flavor text exists for every entry; no secret values leak into the Journal; records update; migration.

ACCEPTANCE: screenshots of the goals widget, a tutorial step, the Journal with discovered and undiscovered entries, and the Records tab.
COMMIT: feat(ui): goals, journal, records and first-run guide
