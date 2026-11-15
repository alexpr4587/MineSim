# 14_event_hunter - wait for a rich vein or slow zone and walk around it.
# Teaches: events(), minerlib.route, minerlib.goto_route and minerlib.ore_map.
# Tick cost: events and ore_map are free; walking and mining use the normal
# costs, and waits cost the requested ticks.
# Unlocks needed: events (News Reader), wait (Patience), scan (Scout).
import minerlib


def find_event():
    for event in events():
        print("event", event["kind"], "at", event["x"], event["y"], "ends in", event["ends_in"])
        if event["kind"] in ("rich_vein", "slow_zone"):
            return event
    return None


event = find_event()
for _ in range(5):
    if event is not None:
        break
    wait(600)
    event = find_event()

if event is None:
    print("no rich vein or slow zone appeared yet")
else:
    print("heading to", event["kind"], "at", event["x"], event["y"])
    minerlib.goto_route(event["x"], event["y"])
    print("arrived at", position(), "peek", peek())
    print("nearby ore:", minerlib.ore_map(2))
    if peek() is not None:
        print("mine result:", mine())
