# 09_market_watcher - watch the market and sell only when prices are high.
# Teaches: price(), prices(), price_history(), minerlib.sma, minerlib.trend,
# minerlib.best_item_to_sell and minerlib.sell_if.
# Tick cost: reading prices and histories is free; a successful sell_if
# costs 2 ticks at the base.
# Unlocks needed: price and prices (Market Watcher), price_history (Chartist),
# sell_stock (Storage Unit).
import minerlib

items = sorted(prices())
print("market items:", len(items))
for item in items[:3]:
    history = price_history(item, 12) or []
    print(
        item,
        "price",
        price(item),
        "samples",
        len(history),
        "sma",
        round(minerlib.sma(item, 5), 2),
        "trend",
        round(minerlib.trend(item, 12), 3),
    )

print("best stocked item:", minerlib.best_item_to_sell())
minerlib.go_home()
print("stone sale:", minerlib.sell_if("stone", 1.0))
