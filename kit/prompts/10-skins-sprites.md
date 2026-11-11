# Prompt 10 of 14 (v0.2): miner skins, sprites and base building

Follow AGENTS.md. Goal: replace the vector miner with pixel-art sprites and add a skin system. No art files are needed: the sprites are data (small text grids plus palettes) and skins are palette swaps of the same frames. PNG sprite sheets are also supported so the author can draw real art later.

First read ui/world_view.py, ui/theme.py, core/save.py, core/progression/* and keep their conventions.

CONTENT:
- sprites.json: 'miner': a 16x16 text grid for each frame of 4 directions (down, up, left, right) x 4 frames (walk0, walk1, mine0, mine1). Every character is a palette role ('.' = transparent): b body, a accent, v visor, d dark outline, m metal (pickaxe and joints), s shadow tone. 'base': a 48x48 grid for the base building (3x3 tiles) with the same roles plus r roof and w window, with a depot door facing south.
- skins.json: list of {id, name, description, unlocked_by, palette} where palette maps each role to a color. Skins: rusty_bot (default), copper_core, steel_walker, golden_hauler, ruby_runner. For now every skin has unlocked_by null (a later prompt wires them to achievements); until then a skin counts as unlocked when unlocked_by is null.
- PNG override: assets/skins/<id>.png laid out as 4 rows (down, up, left, right) x 4 columns (walk0, walk1, mine0, mine1) of 16x16 frames; if the file exists it replaces the generated frames for that skin.

CORE: save version 2 with selected_skin (default rusty_bot) and a migration from version 1 saves. Game.select_skin(id) only accepts unlocked skins; Game.selected_skin. Tests: version 1 saves still load; locked skins cannot be selected.

UI:
1. ui/sprites.py: SpriteBook builds QPixmaps from the grids and palettes (or PNGs) at the current tile size with nearest-neighbor scaling, cached by (skin, direction, animation, frame, tile_px). Validate the grids (16 rows of 16 characters, only known roles) and raise ContentError with file name and path.
2. ui/world_view.py: draw the miner with the selected skin: direction from miner.facing; a 2-frame walk animation while a Move command is active (frame rate scaled with the game speed); a 2-frame swing while Mine is active; idle = frame 0 with a 1-pixel bob. Keep the soft shadow from prompt 9 under it. Draw the base building sprite over the 3x3 base area with its own shadow, replacing the BASE rectangle.
3. ui/wardrobe_panel.py: FloatingPanel (key K and the View menu) with the skins as cards with an animated preview; locked skins are dimmed and show 'Unlocked by: <achievement title>' (use the requirement text of the progression service when it exists).
4. Tests (offscreen): grid validation errors; SpriteBook sizes for tile_px 12 to 64; the PNG override works (generate a temp sheet in the test); selecting a skin changes what the world view draws; old saves load.

ACCEPTANCE: extend tools/screenshot.py with --skin <id> and --moving; it saves artifacts/ui_skin_<id>.png for two different skins; the miner is readable at tile size 24 and the base building is visible.
COMMIT: feat(ui): miner skins, sprites and base building
