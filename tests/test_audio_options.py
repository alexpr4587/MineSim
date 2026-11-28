"""Offscreen tests for the audio options panel and the HUD speaker button."""

from __future__ import annotations

import pytest

from minesim.audio.backend import NullBackend
from minesim.audio.manager import AudioManager
from minesim.audio.settings import AudioSettings
from minesim.core.game import Game
from minesim.ui.hud import HUD
from minesim.ui.options_panel import OptionsPanel


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _manager() -> tuple[AudioManager, AudioSettings, NullBackend]:
    settings = AudioSettings(master=0.8, music=0.25, sfx=0.6)
    backend = NullBackend()
    manager = AudioManager(settings, backend, Game.new().content)
    return manager, settings, backend


def test_options_panel_controls_update_and_persist(qapp, monkeypatch) -> None:
    manager, settings, _backend = _manager()
    saved: list[AudioSettings] = []
    monkeypatch.setattr(
        AudioSettings, "save", lambda self, target=None: saved.append(self.clamped())
    )
    panel = OptionsPanel(audio=manager, settings=settings)
    panel.master_slider.setValue(50)
    assert settings.master == pytest.approx(0.5)
    assert manager.settings.master == pytest.approx(0.5)
    panel.music_slider.setValue(10)
    assert settings.music == pytest.approx(0.1)
    panel.sfx_slider.setValue(70)
    assert settings.sfx == pytest.approx(0.7)
    panel.music_checkbox.setChecked(False)
    assert settings.music_enabled is False
    panel.sfx_checkbox.setChecked(False)
    assert settings.sfx_enabled is False
    panel.mute_checkbox.setChecked(True)
    assert settings.muted is True
    assert saved
    panel.mute_checkbox.setChecked(False)
    panel.sfx_checkbox.setChecked(True)
    panel.add_section("Visuals")
    assert "Visuals" in panel.sections
    panel.test_button.click()
    assert manager.backend.sfx_calls[-1].sound_id == "ui_click"


def test_hud_speaker_toggles_mute_and_opens_options(qapp) -> None:
    manager, settings, backend = _manager()
    hud = HUD(Game.new())
    opened: list[bool] = []
    hud.set_audio(manager, lambda: opened.append(True))
    assert hud.speaker_button.text() == "♪"
    hud.speaker_button.click()
    assert settings.muted is True
    assert hud.speaker_button.isChecked() is True
    assert backend.sfx_calls[-1].sound_id == "toggle_off"
    hud.speaker_button.click()
    assert settings.muted is False
    assert hud.speaker_button.isChecked() is False
    assert backend.sfx_calls[-1].sound_id == "toggle_on"
    hud.open_options()
    assert opened == [True]
