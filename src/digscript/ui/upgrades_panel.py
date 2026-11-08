"""Upgrades panel (key U): buy unlocked upgrades with the BuyUpgrade command.

Lists every upgrade with its level, effect, next cost and a Buy button
(disabled when money is short or the level is maxed). Locked upgrades show
which achievement unlocks them. Buying submits the same ``BuyUpgrade`` command
the player API uses.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from digscript.core.commands import BuyUpgrade
from digscript.core.events import AchievementUnlocked, Sold, UpgradeBought
from digscript.ui.floating_panel import FloatingPanel
from digscript.ui.theme import TEXT_DIM

__all__ = ["UpgradesPanel"]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class _UpgradeRow(QWidget):
    """One upgrade row: name, level/effect/cost info and a Buy button."""

    def __init__(self, upgrade_id: str, panel: UpgradesPanel) -> None:
        super().__init__()
        self.upgrade_id = upgrade_id
        self.panel = panel
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        self.info = QLabel(self)
        self.info.setWordWrap(True)
        layout.addWidget(self.info, 1)

        self.buy = QPushButton("Buy", self)
        self.buy.setFixedWidth(70)
        self.buy.clicked.connect(self._buy)
        layout.addWidget(self.buy)

        self.setLayout(layout)

    def _buy(self) -> None:
        game = self.panel.game
        if game is None:
            return
        ticket = game.submit(BuyUpgrade(self.upgrade_id))
        result = getattr(ticket, "result", None) or {}
        if not result.get("ok"):
            return
        self.panel.refresh()

    def refresh(self) -> None:
        panel = self.panel
        content = panel.content
        game = panel.game
        if content is None or game is None:
            self.info.setText("upgrade data unavailable")
            self.buy.setEnabled(False)
            return
        try:
            upgrade = content.get_upgrade(self.upgrade_id)
        except Exception:
            self.info.setText(f"unknown upgrade {self.upgrade_id}")
            self.buy.setEnabled(False)
            return

        miner = game.miner
        progression = panel.progression
        unlocked = (
            progression.is_upgrade_unlocked(self.upgrade_id) if progression is not None else False
        )

        level = int(getattr(miner, "upgrades", {}).get(self.upgrade_id, 0))
        max_level = int(upgrade.max_level)
        costs = list(upgrade.costs)

        # Effect description.
        changes = upgrade.stat_changes()
        effect = "; ".join(f"{stat} {delta:+d}" for stat, delta in changes.items()) or "—"

        if not unlocked:
            unlocked_by = _get(upgrade, "unlocked_by")
            requirement = ""
            if progression is not None and unlocked_by:
                requirement = progression.requirement_title("achievement", str(unlocked_by))
            self.info.setText(
                f"<b>{upgrade.name}</b> — locked (unlock with the achievement "
                f"{requirement or unlocked_by})"
            )
            self.buy.setEnabled(False)
            self.buy.setToolTip("")
            return

        # Locked-looking but actually unlocked: show cost/level.
        if level >= max_level or level >= len(costs):
            self.info.setText(
                f"<b>{upgrade.name}</b> — level {level}/{max_level} (maxed) · {effect}"
            )
            self.buy.setEnabled(False)
            self.buy.setToolTip("Maximum level reached")
            return

        cost = int(costs[level])
        money = int(getattr(miner, "money", 0))
        affordable = money >= cost
        self.info.setText(
            f"<b>{upgrade.name}</b> — level {level}/{max_level} · {effect} · "
            f"next cost {cost} (money {money})"
        )
        self.buy.setEnabled(affordable)
        self.buy.setToolTip("Buy now" if affordable else f"Need {cost} money (have {money})")


class UpgradesPanel(FloatingPanel):
    """Floating upgrades panel."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        title = kwargs.pop("title", None) or "Upgrades"
        parent = kwargs.pop("parent", None)
        game = kwargs.pop("game", None)
        content = kwargs.pop("content", None)
        progression = kwargs.pop("progression", None) or kwargs.pop("progression_view", None)
        for arg in args:
            if arg is None:
                continue
            if isinstance(arg, QWidget) and parent is None:
                parent = arg
            elif hasattr(arg, "config") and hasattr(arg, "upgrades"):
                if content is None:
                    content = arg
            elif hasattr(arg, "is_upgrade_unlocked"):
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
        self.progression = progression

        super().__init__(title, parent=parent)
        if not self._restored_geometry:
            self.resize(640, 520)
            self.move(520, 60)

        self.content = content

        body = QVBoxLayout()
        body.setContentsMargins(4, 4, 4, 4)
        body.setSpacing(4)
        hint = QLabel("Buy the next level of each unlocked upgrade.", self.content_widget)
        hint.setStyleSheet(f"color: {TEXT_DIM};")
        body.addWidget(hint)
        self.rows_container = QWidget(self.content_widget)
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        body.addWidget(self.rows_container, 1)
        body.addStretch(1)
        self.content_layout.addLayout(body)

        self._rows: dict[str, _UpgradeRow] = {}
        self._build_rows()
        self.refresh()
        self._subscribe()

    def _build_rows(self) -> None:
        if self.content is None:
            return
        upgrades = _get(self.content, "upgrades")
        if isinstance(upgrades, dict):
            items = list(upgrades.values())
        elif isinstance(upgrades, (list, tuple)):
            items = list(upgrades)
        else:
            items = []
        for entry in items:
            uid = str(_get(entry, "id", ""))
            if not uid or uid in self._rows:
                continue
            row = _UpgradeRow(uid, self)
            self.rows_layout.addWidget(row)
            self._rows[uid] = row

    def refresh(self) -> None:
        for row in self._rows.values():
            row.refresh()

    def _subscribe(self) -> None:
        if self.game is None:
            return
        bus = _get(self.game, "events") or _get(self.game, "event_bus")
        if bus is None or not hasattr(bus, "subscribe"):
            return
        try:
            bus.subscribe(UpgradeBought, lambda _e: self.refresh())
            bus.subscribe(Sold, lambda _e: self.refresh())
            bus.subscribe(AchievementUnlocked, lambda _e: self.refresh())
        except Exception:
            return

    def set_game(self, game: Any) -> None:
        """Attach a (new) game and refresh."""
        self.game = game
        if game is not None:
            self.content = _get(game, "content")
            self.progression = (
                _get(game, "progression_service")
                or _get(game, "progression")
                or _get(game, "progression_view")
            )
        self.refresh()
        self._subscribe()

    def showEvent(self, event: Any) -> None:  # noqa: N802
        self.refresh()
        super().showEvent(event)
