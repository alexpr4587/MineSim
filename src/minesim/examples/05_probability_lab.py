# 05_probability_lab - estimate an ore's hidden mining probability.
# Teaches: Samples for tallying attempts and submit_estimate for checking
# your estimate against the game after at least 100 recorded attempts.
# Unlocks needed: submit_estimate (Sampler).
import minerlib

samples = minerlib.Samples()
start_x, start_y = position()

for dx, dy in minerlib.spiral():
    if samples.count("stone") >= 100:
        break
    minerlib.goto(start_x + dx, start_y + dy)
    if peek() == "stone":
        result = mine()
        samples.add("stone", bool(isinstance(result, dict) and result.get("ok")))

print(samples.summary())
print(submit_estimate("stone", samples.rate("stone")))
