# 19_climate_watch - watch the heat and cool down before a shutdown.
# Teaches: temperature(), climate(), minerlib.heat_budget and
# minerlib.cool_down.
# Tick cost: reading the climate is free; cooling uses the normal cool
# duration.
# Energy cost: cooling costs no energy; walking to the station uses the
# normal per-tile energy.
# Unlocks needed: none; temperature, climate and cool are available from
# the start.
import minerlib

state = temperature()
print(
    "layer",
    state["layer"],
    "temperature",
    round(state["temperature"], 1),
    "overheated",
    state["overheated"],
)
print("climate", climate())
print("rough work ticks before overheat:", minerlib.heat_budget())

if state["temperature"] > 30:
    print("cooling down:", minerlib.cool_down(30))
else:
    print("temperature is already comfortable")
