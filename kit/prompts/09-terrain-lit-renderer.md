# Prompt 9 of 14 (v0.2): pseudo-3D terrain (elevation + lit renderer)

Follow AGENTS.md. Goal: make the world look slightly 3D (a lit 2.5D pixel-art look) without changing gameplay. Technique: a height map gives every pixel a surface normal; a sun direction and a dot product give the lighting; the result is posterized into a few bands and mixed between a base color and a shadow color. Style reference: top-down pixel-art terrain with 3 to 4 flat light bands, darker edges on the side facing away from the sun, small dark outlined props, no smooth gradients.

First read core/world/*, ui/world_view.py, ui/theme.py and content/*.json and keep their conventions.

CONTENT:
- config.json: add art_px_per_tile 4, sun_dir [-0.6, -0.7, 0.45] (normalize it in code), light_bands 4, ambient 0.35, height_scale 2.0, pit_depth 0.8, ore_bump_per_hardness 0.12, terrain_noise_scale 12.
- biomes.json: add relief (quarry 0.6, deep_vein 1.0, crystal_caverns 1.4) and shadow_color (a darker, slightly bluer variant of floor_color).

CORE (pure Python, no numpy):
1. core/world/elevation.py: elevation_at(seed, x, y) -> float in [0, 1]: 2-octave value noise built on mix64 (lattice hash + smoothstep interpolation; terrain_noise_scale tiles for the first octave, half of that for the second). Deterministic on every OS. tile_height(world, x, y, tick) = elevation_at * biome.relief * height_scale, plus ore_bump_per_hardness * ore.hardness when the tile holds an ore, minus pit_depth when the tile is depleted. Base tiles use a constant height.
2. Tests: determinism and range of elevation_at; continuity (neighboring tiles differ by less than a threshold); a depleted tile is lower than the same tile when full.

UI (add numpy to the dependencies; numpy is allowed in ui/ only, never in core/):
3. ui/terrain_shader.py: render_chunk(...) -> QImage. Build a height array for the chunk plus a 1-tile margin taken from the neighbors, upsample it bilinearly to art_px_per_tile pixels per tile, compute normals from the finite differences of the height array, light = max(dot(normal, sun), 0), posterize it (round(light * bands) / bands) and mix: final = mix(shadow_color, base_color, ambient + (1 - ambient) * light). The base color is the biome floor_color. Ore tiles get a deterministic speckle of the ore color (about 30 to 40 percent of the art pixels of the tile, chosen with mix64) so ores stay readable; depleted tiles use a darker floor; locked ores keep a clearly different look plus the '?' overlay. The output is at art resolution; the world view scales it with nearest-neighbor (no smoothing) so the pixels stay crisp. Careful: a QImage built from a NumPy buffer does not own the memory; copy it (QImage.copy()) or keep the array alive.
4. ui/world_view.py: use the shader when lighting is enabled. The chunk cache key must include the chunk_version of the chunk AND of its 8 neighbors (normals depend on neighbor heights). View menu: 'Terrain lighting' toggle (default on), also key H when the world view has focus; when off, use the old flat renderer. Persist the setting.
5. The miner and the base are still drawn by QPainter on top of the terrain (prompt 10 replaces them with sprites). Add a soft drop shadow under the miner whose offset points away from the sun.
6. Performance: rebuilding one chunk should take under 15 ms at art_px_per_tile 4. Add a generous timing test (fail only above 100 ms) and log the measured number.
7. Tests (offscreen): a flat height field gives uniform lighting; posterization yields at most light_bands distinct light levels; changing one tile invalidates its chunk and its neighbors only; lit and flat renderers both produce non-blank images. tools/screenshot.py gets a --flat flag and saves artifacts/ui_lit.png and artifacts/ui_flat.png.

ACCEPTANCE: artifacts/ui_lit.png shows banded lighting, visible relief, a readable base, miner and ores; mined tiles look like shallow pits.
COMMIT: feat(ui): lit 2.5D terrain renderer
