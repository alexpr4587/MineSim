"""Tests for the shared surface dock (prompt 32)."""

from __future__ import annotations

from minesim.core.commands import BuyUpgrade, DockRate, DockStatus, Sell, Unload
from minesim.core.events import DockQueued, DockServed
from minesim.core.game import Game


def _game() -> Game:
    game = Game.new(seed=12345)
    game.progression_state.unlocked_features.add("warehouse")
    return game


def test_config_exposes_the_dock_rate() -> None:
    game = Game.new()
    assert game.content.config.dock_rate == 4
    assert game.engine.dock_rate == 4
    assert game.engine.dock_status() == {
        "free": True,
        "queue_length": 0,
        "eta_ticks": 0,
        "rate": 4,
    }


def test_sell_uses_the_dock_and_finishes_at_the_end_of_the_tick() -> None:
    game = _game()
    game.miner.inventory = {"stone": 1}
    served: list[DockServed] = []
    game.events.subscribe(DockServed, served.append)

    ticket = game.submit(Sell())
    assert not ticket.done
    assert game.engine.dock_status()["free"] is False

    game.step()
    assert ticket.done
    assert ticket.result["ok"] is True
    assert game.miner.inventory == {}
    assert game.engine.dock_status()["free"] is True
    assert served[0].miner_id == 0
    assert served[0].units == 1
    assert served[0].waited_ticks == 0


def test_five_miners_queue_in_fifo_order() -> None:
    game = _game()
    queued: list[DockQueued] = []
    served: list[DockServed] = []
    game.events.subscribe(DockQueued, queued.append)
    game.events.subscribe(DockServed, served.append)

    tickets = []
    for miner_id in range(5):
        if miner_id:
            miner = game.engine.spawn_miner()
        else:
            miner = game.miner
        miner.inventory = {"stone": 1}
        tickets.append(game.submit(Unload(), miner_id=miner_id))

    assert [game.engine.miner_by_id(i).dock_state for i in range(5)] == [
        None,
        "queued",
        "queued",
        "queued",
        "queued",
    ]
    assert [event.miner_id for event in queued] == [1, 2, 3, 4]
    assert game.engine.dock_status()["queue_length"] == 4

    for tick in range(1, 6):
        game.step()
        assert [ticket.done for ticket in tickets] == [index < tick for index in range(5)]

    assert [event.miner_id for event in served] == [0, 1, 2, 3, 4]
    assert [event.waited_ticks for event in served] == [0, 1, 2, 3, 4]
    assert game.engine.dock_status()["free"] is True


def test_dock_rate_batches_units() -> None:
    game = _game()
    game.miner.inventory = {"stone": 9}
    ticket = game.submit(Unload())

    game.step()
    game.step()
    assert not ticket.done
    game.step()
    assert ticket.done


def test_empty_unload_still_uses_one_tick() -> None:
    game = _game()
    ticket = game.submit(Unload())
    game.step()
    assert ticket.done


def test_empty_sell_keeps_the_old_two_tick_cost() -> None:
    game = _game()
    assert Sell().cost_ticks(game.engine, game.miner) == 2
    ticket = game.submit(Sell())
    game.step()
    assert not ticket.done
    game.step()
    assert ticket.done


def test_dock_upgrade_raises_the_rate_and_speeds_up_service() -> None:
    game = _game()
    game.player_stats.money = 1000
    ticket = game.submit(BuyUpgrade("dock"))
    assert ticket.done
    assert ticket.result["ok"] is True
    assert game.engine.dock_rate == 6
    assert game.engine.dock.rate == 6

    status = DockStatus().execute(game.engine)
    assert status["rate"] == 6
    assert DockRate().execute(game.engine)["rate"] == 6

    game.miner.inventory = {"stone": 5}
    ticket = game.submit(Unload())
    game.step()
    assert ticket.done


def test_status_command_reports_the_queue() -> None:
    game = _game()
    game.miner.inventory = {"stone": 1}
    game.engine.spawn_miner().inventory = {"stone": 1}
    game.submit(Unload(), miner_id=0)
    game.submit(Unload(), miner_id=1)

    status = DockStatus().execute(game.engine)
    assert status["free"] is False
    assert status["queue_length"] == 1
    assert status["eta_ticks"] == 2
    assert status["rate"] == 4


def test_removing_a_waiting_miner_cancels_its_dock_job() -> None:
    game = _game()
    game.miner.inventory = {"stone": 1}
    game.engine.spawn_miner().inventory = {"stone": 1}
    first = game.submit(Unload(), miner_id=0)
    second = game.submit(Unload(), miner_id=1)
    assert game.engine.dock_status()["queue_length"] == 1

    assert game.engine.remove_miner(1)
    assert second.done is False
    assert game.engine.dock_status()["queue_length"] == 0

    game.step()
    assert first.done
    assert not second.done
