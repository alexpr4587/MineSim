# Prompt 34 of 36 (v0.4): progression extension

Follow AGENTS.md. Goal: building blocks for the v0.4 achievements. No new achievements yet (prompt 35). First read core/progression/*, core/events.py, scripting/manager.py and docs/PROGRESSION.md.

1. New counters from events, documented in docs/PROGRESSION.md: max_layer; descents; mined_layer:<n> (units mined per layer); energy_used (total energy spent); charges; strandings; rescues; overheats; peak_temp (the highest temperature reached by a miner without overheating in that stretch); dock_wait_ticks (total waiting in the dock queue); dock_units (units served by the dock); fail:low_energy and fail:overheated (from MineAttempted reasons and from refused moves); peak_deep_miners (the maximum number of miners at the same time in layers with heat > 0).
2. Publish MoveRefused(miner_id, reason) when a Move is refused (low_energy or overheated) and count it in fail:<reason>. api:<function> still counts successful calls only.
3. Save: bump the version and migrate older saves (new counters 0).
4. Tests: each counter with synthetic events; the refusal events; migration; earlier tests pass.

ACCEPTANCE: a headless scripted session moves every new counter as documented.
COMMIT: feat(core): v0.4 counters
