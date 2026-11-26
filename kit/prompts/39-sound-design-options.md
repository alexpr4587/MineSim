# Prompt 39 of 46 (v0.5): sound design, music per layer and the options panel

Follow AGENTS.md. Goal: give every moment of the game a soft, satisfying sound, with an options panel to control it. First read the audio package from prompt 38, core/events.py, ui/hud.py, ui/world_view.py and ui/floating_panel.py.

1. content/audio_sfx.json: the full list, all in the soft and warm style; frequent sounds have 3 variants:
   UI: ui_click, ui_open, ui_close, toggle_on, toggle_off, pause, resume.
   Movement and mining: step (very quiet), mine_stone, mine_coal, mine_copper, mine_iron, mine_silver, mine_gold, mine_ruby (each one brighter and more bell-like than the last), mine_miss (a soft 'tsk'), ore_pop (a small pop whose pitch can go up with the combo), inventory_full (two gentle notes).
   Economy: sell_small, sell_medium, sell_large (coin cascades), upgrade_buy (two rising notes), contract_done (a warm cadence), refine_start, refine_done, market_up, market_down (barely audible).
   Progress: achievement (a three-note chime with shimmer), unlock, milestone (a longer arpeggio), codex_entry (a soft sparkle).
   World: event_start, event_end, layer_down, layer_up (an elevator whoosh and a soft thud), charge (a rising hum), low_energy (two descending soft notes), overheat (a muted crackle and a low note), recover (a soft chime), stranded, rescue, miner_spawn (a boot-up arpeggio), script_start, script_finish, script_error (a soft low 'bonk', never harsh).
2. content/audio_events.json: maps EventBus events and conditions to sounds, with volume, cooldown_ms, positional and layer_scoped flags (for example OreMined with ore 'ruby' -> mine_ruby; Sold -> sell_small, sell_medium or sell_large depending on the money; AchievementUnlocked -> achievement plus a music duck). Validate that every sound and every event exists.
3. ui/audio_bridge.py subscribes to the EventBus and calls the AudioManager. Positional sounds: pan from the horizontal screen position and volume falling off beyond audio_hearing_radius tiles (config, default 14) from the camera center; only miners on the viewed layer are audible; global events always play. Combo: successive successful mines within combo_window_ticks (config) raise the pitch of ore_pop by one pentatonic step, up to +7 steps, and reset after a miss or a pause.
4. Music per layer: the viewed layer selects the mood with a 2 second crossfade; the music is ducked by 40 percent while the game is paused and by 50 percent for about 1.2 seconds on achievements.
5. ui/options_panel.py (key O and the View menu 'Options...'): an Audio section with master, music and SFX sliders, 'Music on', 'Sound effects on', 'Mute all' and a 'Test sound' button. The sections for visuals and gameplay are added by later prompts (leave a clean extension point). A speaker button in the HUD (click toggles mute; right-click opens Options) and the shortcut Ctrl+Shift+M for mute. Everything persists.
6. Defaults: music on at a low volume; the first run shows a one-time toast 'Music is on. Press O to change the sound.'
7. Tests (offscreen, NullBackend): the mapping tables validate; each event triggers the right sound; cooldowns and the voice cap; positional pan and volume math; layer scoping; combo steps; the ducking schedule; the mood changes with the viewed layer; the options persist; the HUD button and the shortcut toggle the mute state; --selftest-audio still passes.

ACCEPTANCE: a scripted headless session produces a plausible sequence of play calls in the NullBackend log; tools/render_audio.py can render any sound for listening.
COMMIT: feat(audio): sound effects, music per layer and options panel
