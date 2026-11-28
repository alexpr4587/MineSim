"""Options panel: audio controls now, clean sections for later prompts."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from minesim.audio.settings import AudioSettings
from minesim.ui.floating_panel import FloatingPanel
from minesim.ui.theme import FONT_SIZE, TEXT, TEXT_DIM

__all__ = ["OptionsPanel"]


def _percent(value: float) -> int:
    return int(round(max(0.0, min(1.0, float(value))) * 100.0))


class OptionsPanel(FloatingPanel):
    """A floating options window with an extensible section layout.

    The audio section is implemented here. Later prompts add visuals and
    gameplay by calling :meth:`add_section`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        audio = kwargs.pop("audio", None) or kwargs.pop("manager", None)
        settings = kwargs.pop("settings", None)
        kwargs.pop("game", None)
        title = kwargs.pop("title", "Options")
        parent = kwargs.pop("parent", None)
        for arg in args:
            if isinstance(arg, QWidget) and parent is None:
                parent = arg
        if parent is not None:
            kwargs["parent"] = parent
        kwargs.setdefault("default_size", (440, 520))
        super().__init__(title=title, **kwargs)
        self.audio = audio
        self.manager = audio
        self.settings = settings or getattr(audio, "settings", None) or AudioSettings.load()
        self.sections: dict[str, QWidget] = {}
        self._syncing = False
        self._build_audio_section()
        self.sync_controls()

    # -- extension point ------------------------------------------------------

    def add_section(self, title: str) -> QVBoxLayout:
        """Add a titled section and return its layout for later prompts."""
        container = QWidget(self.content_widget)
        container.setObjectName(f"options_section_{title.lower()}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(6)
        header = QLabel(title, container)
        header.setStyleSheet(f"color: {TEXT}; font-weight: bold; font-size: {FONT_SIZE + 2}px;")
        layout.addWidget(header)
        self.content_layout.addWidget(container)
        self.sections[title] = container
        return layout

    def add_section_widget(self, title: str, widget: QWidget) -> None:
        """Add ``widget`` under a titled section (extension point)."""
        layout = self.add_section(title)
        layout.addWidget(widget)

    # -- audio section --------------------------------------------------------

    def _build_audio_section(self) -> None:
        layout = self.add_section("Audio")
        self.master_slider, self.master_value = self._add_slider(
            layout, "Master", "options_master_slider", self._on_master
        )
        self.music_slider, self.music_value = self._add_slider(
            layout, "Music", "options_music_slider", self._on_music
        )
        self.sfx_slider, self.sfx_value = self._add_slider(
            layout, "Sound effects", "options_sfx_slider", self._on_sfx
        )
        self.music_checkbox = QCheckBox("Music on", self.content_widget)
        self.music_checkbox.setObjectName("options_music_checkbox")
        self.music_checkbox.toggled.connect(self._on_music_enabled)
        layout.addWidget(self.music_checkbox)
        self.sfx_checkbox = QCheckBox("Sound effects on", self.content_widget)
        self.sfx_checkbox.setObjectName("options_sfx_checkbox")
        self.sfx_checkbox.toggled.connect(self._on_sfx_enabled)
        layout.addWidget(self.sfx_checkbox)
        self.mute_checkbox = QCheckBox("Mute all", self.content_widget)
        self.mute_checkbox.setObjectName("options_mute_checkbox")
        self.mute_checkbox.toggled.connect(self._on_muted)
        layout.addWidget(self.mute_checkbox)
        test_row = QHBoxLayout()
        self.test_button = QPushButton("Test sound", self.content_widget)
        self.test_button.setObjectName("options_test_sound")
        self.test_button.clicked.connect(self._on_test_sound)
        test_row.addWidget(self.test_button)
        test_row.addStretch(1)
        layout.addLayout(test_row)
        hint = QLabel("Press O to open these options at any time.", self.content_widget)
        hint.setStyleSheet(f"color: {TEXT_DIM};")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)

    def _add_slider(
        self,
        layout: QVBoxLayout,
        label: str,
        object_name: str,
        callback: Any,
    ) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        name = QLabel(label, self.content_widget)
        name.setMinimumWidth(110)
        slider = QSlider(Qt.Orientation.Horizontal, self.content_widget)
        slider.setObjectName(object_name)
        slider.setRange(0, 100)
        slider.valueChanged.connect(callback)
        value = QLabel("0%", self.content_widget)
        value.setMinimumWidth(40)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(name)
        row.addWidget(slider, 1)
        row.addWidget(value)
        layout.addLayout(row)
        return slider, value

    # -- control handlers -----------------------------------------------------

    def _on_master(self, value: int) -> None:
        if self._syncing:
            return
        self.master_value.setText(f"{int(value)}%")
        self._set_volume("master", value / 100.0)

    def _on_music(self, value: int) -> None:
        if self._syncing:
            return
        self.music_value.setText(f"{int(value)}%")
        self._set_volume("music", value / 100.0)

    def _on_sfx(self, value: int) -> None:
        if self._syncing:
            return
        self.sfx_value.setText(f"{int(value)}%")
        self._set_volume("sfx", value / 100.0)

    def _on_music_enabled(self, enabled: bool) -> None:
        if self._syncing:
            return
        self.settings.music_enabled = bool(enabled)
        if self.manager is not None:
            self.manager.set_music_enabled(bool(enabled))
        self._persist()

    def _on_sfx_enabled(self, enabled: bool) -> None:
        if self._syncing:
            return
        self.settings.sfx_enabled = bool(enabled)
        if self.manager is not None:
            self.manager.set_sfx_enabled(bool(enabled))
        self._persist()

    def _on_muted(self, muted: bool) -> None:
        if self._syncing:
            return
        self.settings.muted = bool(muted)
        if self.manager is not None:
            self.manager.set_muted(bool(muted))
        self._persist()

    def _on_test_sound(self) -> None:
        if self.manager is not None:
            self.manager.play("ui_click", volume=0.8)

    def _set_volume(self, name: str, value: float) -> None:
        setattr(self.settings, name, max(0.0, min(1.0, float(value))))
        if self.manager is not None:
            self.manager.set_volumes(**{name: float(value)})
        self._persist()

    def _persist(self) -> None:
        try:
            self.settings.save()
        except Exception:
            pass

    # -- synchronisation ------------------------------------------------------

    def set_audio(self, audio: Any, settings: Any = None) -> None:
        """Attach or replace the audio manager after construction."""
        self.audio = audio
        self.manager = audio
        if settings is not None:
            self.settings = settings
        elif getattr(audio, "settings", None) is not None:
            self.settings = audio.settings
        self.sync_controls()

    def sync_controls(self) -> None:
        """Copy the current settings into every widget without feedback."""
        self._syncing = True
        try:
            settings = self.settings
            self.master_slider.setValue(_percent(settings.master))
            self.music_slider.setValue(_percent(settings.music))
            self.sfx_slider.setValue(_percent(settings.sfx))
            self.master_value.setText(f"{_percent(settings.master)}%")
            self.music_value.setText(f"{_percent(settings.music)}%")
            self.sfx_value.setText(f"{_percent(settings.sfx)}%")
            self.music_checkbox.setChecked(bool(settings.music_enabled))
            self.sfx_checkbox.setChecked(bool(settings.sfx_enabled))
            self.mute_checkbox.setChecked(bool(settings.muted))
        finally:
            self._syncing = False

    def show_panel(self) -> None:
        """Refresh the controls from settings before showing."""
        self.sync_controls()
        super().show_panel()
