# Prompt 31 of 36 (v0.4): heat and ventilation

Follow AGENTS.md. Goal: deeper layers are hot, and airflow is a shared resource of the fleet. The mechanic is always on. First read core/engine.py, core/commands.py, content/layers.json, ui/hud.py, ui/miners_panel.py and the energy code from prompt 30.

CONTENT:
- config.json: heat_gain_per_level 0.12 (temperature per tick of activity per heat level), cool_rate 2.0 (per tick on a station, the base or layer 0), overheat_at 100, cooldown_ticks 300, cooldown_temperature 50, airflow_start 4 (miners that can work in hot layers without penalty), overload_penalty 0.5 (extra heat factor per miner above the airflow), hot_layer_min_heat 1.
- upgrades.json: cooling (-15 percent heat gain per level, 4 levels, costs 400 1200 3000 7000) and ventilation (+2 airflow per level, 5 levels, costs 500 1500 3500 8000 16000); unlocked_by null for now.

CORE:
1. Temperature (0 to 100) per miner. Every tick a miner spends executing an action in a layer with heat > 0 it gains heat_gain_per_level * heat * (1 + overload) * (1 - cooling reduction), where overload = overload_penalty * max(0, miners_in_hot_layers - airflow) and airflow = airflow_start + the ventilation bonus. On layer 0, on stations and on the base it cools by cool_rate per tick.
2. Overheat: at overheat_at the miner shuts down for cooldown_ticks (all its actions are refused with reason 'overheated'), then restarts at cooldown_temperature. Events: MinerOverheated(miner_id) and MinerRecovered(miner_id).
3. Commands (0 ticks except Cool): Temperature(), Climate() -> {layer, heat, airflow, miners_in_hot_layers, overload}, Cool(target=30) (on a station or the base: waits until the temperature reaches the target; the duration comes from the cool rate).
4. API (functions.json, proxies, stubs, docs; unlocked_by null for now): temperature(), cool(target=30), climate(). move() returns False and mine() reports 'overheated' while the miner is shut down.
5. UI: a temperature bar in the HUD and the miners panel (green to red), an 'overheated' badge, an airflow indicator in the HUD ('Air 4 / load 5' with a warning color when overloaded), toasts on overheat and on recovery.
6. Save: temperature and cooldown timers; migrate older saves (temperature 0). Keep a fixture.
7. Tests: heat gain by layer and overload; cooling on stations; the overheat and recovery timeline; airflow and ventilation effects; the cooling upgrade; refusal reasons; determinism; UI renders; earlier tests pass.

ACCEPTANCE: a headless session with six miners in the deep layer and airflow 4 overheats earlier than the same session with airflow 8.
COMMIT: feat(core): heat, overheating and shared ventilation
