# Prompt 19 of 25 (v0.3): world events (core + overlay)

Follow AGENTS.md. Goal: random events that the code has to react to. Events are a pure function of the seed and the tick (no stored state, replays stay identical). First read core/engine.py, core/commands.py, core/market.py, ui/world_view.py and ui/hud.py.

CONTENT: config.json world_event_interval_ticks 2500 and world_event_chance 0.6. events.json with the kinds:
  rich_vein: radius 6, duration 3000, yield_multiplier 2, min_distance 10, max_distance 60
  slow_zone: radius 5, duration 2000, move_cost_multiplier 2, min_distance 8, max_distance 40
  market_news: duration 2000, factor_choices [0.6, 0.7, 1.4, 1.6] (a shortage raises the price, a glut lowers it)

CORE:
1. core/worldevents.py: WorldEvents(seed, config, catalog). Slot = tick // interval; each slot has an event with probability world_event_chance, with kind, position (angle and distance in [min, max] from the base, on integer tiles) or item and factor for news, everything from mix64(seed, slot, k). active_at(tick) lists events (id = slot number, kind, x, y, radius, starts, ends, item, factor); modifiers_at(x, y, tick) -> {yield_multiplier, move_multiplier}.
2. Engine: a successful Mine inside a rich vein gives yield_multiplier items (limited by capacity); Move cost is multiplied (ceil) inside a slow zone. When a market_news event starts the engine calls market.apply_news(item, factor, ends); the shock is removed when it ends. Events: WorldEventStarted(kind, id) and WorldEventEnded(kind, id); Moved gets in_slow_zone and OreMined gets in_rich_vein.
3. Command Events() (0 ticks) and API events() (unlocked_by null for now): the active events as plain dicts (kind, x, y, radius, ends_in, item, direction 'shortage' or 'glut'; never the exact factor); news about locked items is hidden.
4. Save: nothing new to store (the market shock is already saved); bump the version only if something changes.
5. Overlay in ui/world_view.py: translucent circles on the map (golden shimmer for rich veins, gray-blue hatch for slow zones) with a small label; a HUD ticker with icons and countdowns for all active events including news; a toast when an event starts. The news strip of the market panel shows the active news.
6. Tests: determinism for a seed; about world_event_chance of the slots have an event (200 slots, with tolerance); positions respect min and max distance; modifiers inside and outside the radius; mining and moving effects; news changes the market price and the shock ends on time; the overlay renders (offscreen).

ACCEPTANCE: the screenshot shows an active rich vein circle and the HUD ticker; a headless test mines inside a vein and gets the double yield.
COMMIT: feat: world events with overlay
