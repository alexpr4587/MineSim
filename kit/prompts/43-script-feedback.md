# Prompt 43 of 46 (v0.5): seeing your code run

Follow AGENTS.md. Goal: the player should see their script working and feel the payoff of a run. First read runner/main.py, scripting/host.py, scripting/manager.py, ui/code_editor.py, ui/editor_panel.py, ui/console_panel.py and ui/hud.py.

1. Running line: every API request sent by the runner includes the player's current file name and line number (found by walking the frames to the first frame whose file is the player's). The manager forwards it per miner. The editor shows a soft highlight on that line and a small colored badge in the gutter for each miner running that file (several badges when several miners run the same file). The highlight pulses gently while a long command is executing. Option 'Show running line' (section 'Visual', default on). Calls from imported user modules show the module file name; only highlight the line when that file is open.
2. Overhead: the extra frame inspection must be cheap; add a benchmark test (100000 calls cost less than 15 percent more than before).
3. Run summary: when a script finishes or is stopped, the console gets a line and a toast like 'Finished in 1,240 ticks: +$320, 34 ore, 2 achievements', computed from the difference of the stats between the start and the end of that script.
4. Income meter: the HUD shows 'Income $48/min' computed over a rolling window of game time, with an optional small sparkline (reuse the one from the Records tab).
5. Console: lines are prefixed with the miner color and the tick, and the selected miner still follows the console filter.
6. Tests: line numbers are correct in the main file, in functions and in imported modules; multi-miner badges; the highlight clears when the script ends; the summary math; the income meter on a synthetic history; the benchmark.

ACCEPTANCE: a screenshot where three miners run one script and the editor shows the running line with three badges; the summary toast after a finished run.
COMMIT: feat: running-line highlight, run summaries and income meter
