# Prompt 25 of 25 (v0.3): release v0.3.0

Follow AGENTS.md. Package v0.3.0.

1. Version bump to 0.3.0 and a CHANGELOG.md entry: fleet of drones with per-drone scripts and shared memory, warehouse, dynamic market with price history, refinery with six recipes, contracts, world events, the new library (route, trading, data and OOP helpers), 8 new examples, 28 new achievements in 8 tabs, the current save format version.
2. README.md: make the title and the text use the same project name (keep the name that is in the title), refresh the screenshots under docs/ (base panel, market chart, drones), controls (B base, M market, D drones), the feature list and links to the docs.
3. PyInstaller: make sure multi-drone scripts work in the frozen build (multiprocessing spawn, freeze_support first); run --selftest (two drones) and --selftest-ui on the frozen binary in release.yml.
4. CI stays green on Linux and Windows. Add a test that loads a v0.2.0 save fixture to prove the migration.
5. Final checklist in the PR description: a clean clone runs; the frozen binaries pass both selftests; a v0.2.0 save loads; manual playthrough notes (unload, sell stock, refine, deliver a contract, spawn a drone).

ACCEPTANCE: pushing the tag v0.3.0 produces Windows and Linux downloads.
COMMIT: chore: release 0.3.0
