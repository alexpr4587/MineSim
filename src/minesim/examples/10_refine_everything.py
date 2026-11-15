# 10_refine_everything - turn all available warehouse ore into bars.
# Teaches: recipes(), refine_all() and refinery().
# Tick cost: reading recipes and jobs is free; each refine_all call costs
# 2 ticks at the base plus the refinery job time.
# Unlocks needed: recipes, refine and refinery (Smelter).
import minerlib

available = recipes()
for recipe_id in sorted(available):
    recipe = available[recipe_id]
    print(
        recipe_id,
        "inputs",
        recipe["inputs"],
        "outputs",
        recipe["outputs"],
        "ticks",
        recipe["ticks"],
    )

minerlib.go_home()
for recipe_id in sorted(available):
    runs = minerlib.refine_all(recipe_id)
    if runs > 0:
        print("started", runs, "run(s) of", recipe_id)

print("running jobs:", refinery())
