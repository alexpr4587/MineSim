# Prompt 3 of 8: player scripts (subprocess runner, host and API)

Follow AGENTS.md. Implement player scripting: the parent-side host, the child-side runner and the player API. No Qt anywhere in this prompt. Achievement ids are validated in a later prompt; use a ProgressionView test double here.

CONTENT:
- functions.json: list of {name, signature, doc, category, unlocked_by}. Starter functions (unlocked_by null): move(direction), mine(), peek(), position(). Gated: sell() <- first_dig, inventory() <- hello_miner, scan(radius) <- scout, stats() <- data_driven, buy_upgrade(upgrade_id) <- first_sale.
- modules.json: list of {name, unlocked_by}: math (null), random <- wanderer, statistics <- data_driven, collections <- custom_function, heapq <- custom_function.
- Constants injected into the player namespace: North, East, South, West.

SEMANTICS (all values JSON-friendly; tuples travel as lists and are converted back in the proxy):
- move(direction) -> None. mine() -> {ok, reason?, ore?}. peek() -> ore id, None or 'unknown'. position() -> (x, y). inventory() -> {ore: count}. scan(radius) -> [(dx, dy, ore_id or 'unknown')]. stats() -> {ore: {'attempts': n, 'successes': m}}. sell() -> money gained. buy_upgrade(id) -> new level.
- Calling a locked function raises NotUnlockedError inside the player script, with a message like: sell() is locked. Unlock it with the achievement 'First Dig'. The traceback shows the player's line.
- The cost of each call comes from the engine commands. After free_calls_before_forced_tick consecutive zero-cost calls the host inserts Wait(1), so a script can never freeze the game.

scripting/host.py: ScriptHost(engine, content, progression_view, scripts_dir).
- start(filename, source), stop(), pump() -> list of HostEvent. pump() is non-blocking: it reads everything the child sent, validates each request, submits commands to the engine and replies when the ticket is done. States: IDLE, RUNNING, FINISHED, FAILED, STOPPED. Console lines have a kind (out, err, info) and are capped by console_max_lines.
- Publishes ScriptStarted (defines_function computed with ast.parse in the host, never exec), ScriptFinished and ScriptFailed on the EventBus.
- Transport: multiprocessing.get_context('spawn').Process plus Pipe(duplex=True). Messages are JSON sent with send_bytes / recv_bytes. The host never unpickles anything coming from the child.
- Watchdog (the only wall-clock use in the project, and it lives in scripting/): if the child is running player code and neither calls the API nor finishes for script_idle_timeout_s, kill it and report 'Script ran N s without calling the game API (infinite loop?)'. Time spent waiting for the engine does not count. stop() terminates the process and always works.

runner/main.py: child entry point run(conn, source, filename, spec, allowed_modules, scripts_dir).
- Namespace with restricted builtins. Keep: print (redirected to the host), range, len, min, max, sum, abs, round, enumerate, zip, map, filter, sorted, reversed, list, dict, set, tuple, str, int, float, bool, isinstance, any, all, divmod, pow, repr, the exception classes, __build_class__, __name__. Remove: open, exec, eval, compile, input, globals, locals, vars, getattr, setattr, delattr, breakpoint, help.
- __import__ is replaced by a function that only allows allowed_modules, minerlib, and the .py files that sit in scripts_dir (so players can split their custom functions across files).
- API proxies are generated from spec. Every proxy sends a request and blocks for the reply.
- Errors are reported as {type, message, line, traceback_text} using the player's file name, with internal frames stripped.
runner/minerlib.py (importable by players, pure Python on top of the primitives): goto(x, y), go_home(), sweep(width, height) (serpentine generator of positions), spiral() (generator), mine_here() (peek, then mine if possible). Docstrings are mandatory.
tools/gen_stubs.py: generates minesim_api.pyi from functions.json and minerlib so VS Code can autocomplete. ScriptHost writes it into scripts_dir when a script starts.
CLI: `minesim --selftest` runs a headless game, executes a tiny script through the real subprocess runner, prints OK and exits 0 (used by CI and later by the frozen build).

TESTS (real subprocess, marked integration, each under about 5 s): a script that moves and mines changes the engine state as expected; `while True: pass` is killed by the watchdog; stop() kills a running script; a locked function raises NotUnlockedError with the right line number; forbidden builtins fail with NameError; importing random fails before the unlock and works after; a syntax error is reported with its line; print output arrives as console lines; modules in scripts_dir can be imported; 100000 zero-cost calls in a loop do not freeze the engine.

ACCEPTANCE: uv run minesim --selftest prints OK on Linux and Windows (CI).
COMMIT: feat(scripting): subprocess runner, host and player API
