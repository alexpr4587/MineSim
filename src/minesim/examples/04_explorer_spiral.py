# 04_explorer_spiral - explore outward and record where you are.
# Teaches: distance() and biome() plus minerlib.ring for square rings.
# Unlocks needed: distance (Far From Home), biome (Deep Diver).
import minerlib

start_x, start_y = position()
for radius in range(1, 4):
    for dx, dy in minerlib.ring(radius):
        minerlib.goto(start_x + dx, start_y + dy)
        print("distance", distance(), "biome", biome())
