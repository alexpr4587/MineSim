"""Tests for the v0.4 library helpers, modules and examples (prompt 33)."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from minesim.core.commands import (
    Ascend,
    Battery,
    Biome,
    Charge,
    Climate,
    Cool,
    Descend,
    DockRate,
    DockStatus,
    EnergyCost,
    Events,
    Inventory,
    Layer,
    Layers,
    MinerId,
    Miners,
    Move,
    Position,
    Sell,
    Temperature,
    Unload,
    Wait,
)
from minesim.core.content import load_content
from minesim.core.direction import Direction
from minesim.core.engine import AllUnlocked, GameEngine
from minesim.core.events import EventBus
from minesim.core.miner import Miner
from minesim.core.world import World, WorldGenerator
from minesim.runner import minerlib
from minesim.scripting.host import ScriptState
from minesim.scripting.manager import ScriptManager

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def content():
    return load_content()


def _engine(content):
    generator = WorldGenerator(content.config.seed_default, content)
    world = World(generator, content)
    miner = Miner.from_config(content)
    engine = GameEngine(world, miner, content, EventBus(), AllUnlocked())
    return engine, world, miner


def _submit(engine, command):
    ticket = engine.submit(command)
    engine.run_until_idle()
    assert ticket.done
    return ticket.result


def _inject(monkeypatch, engine):
    def submit(command):
        return _submit(engine, command)

    values = {
        "move": lambda direction: bool(submit(Move(Direction.parse(direction)))["ok"]),
        "position": lambda: (submit(Position())["x"], submit(Position())["y"]),
        "battery": lambda: submit(Battery()),
        "charge": lambda: submit(Charge()),
        "energy_cost": lambda action, arg=None: submit(EnergyCost(str(action), arg))["cost"],
        "temperature": lambda: submit(Temperature()),
        "climate": lambda: submit(Climate()),
        "cool": lambda target=30.0: submit(Cool(float(target))),
        "layer": lambda: submit(Layer())["layer"],
        "layers": lambda: submit(Layers())["layers"],
        "descend": lambda: submit(Descend()),
        "ascend": lambda: submit(Ascend()),
        "dock_free": lambda: {
            "free": bool(submit(DockStatus())["free"]),
            "queue": int(submit(DockStatus()).get("queue_length", 0) or 0),
            "eta": int(submit(DockStatus()).get("eta_ticks", 0) or 0),
        },
        "dock_rate": lambda: submit(DockRate())["rate"],
        "inventory": lambda: submit(Inventory())["inventory"],
        "sell": lambda: submit(Sell())["money"],
        "unload": lambda: submit(Unload()),
        "wait": lambda ticks: submit(Wait(int(ticks))),
        "events": lambda: submit(Events())["events"],
        "miner_id": lambda: submit(MinerId())["id"],
        "miners": lambda: submit(Miners())["miners"],
        "biome": lambda: submit(Biome())["biome"],
    }
    for name, value in values.items():
        monkeypatch.setattr(minerlib, name, value)


def _lock(monkeypatch, *names):
    def locked(*_args, **_kwargs):
        raise minerlib.NotUnlockedError("locked")

    for name in names:
        monkeypatch.setattr(minerlib, name, locked)


def test_v04_modules_and_examples(content):
    assert content.modules["json"].unlocked_by == "power_user"
    assert content.modules["copy"].unlocked_by == "galleries_veteran"
    expected = {
        "17_energy_budget",
        "18_go_deep",
        "19_climate_watch",
        "20_dock_etiquette",
        "21_night_shift",
        "22_layer_prospector",
        "23_vent_manager",
        "24_full_automation",
    }
    assert expected <= set(content.examples)
    examples_dir = ROOT / "src" / "minesim" / "examples"
    unlocked_by = {
        "17_energy_budget": "power_user",
        "18_go_deep": "first_descent",
        "19_climate_watch": "cool_head",
        "20_dock_etiquette": "dock_master",
        "21_night_shift": "efficiency_expert",
        "22_layer_prospector": "abyss_gazer",
        "23_vent_manager": "fresh_air",
        "24_full_automation": "abyssal_haul",
    }
    for example_id in expected:
        example = content.examples[example_id]
        assert example.unlocked_by == unlocked_by[example_id]
        path = examples_dir / example.file
        assert path.is_file()
        source = path.read_text(encoding="utf-8")
        assert source.startswith("# ")
        assert "# Tick cost:" in source
        assert "# Energy cost:" in source
        assert "# Unlocks needed:" in source
        compile(source, str(path), "exec")


def test_optionals_fall_back_when_locked(monkeypatch):
    monkeypatch.setattr(minerlib, "position", lambda: (0, 0))
    monkeypatch.setattr(minerlib, "move", lambda direction: True)
    _lock(
        monkeypatch,
        "battery",
        "charge",
        "energy_cost",
        "temperature",
        "cool",
        "climate",
        "layer",
        "layers",
        "descend",
        "ascend",
        "dock_free",
        "miner_id",
        "miners",
        "inventory",
        "events",
        "sell",
        "unload",
        "wait",
    )

    assert minerlib.energy_to(3, 0) == 3
    assert minerlib.can_return() is True
    assert minerlib.charge_full() is False
    assert minerlib.heat_budget() == 1
    assert minerlib.smart_unload() == 0
    assert minerlib.stagger(0) == 1
    assert minerlib.go_up(1) is True
    assert minerlib.dive(1) is False
    assert minerlib.to_station() is True
    monkeypatch.setattr(minerlib, "shared_set", lambda key, value: None)
    assert minerlib.Fleet().balance_load(2) == {0: 0}
    assert list(itertools.islice(minerlib.spiral(), 5)) == [
        (0, 0),
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
    ]


def test_energy_aware_goto_haul_and_charge(content, monkeypatch):
    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine)

    miner.x, miner.y = 0, 0
    assert minerlib.energy_to(4, 0) == 4
    assert minerlib.can_return() is True
    assert minerlib.charge_full() is True

    miner.energy = 3
    assert minerlib.goto(4, 0) is False
    assert (miner.x, miner.y) == (3, 0)

    miner.energy = miner.battery_capacity
    assert minerlib.goto(4, 0) is True
    assert (miner.x, miner.y) == (4, 0)

    miner.energy = 4
    assert minerlib.can_return(0.1) is False

    miner.x, miner.y = 2, 0
    miner.energy = miner.battery_capacity
    miner.inventory["stone"] = 3
    earned = minerlib.haul()
    assert earned > 0
    assert miner.inventory == {}
    assert (miner.x, miner.y) == (2, 0)
    assert miner.energy >= miner.battery_capacity - 2


def test_layer_heat_and_dock_helpers(content, monkeypatch):
    engine, _world, miner = _engine(content)
    _inject(monkeypatch, engine)
    miner.upgrades["shaft"] = 2
    miner.x = miner.y = 0
    miner.temperature = 40.0

    assert minerlib.to_station() is True
    assert minerlib.go_down(2) is True
    assert minerlib.layer() == 2
    assert minerlib.temperature()["heat"] == 1
    assert minerlib.heat_budget() > 0
    assert minerlib.cool_down(30) is True
    assert minerlib.temperature()["temperature"] <= 30.0
    assert minerlib.go_up(2) is True
    assert minerlib.layer() == 0
    assert minerlib.dive(1) is True
    assert minerlib.dive(0) is True

    miner.inventory["stone"] = 2
    assert minerlib.smart_unload() >= 0
    assert minerlib.stagger(5) == 2


def test_energy_aware_worker(monkeypatch):
    calls: dict[str, int] = {"unload": 0}

    monkeypatch.setattr(minerlib, "position", lambda: (0, 0))
    monkeypatch.setattr(minerlib, "goto", lambda x, y: True)
    monkeypatch.setattr(minerlib, "charge", lambda: {"ok": True})
    monkeypatch.setattr(minerlib, "battery", lambda: {"energy": 100, "capacity": 100})
    monkeypatch.setattr(minerlib, "events", lambda: [])
    monkeypatch.setattr(minerlib, "energy_cost", lambda action, arg=None: 1)
    monkeypatch.setattr(minerlib, "inventory", lambda: {"stone": 1})
    monkeypatch.setattr(minerlib, "dock_free", lambda: {"free": True, "queue": 0, "eta": 0})

    def unload():
        calls["unload"] += 1
        return {"moved": {"stone": 1}}

    monkeypatch.setattr(minerlib, "unload", unload)
    _lock(monkeypatch, "temperature", "cool", "climate")

    class Full(minerlib.EnergyAwareWorker):
        def work(self):
            return {"ok": False, "reason": "inventory_full"}

    worker = Full("full")
    assert worker.run(2) == 2
    assert worker.unloads == 2
    assert calls["unload"] == 2

    monkeypatch.setattr(minerlib, "battery", lambda: {"energy": 5, "capacity": 100})
    needy = minerlib.EnergyAwareWorker("needy", rest_margin=0.2)
    assert needy.needs_rest() is True
    assert needy.rest() is True
    assert needy.rests == 1


def test_fleet_assign_and_balance(monkeypatch):
    shared: dict[str, object] = {}
    dives: list[int] = []
    monkeypatch.setattr(minerlib, "miner_id", lambda: 0)
    monkeypatch.setattr(minerlib, "miners", lambda: [{"id": 0}, {"id": 1}, {"id": 2}, {"id": 3}])
    monkeypatch.setattr(
        minerlib,
        "layers",
        lambda: [
            {"index": 0, "name": "Surface", "accessible": True},
            {"index": 1, "name": "Galleries", "accessible": True},
            {"index": 2, "name": "Deep", "accessible": True},
            {"index": 3, "name": "Abyss", "accessible": False},
        ],
    )
    monkeypatch.setattr(minerlib, "shared_get", lambda key, default=None: shared.get(key, default))
    monkeypatch.setattr(minerlib, "shared_set", lambda key, value: shared.__setitem__(key, value))
    monkeypatch.setattr(minerlib, "dive", lambda layer: dives.append(layer) or True)

    fleet = minerlib.Fleet()
    assert fleet.balance_load(2) == {0: 2, 1: 2, 2: 0, 3: 1}
    assert shared["fleet_layers"] == {"0": 2, "1": 2, "2": 0, "3": 1}
    assert fleet.assign_layers({1: 1}) == {0: 2, 1: 1, 2: 0, 3: 1}
    assert dives == []


@pytest.mark.integration
@pytest.mark.parametrize(
    "example_id",
    [
        "17_energy_budget",
        "18_go_deep",
        "19_climate_watch",
        "20_dock_etiquette",
        "21_night_shift",
        "22_layer_prospector",
        "23_vent_manager",
        "24_full_automation",
    ],
)
def test_v04_examples_run_through_subprocess(example_id, content, tmp_path):
    example = content.examples[example_id]
    source = (ROOT / "src" / "minesim" / "examples" / example.file).read_text(encoding="utf-8")
    (tmp_path / example.file).write_text(source, encoding="utf-8")
    engine, _world, _miner = _engine(content)
    manager = ScriptManager(engine, tmp_path)
    manager.start_script(0, example.file)
    try:
        manager.run_lockstep(3000)
        host = manager.host(0)
        assert host is not None
        assert host.state is not ScriptState.FAILED, host.last_error
        assert host.last_error is None
    finally:
        manager.stop_all()
