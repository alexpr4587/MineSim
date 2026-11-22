# 20_dock_etiquette - share the surface dock without crowding it.
# Teaches: dock_free(), minerlib.stagger and minerlib.smart_unload.
# Tick cost: checking the dock is free; waiting uses the waited ticks and
# unloading uses the normal dock duration.
# Energy cost: none; the dock only moves inventory.
# Unlocks needed: none for the dock helpers; unloading itself needs the
# warehouse (Storage Unit).
import minerlib

status = dock_free()
queue = status.get("queue", status.get("queue_length", 0))
eta = status.get("eta", status.get("eta_ticks", 0))
print("dock free:", status["free"], "queue:", queue, "eta:", eta)
print("my backoff:", minerlib.stagger(0), "ticks")

waited = minerlib.smart_unload()
print("waited", waited, "ticks for the dock")
print("dock now free:", dock_free()["free"])
