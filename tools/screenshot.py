"""Capture a smoke-test screenshot of the DigScript UI."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


def main() -> None:
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("DigScript")
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel("DigScript (pre-alpha)"))
    window.resize(400, 200)
    window.show()
    app.processEvents()
    pixmap = window.grab()
    out = Path("artifacts") / "smoke.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(out))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
