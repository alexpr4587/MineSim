# 12_two_miners - inspect the fleet and try to hire a second miner.
# Teaches: miners(), miner_id(), spawn_miner() and minerlib.Fleet.
# Tick cost: reading the fleet is free; spawning costs 5 ticks and money.
# Unlocks needed: miner_id, miners and spawn_miner (Teamwork); a free miner
# bay slot and enough money for the spawn to succeed.
import minerlib

print("my id:", miner_id())
print("fleet:", [(miner["id"], miner["x"], miner["y"]) for miner in miners()])

fleet = minerlib.Fleet()
worker = fleet.spawn("worker.py")
if isinstance(worker, dict):
    print("spawn failed:", worker.get("reason"))
else:
    print("spawned miner", worker)

print("fleet now:", [(miner["id"], miner["state"]) for miner in miners()])
