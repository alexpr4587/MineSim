# Prompt 27 of 36 (v0.3.1): editor tabs you can close, open and manage

Follow AGENTS.md. Goal: close files in the editor without deleting them, and keep many scripts manageable. First read ui/editor_panel.py, ui/code_editor.py and the editor tests.

1. Closing: every tab has a close button (x); middle-click closes a tab; Ctrl+W closes the current tab (only while the editor has focus); Ctrl+Shift+T reopens the last closed tab. Closing NEVER deletes the file: unsaved changes are saved first. A script that is running keeps running when its tab is closed; tabs of running scripts show a small colored dot (the color of the miner that runs it).
2. Opening: an 'Open...' button with a searchable list of every .py file in scripts_dir that is not open (sorted by last modified); picking one opens it in a tab. 'New file' keeps working.
3. File actions in a small menu (the three-dots button): Rename (valid Python module name, because scripts can be imported), Duplicate and Delete. Delete asks for confirmation and moves the file to scripts_dir/.trash with a timestamp; 'Restore deleted...' in the same menu lists and restores trashed files. The trash folder is never offered as importable modules.
4. Persistence: the open tabs and the active tab are remembered between runs (QSettings); files that no longer exist are skipped silently.
5. External changes: if an open file is deleted or renamed outside the game, its tab closes with an info line in the console; files modified externally reload as today when auto-reload is on.
6. Dirty state: a dot in the tab title while there are unsaved edits; autosave after 2 seconds without typing, on Run and on focus loss.
7. HUD: the selected speed button label is still barely readable; give the selected state a high-contrast label and verify it in a screenshot.
8. Single-letter hotkeys stay disabled while a text widget has focus; the new Ctrl shortcuts work only with the editor focused.
9. README: mention the new editor features and Ctrl+W; refresh the miners screenshot. CHANGELOG 0.3.1 entry (rename drones to miners, editor tabs, HUD fix) and a version bump to 0.3.1.
10. Tests (offscreen): closing a tab keeps the file; reopen with Ctrl+Shift+T; Open... lists only closed files; rename validation; delete moves to .trash and restore brings it back; tabs persist across a restart; an external delete closes the tab; the running dot appears; the speed button label has enough contrast (compare pixel colors).

ACCEPTANCE: a screenshot with 12 scripts created, 3 open tabs and the Open... list visible; all tests pass.
COMMIT: feat(ui): closable editor tabs and file management
