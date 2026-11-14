"""Base panel (key B): warehouse, refinery and delivery contracts.

The panel reads the game state and sends every action through the
:class:`~minesim.core.game.Game` convenience methods (``sell_stock``,
``start_refine``, ``deliver_contract`` and ``unload``). It reacts to the
typed events on the game bus, so the views stay in sync with scripts and
the game loop.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from minesim.core.events import (
    AchievementUnlocked,
    ContractDelivered,
    ContractExpired,
    ContractGenerated,
    RefineFinished,
    RefineStarted,
    StockSold,
    TickAdvanced,
    Unloaded,
)
from minesim.ui.floating_panel import FloatingPanel
from minesim.ui.theme import BUTTON_BORDER, DISABLED_TEXT, ERROR, TEXT, TEXT_DIM

__all__ = ["BasePanel"]

_TAB_ALIASES = {
    "base": "warehouse",
    "warehouse": "warehouse",
    "refinery": "refinery",
    "contracts": "contracts",
}


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _item_name(catalog: Any, item_id: str) -> str:
    if catalog is not None:
        try:
            return str(catalog.name(item_id))
        except Exception:
            pass
    return str(item_id).replace("_", " ").title()


def _format_items(items: Any, catalog: Any) -> str:
    if not isinstance(items, dict) or not items:
        return "—"
    return ", ".join(f"{count}× {_item_name(catalog, item)}" for item, count in items.items())


class _RecipeRow(QFrame):
    """One refinery recipe with its Start x1 / Start x5 buttons."""

    def __init__(self, recipe_id: str, panel: BasePanel) -> None:
        super().__init__()
        self.recipe_id = recipe_id
        self.panel = panel
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        top = QHBoxLayout()
        self.name_label = QLabel(self)
        top.addWidget(self.name_label, 1)
        self.start1 = QPushButton("Start x1", self)
        self.start5 = QPushButton("Start x5", self)
        self.start1.clicked.connect(lambda: self._start(1))
        self.start5.clicked.connect(lambda: self._start(5))
        top.addWidget(self.start1)
        top.addWidget(self.start5)
        layout.addLayout(top)

        self.info_label = QLabel(self)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

    def _start(self, times: int) -> None:
        game = self.panel.game
        if game is None:
            return
        game.start_refine(self.recipe_id, times)
        self.panel.refresh()

    def refresh(self) -> None:
        panel = self.panel
        recipe = panel.recipe(self.recipe_id)
        if recipe is None:
            self.name_label.setText(f"Unknown recipe: {self.recipe_id}")
            self.info_label.setText("")
            self.start1.setEnabled(False)
            self.start5.setEnabled(False)
            return

        name = str(_get(recipe, "name", self.recipe_id))
        unlocked = panel.is_recipe_unlocked(self.recipe_id)
        catalog = panel.catalog
        inputs = _format_items(_get(recipe, "inputs", {}), catalog)
        outputs = _format_items(_get(recipe, "outputs", {}), catalog)
        ticks = int(_get(recipe, "ticks", 0))
        price = panel.output_price(recipe)
        info = f"In: {inputs}  →  Out: {outputs} · {ticks} ticks · out price {price}"

        if not unlocked:
            unlocked_by = _get(recipe, "unlocked_by")
            requirement = panel.requirement_title(unlocked_by) if unlocked_by else str(unlocked_by)
            info = f"Locked — unlock with the achievement {requirement}. {info}"
            self.name_label.setText(f"{name} (locked)")
            self.name_label.setStyleSheet(f"color: {DISABLED_TEXT}; font-weight: bold;")
            self.info_label.setStyleSheet(f"color: {DISABLED_TEXT};")
            self.setStyleSheet(f"QFrame {{ border: 1px solid {BUTTON_BORDER}; }}")
            self.info_label.setText(info)
            self.start1.setEnabled(False)
            self.start5.setEnabled(False)
            self.start1.setToolTip("Recipe locked")
            self.start5.setToolTip("Recipe locked")
            return

        self.name_label.setText(name)
        self.name_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        self.info_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.setStyleSheet(f"QFrame {{ border: 1px solid {BUTTON_BORDER}; }}")
        self.info_label.setText(info)

        warehouse = panel.warehouse()
        inputs_ready = True
        if warehouse is not None:
            recipe_inputs = _get(recipe, "inputs", {})
            inputs_ready = all(
                warehouse.count(item) >= int(count) for item, count in recipe_inputs.items()
            )
        else:
            inputs_ready = False
        refinery = panel.refinery()
        slot_free = True
        if refinery is not None:
            slot_free = len(_get(refinery, "jobs", [])) < int(_get(refinery, "slots", 1))

        enabled = inputs_ready and slot_free
        for button in (self.start1, self.start5):
            button.setEnabled(enabled)
        if not inputs_ready:
            tooltip = "Not enough inputs in the warehouse"
        elif not slot_free:
            tooltip = "No free furnace slot"
        else:
            tooltip = "Start refining"
        self.start1.setToolTip(tooltip)
        self.start5.setToolTip(tooltip)


class _ContractCard(QFrame):
    """One delivery contract card with its time-left bar and Deliver button."""

    def __init__(self, status: dict[str, Any], panel: BasePanel) -> None:
        super().__init__()
        self.contract_id = int(status.get("id", 0))
        self.panel = panel
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        top = QHBoxLayout()
        self.title_label = QLabel(self)
        self.title_label.setWordWrap(True)
        top.addWidget(self.title_label, 1)
        self.deliver = QPushButton("Deliver", self)
        self.deliver.clicked.connect(self._deliver)
        top.addWidget(self.deliver)
        layout.addLayout(top)

        self.reward_label = QLabel(self)
        layout.addWidget(self.reward_label)
        self.time_bar = QProgressBar(self)
        layout.addWidget(self.time_bar)
        self.refresh(status)

    def _deliver(self) -> None:
        game = self.panel.game
        if game is None:
            return
        game.deliver_contract(self.contract_id)
        self.panel.refresh()

    def refresh(self, status: dict[str, Any]) -> None:
        panel = self.panel
        item_id = str(status.get("item", ""))
        name = str(status.get("name") or _item_name(panel.catalog, item_id))
        quantity = int(status.get("quantity", 0))
        reward = int(status.get("reward", 0))
        self.title_label.setText(f"{name} ×{quantity}")
        self.title_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        self.reward_label.setText(f"Reward: {reward} money")
        self.reward_label.setStyleSheet(f"color: {TEXT_DIM};")

        created = int(status.get("created", 0))
        deadline = int(status.get("deadline", created + 1))
        ticks_left = int(status.get("ticks_left", max(0, deadline - created)))
        duration = max(1, deadline - created)
        self.time_bar.setRange(0, duration)
        self.time_bar.setValue(max(0, min(duration, ticks_left)))
        self.time_bar.setFormat(f"{ticks_left} ticks left")

        warehouse = panel.warehouse()
        ready = warehouse is not None and warehouse.count(item_id) >= quantity
        self.deliver.setEnabled(ready)
        if ready:
            self.deliver.setToolTip("Deliver the full quantity from the warehouse")
        else:
            self.deliver.setToolTip(
                f"Need {quantity}× {name} in the warehouse "
                f"(have {warehouse.count(item_id) if warehouse is not None else 0})"
            )


class BasePanel(FloatingPanel):
    """Floating base panel with warehouse, refinery and contract tabs."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Base"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        content = kwargs.pop("content", None)
        progression = kwargs.pop("progression", None) or kwargs.pop("progression_view", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget) and parent is None:
                parent = arg
            elif hasattr(arg, "config") and hasattr(arg, "recipes"):
                if content is None:
                    content = arg
            elif hasattr(arg, "is_recipe_unlocked"):
                if progression is None:
                    progression = arg
            elif hasattr(arg, "engine") and hasattr(arg, "miner"):
                if game is None:
                    game = arg
        if kwargs:
            raise TypeError(f"unexpected arguments: {sorted(kwargs)}")
        self.game = game
        if game is not None:
            if content is None:
                content = _get(game, "content")
            if progression is None:
                progression = (
                    _get(game, "progression_service")
                    or _get(game, "progression")
                    or _get(game, "progression_view")
                )
        self.content_data = content
        self.progression = progression

        super().__init__(title, parent=parent)
        if not self._restored_geometry:
            self.resize(780, 570)
            self.move(180, 70)

        self.tabs = QTabWidget(self.content_widget)
        self.content_layout.addWidget(self.tabs)

        self.warehouse_table: QTableWidget
        self.capacity_bar: QProgressBar
        self.sell_everything_button: QPushButton
        self.inventory_label: QLabel
        self.unload_button: QPushButton
        self.unload_hint: QLabel
        self.warehouse_rows: dict[str, dict[str, QPushButton]] = {}

        self.recipe_rows: dict[str, _RecipeRow] = {}
        self.slot_bars: list[QProgressBar] = []
        self.contract_cards: dict[int, _ContractCard] = {}
        self._unsubscribers: list[Any] = []

        self._build_warehouse_tab()
        self._build_refinery_tab()
        self._build_contracts_tab()
        self._rebuild_recipe_rows()
        self.refresh()
        self._subscribe()

    # -- tab construction ----------------------------------------------------

    def _build_warehouse_tab(self) -> None:
        tab = QWidget(self.tabs)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.capacity_bar = QProgressBar(tab)
        self.capacity_bar.setRange(0, 1)
        self.capacity_bar.setValue(0)
        self.capacity_bar.setTextVisible(True)
        layout.addWidget(self.capacity_bar)

        self.warehouse_table = QTableWidget(0, 6, tab)
        self.warehouse_table.setHorizontalHeaderLabels(
            ["Item", "Count", "Price", "Total value", "", ""]
        )
        self.warehouse_table.verticalHeader().setVisible(False)
        self.warehouse_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.warehouse_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.warehouse_table.setAlternatingRowColors(True)
        header = self.warehouse_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.warehouse_table, 1)

        self.sell_everything_button = QPushButton("Sell everything", tab)
        self.sell_everything_button.clicked.connect(self._sell_everything)
        layout.addWidget(self.sell_everything_button, 0, Qt.AlignmentFlag.AlignRight)

        inventory = QFrame(tab)
        inventory.setFrameShape(QFrame.Shape.StyledPanel)
        inventory_layout = QVBoxLayout(inventory)
        inventory_layout.setContentsMargins(6, 4, 6, 4)
        inventory_layout.setSpacing(2)
        inventory_row = QHBoxLayout()
        self.inventory_label = QLabel("Drone 0 inventory: empty", inventory)
        self.inventory_label.setWordWrap(True)
        inventory_row.addWidget(self.inventory_label, 1)
        self.unload_button = QPushButton("Unload", inventory)
        self.unload_button.clicked.connect(self._unload)
        inventory_row.addWidget(self.unload_button)
        inventory_layout.addLayout(inventory_row)
        self.unload_hint = QLabel("", inventory)
        self.unload_hint.setStyleSheet(f"color: {TEXT_DIM};")
        self.unload_hint.setWordWrap(True)
        inventory_layout.addWidget(self.unload_hint)
        layout.addWidget(inventory)

        self.tabs.addTab(tab, "Warehouse")

    def _build_refinery_tab(self) -> None:
        tab = QWidget(self.tabs)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hint = QLabel("Refinery recipes and furnace slots.", tab)
        hint.setStyleSheet(f"color: {TEXT_DIM};")
        layout.addWidget(hint)

        scroll = QScrollArea(tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget(scroll)
        self.recipe_rows_layout = QVBoxLayout(container)
        self.recipe_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.recipe_rows_layout.setSpacing(3)
        self.recipe_rows_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        slots_label = QLabel("Furnace slots", tab)
        slots_label.setStyleSheet(f"color: {TEXT}; font-weight: bold;")
        layout.addWidget(slots_label)
        self.slots_container = QWidget(tab)
        self.slots_layout = QVBoxLayout(self.slots_container)
        self.slots_layout.setContentsMargins(0, 0, 0, 0)
        self.slots_layout.setSpacing(2)
        layout.addWidget(self.slots_container)
        self._ensure_slot_bars()

        self.tabs.addTab(tab, "Refinery")

    def _build_contracts_tab(self) -> None:
        tab = QWidget(self.tabs)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.contracts_empty_label = QLabel("No contracts yet.", tab)
        self.contracts_empty_label.setStyleSheet(f"color: {TEXT_DIM};")
        layout.addWidget(self.contracts_empty_label)

        scroll = QScrollArea(tab)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget(scroll)
        self.contracts_layout = QVBoxLayout(container)
        self.contracts_layout.setContentsMargins(0, 0, 0, 0)
        self.contracts_layout.setSpacing(4)
        self.contracts_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        self.tabs.addTab(tab, "Contracts")

    def _rebuild_recipe_rows(self) -> None:
        while self.recipe_rows_layout.count():
            item = self.recipe_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self.recipe_rows = {}
        recipes = _get(self.content_data, "recipes", {}) or {}
        if isinstance(recipes, dict):
            entries = list(recipes.values())
        else:
            entries = []
        for recipe in entries:
            recipe_id = str(_get(recipe, "id", ""))
            if not recipe_id:
                continue
            row = _RecipeRow(recipe_id, self)
            self.recipe_rows_layout.addWidget(row)
            self.recipe_rows[recipe_id] = row
        self.recipe_rows_layout.addStretch(1)

    def _ensure_slot_bars(self) -> None:
        refinery = self.refinery()
        slots = max(1, int(_get(refinery, "slots", 1) or 1))
        if len(self.slot_bars) == slots:
            return
        while self.slots_layout.count():
            item = self.slots_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self.slot_bars = []
        for index in range(slots):
            bar = QProgressBar(self.slots_container)
            bar.setRange(0, 1)
            bar.setValue(0)
            bar.setFormat(f"Slot {index + 1}: idle")
            self.slots_layout.addWidget(bar)
            self.slot_bars.append(bar)

    # -- state helpers -------------------------------------------------------

    def catalog(self) -> Any:
        """Return the item catalog (engine catalog when available)."""
        catalog = _get(_get(self.game, "engine"), "catalog")
        if catalog is None and self.content_data is not None:
            from minesim.core.items import ItemCatalog

            catalog = ItemCatalog(self.content_data)
        return catalog

    def warehouse(self) -> Any:
        """Return the base warehouse."""
        return _get(_get(self.game, "engine"), "warehouse") or _get(self.game, "warehouse")

    def refinery(self) -> Any:
        """Return the refinery."""
        return _get(_get(self.game, "engine"), "refinery")

    def market(self) -> Any:
        """Return the market."""
        return _get(_get(self.game, "engine"), "market")

    def recipe(self, recipe_id: str) -> Any:
        """Return recipe ``recipe_id`` from the content or None."""
        recipes = _get(self.content_data, "recipes", {})
        if isinstance(recipes, dict):
            return recipes.get(str(recipe_id))
        return None

    def is_recipe_unlocked(self, recipe_id: str) -> bool:
        """Return True when the recipe is unlocked."""
        checker = getattr(self.progression, "is_recipe_unlocked", None)
        if callable(checker):
            try:
                return bool(checker(str(recipe_id)))
            except Exception:
                pass
        recipe = self.recipe(recipe_id)
        return _get(recipe, "unlocked_by") is None

    def requirement_title(self, achievement_id: Any) -> str:
        """Return a human-readable achievement title for ``achievement_id``."""
        if achievement_id is None:
            return ""
        getter = getattr(self.progression, "requirement_title", None)
        if callable(getter):
            try:
                return str(getter("achievement", str(achievement_id)))
            except Exception:
                pass
        return str(achievement_id).replace("_", " ").title()

    def output_price(self, recipe: Any) -> str:
        """Return the current market prices of a recipe's outputs."""
        catalog = self.catalog()
        market = self.market()
        parts: list[str] = []
        outputs = _get(recipe, "outputs", {}) or {}
        for item_id, count in outputs.items():
            name = _item_name(catalog, item_id)
            if market is not None:
                try:
                    price = float(market.price(item_id))
                except Exception:
                    price = 0.0
            else:
                price = float(_get(catalog, "base_value", lambda _item: 0)(item_id))
            parts.append(f"{count}× {name} @ {price:.2f}")
        return ", ".join(parts) if parts else "—"

    def drone_zero(self) -> Any:
        """Return drone 0."""
        drones = _get(self.game, "drones")
        if isinstance(drones, dict):
            return drones.get(0)
        return _get(self.game, "miner")

    def drone_on_base(self, drone: Any) -> bool:
        """Return True when ``drone`` stands on the base tile."""
        world = _get(_get(self.game, "engine"), "world") or _get(self.game, "world")
        if world is None or drone is None:
            return False
        try:
            return bool(world.tile_at(drone.x, drone.y, int(_get(self.game, "tick", 0))).is_base)
        except Exception:
            return False

    # -- refresh -------------------------------------------------------------

    def refresh(self) -> None:
        """Re-read the warehouse, refinery and contract state."""
        self._refresh_warehouse()
        self._refresh_refinery()
        self._refresh_contracts()

    def _refresh_warehouse(self) -> None:
        warehouse = self.warehouse()
        catalog = self.catalog()
        market = self.market()
        items: list[tuple[str, int]] = []
        if warehouse is not None:
            items = [
                (str(item), int(count))
                for item, count in sorted(warehouse.items.items())
                if int(count) > 0
            ]
        self.warehouse_table.setRowCount(len(items))
        self.warehouse_rows = {}
        for row, (item_id, count) in enumerate(items):
            name = _item_name(catalog, item_id)
            if market is not None:
                try:
                    price = float(market.price(item_id))
                except Exception:
                    price = 0.0
            else:
                price = float(_get(catalog, "base_value", lambda _item: 0)(item_id))
            self.warehouse_table.setItem(row, 0, QTableWidgetItem(name))
            self.warehouse_table.setItem(row, 1, QTableWidgetItem(str(count)))
            self.warehouse_table.setItem(row, 2, QTableWidgetItem(f"{price:.2f}"))
            self.warehouse_table.setItem(row, 3, QTableWidgetItem(f"{price * count:.2f}"))

            sell = QPushButton("Sell", self.warehouse_table)
            sell.setToolTip("Sell one unit at the current market price")
            sell.clicked.connect(lambda _checked=False, item=item_id: self._sell(item, 1))
            sell_all = QPushButton("Sell all", self.warehouse_table)
            sell_all.setToolTip("Sell this whole stack")
            sell_all.clicked.connect(lambda _checked=False, item=item_id: self._sell(item, None))
            self.warehouse_table.setCellWidget(row, 4, sell)
            self.warehouse_table.setCellWidget(row, 5, sell_all)
            self.warehouse_rows[item_id] = {"sell": sell, "sell_all": sell_all}

        used = int(_get(warehouse, "total", lambda: 0)()) if warehouse is not None else 0
        capacity = int(_get(warehouse, "capacity", 0) or 0)
        self.capacity_bar.setRange(0, max(1, capacity))
        self.capacity_bar.setValue(min(used, max(1, capacity)))
        self.capacity_bar.setFormat(f"{used}/{capacity}")
        self.sell_everything_button.setEnabled(bool(items))

        drone = self.drone_zero()
        inventory = dict(_get(drone, "inventory", {}) or {}) if drone is not None else {}
        catalog_name = lambda item: _item_name(catalog, item)  # noqa: E731
        inventory_text = ", ".join(
            f"{catalog_name(item)} ×{count}" for item, count in sorted(inventory.items())
        )
        self.inventory_label.setText(
            f"Drone 0 inventory: {inventory_text}" if inventory_text else "Drone 0 inventory: empty"
        )
        on_base = self.drone_on_base(drone)
        has_items = any(int(count) > 0 for count in inventory.values())
        self.unload_button.setEnabled(on_base and has_items)
        if not on_base:
            self.unload_hint.setText("Drone 0 is not on the base — move it to (0, 0) to unload.")
            self.unload_button.setToolTip("The drone must stand on the base")
        elif not has_items:
            self.unload_hint.setText("Drone 0 is on the base with an empty inventory.")
            self.unload_button.setToolTip("Nothing to unload")
        else:
            self.unload_hint.setText("Drone 0 is on the base and can unload.")
            self.unload_button.setToolTip("Move the inventory into the warehouse")

    def _refresh_refinery(self) -> None:
        for row in self.recipe_rows.values():
            row.refresh()
        self._ensure_slot_bars()
        refinery = self.refinery()
        jobs = list(_get(refinery, "jobs", []) or [])
        statuses: list[dict[str, Any]] = []
        if refinery is not None and hasattr(refinery, "status"):
            try:
                statuses = list(refinery.status())
            except Exception:
                statuses = []
        elif jobs:
            statuses = [dict(job) for job in jobs]
        for index, bar in enumerate(self.slot_bars):
            if index >= len(statuses):
                bar.setRange(0, 1)
                bar.setValue(0)
                bar.setFormat(f"Slot {index + 1}: idle")
                bar.setStyleSheet("")
                continue
            status = statuses[index]
            duration = max(1, int(status.get("duration", 1) or 1))
            progress = float(status.get("progress", 0.0) or 0.0)
            percent = max(0, min(100, int(progress * 100)))
            bar.setRange(0, duration)
            bar.setValue(max(0, min(duration, int(progress * duration))))
            name = str(status.get("name") or status.get("recipe") or "job")
            times = int(status.get("times", 1) or 1)
            if bool(status.get("blocked", False)):
                bar.setFormat(f"Slot {index + 1}: BLOCKED — warehouse full")
                bar.setStyleSheet(f"QProgressBar::chunk {{ background-color: {ERROR}; }}")
            else:
                bar.setFormat(f"Slot {index + 1}: {name} ×{times} — {percent}%")
                bar.setStyleSheet("")

    def _refresh_contracts(self) -> None:
        while self.contracts_layout.count():
            item = self.contracts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        self.contract_cards = {}
        statuses: list[dict[str, Any]] = []
        board = _get(_get(self.game, "engine"), "contracts")
        if board is not None and hasattr(board, "status"):
            try:
                statuses = list(board.status())
            except Exception:
                statuses = []
        for status in statuses:
            card = _ContractCard(status, self)
            self.contracts_layout.addWidget(card)
            self.contract_cards[int(status.get("id", 0))] = card
        self.contracts_layout.addStretch(1)
        self.contracts_empty_label.setVisible(not bool(statuses))

    # -- actions -------------------------------------------------------------

    def _sell(self, item: str, amount: int | None) -> None:
        if self.game is None:
            return
        self.game.sell_stock(item, amount)
        self.refresh()

    def _sell_everything(self) -> None:
        if self.game is None:
            return
        warehouse = self.warehouse()
        items = list(warehouse.items) if warehouse is not None else []
        for item in items:
            self.game.sell_stock(item)
        self.refresh()

    def _unload(self) -> None:
        if self.game is None:
            return
        self.game.unload(0)
        self.refresh()

    # -- wiring --------------------------------------------------------------

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
        for event_type in (
            TickAdvanced,
            StockSold,
            Unloaded,
            RefineStarted,
            RefineFinished,
            ContractGenerated,
            ContractDelivered,
            ContractExpired,
            AchievementUnlocked,
        ):
            try:
                self._unsubscribers.append(bus.subscribe(event_type, self._on_event))
            except Exception:
                pass

    def _on_event(self, _event: Any) -> None:
        if self.isVisible():
            self.refresh()

    def set_game(self, game: Any) -> None:
        """Attach a new game, rebuild the recipe list and refresh."""
        self.game = game
        if game is not None:
            self.content_data = _get(game, "content")
            self.progression = (
                _get(game, "progression_service")
                or _get(game, "progression")
                or _get(game, "progression_view")
            )
        self._rebuild_recipe_rows()
        self.refresh()
        self._subscribe()

    def select_tab(self, name: str) -> None:
        """Select a tab by ``base``/``warehouse``/``refinery``/``contracts``."""
        key = _TAB_ALIASES.get(str(name).lower(), str(name).lower())
        labels = ["warehouse", "refinery", "contracts"]
        if key not in labels:
            return
        self.tabs.setCurrentIndex(labels.index(key))

    def current_tab(self) -> str:
        """Return the current tab key (``warehouse``/``refinery``/``contracts``)."""
        labels = ["warehouse", "refinery", "contracts"]
        index = self.tabs.currentIndex()
        return labels[index] if 0 <= index < len(labels) else "warehouse"

    def showEvent(self, event: Any) -> None:  # noqa: N802
        self.refresh()
        super().showEvent(event)
