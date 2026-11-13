# 02_sweep_and_sell - clean a small area and cash in.
# Teaches: minerlib.sweep for an efficient grid sweep, mine_here and haul.
# Unlocks needed: inventory (Hello, Miner), sell (First Dig).
import minerlib

start_x, start_y = position()
for dx, dy in minerlib.sweep(5, 5):
    minerlib.goto(start_x + dx, start_y + dy)
    minerlib.mine_here()

minerlib.haul()
print("inventory after selling:", inventory())
