# Prompt 1 of 8: infinite world (core)

Follow AGENTS.md. Implement the infinite world in core/ (no Qt, no miner yet).

CONTENT (JSON in src/minesim/content/, pydantic models in core/schemas.py, loader in core/content.py using importlib.resources):
- config.json: seed_default 12345, chunk_size 16, region_size_chunks 2, base_half_size 1, tick_hz 10. Later prompts add more keys.
- ores.json: list of {id, name, tier, hardness, base_value, mine_probability, regen_ticks, color, unlocked_by}. unlocked_by is an achievement id (null = available from the start). Initial ores (id: tier, hardness, base_value, mine_probability, regen_ticks, color, unlocked_by):
  stone: 0, 1, 1, 0.95, 300, #7a7a7a, null
  coal: 0, 2, 3, 0.90, 600, #2b2b2b, first_dig
  copper: 1, 3, 8, 0.80, 900, #c9773a, coal_miner
  iron: 2, 4, 15, 0.70, 1200, #b0b7c0, copper_age
  silver: 3, 5, 40, 0.55, 2400, #dfe6ee, iron_will
  gold: 4, 6, 100, 0.40, 3600, #f2c230, silver_lining
  ruby: 5, 8, 400, 0.25, 6000, #d62b4a, gold_rush
- biomes.json: list of {id, name, min_distance, weight, floor_color, ore_weights}. These are the different 'mines':
  quarry: min_distance 0, weight 10, ore_weights stone 70, coal 20, copper 10
  deep_vein: min_distance 40, weight 5, ore_weights stone 40, coal 15, copper 20, iron 20, silver 5
  crystal_caverns: min_distance 100, weight 2, ore_weights stone 30, iron 20, silver 20, gold 15, ruby 10

CODE:
1. core/rng.py: mix64(*ints) -> int (splitmix64 style, masked to 64 bits), unit(h) -> float in [0, 1), weighted_choice(h, items). Pure, and identical on every OS and Python version.
2. core/world/biomes.py: the plane is split into square regions of region_size_chunks * chunk_size tiles, with the origin region centered on (0, 0). Each region picks a biome with weighted_choice among the biomes whose min_distance <= the Chebyshev distance from (0, 0) to the region center. The region containing (0, 0) is always quarry.
3. core/world/generator.py: WorldGenerator(seed, content).ore_at(x, y, epoch=0) picks an ore from the biome ore_weights using mix64(seed, x, y, epoch). Tiles within base_half_size of (0, 0) are BASE (no ore, never minable).
4. core/world/world.py: World(generator, content). tile_at(x, y, tick) -> Tile(ore_id or None, biome_id, is_base, depleted). mine_tile(x, y, tick) marks the tile depleted until tick + ore.regen_ticks; after that time the tile is re-rolled with epoch + 1. That is the regeneration. Keep a delta dict {(x, y): (epoch, regen_at_tick or None)}; the generated layer is never stored. LRU cache of generated chunks (default 256). For the UI: chunk_tiles(cx, cy, tick), a `version` int that grows on every mutation, and to_dict() / from_dict() (delta only).
5. Tests: same seed gives the same tiles and a different seed differs; the origin region is quarry and the base is clear; over 20000 quarry tiles the ore frequencies are within 15% of the weights; mine_tile empties the tile and it returns after regen_ticks with a re-rolled ore; to_dict / from_dict round trip; cache eviction does not change results; content errors name the file and the field; coordinates like -5 and 10**6 work.

ACCEPTANCE: World works headless for any coordinate.
COMMIT: feat(core): infinite deterministic world
