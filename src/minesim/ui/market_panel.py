"""Market panel (key M): item selector, price chart, index table and news.

The chart is drawn with :class:`QPainter` and supports a 10-sample moving
average toggle plus a mouse crosshair that reports the market tick and
the price under the cursor. All state is read from the game; no market
logic lives in the UI.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from minesim.core.events import StockSold, TickAdvanced
from minesim.ui.floating_panel import FloatingPanel
from minesim.ui.theme import (
    ACCENT,
    BACKGROUND,
    BUTTON_BORDER,
    HUD_BACKGROUND,
    SYNTAX_BUILTIN,
    TEXT,
    TEXT_DIM,
)

__all__ = ["MarketPanel", "PriceChart", "moving_average"]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def moving_average(values: list[float], window: int = 10) -> list[float]:
    """Return the moving average of ``values`` with the same length.

    The first samples average the shorter warm-up window so that the
    result always lines up with the input, one value per sample.
    """
    window = max(1, int(window))
    result: list[float] = []
    for index in range(len(values)):
        start = max(0, index - window + 1)
        chunk = values[start : index + 1]
        result.append(sum(float(value) for value in chunk) / len(chunk))
    return result


class PriceChart(QWidget):
    """A line chart of market price samples drawn with :class:`QPainter`."""

    LEFT_MARGIN = 62
    RIGHT_MARGIN = 18
    TOP_MARGIN = 18
    BOTTOM_MARGIN = 34

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.samples: list[float] = []
        self.show_average = False
        self.interval = 100
        self.step = 0
        self._crosshair_index: int | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(320, 200)

    # -- data ---------------------------------------------------------------

    def set_samples(
        self,
        samples: Any,
        *,
        interval: int = 100,
        step: int = 0,
    ) -> None:
        """Replace the plotted samples and the tick mapping."""
        self.samples = [float(value) for value in (samples or [])]
        self.interval = max(1, int(interval))
        self.step = int(step)
        self._crosshair_index = None
        self.update()

    def set_moving_average(self, enabled: bool) -> None:
        """Show or hide the 10-sample moving average line."""
        self.show_average = bool(enabled)
        self.update()

    def average_series(self, window: int = 10) -> list[float]:
        """Return the moving-average series for the current samples."""
        return moving_average(self.samples, window)

    def tick_for_index(self, index: int) -> int:
        """Return the market tick corresponding to sample ``index``."""
        count = len(self.samples)
        first_step = max(0, self.step - count + 1)
        return (first_step + int(index)) * self.interval

    # -- geometry -----------------------------------------------------------

    def _plot_rect(self) -> QRectF:
        width = max(1, self.width())
        height = max(1, self.height())
        return QRectF(
            float(self.LEFT_MARGIN),
            float(self.TOP_MARGIN),
            float(max(10, width - self.LEFT_MARGIN - self.RIGHT_MARGIN)),
            float(max(10, height - self.TOP_MARGIN - self.BOTTOM_MARGIN)),
        )

    def _value_range(self) -> tuple[float, float]:
        if not self.samples:
            return 0.0, 1.0
        low = min(self.samples)
        high = max(self.samples)
        span = high - low
        if span <= 0.0:
            span = max(1.0, abs(high) * 0.05)
        padding = span * 0.08
        return low - padding, high + padding

    def _x_for(self, index: int, plot: QRectF) -> float:
        count = len(self.samples)
        if count <= 1:
            return plot.center().x()
        return plot.left() + plot.width() * index / (count - 1)

    def _y_for(self, price: float, plot: QRectF, low: float, high: float) -> float:
        span = high - low
        if span <= 0.0:
            span = 1.0
        return plot.bottom() - (price - low) / span * plot.height()

    def _index_at(self, x: float) -> int | None:
        if not self.samples:
            return None
        plot = self._plot_rect()
        if x < plot.left() or x > plot.right():
            return None
        if len(self.samples) == 1:
            return 0
        ratio = (x - plot.left()) / max(1.0, plot.width())
        return max(0, min(len(self.samples) - 1, int(round(ratio * (len(self.samples) - 1)))))

    # -- mouse --------------------------------------------------------------

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        index = self._index_at(event.position().x())
        if index != self._crosshair_index:
            self._crosshair_index = index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: Any) -> None:  # noqa: N802
        self._crosshair_index = None
        self.update()
        super().leaveEvent(event)

    # -- painting -----------------------------------------------------------

    def paintEvent(self, event: Any) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BACKGROUND))
        plot = self._plot_rect()

        if not self.samples:
            painter.setPen(QPen(QColor(TEXT_DIM)))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "No price history yet.",
            )
            return

        low, high = self._value_range()
        self._draw_axes(painter, plot, low, high)
        self._draw_series(painter, plot, low, high)
        self._draw_current_marker(painter, plot, low, high)
        if self.show_average:
            self._draw_average(painter, plot, low, high)
        if self._crosshair_index is not None:
            self._draw_crosshair(painter, plot, low, high)

    def _draw_axes(self, painter: QPainter, plot: QRectF, low: float, high: float) -> None:
        grid_pen = QPen(QColor(BUTTON_BORDER), 1)
        axis_pen = QPen(QColor(TEXT_DIM), 1)
        painter.setFont(self.font())
        for line in range(5):
            ratio = line / 4.0
            y = plot.bottom() - ratio * plot.height()
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            price = low + ratio * (high - low)
            painter.setPen(QPen(QColor(TEXT_DIM)))
            painter.drawText(
                QRectF(0, y - 8, self.LEFT_MARGIN - 6, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{price:.2f}",
            )
        painter.setPen(axis_pen)
        painter.drawLine(plot.bottomLeft(), plot.topLeft())
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())

        count = len(self.samples)
        positions = [0, count // 2, count - 1] if count > 2 else list(range(count))
        for index in sorted(set(positions)):
            x = self._x_for(index, plot)
            painter.setPen(grid_pen)
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.setPen(QPen(QColor(TEXT_DIM)))
            painter.drawText(
                QRectF(x - 42, plot.bottom() + 4, 84, 18),
                Qt.AlignmentFlag.AlignCenter,
                f"t{self.tick_for_index(index)}",
            )
        painter.setPen(QPen(QColor(TEXT_DIM)))
        painter.drawText(
            QRectF(plot.left(), self.height() - 14, plot.width(), 14),
            Qt.AlignmentFlag.AlignCenter,
            "market tick",
        )

    def _draw_series(self, painter: QPainter, plot: QRectF, low: float, high: float) -> None:
        polygon = QPolygonF(
            [
                QPointF(self._x_for(index, plot), self._y_for(value, plot, low, high))
                for index, value in enumerate(self.samples)
            ]
        )
        painter.setPen(QPen(QColor(ACCENT), 2))
        painter.drawPolyline(polygon)
        painter.setPen(QPen(QColor(TEXT_DIM)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index, value in enumerate(self.samples):
            x = self._x_for(index, plot)
            y = self._y_for(value, plot, low, high)
            painter.drawEllipse(QPointF(x, y), 1.5, 1.5)

    def _draw_average(self, painter: QPainter, plot: QRectF, low: float, high: float) -> None:
        values = self.average_series(10)
        polygon = QPolygonF(
            [
                QPointF(self._x_for(index, plot), self._y_for(value, plot, low, high))
                for index, value in enumerate(values)
            ]
        )
        pen = QPen(QColor(SYNTAX_BUILTIN), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(polygon)

    def _draw_current_marker(
        self, painter: QPainter, plot: QRectF, low: float, high: float
    ) -> None:
        index = len(self.samples) - 1
        price = self.samples[-1]
        x = self._x_for(index, plot)
        y = self._y_for(price, plot, low, high)
        painter.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        painter.setPen(QPen(QColor(ACCENT), 2))
        painter.setBrush(QColor(ACCENT))
        painter.drawEllipse(QPointF(x, y), 4.0, 4.0)
        painter.setPen(QPen(QColor(TEXT)))
        painter.drawText(
            QRectF(x - 70, max(plot.top(), y - 22), 70, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{price:.2f}",
        )
        if self.show_average:
            painter.setPen(QPen(QColor(SYNTAX_BUILTIN)))
            painter.drawText(
                QRectF(plot.left() + 4, plot.top() + 2, plot.width() - 8, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "10-sample average",
            )

    def _draw_crosshair(self, painter: QPainter, plot: QRectF, low: float, high: float) -> None:
        index = self._crosshair_index
        if index is None or not (0 <= index < len(self.samples)):
            return
        price = self.samples[index]
        x = self._x_for(index, plot)
        y = self._y_for(price, plot, low, high)
        pen = QPen(QColor(TEXT_DIM), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        label = f"tick {self.tick_for_index(index)} · {price:.2f}"
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(label) + 10
        label_rect = QRectF(x + 6, plot.top() + 4, width, 20)
        if label_rect.right() > plot.right():
            label_rect.moveLeft(x - width - 6)
        painter.setPen(QPen(QColor(BUTTON_BORDER)))
        painter.setBrush(QColor(HUD_BACKGROUND))
        painter.drawRoundedRect(label_rect, 3, 3)
        painter.setPen(QPen(QColor(TEXT)))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)


class MarketPanel(FloatingPanel):
    """Floating market panel with an item selector, chart and index table."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Market"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        content = kwargs.pop("content", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget) and parent is None:
                parent = arg
            elif hasattr(arg, "config") and hasattr(arg, "market"):
                if content is None:
                    content = arg
            elif hasattr(arg, "engine") and hasattr(arg, "miner"):
                if game is None:
                    game = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        self.game = game
        if game is not None and content is None:
            content = _get(game, "content")
        self.content_data = content
        self.current_item = ""
        self._row_items: list[str] = []
        self._unsubscribers: list[Any] = []

        super().__init__(title, parent=parent)
        if not self._restored_geometry:
            self.resize(820, 590)
            self.move(150, 50)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        top = QHBoxLayout()
        selector_label = QLabel("Item", self.content_widget)
        top.addWidget(selector_label)
        self.item_selector = QComboBox(self.content_widget)
        top.addWidget(self.item_selector, 1)
        self.average_toggle = QCheckBox("10-sample moving average", self.content_widget)
        self.average_toggle.toggled.connect(self._on_average_toggled)
        top.addWidget(self.average_toggle)
        self.price_label = QLabel("Price: —", self.content_widget)
        self.price_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        top.addWidget(self.price_label)
        layout.addLayout(top)

        self.chart = PriceChart(self.content_widget)
        layout.addWidget(self.chart, 2)

        self.table = QTableWidget(0, 4, self.content_widget)
        self.table.setHorizontalHeaderLabels(["Item", "Price", "Index", "Trend"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.cellClicked.connect(self._on_table_clicked)
        layout.addWidget(self.table, 1)

        news_frame = QFrame(self.content_widget)
        news_frame.setFrameShape(QFrame.Shape.StyledPanel)
        news_layout = QHBoxLayout(news_frame)
        news_layout.setContentsMargins(6, 3, 6, 3)
        news_title = QLabel("Market news", news_frame)
        news_title.setStyleSheet(f"color: {TEXT_DIM};")
        news_layout.addWidget(news_title)
        self.news_label = QLabel("", news_frame)
        self.news_label.setStyleSheet(f"color: {TEXT};")
        self.news_label.setWordWrap(True)
        news_layout.addWidget(self.news_label, 1)
        layout.addWidget(news_frame)

        self.content_layout.addLayout(layout)

        self._populate_items()
        self.item_selector.currentIndexChanged.connect(self._on_item_changed)
        self.refresh()
        self._subscribe()

    # -- state ---------------------------------------------------------------

    def catalog(self) -> Any:
        """Return the item catalog."""
        catalog = _get(_get(self.game, "engine"), "catalog")
        if catalog is None and self.content_data is not None:
            from minesim.core.items import ItemCatalog

            catalog = ItemCatalog(self.content_data)
        return catalog

    def market(self) -> Any:
        """Return the market."""
        return _get(_get(self.game, "engine"), "market")

    def _item_ids(self) -> list[str]:
        catalog = self.catalog()
        if catalog is None:
            return []
        return [str(item) for item in catalog.ids]

    def _item_name(self, item_id: str) -> str:
        catalog = self.catalog()
        if catalog is not None:
            try:
                return str(catalog.name(item_id))
            except Exception:
                pass
        return str(item_id).replace("_", " ").title()

    def _populate_items(self) -> None:
        self.item_selector.blockSignals(True)
        self.item_selector.clear()
        ids = self._item_ids()
        for item_id in ids:
            self.item_selector.addItem(f"{self._item_name(item_id)} ({item_id})", item_id)
        if self.current_item not in ids and ids:
            self.current_item = ids[0]
        index = self.item_selector.findData(self.current_item)
        if index >= 0:
            self.item_selector.setCurrentIndex(index)
        self.item_selector.blockSignals(False)

    def select_item(self, item_id: str) -> None:
        """Select ``item_id`` in the combo box and refresh the panel."""
        item_id = str(item_id)
        index = self.item_selector.findData(item_id)
        if index < 0:
            return
        self.item_selector.setCurrentIndex(index)
        self.current_item = item_id
        self.refresh()

    # -- refresh -------------------------------------------------------------

    def refresh(self) -> None:
        """Re-read market prices, history and the index table."""
        market = self.market()
        ids = self._item_ids()
        if self.current_item not in ids and ids:
            self.current_item = ids[0]
        history: list[float] = []
        interval = 100
        step = 0
        if market is not None:
            interval = int(_get(market, "interval", 100) or 100)
            step = int(_get(market, "step", 0) or 0)
            try:
                history = [float(value) for value in market.history(self.current_item)]
            except Exception:
                history = []
        self.chart.set_samples(history, interval=interval, step=step)
        self.chart.set_moving_average(self.average_toggle.isChecked())

        self.table.setRowCount(len(ids))
        self._row_items = list(ids)
        for row, item_id in enumerate(ids):
            price = 0.0
            index_percent = 100.0
            item_history: list[float] = []
            if market is not None:
                try:
                    price = float(market.price(item_id))
                    index_percent = float(market.index(item_id)) * 100.0
                    item_history = [float(value) for value in market.history(item_id, 2)]
                except Exception:
                    pass
            trend = "→"
            if len(item_history) >= 2:
                change = item_history[-1] - item_history[-2]
                if change > 1e-9:
                    trend = "↑"
                elif change < -1e-9:
                    trend = "↓"
            self.table.setItem(row, 0, QTableWidgetItem(self._item_name(item_id)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{price:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{index_percent:.1f}%"))
            trend_item = QTableWidgetItem(trend)
            trend_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 3, trend_item)
            if item_id == self.current_item:
                self.table.selectRow(row)

        if market is not None and self.current_item:
            try:
                price = float(market.price(self.current_item))
                index_percent = float(market.index(self.current_item)) * 100.0
                self.price_label.setText(f"Price: {price:.2f}  ({index_percent:.1f}%)")
            except Exception:
                self.price_label.setText("Price: —")
        else:
            self.price_label.setText("Price: —")

    # -- events --------------------------------------------------------------

    def _on_item_changed(self, _index: int) -> None:
        item_id = self.item_selector.currentData()
        if item_id:
            self.current_item = str(item_id)
            self.refresh()

    def _on_average_toggled(self, checked: bool) -> None:
        self.chart.set_moving_average(checked)

    def _on_table_clicked(self, row: int, _column: int) -> None:
        if 0 <= row < len(self._row_items):
            self.select_item(self._row_items[row])

    def _subscribe(self) -> None:
        for unsubscribe in self._unsubscribers:
            try:
                unsubscribe()
            except Exception:
                pass
        self._unsubscribers = []
        if self.game is None:
            return
        bus = _get(self.game, "events") or _get(self.game, "event_bus")
        if bus is None or not hasattr(bus, "subscribe"):
            return
        for event_type in (TickAdvanced, StockSold):
            try:
                self._unsubscribers.append(bus.subscribe(event_type, self._on_event))
            except Exception:
                pass

    def _on_event(self, _event: Any) -> None:
        if self.isVisible():
            self.refresh()

    def set_game(self, game: Any) -> None:
        """Attach a new game and refresh the selector and chart."""
        self.game = game
        if game is not None:
            self.content_data = _get(game, "content")
        self.current_item = ""
        self._populate_items()
        self.refresh()
        self._subscribe()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        self.refresh()
        super().showEvent(event)
