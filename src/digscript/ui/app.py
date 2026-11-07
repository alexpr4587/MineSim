"""Application bootstrap and placeholder window."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


def run() -> int:
    """Start the UI and return the exit code."""
    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle("DigScript")
    window.setCentralWidget(QLabel("DigScript"))
    window.resize(800, 600)
    window.show()
    return app.exec()
