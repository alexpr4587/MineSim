"""Application entry point."""

from __future__ import annotations

import argparse
import multiprocessing
import sys
import tempfile
import time
from pathlib import Path


def _run_selftest() -> int:
    """Run a headless game with a tiny script through the real runner."""
    from digscript.core.content import load_content
    from digscript.core.engine import AllUnlocked, GameEngine
    from digscript.core.events import EventBus
    from digscript.core.miner import Miner
    from digscript.core.world import World, WorldGenerator
    from digscript.scripting.host import ScriptHost, ScriptState

    content = load_content()
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    bus = EventBus()
    engine = GameEngine(world, miner, content, bus, AllUnlocked())
    source = "move(East)\nmove(East)\nmine()\nprint(position())\n"
    with tempfile.TemporaryDirectory(prefix="digscript-selftest-") as tmp:
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


def main() -> None:
    """Start DigScript."""
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(prog="digscript")
    parser.add_argument("--selftest", action="store_true")
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
    from digscript.ui.app import run

    run()


if __name__ == "__main__":
    main()
