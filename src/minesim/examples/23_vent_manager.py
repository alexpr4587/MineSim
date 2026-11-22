# 23_vent_manager - spread the fleet and watch the shared airflow.
# Teaches: minerlib.Fleet.balance_load, minerlib.Fleet.assign_layers and
# minerlib.heat_budget.
# Tick cost: the assignment is free; diving uses the normal shaft cost.
# Energy cost: one move per tile plus 15 energy per shaft ride.
# Unlocks needed: none; the fleet helpers fall back to the calling miner
# when fleet functions are still locked.
import minerlib

fleet = minerlib.Fleet()
assignment = fleet.balance_load(2)
print("balanced fleet:", assignment)
print("explicit assignment:", fleet.assign_layers({0: 0}))

print("climate:", climate())
budget = minerlib.heat_budget()
print("rough work ticks before overheat:", budget)
if budget < 30:
    print("cooling down:", minerlib.cool_down(30))
