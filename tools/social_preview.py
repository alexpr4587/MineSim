"""Compose the 1280x640 social preview from a press screenshot.

The image is used as the GitHub social preview and as the og:image for
the itch.io page. Run it after regenerating ``docs/press/hero.png``:

    uv run python tools/social_preview.py
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
)

from minesim.ui.theme import ACCENT, BACKGROUND, TEXT, TEXT_DIM  # noqa: E402

__all__ = ["SIZE", "build_social_preview", "main"]

SIZE = (1280, 640)
TITLE = "MineSim"
SUBTITLE = "Automate a mining operation by writing real Python."
FOOTER = "Python 3.12  ·  MIT  ·  Windows & Linux"


def _cover(image: QImage, width: int, height: int) -> QImage:
    """Scale and center-crop ``image`` to exactly ``width`` x ``height``."""
    scaled = image.scaled(
        width,
        height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, (scaled.height() - height) // 2)
    return scaled.copy(x, y, width, height)


def build_social_preview(source: Path, output: Path) -> Path:
    """Read ``source``, draw the title overlay and save ``output``."""
    app = QGuiApplication.instance() or QGuiApplication([])
    image = QImage(str(source))
    if image.isNull():
        raise FileNotFoundError(f"cannot read screenshot: {source}")
    canvas = _cover(image, *SIZE)
    painter = QPainter(canvas)
    try:
        gradient = QLinearGradient(0, 0, SIZE[0], 0)
        gradient.setColorAt(0.0, QColor(18, 18, 28, 235))
        gradient.setColorAt(0.55, QColor(18, 18, 28, 170))
        gradient.setColorAt(1.0, QColor(18, 18, 28, 20))
        painter.fillRect(QRect(0, 0, *SIZE), gradient)

        painter.setPen(QColor(ACCENT))
        painter.setFont(QFont("DejaVu Sans Mono", 22, QFont.Weight.Bold))
        painter.drawText(
            QRect(72, 92, 760, 40),
            int(Qt.AlignmentFlag.AlignLeft),
            "OPEN SOURCE · PYTHON",
        )

        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("DejaVu Sans Mono", 88, QFont.Weight.Bold))
        painter.drawText(QRect(68, 142, 800, 110), int(Qt.AlignmentFlag.AlignLeft), TITLE)

        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("DejaVu Sans Mono", 30))
        painter.drawText(
            QRect(72, 270, 780, 110),
            int(Qt.AlignmentFlag.AlignLeft) | int(Qt.TextFlag.TextWordWrap),
            SUBTITLE,
        )

        painter.setPen(QColor(TEXT_DIM))
        painter.setFont(QFont("DejaVu Sans Mono", 20))
        painter.drawText(QRect(72, 520, 800, 40), int(Qt.AlignmentFlag.AlignLeft), FOOTER)

        painter.setPen(QColor(ACCENT))
        painter.setBrush(QColor(BACKGROUND))
        painter.drawRoundedRect(QRect(72, 430, 300, 58), 10, 10)
        painter.setFont(QFont("DejaVu Sans Mono", 22, QFont.Weight.Bold))
        painter.drawText(QRect(72, 430, 300, 58), int(Qt.AlignmentFlag.AlignCenter), "WRITE CODE")
    finally:
        painter.end()
    del app
    output.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(output)):
        raise OSError(f"cannot save image: {output}")
    return output


def main() -> int:
    """Parse paths and build the social preview."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(prog="social_preview.py")
    parser.add_argument("--source", type=Path, default=root / "docs" / "press" / "hero.png")
    parser.add_argument(
        "--output", type=Path, default=root / "docs" / "press" / "social-preview.png"
    )
    args = parser.parse_args()
    print(build_social_preview(args.source, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
