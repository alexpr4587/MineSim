# MineSim v0.4.0 release checklist

- [ ] A clean clone runs with `uv sync && uv run minesim`
- [ ] CI is green on both `ubuntu-latest` and `windows-latest`
- [ ] The frozen Windows and Linux binaries pass both `--selftest` (three
      miners on two layers) and `--selftest-ui`
- [ ] A v0.3.0 save (`tests/fixtures/save_v0.3.0.json`) and a v0.3.1 save
      (`tests/fixtures/save_v0.3.1.json`) load and migrate to save format v13
- [ ] Manual playthrough: charge at the base, descend a shaft, overheat in a
      hot layer, queue at the shared dock and watch a stranded miner get
      rescued

## Manual playthrough notes

<!-- Add observations, screenshots or follow-up issues here. -->
