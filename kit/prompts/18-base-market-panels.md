# Prompt 18 of 25 (v0.3): base panel and market panel (UI)

Follow AGENTS.md. Goal: make the new economy playable by hand and visible. First read ui/floating_panel.py, ui/upgrades_panel.py, ui/hud.py, ui/theme.py and core/game.py.

1. ui/base_panel.py (key B and the View menu): FloatingPanel with three tabs.
   - Warehouse: a table of items (name, count, current price, total value), a capacity bar, Sell and Sell all buttons per row and a Sell everything button; it also shows the inventory of drone 0 with an Unload button (enabled only when that drone is on the base, otherwise disabled with a hint).
   - Refinery: the recipes with inputs, outputs, time and current output price; locked recipes dimmed with their unlocking achievement; Start x1 and Start x5 buttons; one progress bar per furnace slot (show the blocked state).
   - Contracts: cards with item, quantity, reward, a time-left bar and a Deliver button (disabled until the warehouse holds enough).
2. ui/market_panel.py (key M and the View menu): an item selector; a line chart of price_history drawn with QPainter (axes with labels, current price marker, optional 10-sample moving average toggle, mouse crosshair showing tick and price); a table with price, index in percent and a trend arrow; a news strip (empty until the events prompt).
3. HUD: show warehouse used/capacity next to the inventory. Fix: the selected speed button (1x) currently shows no visible label; give the selected state a high-contrast label.
4. All actions go through Game methods (sell_stock, start_refine, deliver_contract, unload for drone 0); the panels only read state and react to EventBus events. Hotkeys follow the focus rule from prompt 6.
5. tools/screenshot.py: a --panel base|market|refinery|contracts flag and a scripted session that fills the warehouse and runs some market steps first; save artifacts/ui_<panel>.png.
6. Tests (offscreen): the panels build; the chart renders non-blank and the moving average has the right length; buttons call the right Game methods and update the view; disabled states; layout at 1024x768 without overlaps.

ACCEPTANCE: the screenshots show a filled warehouse, the refinery with a running job, a contract card and a price chart.
COMMIT: feat(ui): base and market panels
