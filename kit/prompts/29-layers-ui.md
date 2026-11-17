# Prompt 29 of 36 (v0.4): layers in the UI

Follow AGENTS.md. Goal: see and understand the layers. First read ui/world_view.py, ui/terrain_shader.py, ui/sprites.py, ui/hud.py, ui/miners_panel.py and content/sprites.json.

1. The world view shows the layer of the selected miner (the chunk cache keys and the shader cache keys include the layer). With 'Follow selected' off, PageUp and PageDown change the viewed layer.
2. Look per layer: floor_tint and light_ambient from layers.json feed the terrain shader (deeper = darker, with a different palette per layer); the ore speckle and the pits keep working.
3. Station sprite: a 48x48 grid in sprites.json (shaft head with an elevator cage and a lamp) drawn on the station of layers 1 to 3; the surface keeps the base house. Add a small up or down arrow badge to the shaft.
4. Transition: a 300 ms fade when the followed miner changes layer, and a toast like 'Miner 2 went down to Old Galleries'.
5. HUD: 'Layer: Old Galleries (1)' for the viewed layer. Miners panel: a layer column. Upgrades panel shows the shaft upgrade as 'reaches layer N'.
6. tools/screenshot.py: --layer N (puts the main miner there with a short mining session) and saves artifacts/ui_layer_N.png.
7. Tests (offscreen): cache keys include the layer; each layer renders non-blank and different from the others; the station sprite validates; PageUp and PageDown only work when not following; the transition does not break the snapshot tools.

ACCEPTANCE: screenshots of the four layers show clearly different looks, with the station and a miner mining.
COMMIT: feat(ui): layer view, stations and transitions
