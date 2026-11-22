# 24_full_automation - coordinate mining, charging, unloading and refining.
# Teaches: minerlib.Fleet.assign_layers, minerlib.safe_farm,
# minerlib.smart_unload, minerlib.charge_full and minerlib.refine_all.
# Tick cost: walking, mining, dock service, shaft rides and refinery work.
# Energy cost: the per-move and per-mine energy of the layer, plus 15 per
# shaft ride.
# Unlocks needed: none; optional steps are skipped cleanly while their
# functions are still locked.
import minerlib

fleet = minerlib.Fleet()
print("assignments:", fleet.assign_layers({0: 1}))
print("balanced:", fleet.balance_load(2))

for entry in layers():
    if not entry["accessible"]:
        continue
    if not minerlib.dive(entry["index"]):
        continue
    mined = minerlib.safe_farm("stone", max_tiles=4)
    print("layer", layer(), "mined", mined)

print("surface:", minerlib.go_up(4), "on layer", layer())
print("unload waited", minerlib.smart_unload(), "ticks")
try:
    print("refinery runs:", minerlib.refine_all("stone_bar"))
except NotUnlockedError:
    print("refining is still locked")
print("charged:", minerlib.charge_full())
