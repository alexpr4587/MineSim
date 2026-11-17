# Prompt 36 of 36 (v0.4): release v0.4.0

Follow AGENTS.md. Package v0.4.0.
1. Version bump to 0.4.0 and a CHANGELOG.md entry: underground layers with shafts and stations, energy and rescue, heat and shared ventilation, the shared dock, the new library, 8 new examples, 17 new achievements (86 in 10 tabs), energy-aware helpers, the current save format version.
2. README.md: refresh the screenshots (layers, the energy and climate HUD, the miners panel), the feature list and its counts (achievements, API functions, examples), the controls (PageUp and PageDown for layers) and the links to the docs.
3. PyInstaller: make sure everything new is in the frozen build; run --selftest (several miners on two layers) and --selftest-ui on the frozen binary in release.yml.
4. CI stays green on Linux and Windows. Add tests that load a v0.3.0 and a v0.3.1 save fixture to prove the migrations.
5. Final checklist in the PR description: a clean clone runs; the frozen binaries pass both selftests; old saves load; manual playthrough notes (charge, descend, overheat, dock queue, rescue).

ACCEPTANCE: pushing the tag v0.4.0 produces Windows and Linux downloads.
COMMIT: chore: release 0.4.0
