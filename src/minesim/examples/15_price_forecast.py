# 15_price_forecast - smooth and fit a price series.
# Teaches: minerlib.moving_average, minerlib.linear_fit, minerlib.Forecast
# and the sma/trend shortcuts.
# Tick cost: all calculations and price history reads are free.
# Unlocks needed: price_history (Chartist).
import minerlib

item = "stone"
history = price_history(item, 20) or []
print("samples:", len(history))

average = minerlib.moving_average(history, 5)
print("moving average:", [round(value, 2) for value in average])

slope, intercept = minerlib.linear_fit(list(range(len(history))), history)
print("linear fit: slope", round(slope, 4), "intercept", round(intercept, 2))

forecast = minerlib.Forecast(alpha=0.4)
for sample in history:
    forecast.update(sample)
print(
    "forecast",
    round(forecast.predict(), 2),
    "sma",
    round(minerlib.sma(item, 10), 2),
    "trend",
    round(minerlib.trend(item, 20), 4),
)
