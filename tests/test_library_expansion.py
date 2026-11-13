"""Tests for the expanded player library (prompt 12)."""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest

from minesim.core.commands import (
    Biome,
    Distance,
    Inspect,
    Inventory,
    Mine,
    Move,
    OreInfo,
    Peek,
    Scan,
    Sell,
    SubmitEstimate,
    Tick,
)
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.engine import AllUnlocked, GameEngine
from minesim.core.events import EstimateSubmitted, EventBus
from minesim.core.miner import Miner
from minesim.core.world import World, WorldGenerator
from minesim.runner import minerlib
from minesim.scripting.host import ScriptHost, ScriptState
from minesim.scripting.stubs import generate_stub_text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def content():
    return load_content()


def _engine(content, *, progression=None):
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    bus = EventBus()
    engine = GameEngine(world, miner, content, bus, progression or AllUnlocked())
    return engine, world, miner, bus


def _submit(engine, command):
    ticket = engine.submit(command)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


def _find_tile(world, ore_id, start=2):
    for y in range(start, start + 40):
        for x in range(start, start + 40):
            if world.tile_at(x, y, 0).ore_id == ore_id:
                return x, y
    raise AssertionError(f"no tile with {ore_id}")


class _LockedCoal:
    def is_ore_unlocked(self, ore_id):
        return ore_id != "coal"

    def is_function_unlocked(self, name):
        return True

    def is_upgrade_unlocked(self, upgrade_id):
        return True

    def is_module_unlocked(self, name):
        return True


def test_functions_and_modules_are_documented(content):
    required = {
        "wait",
        "tick",
        "distance",
        "biome",
        "ore_info",
        "inspect",
        "submit_estimate",
    }
    assert required <= set(content.functions)
    wiring = {
        "wait": "patience",
        "tick": "clockwork",
        "distance": "far_from_home",
        "biome": "deep_diver",
        "ore_info": "appraiser",
        "inspect": "know_your_limits",
        "submit_estimate": "sampler",
    }
    for name in required:
        spec = content.functions[name]
        assert spec.cost
        assert spec.example
        assert spec.unlocked_by == wiring[name]
    for name in ("itertools", "functools", "dataclasses", "typing"):
        assert name in content.modules
        assert content.modules[name].unlocked_by is not None


def test_tick_distance_and_biome(content):
    engine, _world, miner, _bus = _engine(content)
    miner.x, miner.y = 3, -4
    assert _submit(engine, Tick())["tick"] >= 0
    assert _submit(engine, Distance())["distance"] == 4
    assert _submit(engine, Biome())["biome"] in content.biomes


def test_ore_info_hides_probability_and_locked_ores(content):
    engine, _world, _miner, _bus = _engine(content)
    info = _submit(engine, OreInfo("stone"))["info"]
    assert info["id"] == "stone"
    assert "mine_probability" not in info
    assert "probability" not in info

    engine, _world, _miner, _bus = _engine(content, progression=_LockedCoal())
    assert _submit(engine, OreInfo("coal"))["info"] is None

    engine, _world, _miner, _bus = _engine(content)
    assert _submit(engine, OreInfo("no_such_ore"))["info"] is None


def test_inspect_reports_ore_and_regeneration(content):
    engine, world, miner, _bus = _engine(content)
    x, y = _find_tile(world, "stone")
    miner.x, miner.y = x, y
    seen = _submit(engine, Inspect())["inspect"]
    assert seen["ore"] == "stone"
    assert seen["mineable"] is True
    assert seen["reason"] is None
    assert seen["regrows_in"] is None

    world.mine_tile(x, y, engine.tick)
    seen = _submit(engine, Inspect())["inspect"]
    assert seen["ore"] is None
    assert seen["mineable"] is False
    assert seen["reason"] == "nothing_to_mine"
    assert seen["regrows_in"] is not None and seen["regrows_in"] >= 0


def test_submit_estimate_requires_data_and_limits_attempts(content):
    engine, _world, miner, bus = _engine(content)
    bus_events: list[EstimateSubmitted] = []
    bus.subscribe(EstimateSubmitted, bus_events.append)

    result = _submit(engine, SubmitEstimate("stone", 0.9))
    assert result["ok"] is False
    assert result["reason"] == "not_enough_data"
    assert result["attempts"] == 0

    miner.stats.attempts["stone"] = 100
    result = _submit(engine, SubmitEstimate("no_such_ore", 0.5))
    assert result["reason"] == "unknown_ore"

    true_p = content.get_ore("stone").mine_probability
    for _ in range(3):
        result = _submit(engine, SubmitEstimate("stone", true_p))
        assert result == {"ok": True, "close": True}
    result = _submit(engine, SubmitEstimate("stone", true_p))
    assert result["reason"] == "limit_reached"
    assert result["submissions"] == 3
    assert len(bus_events) == 3
    assert all(event.good for event in bus_events)


def test_estimates_round_trip_with_miner(content):
    miner = Miner.from_config(content)
    miner.estimates["stone"] = 2
    restored = Miner.from_dict(miner.to_dict())
    assert restored.estimates == {"stone": 2}


def test_ring_nearest_and_samples(content):
    assert list(minerlib.ring(0)) == [(0, 0)]
    ring = list(minerlib.ring(1))
    assert len(ring) == 8
    assert len(set(ring)) == 8
    assert set(ring) == {
        (-1, -1),
        (0, -1),
        (1, -1),
        (-1, 0),
        (1, 0),
        (-1, 1),
        (0, 1),
        (1, 1),
    }

    samples = minerlib.Samples()
    assert samples.rate("stone") == 0.0
    samples.add("stone", True)
    samples.add("stone", False)
    assert samples.count("stone") == 2
    assert samples.rate("stone") == 0.5
    assert samples.summary()["stone"] == {"attempts": 2, "successes": 1, "rate": 0.5}


def _inject_engine(monkeypatch, engine, miner):
    """Wire minerlib primitives to a headless engine for helper tests."""

    def move(direction):
        return _submit(engine, Move(Direction.parse(direction)))

    def position():
        return (miner.x, miner.y)

    def peek():
        return _submit(engine, Peek())["ore"]

    def mine():
        return _submit(engine, Mine())

    def scan(radius):
        result = _submit(engine, Scan(int(radius)))
        return [tuple(tile) for tile in result["tiles"]]

    def inventory():
        return _submit(engine, Inventory())["inventory"]

    def sell():
        return _submit(engine, Sell())["money"]

    monkeypatch.setattr(minerlib, "move", move)
    monkeypatch.setattr(minerlib, "position", position)
    monkeypatch.setattr(minerlib, "peek", peek)
    monkeypatch.setattr(minerlib, "mine", mine)
    monkeypatch.setattr(minerlib, "scan", scan)
    monkeypatch.setattr(minerlib, "inventory", inventory)
    monkeypatch.setattr(minerlib, "sell", sell)


def test_minerlib_helpers_against_engine(content, monkeypatch):
    engine, world, miner, _bus = _engine(content)
    _inject_engine(monkeypatch, engine, miner)

    minerlib.goto(3, 2)
    assert (miner.x, miner.y) == (3, 2)
    minerlib.go_home()
    assert (miner.x, miner.y) == (0, 0)

    x, y = _find_tile(world, "stone")
    miner.x, miner.y = x, y
    assert minerlib.nearest("stone", 2) is not None
    assert minerlib.goto_nearest("stone", 2) is True
    assert (miner.x, miner.y) == (x, y)
    assert minerlib.mine_until(1) >= 1

    miner.x, miner.y = _find_tile(world, "stone")
    assert minerlib.farm("stone", max_tiles=1) >= 1

    miner.inventory.clear()
    miner.inventory["stone"] = 2
    before = miner.money
    miner.x, miner.y = 2, 3
    earned = minerlib.haul()
    base = content.get_ore("stone").base_value
    expected = math.floor(base) + math.floor(base * (1.0 - content.config.impact_per_unit))
    assert earned == expected
    assert miner.money == before + earned
    assert miner.inventory == {}
    assert (miner.x, miner.y) == (2, 3)


def test_examples_exist_and_compile(content):
    examples_dir = ROOT / "src" / "minesim" / "examples"
    assert len(content.examples) >= 8
    for example in content.examples.values():
        path = examples_dir / example.file
        assert path.is_file()
        source = path.read_text(encoding="utf-8")
        assert source.startswith("# ") or source.startswith("# ruff")
        assert "# Unlocks needed:" in source
        compile(source, str(path), "exec")


def test_docs_are_up_to_date(tmp_path):
    import sys

    sys.path.insert(0, str(ROOT))
    try:
        from tools import gen_docs
    finally:
        sys.path.pop(0)
    output = tmp_path / "API.md"
    gen_docs.generate_api_md(output)
    assert output.read_text(encoding="utf-8") == (ROOT / "docs" / "API.md").read_text(
        encoding="utf-8"
    )


def test_generated_stub_contains_new_api():
    stub = generate_stub_text()
    assert (ROOT / "minesim_api.pyi").read_text(encoding="utf-8") == stub
    for name in (
        "wait",
        "tick",
        "distance",
        "biome",
        "ore_info",
        "inspect",
        "submit_estimate",
        "nearest",
        "goto_nearest",
        "mine_until",
        "haul",
        "farm",
        "ring",
        "class Samples",
    ):
        assert name in stub


@pytest.mark.integration
@pytest.mark.parametrize("example_id", list(load_content().examples))
def test_every_example_runs_in_subprocess_without_error(example_id, content, tmp_path):
    example = content.examples[example_id]
    source = (ROOT / "src" / "minesim" / "examples" / example.file).read_text(encoding="utf-8")
    engine, _world, _miner, _bus = _engine(content)
    host = ScriptHost(engine, content, AllUnlocked(), tmp_path)
    host.start(example.file, source)
    for _ in range(2000):
        host.pump()
        engine.step()
        if host.state is not ScriptState.RUNNING:
            break
    assert host.state is not ScriptState.FAILED, host.last_error
    host.stop()


@pytest.mark.integration
def test_new_primitives_from_player_script(content, tmp_path):
    engine, _world, miner, _bus = _engine(content)
    miner.stats.attempts["stone"] = 100
    host = ScriptHost(engine, content, AllUnlocked(), tmp_path)
    host.start(
        "new_api.py",
        "\n".join(
            [
                'print("tick", tick())',
                'print("distance", distance())',
                'print("biome", biome())',
                'print("ore", ore_info("stone")["id"])',
                'print("inspect", inspect()["ore"])',
                'print("submit", submit_estimate("stone", 0.95))',
                "wait(3)",
                'print("later", tick())',
                "",
            ]
        ),
    )
    deadline = time.monotonic() + 10.0
    while host.state is ScriptState.RUNNING:
        assert time.monotonic() < deadline
        host.pump()
        engine.run_until_idle()
        time.sleep(0.001)
    host.pump()
    assert host.state is ScriptState.FINISHED
    texts = [event.text for event in host.console_lines if event.kind == "out"]
    assert any(text.startswith("tick ") for text in texts)
    assert any(text.startswith("distance ") for text in texts)
    assert "ore stone" in texts
    assert any("'ok': True" in text for text in texts)
    host.stop()


@pytest.mark.integration
def test_wait_is_validated(content, tmp_path):
    engine, _world, _miner, _bus = _engine(content)
    host = ScriptHost(engine, content, AllUnlocked(), tmp_path)
    host.start("bad_wait.py", "wait(0)\n")
    deadline = time.monotonic() + 10.0
    while host.state is ScriptState.RUNNING:
        assert time.monotonic() < deadline
        host.pump()
        engine.run_until_idle()
        time.sleep(0.001)
    host.pump()
    assert host.state is ScriptState.FAILED
    host.stop()
