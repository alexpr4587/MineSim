"""Application entry point."""

from __future__ import annotations

import argparse
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path


def _run_selftest() -> int:
    """Run a headless game with a tiny script through the real runner."""
    from minesim.core.content import load_content
    from minesim.core.engine import AllUnlocked, GameEngine
    from minesim.core.events import EventBus
    from minesim.core.miner import Miner
    from minesim.core.world import World, WorldGenerator
    from minesim.scripting.host import ScriptHost, ScriptState

    content = load_content()
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    bus = EventBus()
    engine = GameEngine(world, miner, content, bus, AllUnlocked())
    source = "move(East)\nmove(East)\nmine()\nprint(position())\n"
    with tempfile.TemporaryDirectory(prefix="minesim-selftest-") as tmp:
        host = ScriptHost(engine, content, AllUnlocked(), Path(tmp))
        try:
            host.start("selftest.py", source)
            deadline = time.monotonic() + 15
            while host.state is ScriptState.RUNNING:
                if time.monotonic() > deadline:
                    host.stop()
                    raise RuntimeError("selftest timed out")
                host.pump()
                engine.run_until_idle()
                time.sleep(0.001)
            if host.state is not ScriptState.FINISHED:
                error = host.last_error or {}
                raise RuntimeError(f"selftest script failed: {error.get('message', host.state)}")
            if (miner.x, miner.y) != (2, 0):
                raise RuntimeError(f"selftest: miner at {(miner.x, miner.y)}, expected (2, 0)")
        finally:
            host.stop()
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
