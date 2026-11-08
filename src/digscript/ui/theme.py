"""Dark UI theme: named colors, monospace font and one stylesheet.

All UI colors and fonts live in this module (per AGENTS.md); other
UI modules import from here instead of hard-coding values.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ACCENT",
    "ACCENT_PRESSED",
    "BACKGROUND",
    "BASE_BORDER",
    "BASE_LABEL",
    "BUTTON_BACKGROUND",
    "BUTTON_BORDER",
    "BUTTON_HOVER",
    "BUTTON_PRESSED",
    "BUTTON_TEXT",
    "COLORS",
    "DISABLED_TEXT",
    "FONT_FAMILY",
    "FONT_SIZE",
    "GRID",
    "HUD_BACKGROUND",
    "LOCKED_MARK",
    "MINER_BODY",
    "MINER_DETAIL",
    "MONOSPACE_FONT",
    "RECENTER_BACKGROUND",
    "RECENTER_TEXT",
    "STYLESHEET",
    "TEXT",
    "TEXT_DIM",
    "apply_theme",
    "dark_palette",
    "get_stylesheet",
]

COLORS: dict[str, str] = {
    "background": "#1e1e2e",
    "surface": "#2a2a3d",
    "hud_background": "#252535",
    "text": "#e6e6e6",
    "text_dim": "#9a9ab0",
    "disabled_text": "#6a6a7d",
    "accent": "#f2a541",
    "accent_pressed": "#d98a2b",
    "button_background": "#3a3a50",
    "button_border": "#555570",
    "button_hover": "#4a4a64",
    "button_pressed": "#2f2f42",
    "button_text": "#e6e6e6",
    "grid": "#3d3d52",
    "miner_body": "#ffd166",
    "miner_detail": "#1e1e2e",
    "base_border": "#f2a541",
    "base_label": "#f2a541",
    "locked_mark": "#101018",
    "recenter_background": "#3a3a50",
    "recenter_text": "#e6e6e6",
}

BACKGROUND = COLORS["background"]
HUD_BACKGROUND = COLORS["hud_background"]
TEXT = COLORS["text"]
TEXT_DIM = COLORS["text_dim"]
DISABLED_TEXT = COLORS["disabled_text"]
ACCENT = COLORS["accent"]
ACCENT_PRESSED = COLORS["accent_pressed"]
BUTTON_BACKGROUND = COLORS["button_background"]
BUTTON_BORDER = COLORS["button_border"]
BUTTON_HOVER = COLORS["button_hover"]
BUTTON_PRESSED = COLORS["button_pressed"]
BUTTON_TEXT = COLORS["button_text"]
GRID = COLORS["grid"]
MINER_BODY = COLORS["miner_body"]
MINER_DETAIL = COLORS["miner_detail"]
BASE_BORDER = COLORS["base_border"]
BASE_LABEL = COLORS["base_label"]
LOCKED_MARK = COLORS["locked_mark"]
RECENTER_BACKGROUND = COLORS["recenter_background"]
RECENTER_TEXT = COLORS["recenter_text"]

MONOSPACE_FONT = "Consolas, 'DejaVu Sans Mono', 'Liberation Mono', monospace"
FONT_FAMILY = MONOSPACE_FONT
FONT_SIZE = 11

STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {TEXT};
    font-family: {MONOSPACE_FONT};
    font-size: {FONT_SIZE}px;
}}
QLabel {{
    background-color: transparent;
    color: {TEXT};
    font-family: {MONOSPACE_FONT};
}}
QPushButton {{
    background-color: {BUTTON_BACKGROUND};
    color: {BUTTON_TEXT};
    border: 1px solid {BUTTON_BORDER};
    border-radius: 4px;
    padding: 4px 10px;
    font-family: {MONOSPACE_FONT};
}}
QPushButton:hover {{
    background-color: {BUTTON_HOVER};
}}
QPushButton:pressed {{
    background-color: {BUTTON_PRESSED};
}}
QPushButton:checked {{
    background-color: {ACCENT};
    color: {MINER_DETAIL};
}}
QPushButton:disabled {{
    color: {DISABLED_TEXT};
}}
"""


def get_stylesheet() -> str:
    """Return the global stylesheet."""
    return STYLESHEET


def dark_palette() -> Any:
    """Return a dark :class:`QPalette` for the application."""
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(BACKGROUND))
    palette.setColor(QPalette.WindowText, QColor(TEXT))
    palette.setColor(QPalette.Base, QColor(HUD_BACKGROUND))
    palette.setColor(QPalette.AlternateBase, QColor(BUTTON_BACKGROUND))
    palette.setColor(QPalette.Text, QColor(TEXT))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(DISABLED_TEXT))
    palette.setColor(QPalette.Button, QColor(BUTTON_BACKGROUND))
    palette.setColor(QPalette.ButtonText, QColor(BUTTON_TEXT))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.HighlightedText, QColor(MINER_DETAIL))
    return palette


def apply_theme(app: Any) -> None:
    """Apply the dark palette, font and stylesheet to ``app``."""
    from PySide6.QtGui import QFont

    app.setPalette(dark_palette())
    app.setStyleSheet(STYLESHEET)
    font = QFont()
    font.setFamily(FONT_FAMILY)
    font.setPointSize(FONT_SIZE)
    app.setFont(font)
