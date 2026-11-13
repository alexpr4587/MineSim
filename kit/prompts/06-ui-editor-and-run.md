# Prompt 6 of 8: UI floating panels, code editor and script execution

Follow AGENTS.md. Add the floating panels framework, the code editor and script execution.

1. ui/floating_panel.py: FloatingPanel(QFrame) is a child widget of the main window overlay (NOT an OS window): title bar to drag, close button, QSizeGrip to resize, stays inside the parent, raises on click, remembers its geometry with QSettings (set the organization and application names). Toggle keys: E editor, F functions reference (L and U come in the next prompt).
2. Hotkey rule: single-key shortcuts (E, F, L, U, C, G, Space, 1 to 5) only work while the world view or the HUD has focus, never while a text widget has focus (otherwise typing code would trigger them). Esc moves focus from the editor to the world view.
3. ui/code_editor.py: CodeEditor(QPlainTextEdit) adapted from the official Qt for Python Code Editor example (line number area and current line highlight) plus PythonHighlighter(QSyntaxHighlighter) following the official Syntax Highlighter example: keywords, builtins, strings, comments, numbers, def and class names, and the game API names in their own color. Also: Tab inserts 4 spaces, Shift+Tab dedents, auto-indent after a line that ends with ':', Ctrl+/ toggles comments, Ctrl+R runs, Ctrl+period stops, Ctrl+wheel changes the font size, and a red marker on the error line.
4. ui/editor_panel.py: tabs for the .py files in scripts_dir (platformdirs user_data_dir('MineSim')/scripts). Create main.py with the starter script on first run. Buttons: New file, Run, Stop, Open scripts folder; a state label (Idle, Running, Finished, Error); an auto-reload option using QFileSystemWatcher so players can edit in VS Code. Save on Run and on focus loss. Run while a script is running stops it first.
5. ui/console_panel.py: read-only log with colors for out, err and info lines, a clear button and auto-scroll; clicking a traceback line moves the editor cursor to that line.
6. ui/api_panel.py: functions reference listing every API function (signature, docstring), the modules and the minerlib helpers. Locked entries are dimmed and say: Locked, unlock with the achievement <title>.
7. Wiring: Run calls ScriptHost.start(filename, source); the game loop calls host.pump() every frame; the console and the editor state follow the host events; ScriptFailed highlights the error line; Stop kills the child; closing the window stops the script.

Starter script written on first run:
  # Welcome! Edit this script and press Run (Ctrl+R).
  for _ in range(10):
      if peek() is not None:
          mine()
      move(East)

TESTS (offscreen; real subprocess for the integration ones): line number width and highlighter formats on a sample; FloatingPanel stays inside the parent and restores its geometry; hotkeys do not fire while the editor has focus; running the starter script moves the miner 10 tiles and unlocks Hello, Miner; a script error highlights the right line; Stop works.

ACCEPTANCE: the screenshot shows the editor panel over the world with highlighted code and the console below it.
COMMIT: feat(ui): floating editor, console and script execution
