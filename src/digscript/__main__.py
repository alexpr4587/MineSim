"""Entry point for the DigScript application."""

import multiprocessing
import sys


def main() -> None:
    """Run the DigScript application."""
    multiprocessing.freeze_support()
    if "--selftest" in sys.argv:
        # Stub for now.
        return
    # Start the UI (placeholder until UI is implemented).
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    from digscript.ui.main_window import MainWindow  # type: ignore[attr-defined]

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
