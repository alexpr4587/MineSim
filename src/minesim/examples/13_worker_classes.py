# 13_worker_classes - build workers with inheritance.
# Teaches: subclassing minerlib.Worker, overriding step() and reusing
# MinerWorker and HaulerWorker from the library.
# Tick cost: each step uses the normal cost of the primitives it calls.
# Unlocks needed: Worker helpers and spawn-free fleet functions (Inheritance
# example), scan (Scout) for MinerWorker and wait (Patience) for HaulerWorker.
import minerlib


class Talker(minerlib.Worker):
    def step(self):
        x, y = position()
        print(self.name, "is at", x, y)
        return True


Talker("talker").run(3)

digger = minerlib.MinerWorker("digger", "stone")
digger.run(5)
print("digger mined", digger.mined, "and hauled", digger.hauls, "time(s)")

shared_set("work", {"x": 0, "y": 0, "item": "stone"})
hauler = minerlib.HaulerWorker("hauler")
hauler.run(2)
shared_set("work", None)
print("hauler carried", hauler.carried)
