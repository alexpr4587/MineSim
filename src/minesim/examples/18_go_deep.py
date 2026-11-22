# 18_go_deep - visit the underground layers and come back up.
# Teaches: layers(), layer(), minerlib.dive, minerlib.go_down and
# minerlib.go_up.
# Tick cost: walking plus 20 ticks per shaft ride.
# Energy cost: one move per tile plus 15 energy per shaft ride.
# Unlocks needed: none; the shaft functions and layer helpers are
# available from the start (buy the shaft upgrade to reach deeper layers).
import minerlib

for entry in layers():
    print(entry["index"], entry["name"], "accessible" if entry["accessible"] else "locked")

print("start on layer", layer())
if minerlib.dive(1):
    print("arrived on layer", layer())
    if minerlib.dive(2):
        print("arrived on layer", layer())
    else:
        print("the shaft is not deep enough for layer 2 yet")
else:
    print("the shaft is not deep enough for layer 1 yet")

print("back on layer", layer(), "after ascent:", minerlib.go_up(3))
