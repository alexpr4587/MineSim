"""Bridge the typed EventBus to the audio manager.

The bridge owns the gameplay-facing audio rules: it maps events to
sounds, computes positional pan/volume, scopes miners to the viewed
layer, tracks the mining combo and selects the music mood of the viewed
layer. It never runs player code.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

from minesim.audio.events import EVENT_TYPES, load_audio_events, rule_matches
from minesim.core.events import LayerChanged, MineAttempted
from minesim.core.schemas import AudioEventRule

__all__ = ["AudioBridge", "MOOD_FALLBACK"]

MOOD_FALLBACK: tuple[str, ...] = ("surface", "galleries", "deep", "abyss")
MUSIC_FADE_MS = 2000


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class AudioBridge:
    """Translate game events into polite AudioManager calls."""

    def __init__(
        self,
        game: Any,
        manager: Any,
        world_view: Any = None,
        content: Any = None,
        *,
        rules: list[AudioEventRule] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.game = game
        self.manager = manager
        self.world_view = world_view
        self.content = content or _get(game, "content")
        self._clock = clock or time.monotonic
        self._rules = rules if rules is not None else load_audio_events()
        self._last_played: dict[int, float] = {}
        self._unsubscribes: list[Callable[[], None]] = []
        self._view_unsubscribe: Callable[[], None] | None = None
        self._mood: str | None = None
        self._combo: int = 0
        self._last_mine_tick: int | None = None
        self._paused: bool = False
        self._subscribe()
        self._watch_world_view()
        self.sync_music()

    # -- properties -----------------------------------------------------------

    @property
    def rules(self) -> list[AudioEventRule]:
        """The loaded event-to-sound rules."""
        return list(self._rules)

    @property
    def combo(self) -> int:
        """The current number of successive successful mines."""
        return self._combo

    @property
    def combo_pitch_steps(self) -> int:
        """The pentatonic pitch offset for the current combo (0 to +7)."""
        return max(0, min(7, self._combo - 1))

    @property
    def mood(self) -> str | None:
        """The music mood currently requested by the bridge."""
        return self._mood

    @property
    def paused(self) -> bool:
        """Whether the bridge is in the paused state."""
        return self._paused

    # -- subscriptions --------------------------------------------------------

    def _bus(self) -> Any:
        return _get(self.game, "events") or _get(self.game, "event_bus")

    def _subscribe(self) -> None:
        bus = self._bus()
        if bus is None or not hasattr(bus, "subscribe"):
            return
        event_names = sorted({rule.event for rule in self._rules})
        for name in event_names:
            event_type = EVENT_TYPES.get(name)
            if event_type is None:
                continue
            unsubscribe = bus.subscribe(event_type, self.handle_event)
            self._unsubscribes.append(unsubscribe)

    def _unsubscribe(self) -> None:
        for unsubscribe in self._unsubscribes:
            try:
                unsubscribe()
            except Exception:
                pass
        self._unsubscribes.clear()

    def _watch_world_view(self) -> None:
        view = self.world_view
        signal = _get(view, "viewed_layer_changed")
        if signal is None or not hasattr(signal, "connect"):
            return
        try:
            signal.connect(self.set_viewed_layer)
        except Exception:
            return

        def disconnect() -> None:
            try:
                signal.disconnect(self.set_viewed_layer)
            except Exception:
                pass

        self._view_unsubscribe = disconnect

    def set_game(self, game: Any) -> None:
        """Attach a new game and re-subscribe to its event bus."""
        self._unsubscribe()
        self.game = game
        self.content = _get(game, "content") or self.content
        self._subscribe()
        self._mood = None
        self.sync_music()

    def set_world_view(self, world_view: Any) -> None:
        """Attach the world view used for camera and layer information."""
        if self._view_unsubscribe is not None:
            self._view_unsubscribe()
            self._view_unsubscribe = None
        self.world_view = world_view
        self._watch_world_view()
        self.sync_music()

    def close(self) -> None:
        """Stop listening to events and the world view."""
        self._unsubscribe()
        if self._view_unsubscribe is not None:
            self._view_unsubscribe()
            self._view_unsubscribe = None

    # -- event handling -------------------------------------------------------

    def handle_event(self, event: Any) -> None:
        """Play every sound rule that matches ``event``."""
        name = type(event).__name__
        if isinstance(event, MineAttempted):
            self._update_combo(event)
        for index, rule in enumerate(self._rules):
            if rule.event != name or not rule_matches(rule, event):
                continue
            self._play_rule(index, rule, event)

    def on_event(self, event: Any) -> None:
        """Alias for :meth:`handle_event`."""
        self.handle_event(event)

    def _play_rule(self, index: int, rule: AudioEventRule, event: Any) -> None:
        now = self._clock()
        cooldown = float(rule.cooldown_ms) / 1000.0
        last = self._last_played.get(index)
        if last is not None and now - last < cooldown:
            return
        volume = float(rule.volume)
        pan = 0.0
        if rule.positional:
            placement = self._placement(event)
            if placement is None:
                return
            layer, x, y = placement
            if rule.layer_scoped and layer != self.viewed_layer():
                return
            camera_x, camera_y = self.camera_center()
            pan, falloff = self.positional_mix(x, y, camera_x, camera_y)
            if falloff <= 0.0:
                return
            volume *= falloff
        pitch_steps = self.combo_pitch_steps if rule.pitch == "combo" else 0
        played = self.manager.play(rule.sound, volume=volume, pan=pan, pitch_steps=pitch_steps)
        if played:
            self._last_played[index] = now
        if rule.duck is not None:
            self.manager.duck(float(rule.duck.amount), int(rule.duck.ms))

    # -- combo ----------------------------------------------------------------

    def _tick(self) -> int:
        tick = _get(self.game, "tick")
        if tick is not None:
            return int(tick)
        return int(_get(_get(self.game, "engine"), "tick", 0) or 0)

    def _combo_window(self) -> int:
        config = _get(self.content, "config")
        return max(0, int(_get(config, "combo_window_ticks", 30) or 0))

    def _update_combo(self, event: Any) -> None:
        if bool(_get(event, "success", False)):
            tick = self._tick()
            if (
                self._last_mine_tick is not None
                and tick - self._last_mine_tick <= self._combo_window()
            ):
                self._combo += 1
            else:
                self._combo = 1
            self._last_mine_tick = tick
        elif str(_get(event, "reason", "")) == "miss":
            self._combo = 0
            self._last_mine_tick = None

    def reset_combo(self) -> None:
        """Reset the mining combo (a miss, a pause or a new game)."""
        self._combo = 0
        self._last_mine_tick = None

    # -- positional audio -----------------------------------------------------

    def viewed_layer(self) -> int:
        """Return the layer the player is looking at."""
        layer = _get(self.world_view, "viewed_layer")
        if layer is not None:
            return int(layer)
        return int(_get(_get(self.game, "miner"), "layer", 0) or 0)

    def camera_center(self) -> tuple[float, float]:
        """Return the camera center in tile coordinates."""
        view = self.world_view
        x = _get(view, "camera_x")
        y = _get(view, "camera_y")
        if x is not None and y is not None:
            return (float(x), float(y))
        miner = _get(self.game, "miner")
        return (
            float(_get(miner, "x", 0) or 0) + 0.5,
            float(_get(miner, "y", 0) or 0) + 0.5,
        )

    def hearing_radius(self) -> float:
        """Return the configured hearing radius in tiles."""
        config = _get(self.content, "config")
        return max(0.0, float(_get(config, "audio_hearing_radius", 14) or 0))

    def positional_mix(
        self,
        x: float,
        y: float,
        camera_x: float,
        camera_y: float,
    ) -> tuple[float, float]:
        """Return ``(pan, volume_factor)`` for a tile position.

        Pan follows the horizontal offset from the camera center. Inside
        the hearing radius the volume is full; it falls off linearly to
        silence at twice the radius.
        """
        radius = self.hearing_radius()
        dx = float(x) - float(camera_x)
        dy = float(y) - float(camera_y)
        if radius <= 0.0:
            return (0.0, 1.0 if dx == 0.0 and dy == 0.0 else 0.0)
        pan = max(-1.0, min(1.0, dx / radius))
        distance = math.hypot(dx, dy)
        if distance <= radius:
            return (pan, 1.0)
        if distance >= radius * 2.0:
            return (pan, 0.0)
        return (pan, 1.0 - (distance - radius) / radius)

    def _miner_position(self, miner_id: int) -> tuple[int, float, float] | None:
        engine = _get(self.game, "engine")
        miners = _get(engine, "miners")
        if not isinstance(miners, dict):
            miners = _get(self.game, "miners")
        if not isinstance(miners, dict):
            return None
        miner = miners.get(int(miner_id))
        if miner is None:
            return None
        return (
            int(_get(miner, "layer", 0) or 0),
            float(_get(miner, "x", 0) or 0) + 0.5,
            float(_get(miner, "y", 0) or 0) + 0.5,
        )

    def _placement(self, event: Any) -> tuple[int, float, float] | None:
        """Return ``(layer, x, y)`` for a positional event."""
        x = _get(event, "x")
        y = _get(event, "y")
        layer = _get(event, "layer")
        if isinstance(event, LayerChanged):
            miner_id = int(_get(event, "miner_id", 0) or 0)
            position = self._miner_position(miner_id)
            if position is not None:
                return (int(_get(event, "to_layer", position[0])), position[1], position[2])
            return (int(_get(event, "to_layer", 0) or 0), 0.5, 0.5)
        if x is not None and y is not None:
            return (int(layer or 0), float(x) + 0.5, float(y) + 0.5)
        miner_id = _get(event, "miner_id")
        if miner_id is None and type(event).__name__ == "MinerSpawned":
            miner_id = _get(event, "id")
        if miner_id is None:
            return None
        position = self._miner_position(int(miner_id))
        if position is None:
            return None
        event_layer = int(layer) if layer is not None else position[0]
        return (event_layer, position[1], position[2])

    # -- music ----------------------------------------------------------------

    def mood_for_layer(self, layer: int) -> str:
        """Return the music mood id for ``layer``."""
        layer_def = None
        getter = _get(self.content, "get_layer")
        if callable(getter):
            try:
                layer_def = getter(int(layer))
            except Exception:
                layer_def = None
        if layer_def is None:
            layers = _get(self.content, "layers")
            if isinstance(layers, dict):
                layer_def = layers.get(int(layer))
        mood = str(_get(layer_def, "music", "") or "")
        available = self._available_moods()
        if mood and (not available or mood in available):
            return mood
        index = max(0, min(len(MOOD_FALLBACK) - 1, int(layer)))
        fallback = MOOD_FALLBACK[index]
        if available and fallback not in available:
            return next(iter(available))
        return fallback

    def _available_moods(self) -> set[str]:
        cache = _get(self.manager, "cache")
        loader = _get(cache, "moods")
        if callable(loader):
            try:
                return set(loader())
            except Exception:
                return set()
        return set()

    def set_viewed_layer(self, layer: int, force: bool = False) -> None:
        """Select the music mood of ``layer`` with a two second crossfade."""
        mood = self.mood_for_layer(int(layer))
        if mood == self._mood and not force:
            return
        self._mood = mood
        self.manager.set_mood(mood, fade_ms=MUSIC_FADE_MS)

    def sync_music(self, force: bool = False) -> None:
        """Apply the music mood of the current viewed layer."""
        self.set_viewed_layer(self.viewed_layer(), force=force)

    # -- pause / mute ---------------------------------------------------------

    def set_paused(self, paused: bool) -> None:
        """Duck the music while paused, reset the combo and play a cue."""
        paused = bool(paused)
        if paused == self._paused:
            return
        self._paused = paused
        self.reset_combo()
        self.manager.set_paused(paused)
        self.manager.play("pause" if paused else "resume", volume=0.7)

    def toggle_pause(self) -> None:
        """Toggle the paused duck state."""
        self.set_paused(not self._paused)

    def play_ui(self, sound_id: str, volume: float = 0.8) -> bool:
        """Play a short UI sound (button click, panel open/close)."""
        return bool(self.manager.play(sound_id, volume=volume))
