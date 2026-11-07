"""Application entry point."""

from __future__ import annotations

import argparse
import multiprocessing


def main() -> None:
    """Start DigScript."""
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(prog="digscript")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return
    from digscript.ui.app import run

    run()


if __name__ == "__main__":
    main()
