"""Tests for miner skins, sprites and the base building (prompt 10)."""

from __future__ import annotations

import copy
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from minesim.core.content import load_content
from minesim.core.game import Game
from minesim.core.save import DEFAULT_SKIN, SaveGame, migrate
from minesim.core.schemas import ContentError, Skin

pytest.importorskip("PySide6")

from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from minesim.ui.sprites import BASE_SIZE, MINER_SIZE, SpriteBook  # noqa: E402
from minesim.ui.wardrobe_panel import WardrobePanel  # noqa: E402
from minesim.ui.world_view import WorldView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def content():
    return load_content()


def _sprites(content):
    return copy.deepcopy(content.sprites.model_dump())


def test_grid_validation_row_count_and_unknown_roles(content) -> None:
    sprites = _sprites(content)
    sprites["miner"]["down"]["walk0"] = sprites["miner"]["down"]["walk0"][:15]
    with pytest.raises(ContentError) as excinfo:
        SpriteBook(sprites=sprites, skins=content.skins)
    message = str(excinfo.value)
    assert "sprites.json" in message
    assert "$.miner.down.walk0" in message

    sprites = _sprites(content)
    row = sprites["miner"]["up"]["mine1"][3]
    sprites["miner"]["up"]["mine1"][3] = "X" + row[1:]
    with pytest.raises(ContentError) as excinfo:
        SpriteBook(sprites=sprites, skins=content.skins)
    message = str(excinfo.value)
    assert "sprites.json" in message
    assert "$.miner.up.mine1.3.0" in message
    assert "unknown palette role" in message


def test_base_grid_validation(content) -> None:
    sprites = _sprites(content)
    sprites["base"][0] = "X" * len(sprites["base"][0])
    with pytest.raises(ContentError) as excinfo:
        SpriteBook(sprites=sprites, skins=content.skins)
    assert "$.base.0.0" in str(excinfo.value)


def test_sprite_sizes_from_12_to_64(qapp, content, tmp_path) -> None:
    book = SpriteBook(content, asset_dir=tmp_path)
    for tile_px in range(12, 65):
        pixmap = book.miner_pixmap("rusty_bot", "down", "walk", tile_px % 2, tile_px)
        assert (pixmap.width(), pixmap.height()) == (tile_px, tile_px)
    base = book.base_pixmap("rusty_bot", 24)
    assert (base.width(), base.height()) == (72, 72)
    assert BASE_SIZE == 48
    assert book.miner_pixmap("rusty_bot", "down", "walk", 0, 24).width() == 24
    assert MINER_SIZE == 16


def test_wardrobe_lists_every_skin(qapp, content) -> None:
    panel = WardrobePanel(game=Game.new(content=content))
    assert panel.game_content is content
    assert list(panel.cards) == list(content.skins)
    assert [card.skin_id for card in panel.cards.values()] == list(content.skins)
    assert panel.cards[DEFAULT_SKIN].is_unlocked()
    panel.hide()


def test_png_override_replaces_generated_frames(qapp, content, tmp_path) -> None:
    sheet = QImage(64, 64, QImage.Format.Format_ARGB32)
    sheet.fill(QColor("#ff00ff"))
    path = tmp_path / "skins" / "rusty_bot.png"
    path.parent.mkdir(parents=True)
    assert sheet.save(str(path))
    book = SpriteBook(content, asset_dir=tmp_path)
    assert book.has_png_override("rusty_bot")
    pixmap = book.miner_pixmap("rusty_bot", "down", "walk", 0, 24)
    color = pixmap.toImage().pixelColor(12, 12)
    assert color.name() == "#ff00ff"


def test_selecting_a_skin_changes_world_view_pixels(qapp, content) -> None:
    game = Game.new()
    view = WorldView(game)
    view.set_terrain_lighting(False, persist=False)
    view.resize(320, 320)
    view.show()
    qapp.processEvents()
    before = view.grab().toImage()
    game.progression_state.unlock_skin("steel_walker")
    assert game.select_skin("steel_walker") == "steel_walker"
    view.update()
    qapp.processEvents()
    after = view.grab().toImage()
    differences = 0
    for y in range(0, before.height(), 2):
        for x in range(0, before.width(), 2):
            if before.pixelColor(x, y) != after.pixelColor(x, y):
                differences += 1
    assert differences > 20
    view.close()


def test_locked_skins_cannot_be_selected(qapp, content) -> None:
    game = Game.new()
    palette = dict(game.content.get_skin("rusty_bot").palette)
    game.content.skins["locked_test"] = Skin(
        id="locked_test",
        name="Locked Test",
        description="Only after the first dig.",
        unlocked_by="first_dig",
        palette=palette,
    )
    with pytest.raises(ValueError):
        game.select_skin("locked_test")
    with pytest.raises(ValueError):
        game.select_skin("no_such_skin")
    assert game.selected_skin == DEFAULT_SKIN
    game.progression_state.complete("first_dig", 0)
    assert game.select_skin("locked_test") == "locked_test"
    assert game.selected_skin == "locked_test"


def test_version_1_saves_load_and_migrate(tmp_path) -> None:
    data = {
        "version": 1,
        "seed": 12345,
        "tick": 7,
        "miner": {},
        "world_delta": {},
        "progression": {},
    }
    migrated = migrate(data)
    assert migrated["version"] == 4
    assert migrated["selected_skin"] == DEFAULT_SKIN
    path = tmp_path / "slot1.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    savegame = SaveGame.load(path)
    assert savegame.selected_skin == DEFAULT_SKIN
    game = Game.load(path)
    assert game.selected_skin == DEFAULT_SKIN


def test_selected_skin_survives_save_round_trip(tmp_path, qapp) -> None:
    game = Game.new()
    game.progression_state.unlock_skin("golden_hauler")
    game.select_skin("golden_hauler")
    path = tmp_path / "slot1.json"
    game.save(path)
    loaded = Game.load(path)
    assert loaded.selected_skin == "golden_hauler"
