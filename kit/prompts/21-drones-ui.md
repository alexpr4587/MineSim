# Prompt 21 of 25 (v0.3): drones UI

Follow AGENTS.md. Goal: control and see the fleet. First read ui/world_view.py, ui/console_panel.py, ui/editor_panel.py and scripting/manager.py.

1. ui/drones_panel.py (key D and the View menu): one row per drone with its badge color, state (Running, Idle, Failed), script, position, inventory used/capacity and the buttons Select, Kill and Assign (dropdown of the scripts in scripts_dir); a Spawn button that shows the price of the next drone and the free slots, with a script picker.
2. World view: clicking a drone selects it; the selected drone gets a highlight ring; a 'Follow selected' toggle (default on) moves the camera to the selected drone; the console panel follows the selection.
3. Editor panel: next to Run, add 'Run on new drone' (spawns a drone with the current file) and show the name of the drone that runs the current file.
4. HUD: drones alive and free slots.
5. tools/screenshot.py: a --drones N flag that spawns N drones with a trivial script and runs some ticks; it saves artifacts/ui_drones.png.
6. Tests (offscreen, real subprocess where needed): the panel rows follow spawn and kill; selection changes the console and the camera; Run on new drone creates a drone; layout without overlaps.

ACCEPTANCE: the screenshot shows several badge-colored drones working, the drones panel and the console of the selected drone.
COMMIT: feat(ui): drones panel and fleet view
