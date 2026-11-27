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
if layer() != 0:
    raise RuntimeError(f"main miner started on layer {layer()}")
shared_set("main_ready", True)
while not (shared_get("worker_1_ready", False) and shared_get("worker_2_ready", False)):
    wait(1)
shared_set("main_go", True)
while not (shared_get("worker_1_done", False) and shared_get("worker_2_done", False)):
    wait(1)
move(East)
move(East)
shared_set("main_done", True)
"""

_SELFTEST_WORKER = """\
worker = miner_id()
if layer() != 1:
    raise RuntimeError(f"worker {worker} started on layer {layer()}")
shared_set(f"worker_{worker}_ready", True)
while not shared_get("main_go", False):
    wait(1)
move(South)
shared_set(f"worker_{worker}_done", True)
"""


def _run_selftest() -> int:
    """Run three cooperating miner scripts, two of them on layer 1."""
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
    engine.player_stats.upgrades["miner_bay"] = 2
    engine.player_stats.upgrades["shaft"] = 1
    workers = [engine.spawn_miner(), engine.spawn_miner()]
    for worker in workers:
        worker.layer = 1
        worker.x = 0
        worker.y = 0
    with tempfile.TemporaryDirectory(prefix="minesim-selftest-") as tmp:
        scripts_dir = Path(tmp)
        (scripts_dir / "selftest_worker.py").write_text(_SELFTEST_WORKER, encoding="utf-8")
        manager = ScriptManager(engine, scripts_dir)
        try:
            manager.start(0, "selftest.py", _SELFTEST_MAIN)
            for worker in workers:
                manager.start(worker.id, "selftest_worker.py", _SELFTEST_WORKER)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                manager.run_lockstep(200)
                states = manager.states()
                if all(state is not ScriptState.RUNNING for state in states.values()):
                    break
            else:
                raise RuntimeError("selftest timed out")
            states = manager.states()
            for miner_id in (0, 1, 2):
                state = states.get(miner_id)
                if state is not ScriptState.FINISHED:
                    error = getattr(manager.host(miner_id), "last_error", None) or {}
                    raise RuntimeError(
                        f"selftest miner {miner_id} failed: {error.get('message', state)}"
                    )
            main_miner = engine.miner_by_id(0)
            if (main_miner.x, main_miner.y, main_miner.layer) != (2, 0, 0):
                raise RuntimeError(
                    "selftest: miner 0 at "
                    f"{(main_miner.x, main_miner.y, main_miner.layer)}, expected (2, 0, 0)"
                )
            for miner_id in (1, 2):
                miner = engine.miner_by_id(miner_id)
                if (miner.x, miner.y, miner.layer) != (0, 1, 1):
                    raise RuntimeError(
                        f"selftest: miner {miner_id} at "
                        f"{(miner.x, miner.y, miner.layer)}, expected (0, 1, 1)"
                    )
            layers = {engine.miner_by_id(miner_id).layer for miner_id in (0, 1, 2)}
            if layers != {0, 1}:
                raise RuntimeError(f"selftest: expected miners on two layers, got {layers}")
            shared = engine.shared_memory
            done = ("main_done", "worker_1_done", "worker_2_done")
            if not all(shared.get(key) for key in done):
                raise RuntimeError(f"selftest: shared memory not coordinated: {shared}")
        finally:
            manager.stop_all()
    print("OK: 3 miners on 2 layers")
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


def _run_selftest_audio() -> int:
    """Render one SFX and one music loop, then exercise the manager silently."""
    from minesim.audio.backend import NullBackend
    from minesim.audio.cache import AudioCache
    from minesim.audio.manager import AudioManager
    from minesim.audio.settings import AudioSettings

    with tempfile.TemporaryDirectory(prefix="minesim-audio-") as tmp:
        root = Path(tmp)
        cache = AudioCache(cache_dir=root / "cache", data_dir=root / "data")
        cache.render_sfx("ui_click")
        cache.render_music("surface", bars=1)
        if not cache.sfx_path("ui_click", 0).is_file():
            raise RuntimeError("selftest-audio: sound effect was not rendered")
        if not cache.music_path("surface").is_file():
            raise RuntimeError("selftest-audio: music loop was not rendered")
        backend = NullBackend()
        manager = AudioManager(AudioSettings(), backend, cache)
        if not manager.play("ui_click"):
            raise RuntimeError("selftest-audio: the manager refused a sound")
        if not manager.set_mood("surface", fade_ms=10):
            raise RuntimeError("selftest-audio: the manager refused the music")
        if not backend.sfx_calls or not backend.music_calls:
            raise RuntimeError("selftest-audio: the backend did not receive the calls")
    print("OK: audio")
    return 0


def main() -> None:
    """Start MineSim."""
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(prog="minesim")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--selftest-ui", action="store_true")
    parser.add_argument("--selftest-audio", action="store_true")
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
    if args.selftest_audio:
        try:
            code = _run_selftest_audio()
        except Exception as exc:
            print(f"selftest-audio failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        if code != 0:
            raise SystemExit(code)
        return
    from minesim.ui.app import run

    run()


if __name__ == "__main__":
    main()
