"""Floating panels: draggable, resizable child widgets over the world view."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QByteArray, QEvent, QPoint, QSettings, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from minesim.ui.theme import BACKGROUND, BUTTON_BORDER, TEXT

__all__ = ["ORGANIZATION_NAME", "APPLICATION_NAME", "FloatingPanel", "ensure_settings_names"]

ORGANIZATION_NAME = "MineSim"
APPLICATION_NAME = "MineSim"


def ensure_settings_names() -> QSettings:
    """Make sure the application reports MineSim organisation/app names."""
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            if not app.organizationName():
                app.setOrganizationName(ORGANIZATION_NAME)
            if not app.applicationName():
                app.setApplicationName(APPLICATION_NAME)
            if app.organizationName() != ORGANIZATION_NAME:
                app.setOrganizationName(ORGANIZATION_NAME)
            if app.applicationName() != APPLICATION_NAME:
                app.setApplicationName(APPLICATION_NAME)
    except Exception:
        pass
    return QSettings(ORGANIZATION_NAME, APPLICATION_NAME)


class _TitleBar(QWidget):
    """Drag handle for a :class:`FloatingPanel`."""

    def __init__(
        self, panel: FloatingPanel, title_label: QLabel, close_button: QPushButton
    ) -> None:
        super().__init__(panel)
        self.panel = panel
        self.title_label = title_label
        self.close_button = close_button
        self._drag_offset: QPoint | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(close_button)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.panel.raise_()
            self.panel.activateWindow()
            parent = self.panel.parentWidget()
            if parent is not None:
                global_pos = event.globalPosition().toPoint()
                parent_pos = parent.mapFromGlobal(global_pos)
                self._drag_offset = parent_pos - self.panel.pos()
            else:
                self._drag_offset = event.globalPosition().toPoint() - self.panel.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            parent = self.panel.parentWidget()
            if parent is not None:
                parent_pos = parent.mapFromGlobal(event.globalPosition().toPoint())
                self.panel.move(parent_pos - self._drag_offset)
            else:
                self.panel.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        self._drag_offset = None
        self.panel.save_geometry()
        super().mouseReleaseEvent(event)


class FloatingPanel(QFrame):
    """A child-widget panel overlaid on the main window (not an OS window).

    It has a title bar to drag it, a close button, a
    :class:`QSizeGrip` to resize, stays inside its parent, raises on
    click and remembers its geometry with :class:`QSettings`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None)
        if title is None:
            title = kwargs.pop("name", None)
        if title is None:
            title = kwargs.pop("panel_title", None)
        parent = kwargs.pop("parent", None)
        content = (
            kwargs.pop("content", None)
            or kwargs.pop("content_widget", None)
            or kwargs.pop("widget", None)
            or kwargs.pop("child", None)
            or kwargs.pop("body", None)
        )
        default_size = kwargs.pop("default_size", None) or kwargs.pop("size", None)
        default_pos = (
            kwargs.pop("default_pos", None)
            or kwargs.pop("pos", None)
            or kwargs.pop("position", None)
        )
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, str):
                if title is None:
                    title = arg
            elif isinstance(arg, QWidget):
                if parent is None:
                    parent = arg
                elif content is None:
                    content = arg
            elif isinstance(arg, (tuple, list)):
                if default_size is None and len(arg) == 2:
                    default_size = tuple(arg)  # type: ignore[assignment]
        if kwargs:
            # Tolerate a few extra Qt-ish kwargs without failing.
            kwargs.pop("window_type", None)
            kwargs.pop("flags", None)
            kwargs.pop("f", None)
            kwargs.pop("w", None)
            if kwargs:
                raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        ensure_settings_names()
        super().__init__(parent)
        self._title: str = str(title) if title is not None else "Panel"
        if not self.objectName():
            super().setObjectName(self._title)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameStyle(QFrame.Shadow.Raised)
        self.setStyleSheet(
            "FloatingPanel { background-color: "
            + BACKGROUND
            + "; border: 1px solid "
            + BUTTON_BORDER
            + "; }"
        )
        self._restored_geometry: bool = False
        self._closing: bool = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.main_layout = main_layout

        self.title_label = QLabel(self._title, self)
        self.title_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.close_button = QPushButton("×", self)
        self.close_button.setObjectName("close_button")
        self.close_button.setToolTip("Close")
        self.close_button.clicked.connect(self.close_panel)
        self.title_bar = _TitleBar(self, self.title_label, self.close_button)
        self.title_bar.setObjectName("title_bar")
        self.title_bar.setStyleSheet(
            f"background-color: {BACKGROUND}; border-bottom: 1px solid {BUTTON_BORDER};"
        )
        main_layout.addWidget(self.title_bar)

        self.content_widget = QWidget(self)
        self.content_widget.setObjectName("content")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content = self.content_widget
        self.body = self.content_widget
        self.body_layout = self.content_layout
        main_layout.addWidget(self.content_widget, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addStretch(1)
        self.grip = QSizeGrip(self)
        self.size_grip = self.grip
        self.resize_grip = self.grip
        self.grip.setObjectName("size_grip")
        bottom.addWidget(self.grip)
        bottom_widget = QWidget(self)
        bottom_widget.setLayout(bottom)
        bottom_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        main_layout.addWidget(bottom_widget)

        if content is not None:
            self.add_widget(content)

        # Default size/position (only when no saved geometry).
        width, height = (520, 420)
        if default_size is not None:
            try:
                width, height = int(default_size[0]), int(default_size[1])
            except Exception:
                pass
        self.resize(width, height)
        if default_pos is not None:
            try:
                self.move(int(default_pos[0]), int(default_pos[1]))
            except Exception:
                pass
        else:
            self.move(40, 40)
        self.load_geometry()
        if not self._restored_geometry:
            self._clamp_to_parent()

        if parent is not None:
            try:
                parent.installEventFilter(self)
            except Exception:
                pass
        self.installEventFilter(self)
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)
        except Exception:
            pass

    # -- settings ------------------------------------------------------------

    def _settings_keys(self) -> list[str]:
        keys: list[str] = []
        try:
            name = super().objectName()
        except Exception:
            name = ""
        candidates = [name, self._title]
        for candidate in candidates:
            if candidate:
                key = f"floatingPanel/{candidate}/geometry"
                if key not in keys:
                    keys.append(key)
        return keys

    def settings_key(self) -> str:
        """Return the primary QSettings key for this panel's geometry."""
        keys = self._settings_keys()
        return keys[0] if keys else "floatingPanel/geometry"

    def save_geometry(self) -> None:
        """Persist geometry (and position/size) to QSettings."""
        try:
            settings = ensure_settings_names()
            data = self.saveGeometry()
            for key in self._settings_keys():
                settings.setValue(key, data)
                settings.setValue(
                    key.replace("/geometry", "/pos"), f"{self.pos().x()},{self.pos().y()}"
                )
                settings.setValue(
                    key.replace("/geometry", "/size"), f"{self.width()}x{self.height()}"
                )
            settings.sync()
        except Exception:
            pass

    def saveGeometryToSettings(self) -> None:  # noqa: N802
        """Alias for :meth:`save_geometry`."""
        self.save_geometry()

    def load_geometry(self) -> bool:
        """Restore geometry from QSettings if present. Returns True if restored."""
        try:
            settings = ensure_settings_names()
            for key in self._settings_keys():
                value = settings.value(key)
                if value is None:
                    continue
                data: QByteArray | None = None
                if isinstance(value, QByteArray):
                    data = value
                elif isinstance(value, (bytes, bytearray)):
                    data = QByteArray(bytes(value))  # type: ignore[arg-type]
                elif isinstance(value, str):
                    # QByteArray stored as string in some test doubles.
                    try:
                        data = QByteArray(value.encode("utf-8"))
                    except Exception:
                        data = None
                if data is not None and self.restoreGeometry(data):
                    self._restored_geometry = True
                    self._clamp_to_parent()
                    return True
                # Fallback to pos/size strings.
                pos = settings.value(key.replace("/geometry", "/pos"))
                size = settings.value(key.replace("/geometry", "/size"))
                if pos and size:
                    try:
                        px, py = str(pos).split(",")
                        sw, sh = str(size).split("x")
                        self.move(int(px), int(py))
                        self.resize(int(sw), int(sh))
                        self._restored_geometry = True
                        self._clamp_to_parent()
                        return True
                    except Exception:
                        pass
        except Exception:
            pass
        return False

    def restore_geometry_from_settings(self) -> bool:
        """Alias for :meth:`load_geometry`."""
        return self.load_geometry()

    def loadGeometryFromSettings(self) -> bool:  # noqa: N802
        """Alias for :meth:`load_geometry`."""
        return self.load_geometry()

    # -- content -------------------------------------------------------------

    def add_widget(self, widget: QWidget) -> None:
        """Add ``widget`` to the panel's content area."""
        self.content_layout.addWidget(widget)

    def addWidget(self, widget: QWidget) -> None:  # noqa: N802
        """Alias for :meth:`add_widget`."""
        self.add_widget(widget)

    def set_content(self, widget: QWidget) -> None:
        """Replace the panel content with ``widget``."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.setParent(None)
        self.content_layout.addWidget(widget)

    def set_content_widget(self, widget: QWidget) -> None:
        """Alias for :meth:`set_content`."""
        self.set_content(widget)

    # -- title / visibility ----------------------------------------------------

    def set_title(self, title: str) -> None:
        """Set the panel title."""
        self._title = str(title)
        self.title_label.setText(self._title)
        self.setWindowTitle(self._title)

    def title(self) -> str:
        """Return the panel title."""
        return self._title

    def get_title(self) -> str:
        """Alias for :meth:`title`."""
        return self._title

    def toggle(self) -> None:
        """Show the panel if hidden, hide it if visible."""
        if self.isVisible():
            self.hide_panel()
        else:
            self.show_panel()

    def toggle_visible(self) -> None:
        """Alias for :meth:`toggle`."""
        self.toggle()

    def toggle_panel(self) -> None:
        """Alias for :meth:`toggle`."""
        self.toggle()

    def show_panel(self) -> None:
        """Show the panel, raised and inside its parent."""
        self._clamp_to_parent()
        self.show()
        self.raise_()

    def hide_panel(self) -> None:
        """Hide the panel, saving geometry."""
        self.save_geometry()
        self.hide()

    def close_panel(self) -> None:
        """Hide the panel (close button), saving geometry."""
        self.save_geometry()
        self.hide()
        self._closing = True

    def closePanel(self) -> None:  # noqa: N802
        """Alias for :meth:`close_panel`."""
        self.close_panel()

    def is_open(self) -> bool:
        """Return True when the panel is visible."""
        return self.isVisible()

    @property
    def is_closed(self) -> bool:
        """Return True after the close button was used."""
        return self._closing

    # -- staying inside parent / raising ---------------------------------------

    def _clamp_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        try:
            pw, ph = parent.width(), parent.height()
        except Exception:
            return
        if pw <= 0 or ph <= 0:
            return
        x, y = self.pos().x(), self.pos().y()
        w, h = self.width(), self.height()
        new_x = min(max(0, x), max(0, pw - w)) if w <= pw else 0
        new_y = min(max(0, y), max(0, ph - h)) if h <= ph else 0
        if (new_x, new_y) != (x, y):
            # Avoid recursion via moveEvent guard.
            self._clamping = True
            try:
                super().move(new_x, new_y)
            finally:
                self._clamping = False

    def clamp_to_parent(self) -> None:
        """Alias for :meth:`_clamp_to_parent`."""
        self._clamp_to_parent()

    def move(self, *args: Any) -> None:  # noqa: N802
        """Move the panel, always staying inside its parent."""
        super().move(*args)
        if not getattr(self, "_clamping", False):
            self._clamp_to_parent()

    def resize(self, *args: Any) -> None:  # noqa: N802
        """Resize the panel, always staying inside its parent."""
        super().resize(*args)
        if not getattr(self, "_clamping", False):
            self._clamp_to_parent()

    def show(self) -> None:  # noqa: N802
        """Show the panel, clamped inside its parent."""
        self._clamp_to_parent()
        super().show()
        self._clamp_to_parent()

    def moveEvent(self, event: Any) -> None:  # noqa: N802
        super().moveEvent(event)
        if not getattr(self, "_clamping", False):
            self._clamp_to_parent()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not getattr(self, "_clamping", False):
            self._clamp_to_parent()

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        self.raise_()
        try:
            self.activateWindow()
        except Exception:
            pass
        super().mousePressEvent(event)

    def eventFilter(self, obj: Any, event: Any) -> bool:  # noqa: N802
        try:
            if event.type() == QEvent.Type.MouseButtonPress:
                title_bar = getattr(self, "title_bar", None)
                if obj is title_bar or obj is self or self.isAncestorOf(obj):
                    try:
                        self.raise_()
                    except Exception:
                        pass
            if event.type() == QEvent.Type.Resize and obj is self.parentWidget():
                self._clamp_to_parent()
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        self.save_geometry()
        self.hide()
        self._closing = True
        event.accept()
