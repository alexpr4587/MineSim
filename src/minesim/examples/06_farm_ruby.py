# 06_farm_ruby - farm one rare ore and sell the haul.
# Teaches: minerlib.farm, which sweeps outward, mines only the requested
# ore and automatically hauls when the inventory is full.
# Unlocks needed: ruby (Gold Rush), sell (First Dig), inventory (Hello, Miner).
import minerlib

mined = minerlib.farm("ruby", max_tiles=40)
print("rubies mined:", mined)
