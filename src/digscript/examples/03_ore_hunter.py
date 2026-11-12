# 03_ore_hunter - find a specific ore instead of digging blindly.
# Teaches: scan() through minerlib.nearest and the goto_nearest shortcut.
# Unlocks needed: scan (Scout).
import minerlib

offset = minerlib.nearest("coal")
if offset is None:
    print("no coal in scanner range")
else:
    print("coal at offset", offset)
    if minerlib.goto_nearest("coal"):
        print("mined", minerlib.mine_until(1), "coal")
