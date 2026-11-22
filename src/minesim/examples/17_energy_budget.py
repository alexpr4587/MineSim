# 17_energy_budget - plan a trip that always leaves enough power to return.
# Teaches: battery(), minerlib.energy_to, minerlib.can_return and
# minerlib.charge_full.
# Tick cost: calls that only read state are free; moving uses the normal
# move cost and charging uses the normal charge duration.
# Energy cost: one move costs the layer's per-tile energy; charging costs
# no energy.
# Unlocks needed: none; battery, charge and the energy helpers are
# available from the start.
import minerlib

energy, capacity = battery()
print("battery", energy, "/", capacity)

for target in ((3, 0), (6, 0), (9, 0)):
    needed = minerlib.energy_to(*target)
    print("to", target, "needs", needed, "energy")
    if not minerlib.can_return():
        print("returning before the battery gets too low")
        break
    if not minerlib.goto(*target):
        print("could not continue to", target)
        break

if minerlib.go_home():
    print("charged at the base:", minerlib.charge_full())
