# 07_regen_cycle - watch the clock while a mined tile regenerates.
# Teaches: tick() for reading the game clock and wait() for passing time.
# Unlocks needed: wait (Patience).
start = tick()
if peek() is not None:
    mine()
print("mined at tick", start)
wait(320)
print("checked again at tick", tick())
