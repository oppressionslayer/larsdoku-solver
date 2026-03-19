"""Larsdoku — Built-in puzzle collections for benchmarking.

Collections:
  FAMOUS_10     — 10 hardest famous Sudoku puzzles (all unique solution)
  EXPERT_669    — 669 expert-level puzzles, box-shuffled for originality
  TOP1465       — The canonical Top1465 benchmark (Stertenbrink/dukuso)

Usage:
  from larsdoku.puzzles import FAMOUS_10, EXPERT_669, TOP1465
"""
from __future__ import annotations

from larsdoku.expert_669 import EXPERT_669
from larsdoku.top1465 import TOP1465

# ══════════════════════════════════════════════════════════════
# FAMOUS 10 — Hardest famous Sudoku puzzles ever published
# ══════════════════════════════════════════════════════════════

FAMOUS_10 = [
    # (name, author, year, puzzle_string)
    ("AI Escargot", "Arto Inkala", 2006,
     "100007090030020008009600500005300900010080002600004000300000010040000007007000300"),
    ("Inkala's World's Hardest", "Arto Inkala", 2012,
     "800000000003600000070090200050007000000045700000100030001000068008500010090000400"),
    ("Golden Nugget", "tarek", 2007,
     "000000039000010005003005800008009006070020000100400000009008050020000600400700000"),
    ("Easter Monster", "champagne", 2007,
     "100000002090400050006000700050903000000070000000850040700000600030009080002000001"),
    ("Platinum Blonde", "coloin", 2005,
     "000000012000000003002300400001800005060070800000009000008500009000040050047006000"),
    ("Maze (17-clue)", "tarek", 2007,
     "000000010400000000020000000000050407008000300001090000300400200050100000000806000"),
    ("champagne's Burst", "champagne", 2008,
     "000000000000003085001020000000507000004000100090000000500000073002010000000040009"),
    ("Kolk's Reciprocal", "gsfk (Kolk)", 2008,
     "000700800006000031040002000024070000010030080000060290000800070860000500002006000"),
    ("Pearly Gates", "coloin", 2006,
     "000000000000036000007000200060070009000200080100004000003000700800620000000100005"),
    ("17-clue Hardest (Royle #1)", "Gordon Royle", 2005,
     "000000010000003200050060000000080004090000000000100700700000800010200000000040060"),
]
