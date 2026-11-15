# 11_contract_runner - fulfil the best delivery contract the stock can cover.
# Teaches: contracts(), minerlib.best_contract and minerlib.fulfill.
# Tick cost: reading the board is free; fulfilling costs 2 ticks to deliver
# plus any mining or refining needed for missing items.
# Unlocks needed: contracts and deliver (order board), refine and refinery
# (Smelter) when a contract asks for a refined product.
import minerlib

board = contracts()
print("open contracts:", len(board))
for contract in board:
    print(
        contract["id"],
        contract["item"],
        contract["quantity"],
        "reward",
        contract["reward"],
        "ticks left",
        contract["ticks_left"],
    )

contract = minerlib.best_contract()
if contract is None:
    print("nothing in stock to deliver yet")
else:
    print("fulfilling contract", contract["id"], "for", contract["item"])
    print("earned:", minerlib.fulfill(contract["id"]))
