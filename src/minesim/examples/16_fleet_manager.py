# 16_fleet_manager - coordinate drones through shared memory.
# Teaches: minerlib.Fleet broadcast/gather plus shared_set/shared_get.
# Tick cost: shared memory reads and writes are free.
# Unlocks needed: shared_get and shared_set (Teamwork).
import minerlib

fleet = minerlib.Fleet()
fleet.broadcast("goal", {"x": 4, "y": 2, "item": "stone"})
fleet.broadcast("total", 3)

print("goal:", fleet.gather("goal"))
print("total:", fleet.gather("total"))
print("unknown key:", fleet.gather("missing"))

for drone in drones():
    print("drone", drone["id"], "at", drone["x"], drone["y"], "state", drone["state"])

print("fleet ids:", [drone["id"] for drone in drones()])
