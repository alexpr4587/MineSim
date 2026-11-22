# 21_night_shift - let a worker rest, unload and keep going on its own.
# Teaches: subclassing minerlib.EnergyAwareWorker and overriding work().
# Tick cost: whatever the work uses, plus walking, charging and unloading.
# Energy cost: one move per tile and the normal mining energy.
# Unlocks needed: none; the helper falls back gracefully when optional
# functions are still locked.
import minerlib


class NightDigger(minerlib.EnergyAwareWorker):
    def work(self):
        if peek() is not None:
            return mine()
        x, y = position()
        if not minerlib.goto(x + 1, y):
            return False
        return True


digger = NightDigger("night-shift", rest_margin=0.2)
steps = digger.run(20)
print("steps", steps, "rests", digger.rests, "unloads", digger.unloads)
print("battery", battery(), "at", position())
