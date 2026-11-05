# Prompt 5 of 8: UI main window and world view

Follow AGENTS.md. First UI step: main window, camera and world rendering with PySide6. No editor yet.

0. Small core change first (the view needs it): in core/world add advance(tick), called by the engine on every tick, which processes due regenerations (min-heap of (regen_at_tick, x, y)), and chunk_version(cx, cy), a per-chunk counter that changes whenever a tile of that chunk is mined or regenerates. Keep tile_at consistent with advance. Tests: a tile mined at tick t stays depleted until its regeneration tick; chunk_version changes exactly when mining and when regeneration happen.
1. ui/theme.py: dark palette (named colors), a monospace font choice, one global stylesheet.
2. ui/world_view.py: WorldView(QWidget) draws the tiles around a camera center with QPainter only (no QGraphicsScene). Cache one QPixmap per chunk keyed by (cx, cy, chunk_version, tile_px) and rebuild only the chunks whose version changed (LRU, about 200 chunks). Tile colors come from the biome floor_color and the ore color; locked ores are drawn as the floor color with a dark '?' pattern; depleted tiles are darker; the base area has a border and a BASE label. The miner is a simple vector robot facing its last direction, with a smooth visual interpolation between tiles. The camera follows the miner by default; the mouse wheel zooms (tile size 12 to 64 px); middle or right drag pans and shows a Recenter (C) button; G toggles a grid.
3. ui/hud.py: top bar with money, inventory used/capacity, tick, position and speed buttons (Pause, 1x, 2x, 5x, 20x). It reads state through Game getters and EventBus events.
4. ui/game_loop.py: a QTimer every 16 ms converts real elapsed time into engine ticks (tick_hz * speed, at most 200 per frame) and calls engine.step(). Space toggles pause; keys 1 to 5 set the speed.
5. ui/main_window.py and ui/app.py: QMainWindow with WorldView as the central widget and the HUD on top. main() loads the autosave if it exists, otherwise starts a new game.
6. tools/screenshot.py: builds the real MainWindow offscreen, runs N ticks with a hard-coded command sequence submitted straight to the engine (no scripting yet), grabs the window and saves artifacts/ui_main.png. Flags: --ticks, --size.
7. Tests (offscreen): the window builds; WorldView renders a non-blank image (pixel variance check) and only the changed chunks are rebuilt after a mine; game loop speed math; zoom and pan clamps.

ACCEPTANCE: uv run python tools/screenshot.py --ticks 300 saves a PNG with the base, the surrounding quarry tiles and the miner.
COMMIT: feat(ui): main window and world view
