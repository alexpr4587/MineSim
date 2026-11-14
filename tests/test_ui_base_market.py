"""Tests for the base and market panels (prompt 18)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QRect, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from minesim.core.game import Game  # noqa: E402
from minesim.ui.base_panel import BasePanel  # noqa: E402
from minesim.ui.hud import HUD  # noqa: E402
from minesim.ui.main_window import MainWindow  # noqa: E402
from minesim.ui.market_panel import MarketPanel, PriceChart, moving_average  # noqa: E402
from minesim.ui.theme import STYLESHEET  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _clean_settings(qapp):
    QSettings("MineSim", "MineSim").clear()
    yield
    QSettings("MineSim", "MineSim").clear()


def _image_colors(pixmap) -> int:
    image = pixmap.toImage()
    colors = set()
    for y in range(0, image.height(), 4):
        for x in range(0, image.width(), 4):
            color = image.pixelColor(x, y)
            colors.add((color.red(), color.green(), color.blue()))
    return len(colors)


def _key(window, key):
    window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.NoModifier))


def test_base_panel_builds_with_three_tabs(qapp):
    game = Game.new()
    game.engine.warehouse.add("stone", 10)
    game.engine.warehouse.add("coal", 5)
    panel = BasePanel(game=game)
    panel.resize(780, 570)
    panel.show()
    qapp.processEvents()
    assert panel.tabs.count() == 3
    labels = [panel.tabs.tabText(index) for index in range(panel.tabs.count())]
    assert labels == ["Warehouse", "Refinery", "Contracts"]
    assert panel.warehouse_table.rowCount() == 2
    assert panel.capacity_bar.maximum() == game.engine.warehouse.capacity
    assert "15/100" in panel.capacity_bar.format()
    assert panel.sell_everything_button.isEnabled()
    panel.close()


def test_market_chart_draws_and_average_has_right_length(qapp):
    samples = [100.0 + index * 1.5 for index in range(40)]
    chart = PriceChart()
    chart.resize(640, 320)
    chart.set_samples(samples, interval=100, step=40)
    chart.set_moving_average(True)
    chart.show()
    qapp.processEvents()
    assert _image_colors(chart.grab()) > 4
    chart._crosshair_index = 10
    chart.update()
    qapp.processEvents()
    assert _image_colors(chart.grab()) > 4
    average = moving_average(samples, 10)
    assert len(average) == len(samples)
    assert chart.average_series() == pytest.approx(average)
    chart.close()


def test_market_panel_selector_chart_and_table(qapp):
    game = Game.new()
    for _ in range(350):
        game.step()
    panel = MarketPanel(game=game)
    panel.resize(820, 590)
    panel.show()
    qapp.processEvents()
    assert panel.item_selector.count() == len(game.engine.catalog.ids)
    assert panel.table.rowCount() == len(game.engine.catalog.ids)
    panel.select_item("stone")
    assert panel.current_item == "stone"
    assert panel.chart.samples == pytest.approx(game.engine.market.history("stone"))
    assert panel.price_label.text().startswith("Price: ")
    panel.average_toggle.setChecked(True)
    assert panel.chart.show_average
    panel.close()


def test_warehouse_buttons_call_sell_stock(qapp):
    game = Game.new()
    game.engine.warehouse.add("stone", 5)
    calls: list[tuple[str, int | None]] = []
    original = game.sell_stock

    def spy(item, amount=None):
        calls.append((item, amount))
        return original(item, amount)

    game.sell_stock = spy
    panel = BasePanel(game=game)
    panel.show()
    qapp.processEvents()
    panel.warehouse_rows["stone"]["sell"].click()
    assert calls == [("stone", 1)]
    assert game.engine.warehouse.count("stone") == 4
    panel.warehouse_rows["stone"]["sell_all"].click()
    assert calls[-1] == ("stone", None)
    assert game.engine.warehouse.count("stone") == 0
    game.engine.warehouse.add("coal", 2)
    panel.refresh()
    panel.sell_everything_button.click()
    assert calls[-1] == ("coal", None)
    assert game.engine.warehouse.count("coal") == 0
    panel.close()


def test_unload_button_enabled_only_on_base(qapp):
    game = Game.new()
    game.miner.inventory = {"stone": 2}
    game.miner.x, game.miner.y = 5, 5
    panel = BasePanel(game=game)
    panel.show()
    qapp.processEvents()
    assert not panel.unload_button.isEnabled()
    assert "not on the base" in panel.unload_hint.text()

    game.miner.x, game.miner.y = 0, 0
    panel.refresh()
    assert panel.unload_button.isEnabled()
    calls: list[int] = []
    original = game.unload

    def spy(drone_id=0):
        calls.append(int(drone_id))
        return original(drone_id)

    game.unload = spy
    panel.unload_button.click()
    assert calls == [0]
    assert game.engine.warehouse.count("stone") == 2
    assert not game.miner.inventory
    panel.close()


def test_refinery_buttons_start_jobs_and_slots_show_state(qapp):
    game = Game.new()
    game.engine.warehouse.add("copper", 20)
    calls: list[tuple[str, int]] = []
    original = game.start_refine

    def spy(recipe_id, times=1):
        calls.append((recipe_id, int(times)))
        return original(recipe_id, times)

    game.start_refine = spy
    panel = BasePanel(game=game)
    panel.show()
    qapp.processEvents()
    row = panel.recipe_rows["copper_bar"]
    assert row.start1.isEnabled()
    row.start1.click()
    assert calls == [("copper_bar", 1)]
    assert game.engine.refinery.status()[0]["recipe"] == "copper_bar"
    assert len(panel.slot_bars) == game.engine.refinery.slots
    assert "Copper Bar" in panel.slot_bars[0].format()
    assert not panel.recipe_rows["copper_bar"].start1.isEnabled()
    panel.close()

    other = Game.new()
    other.engine.warehouse.add("copper", 15)
    second = BasePanel(game=other)
    second.show()
    qapp.processEvents()
    second.recipe_rows["copper_bar"].start5.click()
    assert other.engine.refinery.status()[0]["times"] == 5
    second.close()


def test_refinery_slot_shows_blocked_state(qapp):
    game = Game.new()
    game.engine.warehouse.add("copper", 3)
    panel = BasePanel(game=game)
    panel.show()
    qapp.processEvents()
    panel.recipe_rows["copper_bar"].start1.click()
    game.engine.warehouse.capacity = 0
    for _ in range(60):
        game.step()
    panel.refresh()
    assert "BLOCKED" in panel.slot_bars[0].format()
    panel.close()


def test_locked_recipe_is_dimmed_and_disabled(qapp):
    game = Game.new()
    panel = BasePanel(game=game)
    panel.show()
    qapp.processEvents()

    class LockedProgression:
        def is_recipe_unlocked(self, _recipe_id: str) -> bool:
            return False

    panel.progression = LockedProgression()
    panel._rebuild_recipe_rows()
    panel.refresh()
    row = panel.recipe_rows["copper_bar"]
    assert "Locked" in row.info_label.text()
    assert not row.start1.isEnabled()
    assert not row.start5.isEnabled()
    panel.close()


def test_contract_card_deliver_disabled_until_stock(qapp):
    game = Game.new()
    game.engine.warehouse.capacity = 1_000_000
    while not game.engine.contracts.contracts:
        game.step()
    contract = game.engine.contracts.contracts[0]
    panel = BasePanel(game=game)
    panel.show()
    qapp.processEvents()
    card = panel.contract_cards[contract.id]
    assert not card.deliver.isEnabled()

    game.engine.warehouse.add(contract.item, contract.quantity)
    panel.refresh()
    card = panel.contract_cards[contract.id]
    assert card.deliver.isEnabled()
    calls: list[int] = []
    original = game.deliver_contract

    def spy(contract_id):
        calls.append(int(contract_id))
        return original(contract_id)

    game.deliver_contract = spy
    money_before = game.miner.money
    card.deliver.click()
    assert calls == [contract.id]
    assert contract.id not in panel.contract_cards
    assert game.miner.money > money_before
    panel.close()


def test_panels_fit_1024x768_without_overlaps(qapp, tmp_path):
    game = Game.new()
    window = MainWindow(game, scripts_dir=tmp_path)
    window.resize(1024, 768)
    window.show()
    window.show_base()
    window.show_market()
    qapp.processEvents()

    for panel in (window.base_panel, window.market_panel):
        assert window.rect().contains(panel.geometry())
        assert panel.width() > 300 and panel.height() > 200

    def direct_rects(widget: QWidget) -> list[QRect]:
        children = widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
        return [
            QRect(child.mapTo(widget, QPoint(0, 0)), child.size())
            for child in children
            if child.isVisible()
        ]

    for tab_index in range(window.base_panel.tabs.count()):
        tab = window.base_panel.tabs.widget(tab_index)
        rects = direct_rects(tab)
        for first in range(len(rects)):
            for second in range(first + 1, len(rects)):
                assert not rects[first].intersects(rects[second])
    market_rects = direct_rects(window.market_panel.content_widget)
    for first in range(len(market_rects)):
        for second in range(first + 1, len(market_rects)):
            assert not market_rects[first].intersects(market_rects[second])
    window.close()


def test_b_and_m_toggle_panels_from_world(qapp, tmp_path):
    window = MainWindow(Game.new(), scripts_dir=tmp_path)
    window.show()
    window.world_view.setFocus()
    qapp.processEvents()
    assert not window.base_panel.isVisible()
    assert not window.market_panel.isVisible()
    _key(window, Qt.Key.Key_B)
    assert window.base_panel.isVisible()
    _key(window, Qt.Key.Key_B)
    assert not window.base_panel.isVisible()
    _key(window, Qt.Key.Key_M)
    assert window.market_panel.isVisible()
    _key(window, Qt.Key.Key_M)
    assert not window.market_panel.isVisible()
    window.close()


def test_hud_shows_warehouse_and_selected_speed_is_high_contrast(qapp):
    game = Game.new()
    game.engine.warehouse.add("stone", 12)
    hud = HUD(game)
    hud.refresh()
    assert "12/100" in hud.warehouse_label.text()
    hud.set_speed(1)
    assert hud.speed_buttons[1].isChecked()
    assert "QPushButton:checked" in STYLESHEET
    assert "font-weight: bold" in STYLESHEET
    hud.close()
