"""Save a placeholder window screenshot to artifacts/smoke.png."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow  # noqa: E402


def main() -> None:
    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle("DigScript")
    window.setCentralWidget(QLabel("DigScript"))
    window.resize(800, 600)
    window.show()
    app.processEvents()
    out = Path(__file__).resolve().parents[1] / "artifacts" / "smoke.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(out))
    window.close()


if __name__ == "__main__":
    main()
