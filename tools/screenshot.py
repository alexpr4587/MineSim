"""Screenshot the real main window offscreen.

Builds the real :class:`~minesim.ui.main_window.MainWindow`, runs N
ticks with a hard-coded command sequence submitted straight to the
engine, shows the editor panel over the world (with the console below
it), grabs the window and saves a PNG. By default the lit terrain
renderer is used and the image is saved to ``artifacts/ui_lit.png``;
``--flat`` disables lighting and saves ``artifacts/ui_flat.png``.

Flags: ``--ticks`` (default 300), ``--size`` (``WIDTHxHEIGHT``,
default 1024x768), ``--flat``, ``--skin`` (select a miner skin, saved as
``artifacts/ui_skin_<id>.png``), ``--moving`` (leave a Move command
active so the walk animation is captured), ``--achievements`` (keep the
achievements panel visible), ``--wardrobe`` (show the wardrobe panel,
saved as ``artifacts/ui_wardrobe.png``) and ``--output``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim.core.commands import Mine, Move, Sell  # noqa: E402
from minesim.core.direction import Direction  # noqa: E402
from minesim.core.game import Game  # noqa: E402
from minesim.ui.main_window import MainWindow  # noqa: E402
from minesim.ui.theme import apply_theme  # noqa: E402

__all__ = ["COMMAND_SEQUENCE", "build_window", "main", "parse_size"]

COMMAND_SEQUENCE = [
    Move(Direction.EAST),
    Move(Direction.EAST),
    Mine(),
    Mine(),
    Mine(),
    Mine(),
    Move(Direction.WEST),
    Move(Direction.WEST),
    Sell(),
    Move(Direction.SOUTH),
    Move(Direction.SOUTH),
    Mine(),
    Mine(),
    Mine(),
    Mine(),
    Move(Direction.NORTH),
    Move(Direction.NORTH),
    Move(Direction.EAST),
    Mine(),
    Mine(),
    Mine(),
]


def parse_size(value: str) -> tuple[int, int]:
    """Parse a ``WIDTHxHEIGHT`` (or ``WIDTH,HEIGHT``) size string."""
    text = str(value).strip().lower().replace(",", "x")
    parts = text.split("x")
    if len(parts) == 1:
        size = int(parts[0])
        return (size, size)
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"invalid size: {value!r} (expected WIDTHxHEIGHT)")
    return (int(parts[0]), int(parts[1]))


def build_window(
    ticks: int = 300,
    size: tuple[int, int] = (1024, 768),
    flat: bool = False,
    skin: str | None = None,
    moving: bool = False,
) -> MainWindow:
    """Build the real main window and run ``ticks`` engine ticks."""
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    game = Game.new()
    if skin:
        game.select_skin(skin)
    window = MainWindow(game)
    window.world_view.set_terrain_lighting(not flat, persist=False)
    window.resize(size[0], size[1])
    window.show()
    for command in COMMAND_SEQUENCE:
        game.submit(command)
    for _ in range(int(ticks)):
        game.engine.step()
    if moving:
        game.submit(Move(Direction.EAST))
        game.engine.step()
    window.game_loop.stop()
    window.world_view.snap_visual_to_miner()
    window.world_view.center_on_miner()
    window.hud.refresh()
    editor_panel = getattr(window, "editor_panel", None)
    if editor_panel is not None:
        from minesim.ui.editor_panel import STARTER_SCRIPT

        editor = getattr(editor_panel, "editor", None) or getattr(editor_panel, "code_editor", None)
        if editor is not None and not editor.toPlainText().strip():
            editor.setPlainText(STARTER_SCRIPT)
        try:
            editor_panel.show_panel()
        except Exception:
            editor_panel.show()
        console = getattr(window, "console_panel", None)
        if console is not None:
            console.append_line("hello from MineSim", "out")
            console.append_line("miner ready", "info")
        editor_panel.raise_()
        # Run the starter script so the first achievement (hello_miner) completes,
        # then open the achievements screen (key L) for the screenshot.
        try:
            editor_panel.run()
            for _ in range(4000):
                window.game_loop.advance(100)
                app.processEvents()
                if str(window.host.state) != "RUNNING":
                    break
        except Exception:
            pass
        try:
            window.show_achievements()
        except Exception:
            try:
                window.achievements_panel.show_panel()
            except Exception:
                pass
    app.processEvents()
    return window


def main() -> int:
    """Parse flags, screenshot the window and save the PNG."""
    parser = argparse.ArgumentParser(prog="screenshot.py")
    parser.add_argument("--ticks", type=int, default=300)
    parser.add_argument("--size", type=parse_size, default=(1024, 768))
    parser.add_argument(
        "--flat",
        action="store_true",
        help="disable terrain lighting and save artifacts/ui_flat.png",
    )
    parser.add_argument("--skin", default=None, help="select a miner skin by id")
    parser.add_argument(
        "--moving",
        action="store_true",
        help="leave a Move command active so the walk animation is visible",
    )
    parser.add_argument(
        "--achievements",
        action="store_true",
        help="keep the achievements panel visible and save artifacts/ui_achievements.png",
    )
    parser.add_argument(
        "--wardrobe",
        action="store_true",
        help="show the wardrobe panel and save artifacts/ui_wardrobe.png",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    window = build_window(
        ticks=args.ticks,
        size=args.size,
        flat=args.flat,
        skin=args.skin,
        moving=args.moving,
    )
    for panel_name in (
        "achievements_panel",
        "upgrades_panel",
        "wardrobe_panel",
        "editor_panel",
        "api_panel",
    ):
        if args.achievements and panel_name == "achievements_panel":
            continue
        if args.wardrobe and panel_name == "wardrobe_panel":
            continue
        panel = getattr(window, panel_name, None)
        if panel is not None:
            try:
                panel.hide_panel()
            except Exception:
                panel.hide()
    if args.wardrobe:
        try:
            window.show_wardrobe()
        except Exception:
            window.wardrobe_panel.show_panel()
    toast_manager = getattr(window, "toast_manager", None)
    current_toast = getattr(toast_manager, "_current", None)
    if current_toast is not None:
        current_toast.hide()
    window.world_view.setFocus()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    default_name = "ui_flat.png" if args.flat else "ui_lit.png"
    if args.skin:
        default_name = f"ui_skin_{args.skin}.png"
    if args.achievements:
        default_name = "ui_achievements.png"
    if args.wardrobe:
        default_name = "ui_wardrobe.png"
    out = args.output or (Path(__file__).resolve().parents[1] / "artifacts" / default_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(out))
    window.close()
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
