"""Main application window (placeholder)."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MainWindow(QWidget):
    """Top-level window for the DigScript application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DigScript")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("DigScript (pre-alpha)"))
