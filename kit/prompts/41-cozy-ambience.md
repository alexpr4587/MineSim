# Prompt 41 of 46 (v0.5): cozy ambience (light, time of day, weather, ambient sound)

Follow AGENTS.md. Goal: make the world feel warm and alive without changing gameplay. First read ui/world_view.py, ui/terrain_shader.py, ui/fx/*, audio/*, content/layers.json and content/sprites.json.

1. Time of day on the surface: ui/cozy/timeofday.py, a pure function of the game tick (day_length_ticks in config, default 24000) returning a tint, an ambient level and a night factor with smooth transitions (dawn, day, golden dusk, soft blue night). It only affects visuals. The terrain gets the tint; underground layers keep their own ambient from layers.json.
2. Lights: ui/cozy/lights.py composes a light layer at a quarter of the resolution with numpy (darken by the ambient level, then add soft warm radial lights) and upscales it. Light sources: the base windows and the station lamps (with a gentle flicker), and a small headlamp on every miner (radius about 3 tiles, brighter in dark layers). Budget: under 4 ms per frame; a quality option (off, low, high).
3. Ambient particles: dust motes drifting in the lamp light, fireflies near the base at night, rising embers or heat shimmer in hot layers.
4. Life: chimney smoke on the base house, window glow at night, a flickering station lamp; a miner that has had nothing to do for about 5 seconds gets a small 'zZz' bubble and a gentle sway.
5. Weather: soft rain on the surface from time to time (a pure function of the seed and the tick, a few minutes long, deterministic, never affecting gameplay): thin rain streaks, a slightly cooler tint, ripples near the base. Underground there is no rain.
6. Ambient sound beds (procedural, looped, quiet): surface wind, rain (filtered noise, muffled underground), galleries (a low hum and sparse drips), deep (a warm drone and crackle), abyss (a deep rumble). The audio manager crossfades the beds with the viewed layer and the weather. Add the SFX or bed recipes you need.
7. Options (section 'Visual'): 'Cozy look' (vignette and warm grading), time of day (on or off), weather (on or off), lighting quality, ambient sound on or off. Defaults: all on, lighting high.
8. Event: WeatherChanged(kind, starts, ends) published by a small UI-side service (not by core); the Journal of the next prompt can record 'rain'.
9. tools/screenshot.py: --time dawn|day|dusk|night, --weather rain and --layer N, saving artifacts/ui_cozy_*.png.
10. Tests: timeofday is continuous and periodic; the weather is deterministic for a seed; the light layer composes non-blank images of the right size; quality off disables it; ambient beds switch with the layer in the NullBackend; the options persist; the performance budget (with a generous threshold).

ACCEPTANCE: screenshots of dusk on the surface, rain, and a lit gallery with miner headlamps look warm and readable; the terrain and the ores stay easy to identify.
COMMIT: feat(ui): cozy lighting, time of day, weather and ambient sound
