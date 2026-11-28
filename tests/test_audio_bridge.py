"""Tests for the EventBus to audio bridge and audio event mapping."""

from __future__ import annotations

from types import SimpleNamespace

from minesim.audio.backend import NullBackend
from minesim.audio.events import load_audio_events, rule_matches
from minesim.audio.manager import AudioManager
from minesim.audio.settings import AudioSettings
from minesim.core.events import (
    AchievementUnlocked,
    LayerChanged,
    MineAttempted,
    Moved,
    OreMined,
    Sold,
)
from minesim.core.game import Game
from minesim.ui.audio_bridge import AudioBridge


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _bridge(game: Game, world_view: object | None = None) -> tuple[AudioBridge, NullBackend]:
    backend = NullBackend()
    settings = AudioSettings(master=1.0, music=1.0, sfx=1.0)
    manager = AudioManager(settings, backend, game.content, clock=_Clock())
    bridge = AudioBridge(game, manager, world_view=world_view, content=game.content)
    return bridge, backend


def test_audio_event_rules_validate_and_map_ores() -> None:
    rules = load_audio_events()
    ruby = [rule for rule in rules if rule.event == "OreMined" and rule.sound == "mine_ruby"]
    assert ruby
    assert rule_matches(ruby[0], OreMined(miner_id=0, ore_id="ruby", layer=0))
    assert not rule_matches(ruby[0], OreMined(miner_id=0, ore_id="gold", layer=0))


def test_event_publishes_expected_sound() -> None:
    game = Game.new()
    _bridge_instance, backend = _bridge(game)
    game.events.publish(OreMined(miner_id=0, ore_id="ruby", layer=0))
    assert backend.sfx_calls[-1].sound_id == "mine_ruby"
    game.events.publish(Sold(miner_id=0, money=50, items={"stone": 1}, avg_index=1.0))
    assert backend.sfx_calls[-1].sound_id == "sell_small"


def test_positional_math_and_layer_scoping() -> None:
    game = Game.new()
    view = SimpleNamespace(viewed_layer=0, camera_x=0.0, camera_y=0.0)
    bridge, backend = _bridge(game, view)
    pan, falloff = bridge.positional_mix(7.0, 0.0, 0.0, 0.0)
    assert pan == 0.5
    assert falloff == 1.0
    pan, falloff = bridge.positional_mix(28.0, 0.0, 0.0, 0.0)
    assert pan == 1.0
    assert falloff == 0.0
    bridge.handle_event(Moved(miner_id=0, x=0, y=0, layer=1))
    assert not backend.sfx_calls
    bridge.handle_event(Moved(miner_id=0, x=0, y=0, layer=0))
    assert backend.sfx_calls[-1].sound_id == "step"


def test_combo_raises_pitch_and_miss_resets_it() -> None:
    game = Game.new()
    bridge, backend = _bridge(game)
    for expected in (0, 1, 2):
        game.events.publish(
            MineAttempted(miner_id=0, ore_id="stone", layer=0, success=True, reason=None)
        )
        assert backend.sfx_calls[-1].sound_id == "ore_pop"
        assert backend.sfx_calls[-1].pitch_steps == expected
    game.events.publish(
        MineAttempted(miner_id=0, ore_id="stone", layer=0, success=False, reason="miss")
    )
    assert bridge.combo == 0
    game.events.publish(
        MineAttempted(miner_id=0, ore_id="stone", layer=0, success=True, reason=None)
    )
    assert backend.sfx_calls[-1].pitch_steps == 0


def test_music_mood_follows_viewed_layer() -> None:
    game = Game.new()
    view = SimpleNamespace(viewed_layer=0, camera_x=0.0, camera_y=0.0)
    bridge, backend = _bridge(game, view)
    assert bridge.mood == "surface"
    bridge.set_viewed_layer(1)
    assert bridge.mood == "galleries"
    assert backend.music_calls[-1].sound_id == "galleries"
    assert backend.music_calls[-1].fade_ms == 2000
    bridge.set_viewed_layer(3)
    assert bridge.mood == "abyss"


def test_achievement_ducks_and_pause_ducks_only_music() -> None:
    game = Game.new()
    clock = _Clock()
    backend = NullBackend()
    manager = AudioManager(
        AudioSettings(master=1.0, music=1.0, sfx=1.0), backend, game.content, clock=clock
    )
    AudioBridge(game, manager, content=game.content)
    game.events.publish(AchievementUnlocked(id="first"))
    assert backend.volumes[1] < 1.0
    assert backend.volumes[2] < 1.0
    clock.advance(1.3)
    manager.set_paused(True)
    assert backend.volumes[1] == 0.6
    assert backend.volumes[2] == 1.0
    manager.set_paused(False)
    assert backend.volumes[1] == 1.0
    assert backend.volumes[2] == 1.0


def test_layer_changed_uses_direction_conditions() -> None:
    game = Game.new()
    _bridge_instance, backend = _bridge(game)
    game.events.publish(LayerChanged(miner_id=0, from_layer=0, to_layer=1))
    assert backend.sfx_calls[-1].sound_id == "layer_down"
    game.events.publish(LayerChanged(miner_id=0, from_layer=1, to_layer=0))
    assert backend.sfx_calls[-1].sound_id == "layer_up"
