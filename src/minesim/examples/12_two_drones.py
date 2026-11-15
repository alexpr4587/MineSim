# 12_two_drones - inspect the fleet and try to hire a second drone.
# Teaches: drones(), drone_id(), spawn_drone() and minerlib.Fleet.
# Tick cost: reading the fleet is free; spawning costs 5 ticks and money.
# Unlocks needed: drone_id, drones and spawn_drone (Teamwork); a free drone
# bay slot and enough money for the spawn to succeed.
import minerlib

print("my id:", drone_id())
print("fleet:", [(drone["id"], drone["x"], drone["y"]) for drone in drones()])

fleet = minerlib.Fleet()
worker = fleet.spawn("worker.py")
if isinstance(worker, dict):
    print("spawn failed:", worker.get("reason"))
else:
    print("spawned drone", worker)

print("fleet now:", [(drone["id"], drone["state"]) for drone in drones()])
