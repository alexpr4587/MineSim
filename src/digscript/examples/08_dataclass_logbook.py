# 08_dataclass_logbook - keep a typed log of your expedition.
# Teaches: classes and the dataclasses module, combined with tick(),
# position() and peek().
# Unlocks needed: dataclasses (Object Oriented), inventory (Hello, Miner).
from dataclasses import dataclass


@dataclass
class LogEntry:
    tick: int
    x: int
    y: int
    ore: str | None


log: list[LogEntry] = []
for _ in range(5):
    x, y = position()
    log.append(LogEntry(tick(), x, y, peek()))
    move(East)

for entry in log:
    print(entry)
