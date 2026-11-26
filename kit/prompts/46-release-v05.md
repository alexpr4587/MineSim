# Prompt 46 of 46 (v0.5): release v0.5.0

Follow AGENTS.md. Package v0.5.0.
1. Version bump to 0.5.0 and a CHANGELOG.md entry: procedural sound effects and music, the options panel, game feel effects, cozy lighting, time of day, weather and ambient sound, the goals widget, the Journal and records, the first-run guide, the running-line highlight and run summaries, seeds, replays, showcase mode and clip capture, 11 new achievements (97 in 11 tabs), four cozy skins, the current save format version.
2. README.md and docs/FEATURES.md: refresh the screenshots (hero, cozy dusk, rain, Journal, goals), the feature list, the controls (O options, J journal, F9 showcase mode, F12 screenshot, Ctrl+Shift+M mute) and the links; regenerate the images in docs/press/.
3. PyInstaller: make sure QtMultimedia and its plugins are in the frozen build; run --selftest, --selftest-ui and --selftest-audio on the frozen binary in release.yml. If the frozen build finds no audio device the game must start silently without errors.
4. CI stays green on Linux and Windows. Add a v0.4.0 save fixture to prove the migration.
5. Final checklist in the PR description: a clean clone runs; the frozen binaries pass the three selftests; old saves load; manual playthrough notes (sound on and off, rain, the first-run guide, the Journal, a replay export and a captured clip).

ACCEPTANCE: pushing the tag v0.5.0 produces Windows and Linux downloads.
COMMIT: chore: release 0.5.0
