# Prompt 28 of 36 (v0.4): strata (layers) in the core

Follow AGENTS.md. Goal: underground layers below the surface, each with its own map, ores and character, reached by a shaft at the base. Layer 0 is today's world and must not change at all. First read core/world/*, core/engine.py, core/commands.py, the miner entity, core/game.py, core/save.py, core/worldevents.py, content/biomes.json and the world and engine tests.

0. Golden test first: store the tiles of a fixed set of coordinates (about 2000 tiles over several chunks, seed 12345) and a fixed mining session on the current code. After this prompt they must be identical for layer 0.

CONTENT:
- layers.json: list of {index, id, name, energy_multiplier, heat, floor_tint, light_ambient}: 0 surface (Surface, 1.0, 0), 1 galleries (Old Galleries, 1.2, 0), 2 deep (Deep Level, 1.5, 1), 3 abyss (Abyssal Rock, 2.0, 2). energy_multiplier and heat are used by the next prompts; store them now.
- biomes.json: add a layer field (existing biomes are layer 0) and new biomes with min_distance 0 and their own relief and colors:
  gallery (layer 1): stone 35, coal 15, copper 20, iron 20, silver 10
  deep_seam (layer 2): stone 25, iron 20, silver 25, gold 20, ruby 10
  abyssal_vein (layer 3): stone 15, silver 20, gold 35, ruby 30
- config.json: shaft_ticks 20, station_half_size 1.
- upgrades.json: shaft (the maximum reachable layer equals the level; 3 levels, costs 500 3000 12000; unlocked_by null for now).

CORE:
1. World, WorldGenerator, biomes and elevation take a layer argument. For layer 0 the hashes stay exactly as they are (mix the layer into the hash only when it is not 0). Chunk caches, the mined delta and chunk_version are keyed by layer. Every layer has a station (3x3 around (0, 0), not minable) in place of the base; the surface base stays as it is.
2. Miners get a layer field (default 0). Peek, Mine, Scan, Move, Wait and the rest act on the layer of the miner. Selling, Unload, SellStock, Refine, Deliver and the contract and market commands require the surface base (reason 'not_on_surface_base').
3. New commands Descend() and Ascend(): only on a station tile of the current layer; Descend needs layer + 1 <= the shaft upgrade level (reason 'shaft_too_shallow'); the miner appears on the origin of the target layer; cost shaft_ticks. Result {ok, layer, reason}. Layers() lists {index, name, accessible} (0 ticks) and Layer() returns the current layer index.
4. World events (rich veins, slow zones, news) stay surface-only: modifiers_at is neutral on other layers.
5. Events: LayerChanged(miner_id, from_layer, to_layer); Moved, MineAttempted and OreMined carry layer.
6. API (functions.json, proxies, stubs, docs; unlocked_by null for now): layer(), layers(), descend(), ascend(). distance() and position() are relative to the layer origin.
7. Save: a new version; miners store their layer; the mined delta is stored per layer (existing deltas become layer 0). Migrate older saves; keep a fixture.
8. Tests: golden layer 0; layers differ from each other and are deterministic; deltas do not leak between layers; Descend and Ascend rules (station only, shaft level, cost, arrival position); surface-only commands refuse elsewhere; events neutral off the surface; migration; a headless session goes down, mines, comes back and sells.

ACCEPTANCE: all earlier tests pass unchanged and the new layer tests pass.
COMMIT: feat(core): underground layers with shafts
