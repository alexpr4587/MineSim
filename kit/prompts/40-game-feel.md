# Prompt 40 of 46 (v0.5): game feel (juice)

Follow AGENTS.md. Goal: make every action feel good with small, soft effects. First read ui/world_view.py, ui/hud.py, ui/toasts.py, ui/audio_bridge.py and ui/options_panel.py.

1. ui/fx/ package, all drawn with QPainter and driven by the EventBus (never by polling core state):
   - particles.py: a pool of at most 600 particles; kinds: dust puff (ore color), sparkle (for gold and ruby), coin burst, confetti, smoke.
   - floating_text.py: numbers and words that pop, rise and fade ('+1 coal', '+$120', 'x5 combo').
   - shake.py: a camera shake with trauma that decays; very small amplitudes.
   - pulses.py: HUD pulses and a money counter that rolls up smoothly to the new value.
2. Triggers: mining success (a dust puff plus a floating '+1 <ore>' in the ore color; rare ores get a bigger text, a sparkle ring and a 3 percent zoom pulse); a miss (a tiny gray puff); a combo counter near the miner that grows with the streak; sell (a coin burst that flies to the HUD money counter, which rolls up); unload (small item icons fly from the miner to the warehouse button); upgrade bought (a ring pulse and 'Level N'); inventory full (the inventory label shakes); achievement (the toast gets a sparkle burst and a soft screen-edge glow); every fifth achievement (confetti); the first time in a new layer (a light bloom); low energy (the battery icon blinks).
3. Performance guard: effects only for miners on the viewed layer and near the camera; a global budget of effects per second that shrinks with the game speed (at 20x only rare or important effects); the particle count is capped.
4. Determinism: the effects use their own RNG seeded from the game tick, so screenshots and captured clips are reproducible.
5. Options (extend the panel from prompt 39, section 'Visual'): particles, floating numbers, camera shake, reduce motion (disables shake, pulses, zoom pulses and the screen glow), effect density (low, medium, high). Defaults: all on, shake off, density medium.
6. Tests: pool limits; each trigger spawns the expected effect kinds; reduce motion disables the right effects; the budget at speed 20 stays under the cap for 5000 events; the money counter reaches the target value; frame rendering stays non-blank and within a generous time budget; the same seed gives identical effect states.

ACCEPTANCE: screenshots (tools/screenshot.py --fx) show dust, floating numbers and a coin burst; a headless run with 8 miners at speed 20 stays readable (not cluttered).
COMMIT: feat(ui): game feel effects
