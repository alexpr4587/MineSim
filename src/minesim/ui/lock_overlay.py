"""Lock overlays for UI features that an achievement has not unlocked yet."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from minesim.ui.theme import BACKGROUND, LOCKED_MARK, TEXT, TEXT_DIM

__all__ = ["LockOverlay"]


class LockOverlay(QWidget):
    """A centred message that covers a panel while its feature is locked."""

    def __init__(
        self,
        parent: QWidget,
        feature_id: str = "",
        title: str = "",
    ) -> None:
        super().__init__(parent)
        self.feature_id = str(feature_id)
        self.unlock_title = str(title)
        self.locked = False
        self.setObjectName("lock_overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QWidget#lock_overlay {{ background-color: {BACKGROUND}; "
            f"border: 1px solid {LOCKED_MARK}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.addStretch(1)
        self.mark_label = QLabel(LOCKED_MARK, self)
        self.mark_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mark_label.setStyleSheet(f"color: {LOCKED_MARK}; font-size: 28px;")
        layout.addWidget(self.mark_label)
        self.message_label = QLabel("Locked", self)
        self.message_label.setObjectName("lock_overlay_message")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        layout.addWidget(self.message_label)
        self.hint_label = QLabel(
            "This feature unlocks as you progress through the achievements.",
            self,
        )
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet(f"color: {TEXT_DIM};")
        layout.addWidget(self.hint_label)
        layout.addStretch(1)
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())
        self.hide()

    def _message(self) -> str:
        if self.locked and self.unlock_title:
            return f"Unlocks with: {self.unlock_title}"
        return "Locked"

    def set_locked(self, locked: bool, title: str = "") -> None:
        """Show or hide the overlay and update the unlocking achievement title."""
        self.locked = bool(locked)
        self.unlock_title = str(title or "")
        self.message_label.setText(self._message())
        if self.locked:
            self.setGeometry(self.parentWidget().rect())
            self.show()
            self.raise_()
        else:
            self.hide()

    def eventFilter(self, watched: Any, event: QEvent) -> bool:  # noqa: N802
        if watched is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
            if self.locked:
                self.raise_()
        return super().eventFilter(watched, event)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        self.setGeometry(self.parentWidget().rect())
        super().showEvent(event)
