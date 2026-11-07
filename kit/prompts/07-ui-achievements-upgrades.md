# Prompt 7 of 8: UI achievements (key L), upgrades and saving

Follow AGENTS.md. Add the achievements screen (key L, like Minecraft advancements), the upgrades panel, notifications and saving.

1. ui/achievements_panel.py: large FloatingPanel with one tab per achievements.json tab (Code, Mining, Business). The tree is drawn with QGraphicsScene and QGraphicsView: rounded square nodes with an icon letter, lines from parent to child. The layout is a pure function layout_tree(nodes) -> {id: (col, row)} (column = depth, rows chosen so siblings never overlap) with unit tests. Node states: completed (filled, check mark), available (outlined, progress ring), locked (dimmed). Tooltip: title, description, progress such as 7/20, and rewards such as Unlocks: scan() function. Drag to pan; Esc or L closes it.
2. ui/upgrades_panel.py (key U): the unlocked upgrades with level, effect, next cost and a Buy button (disabled when money is short or the level is maxed); locked upgrades show which achievement unlocks them. Buying uses the same BuyUpgrade command as the API.
3. ui/toasts.py: a non-blocking toast in the top-right corner when AchievementUnlocked fires (title and reward line, 4 s, queued if several).
4. Saving: autosave every 30 s of wall-clock and on close through Game.save; a small menu (F10) with New game and Load.
5. Tests: layout_tree (no overlaps, parents left of children); node states after events; keyboard toggles; buying an upgrade changes the miner stats and the money; toast queue.

ACCEPTANCE: the screenshot of the L screen shows the three tabs with the first nodes completed after the starter script ran.
COMMIT: feat(ui): achievements, upgrades and toasts
