"""Offscreen UI tests for layer viewing, stations and transitions (prompt 29)."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from minesim.core.content import load_content
from minesim.core.game import Game
from minesim.core.schemas import ContentError

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim.ui.hud import HUD  # noqa: E402
from minesim.ui.miners_panel import MinersPanel  # noqa: E402
from minesim.ui.sprites import STATION_SIZE, SpriteBook  # noqa: E402
from minesim.ui.terrain_shader import render_chunk  # noqa: E402
from minesim.ui.upgrades_panel import UpgradesPanel  # noqa: E402
from minesim.ui.world_view import WorldView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def content():
    return load_content()


def _press(view: WorldView, key: Qt.Key) -> None:
    event = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
    view.keyPressEvent(event)


def _image_samples(image) -> list[tuple[int, int, int]]:
    return [
        (
            image.pixelColor(x, y).red(),
            image.pixelColor(x, y).green(),
            image.pixelColor(x, y).blue(),
        )
        for y in range(0, image.height(), 4)
        for x in range(0, image.width(), 4)
    ]


def test_chunk_cache_keys_include_layer(qapp, content) -> None:
    game = Game.new(content=content)
    view = WorldView(game)
    view.set_terrain_lighting(True, persist=False)
    view.set_viewed_layer(0)
    view.get_chunk_pixmap(0, 0)
    key0 = next(reversed(view.pixmap_cache))
    assert key0[2] == 0

    view.set_viewed_layer(2)
    view.get_chunk_pixmap(0, 0)
    key2 = next(reversed(view.pixmap_cache))
    assert key2[2] == 2
    assert key0[:3] != key2[:3]
    view.close()


def test_each_layer_renders_non_blank_and_different(content) -> None:
    world = Game.new(content=content).world
    samples = {}
    for layer in range(4):
        image = render_chunk(world, 0, 0, 0, content=content, layer=layer)
        assert not image.isNull()
        samples[layer] = _image_samples(image)
        assert len(set(samples[layer])) > 1
    for first in range(4):
        for second in range(first + 1, 4):
            assert samples[first] != samples[second]


def test_station_sprite_validates(qapp, content) -> None:
    book = SpriteBook(content)
    assert STATION_SIZE == 48
    pixmap = book.station_pixmap("rusty_bot", 24)
    assert (pixmap.width(), pixmap.height()) == (72, 72)

    sprites = copy.deepcopy(content.sprites.model_dump())
    sprites["station"][0] = "X" * len(sprites["station"][0])
    with pytest.raises(ContentError) as excinfo:
        SpriteBook(sprites=sprites, skins=content.skins)
    assert "$.station.0.0" in str(excinfo.value)


def test_page_keys_only_change_layer_when_not_following(qapp, content) -> None:
    game = Game.new(content=content)
    view = WorldView(game)
    view.resize(320, 320)
    view.show()
    qapp.processEvents()
    view.set_viewed_layer(0)
    view.follow_selected = True

    _press(view, Qt.Key.Key_PageDown)
    assert view.viewed_layer == 0
    _press(view, Qt.Key.Key_PageUp)
    assert view.viewed_layer == 0

    view.set_follow_selected(False)
    _press(view, Qt.Key.Key_PageDown)
    assert view.viewed_layer == 1
    _press(view, Qt.Key.Key_PageDown)
    assert view.viewed_layer == 2
    _press(view, Qt.Key.Key_PageUp)
    assert view.viewed_layer == 1
    for _ in range(10):
        _press(view, Qt.Key.Key_PageDown)
    assert view.viewed_layer == 3
    view.close()


def test_layer_transition_does_not_break_snapshots(qapp, content) -> None:
    game = Game.new(content=content)
    view = WorldView(game)
    view.resize(320, 320)
    view.show()
    qapp.processEvents()
    view.follow_selected = True
    view.set_viewed_layer(0)
    game.miner.layer = 1
    view._advance_visual()
    assert view.viewed_layer == 1
    assert view._fade_alpha > 0.0
    view.finish_layer_transition()
    assert view._fade_alpha == 0.0
    image = view.grab().toImage()
    assert len(_image_samples(image)) > 0
    view.close()


def test_hud_panel_and_upgrade_show_the_layer(qapp, content, tmp_path) -> None:
    game = Game.new(content=content)
    view = WorldView(game)
    view.set_viewed_layer(1)
    hud = HUD(game, world_view=view)
    hud.refresh()
    assert "Old Galleries (1)" in hud.layer_label.text()

    game.miner.layer = 2
    game.progression_state.unlock_upgrade("shaft")
    panel = MinersPanel(game=game, scripts_dir=tmp_path, world_view=view, parent=None)
    panel.refresh()
    assert panel.rows[0].layer_label.text() == "Layer: 2"
    assert panel.rows[0].layer_label.toolTip() == "Deep Level"

    upgrades = UpgradesPanel(game=game)
    upgrades.refresh()
    assert "reaches layer" in upgrades._rows["shaft"].info.text()
    upgrades.close()
    panel.close()
    hud.close()
    view.close()


def test_layer_screenshot_tool_builds(tmp_path) -> None:
    path = Path(__file__).resolve().parents[1] / "tools" / "screenshot.py"
    out = tmp_path / "ui_layer_2.png"
    result = subprocess.run(
        [sys.executable, str(path), "--ticks", "0", "--layer", "2", "--output", str(out)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()
    assert out.stat().st_size > 0
    assert str(out) in result.stdout
