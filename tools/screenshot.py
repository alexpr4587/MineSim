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
saved as ``artifacts/ui_wardrobe.png``), ``--panel base|market|refinery|contracts``
(a scripted economy session, saved as ``artifacts/ui_<panel>.png``),
``--locked`` (lock every feature and show the market lock overlay,
saved as ``artifacts/ui_locked.png``), ``--editor-tabs`` (12 scripts,
three open tabs and the Open… list, saved as
``artifacts/ui_editor_tabs.png``), ``--layer N`` (put the main miner on
layer N, run a short mining session and save ``artifacts/ui_layer_N.png``),
``--dock`` (queue miners at the shared dock and save
``artifacts/ui_dock.png``), ``--climate`` (a hot layer, a low battery and the
energy/climate HUD with the miners panel, saved as ``artifacts/ui_climate.png``),
``--options`` (the audio options panel, saved as ``artifacts/ui_options.png``),
``--preset hero|editor|layers|market|miners|base`` (deterministic press scenes
saved at 1920x1080 and 1080x1920 into ``docs/press/``) and ``--output``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "1")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim.core.commands import Mine, Move, Sell, Unload  # noqa: E402
from minesim.core.direction import Direction  # noqa: E402
from minesim.core.game import Game  # noqa: E402
from minesim.ui.main_window import MainWindow  # noqa: E402
from minesim.ui.theme import apply_theme  # noqa: E402

__all__ = [
    "COMMAND_SEQUENCE",
    "MINER_SCRIPT",
    "PRESS_PRESETS",
    "PRESS_SIZES",
    "build_press_window",
    "build_window",
    "main",
    "parse_size",
    "prepare_climate",
    "prepare_economy",
    "render_preset",
    "unlock_everything",
]

MINER_SCRIPT = (
    "# Trivial worker: report once, then patrol the base until stopped.\n"
    "print('miner', miner_id(), 'online')\n"
    "while True:\n"
    "    move(East)\n"
    "    move(West)\n"
)

EDITOR_SCRIPTS = (
    "main.py",
    "sweep.py",
    "scan.py",
    "spiral.py",
    "market.py",
    "refine.py",
    "contracts.py",
    "fleet.py",
    "events.py",
    "forecast.py",
    "helpers.py",
    "worker.py",
)

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


def unlock_everything(game: Game) -> Game:
    """Unlock every feature, function and recipe for a documentation screenshot."""
    state = game.progression_state
    for feature in game.content.features.values():
        state.unlocked_features.add(feature.id)
    for function in game.content.functions.values():
        state.unlocked_functions.add(function.name)
    for module in game.content.modules.values():
        state.unlocked_modules.add(module.name)
    for recipe in game.content.recipes.values():
        state.unlocked_recipes.add(recipe.id)
    for ore in game.content.ores.values():
        state.unlock_ore(ore.id)
    for skin in game.content.skins.values():
        state.unlock_skin(skin.id)
    for upgrade in game.content.upgrades.values():
        state.unlock_upgrade(upgrade.id)
    return game


def prepare_economy(game: Game, ticks: int = 3000) -> Game:
    """Fill the warehouse, run the market and start a refinery job.

    Used by the ``--panel`` screenshots so the base and market panels show
    real stock, live prices, a running job and generated contracts.
    """
    game.engine.warehouse.capacity = max(200, int(game.engine.warehouse.capacity))
    for _ in range(max(0, int(ticks))):
        game.step()
    warehouse = game.engine.warehouse
    for item, count in (
        ("stone", 30),
        ("coal", 20),
        ("copper", 20),
        ("iron", 10),
        ("silver", 6),
        ("gold", 3),
        ("ruby", 1),
        ("copper_bar", 4),
        ("iron_bar", 3),
    ):
        warehouse.add(item, count)
    game.miner.money = 2500
    game.miner.x, game.miner.y = 0, 0
    game.miner.inventory = {"copper": 4, "stone": 3, "coal": 2}
    game.start_refine("copper_bar", 5)
    for _ in range(120):
        game.step()
    return game


def _write_editor_scripts(scripts_dir: Path) -> None:
    """Create the twelve scripts used by the editor-tabs screenshot."""
    source = (
        "# {name}: sample automation for the editor-tabs screenshot.\n"
        "for _ in range(12):\n"
        "    if peek() is not None:\n"
        "        mine()\n"
        "    move(East)\n"
    )
    for name in EDITOR_SCRIPTS:
        try:
            (scripts_dir / name).write_text(source.format(name=name[:-3]), encoding="utf-8")
        except OSError:
            pass


def _setup_editor_tabs(
    window: MainWindow,
    scripts_dir: Path,
    app: QApplication,
    open_names: tuple[str, ...] = ("main.py", "sweep.py", "scan.py"),
    show_open: bool = True,
) -> None:
    """Open a few tabs and leave the searchable Open… list on screen."""
    panel = getattr(window, "editor_panel", None)
    if panel is None:
        return
    panel.close_all_tabs(save=False, remember=False)
    for name in open_names:
        path = Path(scripts_dir) / name
        if path.is_file():
            panel.add_file(path)
    if panel.tabs.count() > 1:
        panel.tabs.setCurrentIndex(1)
    try:
        panel.show_panel()
        panel.move(300, 40)
        panel.resize(700, 560)
    except Exception:
        panel.show()
    if show_open:
        try:
            panel.open_dialog()
            panel.open_files_popup.resize(380, 280)
            panel.open_files_popup.move(170, 150)
        except Exception:
            pass
    window.hud.refresh()
    app.processEvents()


def prepare_dock(game: Game, count: int = 5) -> Game:
    """Queue several miners at the shared dock for the dock screenshot."""
    game.progression_state.unlocked_features.add("warehouse")
    for miner_id in range(max(1, int(count))):
        if miner_id:
            miner = game.engine.spawn_miner()
        else:
            miner = game.miner
        miner.x, miner.y = 0, 0
        miner.inventory = {"stone": 1}
        game.submit(Unload(), miner_id=miner_id)
    return game


def prepare_layer(game: Game, layer: int) -> Game:
    """Put miner 0 on ``layer`` and run a short mining session there."""
    layer = max(0, int(layer))
    game.progression_state.unlock_upgrade("shaft")
    game.player_stats.upgrades["shaft"] = max(
        int(game.player_stats.upgrades.get("shaft", 0) or 0), layer
    )
    game.miner.layer = layer
    game.miner.x, game.miner.y = 0, 0
    session = (
        Move(Direction.EAST),
        Move(Direction.EAST),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Move(Direction.EAST),
        Mine(),
        Mine(),
        Mine(),
        Mine(),
        Move(Direction.SOUTH),
        Mine(),
        Mine(),
    )
    for command in session:
        game.submit(command)
        game.run_until_idle()
    return game


def prepare_climate(game: Game, count: int = 4) -> Game:
    """Show a hot layer, a low battery and the energy/climate HUD."""
    count = max(1, int(count))
    game.progression_state.unlock_upgrade("shaft")
    game.progression_state.unlock_upgrade("ventilation")
    game.player_stats.upgrades["shaft"] = max(
        int(game.player_stats.upgrades.get("shaft", 0) or 0), 2
    )
    game.player_stats.upgrades["miner_bay"] = max(
        int(game.player_stats.upgrades.get("miner_bay", 0) or 0), count - 1
    )
    game.player_stats.money = 10000
    for _ in range(count - 1):
        game.engine.spawn_miner()
    offsets = ((2, 0), (-2, 0), (0, 2), (0, -2), (3, 2), (-3, -2))
    for index, miner_id in enumerate(sorted(game.engine.miners)):
        miner = game.engine.miner_by_id(miner_id)
        if index == 0:
            miner.layer = 2
            miner.x, miner.y = 0, 0
            miner.energy = max(0, int(miner.battery_capacity) - 10)
            miner.temperature = 100.0
        else:
            dx, dy = offsets[(index - 1) % len(offsets)]
            miner.layer = 0
            miner.x, miner.y = dx, dy
    return game


def _find_rich_vein(game: Game) -> object | None:
    """Return the first active rich vein for the screenshot."""
    world_events = getattr(game.engine, "world_events", None)
    if world_events is None:
        return None
    for slot in range(400):
        event = world_events.event_for_slot(slot)
        if event is not None and event.kind == "rich_vein" and event.x is not None:
            return event
    return None


def _position_on_rich_vein(window: MainWindow, game: Game) -> None:
    """Put the miner in a rich vein and show its event ticker."""
    event = _find_rich_vein(game)
    if event is None:
        return
    game.engine.tick = int(event.starts) + 100
    game._engine.tick = int(event.starts) + 100
    game.miner.x, game.miner.y = int(event.x), int(event.y)
    window.world_view.snap_visual_to_miner()
    window.world_view.center_on_miner()
    window.hud.refresh()


def _setup_miners(window: MainWindow, game: Game, count: int, app: QApplication) -> None:
    """Spawn ``count`` extra miners, run the worker script and show the fleet UI."""
    scripts_dir = getattr(window, "scripts_dir", None)
    manager = getattr(window, "manager", None)
    worker_source = MINER_SCRIPT
    upgrades = getattr(game.player_stats, "upgrades", None)
    if upgrades is not None:
        upgrades["miner_bay"] = max(int(upgrades.get("miner_bay", 0)), int(count) + 1)
    game.player_stats.money = max(int(game.player_stats.money), 10000)
    if scripts_dir is not None:
        try:
            (Path(scripts_dir) / "worker.py").write_text(worker_source, encoding="utf-8")
        except OSError:
            pass
    for _ in range(max(0, int(count))):
        game.engine.spawn_miner()
    offsets = ((2, 0), (-2, 0), (0, 2), (0, -2), (3, 2), (-3, -2), (2, -3), (-2, 3))
    extra_ids = [miner_id for miner_id in sorted(game.engine.miners) if miner_id != 0]
    for index, miner_id in enumerate(extra_ids):
        dx, dy = offsets[index % len(offsets)]
        miner = game.engine.miner_by_id(miner_id)
        miner.x, miner.y = dx, dy
        if manager is not None:
            try:
                manager.start(miner_id, "worker.py", worker_source)
            except Exception:
                pass
    for _ in range(500):
        window.game_loop.advance(100)
        app.processEvents()
        if manager is None:
            break
        if all(manager.console(miner_id) for miner_id in extra_ids):
            break
        time.sleep(0.002)
    window.game_loop.stop()
    window.world_view.snap_visual_to_miner()
    editor_panel = getattr(window, "editor_panel", None)
    if editor_panel is not None:
        try:
            editor_panel.show_panel()
        except Exception:
            editor_panel.show()
        try:
            editor_panel.move(378, 44)
            editor_panel.resize(636, 320)
        except Exception:
            pass
    window.show_miners()
    try:
        window.miners_panel.move(8, 44)
        window.miners_panel.resize(350, 440)
    except Exception:
        pass
    selected = extra_ids[0] if extra_ids else 0
    try:
        window.miners_panel.select_miner(selected)
        window.console_panel._reload_console()
    except Exception:
        pass
    window.hud.refresh()
    window.world_view.update()
    app.processEvents()


PRESS_SEED = 12345
PRESS_SIZES: tuple[tuple[int, int], ...] = ((1920, 1080), (1080, 1920))
PRESS_PRESETS: tuple[str, ...] = ("hero", "editor", "layers", "market", "miners", "base")
PRESS_OUTPUT_NAMES: dict[str, tuple[str, str]] = {
    "hero": ("hero.png", "hero-vertical.png"),
    "editor": ("editor.png", "editor-vertical.png"),
    "layers": ("layers.png", "layers-vertical.png"),
    "market": ("market.png", "market-vertical.png"),
    "miners": ("miners.png", "miners-vertical.png"),
    "base": ("base.png", "base-vertical.png"),
}

PRESS_SCRIPTS: dict[str, str] = {
    "fleet.py": (
        "# Keep the whole fleet mining the nearest ore, then unload at the base.\n"
        "from minerlib import nearest, goto, mine_until, go_home\n\n"
        "for miner in miners():\n"
        '    assign(miner, "target", nearest_ore(miner))\n\n'
        "while True:\n"
        "    ore = nearest_ore(miner_id())\n"
        "    if ore is not None:\n"
        "        goto(ore.x, ore.y)\n"
        '        mine_until("full")\n'
        "    go_home()\n"
        "    unload()\n"
    ),
    "market.py": (
        "# Sell when the market is above its recent average.\n"
        'prices = price_history("gold", 30)\n'
        "average = sum(prices) / max(1, len(prices))\n"
        'if price("gold") > average * 1.08:\n'
        '    sell_stock("gold")\n'
        "else:\n"
        "    wait(10)\n"
    ),
    "sweep.py": (
        "# Sweep east, mine every ore, and return before the battery is empty.\n"
        "for step in range(24):\n"
        "    if peek() is not None:\n"
        "        mine()\n"
        '    if battery() < energy_cost("home") + 20:\n'
        "        go_home()\n"
        "        charge()\n"
        "        break\n"
        "    move(East)\n"
    ),
    "worker.py": (
        "# A small worker class that remembers what it has mined.\n"
        "class Worker:\n"
        "    def __init__(self, name):\n"
        "        self.name = name\n"
        "        self.mined = 0\n\n"
        "    def step(self):\n"
        "        if peek() is not None:\n"
        "            mine()\n"
        "            self.mined += 1\n"
        "        move(East)\n\n"
        'worker = Worker(f"miner-{miner_id()}")\n'
        "for _ in range(20):\n"
        "    worker.step()\n"
    ),
    "main.py": (
        "# Main script: read the shared fleet memory and keep mining.\n"
        'print("fleet online", miners())\n'
        "while True:\n"
        "    if peek() is not None:\n"
        "        mine()\n"
        "    move(East)\n"
    ),
}

PRESS_CONSOLE_LINES: tuple[tuple[str, str], ...] = (
    ("fleet online: 6 miners", "out"),
    ("miner 1 assigned to fleet.py", "info"),
    ("copper +3, iron +1", "out"),
    ("market: gold up 8.2%", "info"),
    ("dock: 2 jobs queued", "out"),
)


def _write_press_scripts(scripts_dir: Path) -> None:
    """Write the small, readable scripts shown in the press screenshots."""
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for name, source in PRESS_SCRIPTS.items():
        (scripts_dir / name).write_text(source, encoding="utf-8")


def _press_positions(
    game: Game,
    layer: int,
    count: int,
    center: tuple[int, int] = (0, 0),
) -> list[tuple[int, int]]:
    """Return deterministic ore tiles near ``center`` on ``layer``."""
    cx, cy = int(center[0]), int(center[1])
    positions: list[tuple[int, int]] = []
    taken: set[tuple[int, int]] = set()
    for radius in range(1, 18):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                x, y = cx + dx, cy + dy
                if (x, y) in taken:
                    continue
                try:
                    tile = game.world.tile_at(x, y, game.tick, layer=layer)
                except Exception:
                    continue
                if tile is None or tile.ore_id is None or getattr(tile, "depleted", False):
                    continue
                if any(max(abs(x - px), abs(y - py)) < 3 for px, py in positions):
                    continue
                taken.add((x, y))
                positions.append((x, y))
                if len(positions) >= count:
                    return positions
    fallback = ((2, 0), (-2, 0), (0, 2), (0, -2), (3, 2), (-3, -2), (2, -3), (-2, 3))
    for dx, dy in fallback:
        if len(positions) >= count:
            break
        x, y = cx + dx, cy + dy
        if (x, y) not in taken:
            taken.add((x, y))
            positions.append((x, y))
    return positions


def _prepare_press_game(preset: str) -> Game:
    """Build one deterministic, fully populated game state for a preset."""
    game = Game.new(seed=PRESS_SEED)
    unlock_everything(game)
    prepare_economy(game, ticks=3200)
    game.player_stats.money = 14850
    game.player_stats.upgrades["miner_bay"] = 8
    game.player_stats.upgrades["shaft"] = 2
    game.player_stats.upgrades["dock"] = 1
    game.player_stats.upgrades["ventilation"] = 1
    warehouse = game.engine.warehouse
    warehouse.capacity = max(500, int(warehouse.capacity))
    for item, amount in (
        ("stone", 64),
        ("coal", 48),
        ("copper", 36),
        ("iron", 28),
        ("silver", 14),
        ("gold", 8),
        ("ruby", 3),
        ("copper_bar", 12),
        ("iron_bar", 8),
    ):
        warehouse.add(item, amount)
    layer = 3 if preset == "layers" else 2 if preset in ("hero", "editor", "miners") else 0
    center = (8, 8) if preset in ("hero", "editor", "miners", "layers") else (0, 0)
    positions = _press_positions(game, layer, 6, center)
    for _ in range(5):
        game.engine.spawn_miner()
    miners = [game.engine.miner_by_id(miner_id) for miner_id in sorted(game.engine.miners)]
    directions = (Direction.EAST, Direction.SOUTH, Direction.WEST, Direction.NORTH)
    inventories = (
        {"copper": 4, "stone": 3, "coal": 2},
        {"iron": 3, "stone": 2},
        {"gold": 1, "copper": 2},
        {"coal": 4},
        {"silver": 2, "stone": 1},
        {"stone": 2},
    )
    script_names = ("fleet.py", "fleet.py", "sweep.py", "market.py", "worker.py", "main.py")
    for index, miner in enumerate(miners):
        x, y = positions[index % len(positions)] if positions else (index, 0)
        if preset == "base" and index == 0:
            x, y = 0, 0
        miner.layer = layer
        miner.x, miner.y = int(x), int(y)
        miner.facing = directions[index % len(directions)]
        miner.inventory = dict(inventories[index % len(inventories)])
        miner.energy = max(0, int(miner.battery_capacity) - index * 17)
        miner.temperature = 8.0 + index * 6.5
        miner.script = script_names[index % len(script_names)]
        command = Mine() if index % 3 == 0 else Move(directions[(index + 1) % len(directions)])
        game.submit(command, miner_id=miner.id)
    for _ in range(1):
        game.step()
    game.start_refine("iron_bar", 5)
    return game


def _hide_all_press_panels(window: MainWindow) -> None:
    """Hide every floating panel before composing a preset scene."""
    for panel_name in (
        "achievements_panel",
        "upgrades_panel",
        "wardrobe_panel",
        "editor_panel",
        "api_panel",
        "base_panel",
        "market_panel",
        "miners_panel",
    ):
        panel = getattr(window, panel_name, None)
        if panel is None:
            continue
        try:
            panel.hide_panel()
        except Exception:
            try:
                panel.hide()
            except Exception:
                pass


def _setup_press_editor(
    window: MainWindow,
    scripts_dir: Path,
    open_names: tuple[str, ...],
    current_name: str,
) -> None:
    """Open a few readable scripts in the editor and fill the console."""
    panel = getattr(window, "editor_panel", None)
    if panel is None:
        return
    panel.close_all_tabs(save=False, remember=False)
    for name in open_names:
        path = Path(scripts_dir) / name
        if path.is_file():
            panel.add_file(path)
    index = panel.tab_index(current_name)
    if index >= 0:
        panel.tabs.setCurrentIndex(index)
    console = getattr(window, "console_panel", None)
    if console is not None:
        try:
            console.clear()
        except Exception:
            pass
        for text, kind in PRESS_CONSOLE_LINES:
            console.append_line(text, kind)
    window.hud.refresh()


def _fit_press_hud(window: MainWindow, size: tuple[int, int]) -> None:
    """Hide the least important HUD labels on the narrow portrait canvas."""
    labels = (
        "tick_label",
        "position_label",
        "warehouse_label",
        "dock_label",
        "miners_label",
        "airflow_label",
    )
    if size[0] >= 1400:
        return
    for name in labels:
        label = getattr(window.hud, name, None)
        if label is not None:
            label.hide()


def _configure_press_window(window: MainWindow, preset: str, size: tuple[int, int]) -> None:
    """Show the panels and geometry that make each preset readable."""
    width, height = size
    landscape = width >= height
    margin = 24 if landscape else 20
    top = 72 if landscape else 84
    _hide_all_press_panels(window)
    _fit_press_hud(window, size)
    if preset in ("hero", "editor", "miners"):
        window.show_editor()
        editor = window.editor_panel
        if landscape:
            editor.move(int(width * 0.53), top)
            editor.resize(int(width * 0.44), int(height * 0.68))
        else:
            editor.move(margin, int(height * 0.55))
            editor.resize(width - 2 * margin, int(height * 0.41))
    if preset in ("miners", "layers"):
        window.show_miners()
        panel = window.miners_panel
        if landscape:
            panel.move(margin, top)
            panel.resize(int(width * 0.25), int(height * 0.64))
        else:
            panel.move(margin, top)
            panel.resize(width - 2 * margin, int(height * 0.26))
    if preset == "editor":
        window.show_api_panel()
        api = window.api_panel
        if landscape:
            api.move(margin, top)
            api.resize(int(width * 0.24), int(height * 0.66))
        else:
            api.move(margin, top)
            api.resize(width - 2 * margin, int(height * 0.26))
        api.text_edit.find("mine")
    if preset == "market":
        window.show_market()
        panel = window.market_panel
        if landscape:
            panel.move(int(width * 0.46), top)
            panel.resize(int(width * 0.51), int(height * 0.78))
        else:
            panel.move(margin, int(height * 0.30))
            panel.resize(width - 2 * margin, int(height * 0.62))
        panel.select_item("gold")
    if preset == "base":
        window.show_base()
        panel = window.base_panel
        if landscape:
            panel.move(int(width * 0.46), top)
            panel.resize(int(width * 0.51), int(height * 0.78))
        else:
            panel.move(margin, int(height * 0.30))
            panel.resize(width - 2 * margin, int(height * 0.62))
        panel.select_tab("warehouse")
    if preset == "miners":
        try:
            window.miners_panel.select_miner(2)
            if window.console_panel is not None:
                window.console_panel.set_miner(2)
                window.console_panel.clear()
                for text, kind in PRESS_CONSOLE_LINES:
                    window.console_panel.append_line(text, kind)
        except Exception:
            pass
    window.hud.set_speed(2)
    window.world_view.setFocus()


def build_press_window(
    preset: str,
    size: tuple[int, int] = PRESS_SIZES[0],
    scripts_dir: Path | None = None,
) -> MainWindow:
    """Build one deterministic press preset window at ``size``."""
    if preset not in PRESS_PRESETS:
        raise ValueError(f"unknown preset: {preset!r}")
    QSettings("MineSim", "MineSim").clear()
    if scripts_dir is None:
        scripts_dir = Path(tempfile.mkdtemp(prefix="minesim_press_"))
        _write_press_scripts(scripts_dir)
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    game = _prepare_press_game(preset)
    window = MainWindow(game, scripts_dir=scripts_dir)
    window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    window.game_loop.stop()
    try:
        window._autosave_timer.stop()
    except Exception:
        pass
    try:
        window.world_view._anim_timer.stop()
    except Exception:
        pass
    window.world_view.set_terrain_lighting(True, persist=False)
    window.world_view.set_tile_px(40 if size[0] >= 1400 else 36)
    window.resize(int(size[0]), int(size[1]))
    window.show()
    layer = 3 if preset == "layers" else 2 if preset in ("hero", "editor", "miners") else 0
    if preset in ("hero", "editor", "miners", "layers"):
        center = (8.0, 8.0)
    elif preset == "base" and size[0] >= size[1]:
        center = (8.0, 0.0)
    elif preset == "base":
        center = (0.0, 22.0)
    else:
        center = (0.0, 0.0)
    window.world_view.snap_visual_to_miner()
    window.world_view.center_on_miner()
    window.world_view.set_viewed_layer(layer)
    window.world_view.finish_layer_transition()
    window.world_view.snap_visual_to_miner()
    window.world_view.camera_x = center[0]
    window.world_view.camera_y = center[1]
    if preset in ("hero", "editor", "miners"):
        if preset == "miners":
            names = ("worker.py", "fleet.py", "main.py")
        elif preset == "editor":
            names = ("fleet.py", "market.py", "sweep.py", "main.py")
        else:
            names = ("fleet.py", "market.py", "main.py")
        _setup_press_editor(window, scripts_dir, names, names[0])
    _configure_press_window(window, preset, size)
    window.hud.refresh()
    window.world_view.update()
    app.processEvents()
    window.resize(int(size[0]), int(size[1]))
    app.processEvents()
    return window


def render_preset(
    preset: str,
    output_dir: Path | None = None,
    sizes: tuple[tuple[int, int], ...] = PRESS_SIZES,
) -> list[Path]:
    """Render one preset at every size and return the saved paths."""
    root = Path(__file__).resolve().parents[1]
    target_dir = Path(output_dir) if output_dir is not None else root / "docs" / "press"
    target_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = Path(tempfile.mkdtemp(prefix="minesim_press_"))
    _write_press_scripts(scripts_dir)
    saved: list[Path] = []
    try:
        for index, size in enumerate(sizes):
            window = build_press_window(preset, size, scripts_dir)
            try:
                pixmap = window.grab()
                if (pixmap.width(), pixmap.height()) != (int(size[0]), int(size[1])):
                    pixmap = pixmap.scaled(
                        int(size[0]),
                        int(size[1]),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                names = PRESS_OUTPUT_NAMES[preset]
                name = names[min(index, len(names) - 1)]
                out = target_dir / name
                pixmap.save(str(out))
                saved.append(out)
            finally:
                window.close()
                app = QApplication.instance()
                if app is not None:
                    app.processEvents()
    finally:
        shutil.rmtree(scripts_dir, ignore_errors=True)
    return saved


def build_window(
    ticks: int = 300,
    size: tuple[int, int] = (1024, 768),
    flat: bool = False,
    skin: str | None = None,
    moving: bool = False,
    fleet: int = 0,
    miners: int = 0,
    panel: str | None = None,
    events: bool = False,
    locked: bool = False,
    editor_tabs: bool = False,
    layer: int | None = None,
    dock: bool = False,
    api: bool = False,
    climate: bool = False,
    options: bool = False,
) -> MainWindow:
    """Build the real main window and run ``ticks`` engine ticks."""
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    game = Game.new()
    if locked:
        from minesim.core.schemas import Feature

        for feature_id in ("warehouse", "market", "refinery", "contracts", "miners"):
            feature = game.content.features.get(feature_id)
            if feature is None:
                continue
            game.content.features[feature_id] = Feature(
                id=feature.id,
                name=feature.name,
                description=feature.description,
                unlocked_by="first_dig",
            )
            game.progression_state.unlocked_features.discard(feature_id)
    scripts_dir: Path | None = None
    if miners:
        scripts_dir = Path(tempfile.mkdtemp(prefix="minesim_miners_"))
        (scripts_dir / "worker.py").write_text(MINER_SCRIPT, encoding="utf-8")
    if editor_tabs:
        scripts_dir = Path(tempfile.mkdtemp(prefix="minesim_editor_tabs_"))
        _write_editor_scripts(scripts_dir)
    if panel or miners or layer is not None or dock or api or climate:
        unlock_everything(game)
    if panel:
        prepare_economy(game)
    if layer is not None:
        prepare_layer(game, int(layer))
    if climate:
        prepare_climate(game)
    if dock:
        prepare_dock(game)
    if skin:
        game.select_skin(skin)
    for _ in range(max(0, int(fleet))):
        game.engine.spawn_miner()
    offsets = ((2, 0), (-2, 0), (0, 2), (0, -2))
    for index, miner_id in enumerate(sorted(game.engine.miners)):
        if miner_id == 0:
            continue
        dx, dy = offsets[(index - 1) % len(offsets)]
        game.engine.miner_by_id(miner_id).x = dx
        game.engine.miner_by_id(miner_id).y = dy
    window = MainWindow(game, scripts_dir=scripts_dir) if scripts_dir else MainWindow(game)
    window.world_view.set_terrain_lighting(not flat, persist=False)
    window.resize(size[0], size[1])
    window.show()
    if dock or options:
        window.game_loop.stop()
    if options:
        panel = getattr(window, "options_panel", None)
        if panel is not None:
            try:
                panel.show_panel()
                panel.move(292, 110)
                panel.resize(440, 520)
            except Exception:
                pass
    if editor_tabs and scripts_dir is not None:
        window.game_loop.stop()
        _setup_editor_tabs(window, scripts_dir, app)
    if miners:
        _setup_miners(window, game, int(miners), app)
    if (
        panel is None
        and not miners
        and not editor_tabs
        and layer is None
        and not dock
        and not climate
    ):
        for command in COMMAND_SEQUENCE:
            game.submit(command)
        for _ in range(int(ticks)):
            game.engine.step()
        if moving:
            game.submit(Move(Direction.EAST))
            game.engine.step()
    if layer is not None:
        window.game_loop.stop()
        window.world_view.snap_visual_to_miner()
        window.world_view.center_on_miner()
        window.world_view.set_viewed_layer(int(layer))
        window.world_view.finish_layer_transition()
    elif climate:
        window.game_loop.stop()
        window.world_view.snap_visual_to_miner()
        window.world_view.center_on_miner()
        window.world_view.set_viewed_layer(2)
        window.world_view.finish_layer_transition()
    elif not miners:
        window.game_loop.stop()
        window.world_view.snap_visual_to_miner()
        window.world_view.center_on_miner()
    window.hud.refresh()
    editor_panel = getattr(window, "editor_panel", None)
    if (
        editor_panel is not None
        and panel is None
        and not miners
        and layer is None
        and not dock
        and not climate
    ):
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
    if events:
        _position_on_rich_vein(window, game)
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
        "--fleet",
        type=int,
        default=0,
        help="spawn N extra miners and save artifacts/ui_miners.png",
    )
    parser.add_argument(
        "--miners",
        type=int,
        default=0,
        help="spawn N worker miners and save artifacts/ui_miners.png",
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
    parser.add_argument(
        "--events",
        action="store_true",
        help="center on an active rich vein and save artifacts/ui_events.png",
    )
    parser.add_argument(
        "--panel",
        choices=("base", "market", "refinery", "contracts"),
        default=None,
        help="screenshot a base/market panel after a scripted economy session",
    )
    parser.add_argument(
        "--locked",
        action="store_true",
        help="lock every feature and save artifacts/ui_locked.png",
    )
    parser.add_argument(
        "--editor-tabs",
        action="store_true",
        help="create 12 scripts, open 3 tabs with the Open… list and save "
        "artifacts/ui_editor_tabs.png",
    )
    parser.add_argument(
        "--layer",
        type=int,
        default=None,
        help="put the main miner on layer N and save artifacts/ui_layer_N.png",
    )
    parser.add_argument(
        "--dock",
        action="store_true",
        help="queue miners at the shared dock and save artifacts/ui_dock.png",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="show the API reference panel and save artifacts/ui_api.png",
    )
    parser.add_argument(
        "--climate",
        action="store_true",
        help="show a hot layer and the energy/climate HUD with the miners panel, "
        "saved as artifacts/ui_climate.png",
    )
    parser.add_argument(
        "--options",
        action="store_true",
        help="show the audio options panel and save artifacts/ui_options.png",
    )
    parser.add_argument(
        "--preset",
        choices=PRESS_PRESETS,
        default=None,
        help="build a press scene and save docs/press/<preset>.png plus its "
        "1080x1920 portrait variant",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.preset:
        for path in render_preset(args.preset, output_dir=args.output_dir):
            print(path)
        return 0
    window = build_window(
        ticks=args.ticks,
        size=args.size,
        flat=args.flat,
        skin=args.skin,
        moving=args.moving,
        fleet=args.fleet,
        miners=args.miners,
        panel=args.panel,
        events=args.events,
        locked=args.locked,
        editor_tabs=args.editor_tabs,
        layer=args.layer,
        dock=args.dock,
        api=args.api,
        climate=args.climate,
        options=args.options,
    )
    for panel_name in (
        "achievements_panel",
        "upgrades_panel",
        "wardrobe_panel",
        "editor_panel",
        "api_panel",
        "base_panel",
        "market_panel",
        "miners_panel",
    ):
        if args.achievements and panel_name == "achievements_panel":
            continue
        if args.wardrobe and panel_name == "wardrobe_panel":
            continue
        if args.miners and panel_name in ("miners_panel", "editor_panel"):
            continue
        if args.climate and panel_name == "miners_panel":
            continue
        if args.options and panel_name == "options_panel":
            continue
        if args.editor_tabs and panel_name == "editor_panel":
            continue
        panel = getattr(window, panel_name, None)
        if panel is not None:
            try:
                panel.hide_panel()
            except Exception:
                panel.hide()
    if args.api:
        try:
            window.api_panel.show_panel()
        except Exception:
            window.api_panel.show()
        window.api_panel.resize(620, 620)
        window.api_panel.move(330, 40)
        window.api_panel.text_edit.find("safe_farm")
        scroll = window.api_panel.text_edit.verticalScrollBar()
        scroll.setValue(scroll.value() + 120)
    elif args.wardrobe:
        try:
            window.show_wardrobe()
        except Exception:
            window.wardrobe_panel.show_panel()
    elif args.options:
        try:
            window.show_options()
        except Exception:
            window.options_panel.show_panel()
        window.options_panel.move(292, 110)
        window.options_panel.resize(440, 520)
    elif args.climate:
        try:
            window.show_miners()
        except Exception:
            window.miners_panel.show_panel()
        window.miners_panel.move(8, 44)
        window.miners_panel.resize(350, 440)
    if args.locked and not args.panel:
        try:
            window.show_market()
        except Exception:
            window.market_panel.show_panel()
    elif args.panel == "market":
        try:
            window.show_market()
        except Exception:
            window.market_panel.show_panel()
    elif args.panel:
        try:
            window.show_base()
        except Exception:
            window.base_panel.show_panel()
        window.base_panel.select_tab(args.panel)
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
    if args.fleet:
        default_name = "ui_fleet.png"
    if args.wardrobe:
        default_name = "ui_wardrobe.png"
    if args.panel:
        default_name = f"ui_{args.panel}.png"
    if args.events:
        default_name = "ui_events.png"
    if args.miners:
        default_name = "ui_miners.png"
    if args.locked:
        default_name = "ui_locked.png"
    if args.editor_tabs:
        default_name = "ui_editor_tabs.png"
    if args.layer is not None:
        default_name = f"ui_layer_{int(args.layer)}.png"
    if args.dock:
        default_name = "ui_dock.png"
    if args.api:
        default_name = "ui_api.png"
    if args.climate:
        default_name = "ui_climate.png"
    if args.options:
        default_name = "ui_options.png"
    out = args.output or (Path(__file__).resolve().parents[1] / "artifacts" / default_name)
    out.parent.mkdir(parents=True, exist_ok=True)
    window.grab().save(str(out))
    window.close()
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
