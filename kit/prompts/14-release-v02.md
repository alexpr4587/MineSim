# Prompt 14 of 14 (v0.2): release v0.2.0

Follow AGENTS.md. Package v0.2.0.

1. Version bump to 0.2.0 and a CHANGELOG.md entry: lit terrain, skins and sprites, 41 achievements in 5 tabs, 7 new API functions, new minerlib helpers, 4 new modules, 8 example scripts, save format v3.
2. README.md: new screenshots under docs/ (lit terrain, wardrobe), updated controls (H terrain lighting, K wardrobe), a feature list, and links to docs/API.md, docs/GUIDE.md and docs/BALANCE.md.
3. PyInstaller spec: include the new data folders (examples, assets) and numpy. Add a --selftest-ui flag that, offscreen, renders one lit chunk and one skin sprite and exits 0; run it on the frozen binary in release.yml next to --selftest.
4. CI stays green on Linux and Windows; print the chunk render timing in the CI output.
5. Final checklist in the PR description: a clean clone runs; the frozen binaries pass both selftests; a v0.1.0 save loads in v0.2.0; manual playthrough notes.

ACCEPTANCE: pushing the tag v0.2.0 produces Windows and Linux downloads.
COMMIT: chore: release 0.2.0
