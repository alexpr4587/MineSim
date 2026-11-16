# MineSim v0.3.0 release checklist

- [ ] A clean clone runs with `uv sync && uv run minesim`
- [ ] CI is green on both `ubuntu-latest` and `windows-latest`
- [ ] The frozen Windows and Linux binaries pass both `--selftest` (two drones)
      and `--selftest-ui`
- [ ] A v0.2.0 save (`tests/fixtures/save_v0.2.0.json`) loads and migrates to
      save format v8
- [ ] Manual playthrough: unload into the warehouse, sell stock on the market,
      refine a recipe, deliver a contract and spawn a drone with its own script

## Manual playthrough notes

<!-- Add observations, screenshots or follow-up issues here. -->
