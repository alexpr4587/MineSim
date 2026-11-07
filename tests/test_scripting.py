"""Integration tests for player scripting (prompt 03, real subprocess)."""

from __future__ import annotations

import time

import pytest

from digscript.core.content import load_content
from digscript.core.engine import AllUnlocked, GameEngine
from digscript.core.events import EventBus, ScriptFailed, ScriptFinished, ScriptStarted
from digscript.core.miner import Miner
from digscript.core.world import World, WorldGenerator
from digscript.runner import minerlib
from digscript.scripting.host import ScriptHost, ScriptState

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def content():
    return load_content()


def _make(content, *, progression=None, idle_timeout=None, free_calls=None):
    if idle_timeout is not None or free_calls is not None:
        updates = {}
        if idle_timeout is not None:
            updates["script_idle_timeout_s"] = idle_timeout
        if free_calls is not None:
            updates["free_calls_before_forced_tick"] = free_calls
        content = load_content()
        content.config = content.config.model_copy(update=updates)
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    bus = EventBus()
    view = progression or AllUnlocked()
    engine = GameEngine(world, miner, content, bus, view)
    return engine, world, miner, bus, view, content


def _run(host, engine, timeout=10.0):
    deadline = time.monotonic() + timeout
    while host.state is ScriptState.RUNNING:
        assert time.monotonic() < deadline, "script did not finish in time"
        host.pump()
        engine.run_until_idle()
        time.sleep(0.001)
    host.pump()
    return host.state


class _LockedView:
    """Test double: only starter functions/modules are unlocked."""

    def __init__(self, unlocked_functions=(), unlocked_modules=()):
        self._functions = set(unlocked_functions)
        self._modules = set(unlocked_modules)

    def is_ore_unlocked(self, ore_id):
        return True

    def is_function_unlocked(self, name):
        return name in self._functions

    def is_upgrade_unlocked(self, upgrade_id):
        return True

    def is_module_unlocked(self, name):
        return name in self._modules

    def requirement_title(self, kind, ident):
        titles = {
            "first_dig": "First Dig",
            "hello_miner": "Hello, Miner",
            "scout": "Scout",
            "data_driven": "Data Driven",
            "first_sale": "First Sale",
            "wanderer": "Wanderer",
            "custom_function": "Your Own Function",
        }
        return titles.get(ident, ident)


def test_move_and_mine_change_engine_state(content, tmp_path):
    engine, world, miner, bus, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    started, finished = [], []
    bus.subscribe(ScriptStarted, started.append)
    bus.subscribe(ScriptFinished, finished.append)
    host.start("s.py", "move(East)\nmove(East)\nmine()\n")
    assert _run(host, engine) is ScriptState.FINISHED
    assert (miner.x, miner.y) == (2, 0)
    assert started and started[0].defines_function is False
    assert finished
    assert (tmp_path / "digscript_api.pyi").is_file()
    host.stop()


def test_defines_function_flag(content, tmp_path):
    engine, _, _, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "def helper():\n    return 1\n\nhelper()\n")
    assert _run(host, engine) is ScriptState.FINISHED
    assert host.defines_function is True
    host.stop()


def test_watchdog_kills_infinite_loop(content, tmp_path):
    engine, _, _, _, view, _ = _make(content, idle_timeout=0.5)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "while True:\n    pass\n")
    assert _run(host, engine, timeout=8) is ScriptState.FAILED
    assert host.last_error is not None
    assert "without calling the game API" in host.last_error["message"]
    host.stop()


def test_stop_kills_running_script(content, tmp_path):
    engine, _, _, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "while True:\n    pass\n")
    time.sleep(0.2)
    host.pump()
    host.stop()
    assert host.state is ScriptState.STOPPED
    assert host.process is None or not host.process.is_alive()
    assert _run(host, engine, timeout=2) is ScriptState.STOPPED


def test_locked_function_raises_with_line(content, tmp_path):
    engine, _, _, bus, view, _ = _make(content, progression=_LockedView())
    failed = []
    bus.subscribe(ScriptFailed, failed.append)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "print('before')\nsell()\n")
    assert _run(host, engine) is ScriptState.FAILED
    assert host.last_error["type"] == "NotUnlockedError"
    assert "sell() is locked" in host.last_error["message"]
    assert "First Dig" in host.last_error["message"]
    assert host.last_error["line"] == 2
    assert "s.py" in host.last_error["traceback_text"]
    assert failed and failed[0].error_type == "NotUnlockedError"
    host.stop()


def test_forbidden_builtin_fails_with_name_error(content, tmp_path):
    engine, _, _, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "open('x.txt')\n")
    assert _run(host, engine) is ScriptState.FAILED
    assert host.last_error["type"] == "NameError"
    host.stop()


def test_module_unlock_gating(content, tmp_path):
    engine, _, _, _, _, _ = _make(content, progression=_LockedView())
    host = ScriptHost(engine, content, _LockedView(), tmp_path)
    host.start("s.py", "import random\n")
    assert _run(host, engine) is ScriptState.FAILED
    assert "random" in host.last_error["message"]
    host.stop()

    engine, _, _, _, _, _ = _make(content, progression=_LockedView(unlocked_modules={"random"}))
    host = ScriptHost(engine, content, _LockedView(unlocked_modules={"random"}), tmp_path)
    host.start("s.py", "import random\nrandom.seed(1)\nprint(random.random() >= 0)\n")
    assert _run(host, engine) is ScriptState.FINISHED
    host.stop()


def test_syntax_error_reports_line(content, tmp_path):
    engine, _, _, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("broken.py", "x = 1\ny = (\n")
    assert _run(host, engine) is ScriptState.FAILED
    assert host.last_error["type"] == "SyntaxError"
    assert host.last_error["line"] == 2
    assert "broken.py" in host.last_error["traceback_text"]
    host.stop()


def test_print_arrives_as_console_lines(content, tmp_path):
    engine, _, _, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "print('hello world')\nprint('second')\n")
    assert _run(host, engine) is ScriptState.FINISHED
    texts = [event.text for event in host.console_lines if event.kind == "out"]
    assert "hello world" in texts
    assert "second" in texts
    assert all(event.kind in ("out", "err", "info") for event in host.console_lines)
    host.stop()


def test_scripts_dir_module_can_be_imported(content, tmp_path):
    (tmp_path / "helper.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    engine, _, _, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "import helper\nprint(helper.answer())\n")
    assert _run(host, engine) is ScriptState.FINISHED
    assert "42" in [event.text for event in host.console_lines]
    host.stop()


def test_minerlib_import_and_helpers(content, tmp_path):
    engine, _, _, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    source = (
        "import minerlib\n"
        "minerlib.goto(2, 1)\n"
        "print(position())\n"
        "minerlib.go_home()\n"
        "print(position())\n"
    )
    host.start("s.py", source)
    assert _run(host, engine) is ScriptState.FINISHED
    assert (host.engine.miner.x, host.engine.miner.y) == (0, 0)
    host.stop()


def test_zero_cost_calls_do_not_freeze_engine(content, tmp_path):
    engine, _, miner, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    host.start("s.py", "for i in range(5000):\n    peek()\nprint('done')\n")
    assert _run(host, engine, timeout=15) is ScriptState.FINISHED
    assert engine.tick > 0
    assert "done" in [event.text for event in host.console_lines]
    host.stop()


def test_api_return_values(content, tmp_path):
    engine, _, miner, _, view, _ = _make(content)
    host = ScriptHost(engine, content, view, tmp_path)
    source = (
        "print(peek())\n"
        "print(position())\n"
        "move(East)\n"
        "print(position())\n"
        "r = mine()\n"
        "print(r['ok'])\n"
    )
    host.start("s.py", source)
    assert _run(host, engine) is ScriptState.FINISHED
    texts = [event.text for event in host.console_lines]
    assert "(0, 0)" in texts
    assert "(1, 0)" in texts
    host.stop()


def test_minerlib_pure_helpers():
    assert list(minerlib.sweep(3, 2)) == [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1)]
    spiral = minerlib.spiral()
    first = [next(spiral) for _ in range(5)]
    assert first == [(0, 0), (1, 0), (1, 1), (0, 1), (-1, 1)]
    for fn in (
        minerlib.goto,
        minerlib.go_home,
        minerlib.sweep,
        minerlib.spiral,
        minerlib.mine_here,
    ):
        assert fn.__doc__
