# 22_layer_prospector - sample the ore on every reachable layer.
# Teaches: minerlib.dive, minerlib.safe_farm and minerlib.go_up.
# Tick cost: walking, mining, hauling and charging as needed.
# Energy cost: the per-move and per-mine energy of the current layer.
# Unlocks needed: none; safe_farm stops cleanly when an action is locked.
import minerlib

for entry in layers():
    if not entry["accessible"]:
        print("layer", entry["index"], entry["name"], "is not reachable yet")
        continue
    if not minerlib.dive(entry["index"]):
        print("could not reach layer", entry["index"])
        continue
    mined = minerlib.safe_farm("stone", max_tiles=6)
    print("layer", layer(), "name", entry["name"], "mined", mined, "stone")

print("returning to the surface:", minerlib.go_up(4), "now on", layer())
