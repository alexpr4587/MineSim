# Social posts

Replace `[repository link]` with `https://github.com/alexpr4587/MineSim`
before posting. Keep the tone plain: describe what the game is and what the
player does, without promising more than the build delivers.

## Show HN

**Show HN: MineSim – a mining game where you automate the base with real Python**

I made a small 2D top-down game about a mining robot. The editor is inside the
game, and the scripts are ordinary Python: loops, functions, modules, classes
and a shared key/value memory for a fleet of miners.

The world is infinite and seeded, every ore has its own mining probability, and
achievements unlock API functions and Python modules as you play. There is a
warehouse, a market with price history, a refinery and delivery contracts.

It runs on Windows and Linux, and it is MIT licensed. Scripts run in a separate
subprocess with a restricted namespace, but that is not a security sandbox, so
only run scripts you trust.

Downloads: [repository link]

I would especially like feedback from people who teach Python or play
automation games: is the first script easy to find, and does the progression
make sense?

## Reddit (Python or incremental games)

**I made a mining game where you automate everything with real Python**

MineSim is a 2D top-down game with a Python editor inside it. You start with one
miner, write a loop, and slowly unlock a fleet, a warehouse, a market, a
refinery and deeper layers.

Some details that might be interesting here:

- Every ore has a separate mining probability, so route planning is a small
  data problem.
- Miners have batteries, heat and shared ventilation, so automation has real
  constraints.
- Each miner runs its own script and the fleet shares typed key/value memory.
- Achievements unlock API functions and Python modules, including `itertools`,
  `functools`, `dataclasses` and `typing`.
- The release build is Windows and Linux, and the project is MIT licensed.

It is not a security sandbox; the script subprocess has a restricted namespace,
so only run scripts you trust.

Repository and downloads: [repository link]

Happy to answer questions about the architecture or the progression.

## Short video captions

1. **One miner to a fleet.** "I wrote a Python loop, then gave every miner its
   own script. This is the same base ten minutes later." [repository link]

2. **The market bot.** "Mine ore, refine bars, and sell only when the price is
   above the recent average. The chart is the fun part." [repository link]

3. **Going deeper.** "Four layers, one shaft, and a ventilation budget. The
   script has to cool down before the miner does." [repository link]
