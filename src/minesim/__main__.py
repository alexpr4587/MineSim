"""Application entry point."""

from __future__ import annotations

import argparse
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path

_SELFTEST_MAIN = """\
worker = spawn_miner("selftest_worker.py")
if not isinstance(worker, int):
    raise RuntimeError(f"spawn failed: {worker}")
shared_set("main_ready", True)
while not shared_get("worker_ready", False):
    wait(1)
shared_set("main_go", True)
while not shared_get("worker_done", False):
    wait(1)
move(East)
move(East)
shared_set("main_done", True)
"""

_SELFTEST_WORKER = """\
shared_set("worker_ready", True)
while not shared_get("main_go", False):
    wait(1)
move(South)
shared_set("worker_done", True)
"""


def _run_selftest() -> int:
    """Run two cooperating miner scripts through the real runner."""
    from minesim.core.content import load_content
    from minesim.core.engine import AllUnlocked, GameEngine
    from minesim.core.events import EventBus
    from minesim.core.miner import Miner
    from minesim.core.world import World, WorldGenerator
    from minesim.scripting.host import ScriptState
    from minesim.scripting.manager import ScriptManager

    content = load_content()
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    bus = EventBus()
    engine = GameEngine(world, miner, content, bus, AllUnlocked())
    engine.player_stats.money = 1000
    engine.player_stats.upgrades["miner_bay"] = 1
    with tempfile.TemporaryDirectory(prefix="minesim-selftest-") as tmp:
        scripts_dir = Path(tmp)
        (scripts_dir / "selftest_worker.py").write_text(_SELFTEST_WORKER, encoding="utf-8")
        manager = ScriptManager(engine, scripts_dir)
        try:
            manager.start(0, "selftest.py", _SELFTEST_MAIN)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                manager.run_lockstep(200)
                states = manager.states()
                if all(state is not ScriptState.RUNNING for state in states.values()):
                    break
            else:
                raise RuntimeError("selftest timed out")
            states = manager.states()
            for miner_id in (0, 1):
                state = states.get(miner_id)
                if state is not ScriptState.FINISHED:
                    error = getattr(manager.host(miner_id), "last_error", None) or {}
                    raise RuntimeError(
                        f"selftest miner {miner_id} failed: {error.get('message', state)}"
                    )
            if (engine.miner_by_id(0).x, engine.miner_by_id(0).y) != (2, 0):
                raise RuntimeError(
                    f"selftest: miner 0 at {(engine.miner_by_id(0).x, engine.miner_by_id(0).y)}, "
                    "expected (2, 0)"
                )
            if (engine.miner_by_id(1).x, engine.miner_by_id(1).y) != (0, 1):
                raise RuntimeError(
                    f"selftest: miner 1 at {(engine.miner_by_id(1).x, engine.miner_by_id(1).y)}, "
                    "expected (0, 1)"
                )
            shared = engine.shared_memory
            if not shared.get("main_done") or not shared.get("worker_done"):
                raise RuntimeError(f"selftest: shared memory not coordinated: {shared}")
        finally:
            manager.stop_all()
    print("OK")
    return 0


def _run_selftest_ui() -> int:
    """Render one lit chunk and one skin sprite offscreen, then exit."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from minesim.core.game import Game
    from minesim.ui.sprites import SpriteBook
    from minesim.ui.terrain_shader import render_chunk

    app = QApplication.instance() or QApplication([])
    game = Game.new()
    app.processEvents()

    started = time.perf_counter()
    chunk = render_chunk(game.world, 0, 0, 0, content=game.content)
    chunk_ms = (time.perf_counter() - started) * 1000.0
    if chunk.isNull() or chunk.width() <= 0 or chunk.height() <= 0:
        raise RuntimeError("selftest-ui: lit chunk render produced no image")

    sprites = SpriteBook(game.content)
    sprite = sprites.miner_pixmap(game.selected_skin, "down", "walk0", 0, 16)
    if sprite.isNull() or sprite.width() <= 0 or sprite.height() <= 0:
        raise RuntimeError("selftest-ui: skin sprite render produced no pixmap")

    print(
        f"selftest-ui OK: lit chunk {chunk.width()}x{chunk.height()} in {chunk_ms:.2f} ms; "
        f"skin sprite {sprite.width()}x{sprite.height()} ({game.selected_skin})"
    )
    return 0


def main() -> None:
    """Start MineSim."""
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(prog="minesim")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--selftest-ui", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        try:
            code = _run_selftest()
        except Exception as exc:
            print(f"selftest failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        if code != 0:
            raise SystemExit(code)
        return
    if args.selftest_ui:
        try:
            code = _run_selftest_ui()
        except Exception as exc:
            print(f"selftest-ui failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        if code != 0:
            raise SystemExit(code)
        return
    from minesim.ui.app import run

    run()


if __name__ == "__main__":
    main()
