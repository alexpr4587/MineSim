"""Fleet of drones: golden regression, commands, saves and rendering."""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from minesim.core.commands import (  # noqa: E402
    BuyUpgrade,
    Inventory,
    Mine,
    Move,
    Position,
    RemoveDrone,
    Sell,
    SpawnDrone,
    Stats,
    Wait,
)
from minesim.core.direction import Direction  # noqa: E402
from minesim.core.events import (  # noqa: E402
    DroneRemoved,
    DroneSpawned,
    MineAttempted,
    Moved,
    OreMined,
    Sold,
    TickAdvanced,
    UpgradeBought,
)
from minesim.core.game import Game  # noqa: E402
from minesim.core.save import SaveGame, migrate  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOLDEN = FIXTURES / "golden_session_v3.json"

_DRONE_EVENTS = {"Moved", "MineAttempted", "OreMined", "Sold", "UpgradeBought"}


def _commands() -> list[object]:
    return [
        Move(Direction.EAST),
        Move(Direction.EAST),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Move(Direction.WEST),
        Move(Direction.WEST),
        Sell(),
        BuyUpgrade("backpack"),
        BuyUpgrade("backpack"),
        BuyUpgrade("pickaxe"),
        BuyUpgrade("motor"),
        BuyUpgrade("scanner"),
        Move(Direction.EAST),
        Move(Direction.EAST),
        Mine(),
        Mine(),
        Mine(),
        Move(Direction.NORTH),
        Move(Direction.NORTH),
        Mine(),
        Move(Direction.SOUTH),
        Move(Direction.SOUTH),
        Move(Direction.SOUTH),
        Mine(),
        Move(Direction.WEST),
        Move(Direction.WEST),
        Sell(),
        Wait(3),
        Position(),
        Inventory(),
        Stats(),
        Move(Direction.SOUTH),
        Move(Direction.SOUTH),
        Move(Direction.EAST),
        Move(Direction.EAST),
        Mine(),
        Mine(),
        Move(Direction.NORTH),
        Move(Direction.NORTH),
        Move(Direction.WEST),
        Move(Direction.WEST),
        Sell(),
        BuyUpgrade("backpack"),
        Mine(),
        Wait(2),
    ]


def _event_record(event: object) -> dict[str, object]:
    record: dict[str, object] = {"type": type(event).__name__}
    if type(event).__name__ in _DRONE_EVENTS:
        record.setdefault("drone_id", 0)
    for field in dataclasses.fields(event):
        record[field.name] = getattr(event, field.name)
    return record


def _legacy_miner_dict(game: Game) -> dict[str, object]:
    """The pre-fleet ``Miner.to_dict()`` view of drone 0 and player stats."""
    drone = game.miner
    stats = game.player_stats
    return {
        "x": drone.x,
        "y": drone.y,
        "facing": drone.facing.name.lower(),
        "inventory": dict(drone.inventory),
        "capacity": stats.capacity,
        "money": stats.money,
        "tool_power": stats.tool_power,
        "tool_tier": stats.tool_tier,
        "move_ticks": stats.move_ticks,
        "scan_radius": stats.scan_radius,
        "stats": stats.stats.to_dict(),
        "upgrades": dict(stats.upgrades),
        "estimates": dict(stats.estimates),
    }


def _run_session() -> dict[str, object]:
    game = Game.new(seed=12345)
    game.miner.money = 1000
    for upgrade_id in ("backpack", "pickaxe", "motor", "scanner"):
        game.progression_state.unlock_upgrade(upgrade_id)
    log: list[dict[str, object]] = []
    for event_type in (
        Moved,
        MineAttempted,
        OreMined,
        Sold,
        UpgradeBought,
        TickAdvanced,
    ):
        game.events.subscribe(event_type, lambda event, log=log: log.append(_event_record(event)))
    for command in _commands():
        ticket = game.submit(command)
        game.run_until_idle()
        assert ticket.done
    return {
        "seed": game.seed,
        "tick": game.tick,
        "attempt_counter": game.engine.attempt_counter,
        "miner": _legacy_miner_dict(game),
        "world": game.world.to_dict(),
        "progression": game.progression_state.to_dict(),
        "events": log,
    }


def test_golden_single_drone_session_is_unchanged() -> None:
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert _run_session() == expected


# -- fleet behaviour ---------------------------------------------------------


def _fleet_events() -> tuple[type, ...]:
    return (
        Moved,
        MineAttempted,
        OreMined,
        Sold,
        UpgradeBought,
        TickAdvanced,
        DroneSpawned,
        DroneRemoved,
    )


def _two_drone_snapshot(seed: int = 777) -> dict[str, object]:
    game = Game.new(seed=seed)
    game.player_stats.money = 1000
    log: list[dict[str, object]] = []
    for event_type in _fleet_events():
        game.events.subscribe(event_type, lambda event, log=log: log.append(_event_record(event)))
    game.engine.spawn_drone()
    game.engine.spawn_drone()
    command_lists: dict[int, list[object]] = {
        0: [
            Move(Direction.EAST),
            Move(Direction.EAST),
            Mine(),
            Move(Direction.WEST),
            Move(Direction.WEST),
            Sell(),
        ],
        1: [
            Wait(1),
            Move(Direction.SOUTH),
            Mine(),
            Move(Direction.NORTH),
            Move(Direction.NORTH),
            Move(Direction.SOUTH),
        ],
        2: [Move(Direction.WEST), Mine(), Move(Direction.EAST), Mine()],
    }
    for drone_id, commands in command_lists.items():
        for command in commands:
            game.engine.submit(command, drone_id=drone_id)
    game.run_until_idle()
    return {
        "tick": game.tick,
        "attempt_counter": game.engine.attempt_counter,
        "player_stats": game.player_stats.to_dict(),
        "fleet": {
            drone_id: game.engine.drone(drone_id).to_fleet_dict()
            for drone_id in sorted(game.engine.drones)
        },
        "events": log,
    }


def test_two_drones_are_deterministic() -> None:
    assert _two_drone_snapshot() == _two_drone_snapshot()


def test_step_processes_drones_in_increasing_id_order() -> None:
    game = Game.new(seed=1)
    engine = game.engine
    engine.spawn_drone()
    engine.spawn_drone()
    moved: list[Moved] = []
    engine.events.subscribe(Moved, moved.append)
    engine.submit(Move(Direction.EAST), drone_id=2)
    engine.submit(Move(Direction.EAST), drone_id=1)
    engine.run_until_idle()
    assert [event.drone_id for event in moved] == [1, 2]
    assert engine.drone(2).x == engine.drone(1).x == 1


def test_spawn_limits_costs_and_drone_bay() -> None:
    game = Game.new(seed=2)
    engine = game.engine
    assert engine.max_drones == 1
    first = game.submit(SpawnDrone())
    game.run_until_idle()
    assert first.result == {"ok": False, "reason": "no_slot"}

    game.progression_state.unlock_upgrade("drone_bay")
    game.player_stats.money = 5000
    assert game.submit(BuyUpgrade("drone_bay")).result["ok"]
    game.run_until_idle()
    assert engine.max_drones == 2

    spent = game.player_stats.money
    ticket = game.submit(SpawnDrone())
    game.run_until_idle()
    assert ticket.result["ok"] is True
    assert ticket.result["drone_id"] == 1
    assert ticket.result["cost"] == 300
    assert game.player_stats.money == spent - 300
    assert engine.drone(1).position == (0, 0)

    no_slot = game.submit(SpawnDrone())
    game.run_until_idle()
    assert no_slot.result == {"ok": False, "reason": "no_slot"}

    assert game.submit(BuyUpgrade("drone_bay")).result["ok"]
    game.run_until_idle()
    assert engine.max_drones == 3
    second = game.submit(SpawnDrone())
    game.run_until_idle()
    assert second.result["cost"] == 800
    assert second.result["drone_id"] == 2

    assert game.submit(BuyUpgrade("drone_bay")).result["ok"]
    game.run_until_idle()
    assert engine.max_drones == 4
    game.player_stats.money = 100
    broke = game.submit(SpawnDrone())
    game.run_until_idle()
    assert broke.result["ok"] is False
    assert broke.result["reason"] == "not_enough_money"
    assert broke.result["cost"] == 2000


def test_remove_drone_never_removes_zero_and_reuses_free_id() -> None:
    game = Game.new(seed=3)
    engine = game.engine
    game.progression_state.unlock_upgrade("drone_bay")
    game.progression_state.unlock_upgrade("drone_bay")
    game.player_stats.upgrades["drone_bay"] = 2
    game.player_stats.money = 5000
    for _ in range(2):
        assert game.submit(SpawnDrone()).done
    assert sorted(engine.drones) == [0, 1, 2]
    engine.drone(1).inventory = {"stone": 5}
    removed: list[DroneRemoved] = []
    engine.events.subscribe(DroneRemoved, removed.append)

    main = game.submit(RemoveDrone(0))
    assert main.result["ok"] is False
    assert main.result["reason"] == "cannot_remove_main"

    ticket = game.submit(RemoveDrone(1))
    assert ticket.result == {"ok": True, "drone_id": 1}
    assert engine.has_drone(1) is False
    with pytest.raises(KeyError):
        engine.drone(1)
    assert [event.id for event in removed] == [1]
    assert engine.remove_drone(0) is False
    assert engine.remove_drone(99) is False

    replacement = engine.spawn_drone()
    assert replacement.id == 1


def test_save_v3_fixture_migrates_to_fleet() -> None:
    path = FIXTURES / "save_v3.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    migrated = migrate(data)
    assert migrated["version"] == 5
    assert migrated["player_stats"]["money"] == 43
    assert migrated["fleet"] == [{"id": 0, "x": 0, "y": 0, "facing": "west", "inventory": {}}]
    assert migrated["warehouse"] == {}
    assert migrated["market"] == {}

    savegame = SaveGame.load(path)
    assert savegame.version == 5
    game = Game.load(path)
    assert len(game.drones) == 1
    assert game.player_stats.money == 43
    assert game.miner.stats.attempts == {"stone": 1}
    assert (game.miner.x, game.miner.y) == (0, 0)
    assert game.miner.facing is Direction.WEST


def test_save_v4_fixture_migrates_to_warehouse_and_market() -> None:
    path = FIXTURES / "save_v4.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    migrated = migrate(data)
    assert migrated["version"] == 5
    assert migrated["warehouse"] == {}
    assert migrated["market"] == {}

    savegame = SaveGame.load(path)
    assert savegame.version == 5
    game = Game.load(path)
    assert game.engine.warehouse.total() == 0
    assert game.engine.warehouse.capacity == game.content.config.warehouse_start_capacity
    assert game.engine.market.step == 0
    assert game.engine.market.history("stone") == []


def test_fleet_save_round_trip(tmp_path) -> None:
    game = Game.new(seed=4)
    game.player_stats.money = 10000
    game.engine.spawn_drone()
    game.engine.spawn_drone()
    game.engine.drone(1).x, game.engine.drone(1).y = 4, -2
    game.engine.drone(1).inventory = {"coal": 3}
    game.engine.drone(2).facing = Direction.SOUTH
    path = game.save(tmp_path / "slot.json")
    loaded = Game.load(path)
    assert sorted(loaded.drones) == [0, 1, 2]
    for drone_id in (0, 1, 2):
        assert loaded.engine.drone(drone_id).to_fleet_dict() == (
            game.engine.drone(drone_id).to_fleet_dict()
        )
    assert loaded.player_stats.to_dict() == game.player_stats.to_dict()
    assert loaded.world.to_dict() == game.world.to_dict()
    assert loaded.tick == game.tick


def test_world_view_draws_every_drone() -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from minesim.ui.world_view import WorldView

    app = QApplication.instance() or QApplication([])
    game = Game.new(seed=5)
    game.player_stats.money = 10000
    game.engine.spawn_drone()
    game.engine.spawn_drone()
    game.engine.drone(1).x, game.engine.drone(1).y = 2, 0
    game.engine.drone(2).x, game.engine.drone(2).y = 0, 2
    view = WorldView(game)
    view.resize(320, 240)
    view.show()
    app.processEvents()
    assert [drone.id for drone in view.drones] == [0, 1, 2]
    pixmap = view.grab()
    image = pixmap.toImage()
    colors = {
        (image.pixelColor(x, y).red(), image.pixelColor(x, y).green())
        for y in range(0, image.height(), 6)
        for x in range(0, image.width(), 6)
    }
    assert len(colors) > 5
    view.close()
