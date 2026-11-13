# Prompt 16 of 25 (v0.3): items, warehouse and dynamic market (core)

Follow AGENTS.md. Goal: a base warehouse and a market whose prices move over time, plus the API to use them. First read core/engine.py, core/commands.py, core/game.py, core/save.py, content/ores.json, content/functions.json and the economy tests.

CONTENT:
- config.json: market_interval_ticks 100, market_history_len 240, warehouse_start_capacity 100, impact_per_unit 0.01, impact_recovery 0.15, impact_cap 0.5.
- products.json: {id, name, base_value, color, unlocked_by}. Products come from the refinery (next prompt): copper_bar 40, iron_bar 90, steel_bar 260, silver_bar 170, gold_bar 420, cut_ruby 1100. unlocked_by null for now.
- market.json: per item {item, volatility, reversion, min_index, max_index}. Ores (volatility, reversion, min, max): stone 0.02 0.15 0.8 1.25; coal 0.03 0.12 0.7 1.4; copper 0.04 0.10 0.6 1.6; iron 0.05 0.10 0.55 1.8; silver 0.07 0.08 0.5 2.0; gold 0.09 0.08 0.45 2.3; ruby 0.12 0.06 0.4 2.6. Products use the values of their main ore with the volatility multiplied by 0.8.
- upgrades.json: add warehouse: capacity +100 per level, 5 levels, costs 150 400 1000 2500 6000, unlocked_by null for now.

CORE:
1. core/items.py: ItemCatalog unifying ores and products (value, kind, color). Warehouse items are item ids.
2. core/warehouse.py: Warehouse(capacity): add(item, n) -> accepted, remove(item, n), count(item), total(), to_dict() / from_dict().
3. core/market.py: Market(seed, catalog, config, market_config). State per item: index (starts at 1.0), impact (0) and shock (1.0, used by world events later). Every market_interval_ticks the market takes a step: index += reversion * (1 - index) + volatility * u, where u in [-1, 1] comes from unit(mix64(seed, item_number, step)) (item_number is the position in the sorted catalog, never Python's hash), then clamp to [min_index, max_index]; impact decays multiplicatively by impact_recovery; the price sample goes into a history ring buffer. price(item) = base_value * index * (1 - impact) * shock. sell(item, n) sells unit by unit: each unit pays the current price and then raises impact by impact_per_unit (capped by impact_cap); revenue = floor(sum of the unit prices) so money stays an integer. advance(tick) performs the pending steps. apply_news(item, factor, until_tick) (used by the events prompt). to_dict() / from_dict().
4. Commands: Unload() (on the base: moves the drone inventory into the warehouse up to its capacity; result {moved, left}; cost 1 tick), SellStock(item, amount=None) (on the base, from the warehouse; cost sell_ticks), Stock(), Price(item), Prices(), PriceHistory(item, n) (0 ticks; None for items that are not unlocked; prices rounded to 2 decimals in the results). The existing Sell() now sells the whole drone inventory at market prices (still only on the base).
5. Events: Sold carries avg_index (price index weighted by units at sale time) and items; new Unloaded(items) and StockSold(item, amount, money).
6. API (functions.json, runner proxies, stubs, docs; unlocked_by null for now): unload(), stock(), sell_stock(item, amount=None), price(item), prices(), price_history(item, n=50).
7. RemoveDrone from prompt 15: when the removed drone is on a base tile, its inventory goes to the warehouse (up to capacity).
8. Save version 5: warehouse and market state; migrate version 4 (empty warehouse, fresh market). Keep a fixture.
9. Tests: deterministic prices for a seed; bounds respected; mean index within 0.15 of 1.0 over 5000 steps; impact lowers the price and recovers; revenue is an integer and equals the iterated sum; history length; warehouse capacity limits; Unload and SellStock rules; save/load gives identical future prices; Sell() tests updated for market prices; all earlier tests still pass.

ACCEPTANCE: a headless session mines, unloads, waits, and sells stock at changing prices.
COMMIT: feat(core): warehouse, items and dynamic market
