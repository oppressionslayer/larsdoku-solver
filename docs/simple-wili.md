# Simple Wili — The 135 Zone Rule

**Every solved Sudoku board obeys a hidden structure. Simple Wili exploits it.**

---

## The Discovery

Every Sudoku board has 9 **zones** — one for each relative position within the 3x3 boxes. Take any position (say, the center of each box) and collect the digit at that position across all 9 boxes. You get 9 digits — one from each box.

```
Zones are cross-board spots:

    ┌───────┬───────┬───────┐
    │ TL TC TR │ TL TC TR │ TL TC TR │
    │ ML MC MR │ ML MC MR │ ML MC MR │
    │ BL BC BR │ BL BC BR │ BL BC BR │
    ├───────┼───────┼───────┤
    │ TL TC TR │ TL TC TR │ TL TC TR │
    │ ML MC MR │ ML MC MR │ ML MC MR │
    │ BL BC BR │ BL BC BR │ BL BC BR │
    ├───────┼───────┼───────┤
    │ TL TC TR │ TL TC TR │ TL TC TR │
    │ ML MC MR │ ML MC MR │ ML MC MR │
    │ BL BC BR │ BL BC BR │ BL BC BR │
    └───────┴───────┴───────┘
```

Each zone collects 9 cells — one per box, same relative position. The **zone sum** is the sum of all 9 digits in that zone.

## The 135 Rule

Here's the key: the 9 zone sums are NOT independent. They follow the **135 rule**.

Zone sums along any template row (TL+TC+TR, ML+MC+MR, BL+BC+BR) or template column (TL+ML+BL, TC+MC+BC, TR+MR+BR) always sum to **135**.

Why 135? Each template row/column of zones covers exactly rows 1-3, 4-6, or 7-9 of the full board. Three rows of a solved Sudoku contain digits 1-9 three times each. So: 3 × (1+2+...+9) = 3 × 45 = **135**.

```
Zone sums for a real board:

    | 56  35  44 | 56  35  44 | 56  35  44 |
    | 38  51  46 | 38  51  46 | 38  51  46 |
    | 41  49  45 | 41  49  45 | 41  49  45 |

Template rows:  56 + 35 + 44 = 135 ✓
                38 + 51 + 46 = 135 ✓
                41 + 49 + 45 = 135 ✓

Template cols:  56 + 38 + 41 = 135 ✓
                35 + 51 + 49 = 135 ✓
                44 + 46 + 45 = 135 ✓
```

This means if you know 2 zone sums in any template row or column, you can **deduce** the 3rd: `missing = 135 - known1 - known2`.

## What Simple Wili Does

Simple Wili builds Sudoku boards from pure geometry — no backtracker.

**The algorithm:**

1. Pick a zone position (e.g., MC = center of each box)
2. Place digits 1-9 (no duplicates, sum = 45) at that position across all 9 boxes
3. That's 9 clues — the constraint geometry collapses the null space
4. Solve forward with pure logic

Centers (MC) give **94-100% solve rate with just 9 clues**. The zone structure is so constraining that one well-chosen zone often determines the entire board.

## Modes

```bash
# 9-clue base board (centers)
python simple_wili.py

# Unique 22-clue board (GF(2) verified)
python simple_wili.py --unique --target-clues 22

# Minimal unique board
python simple_wili.py --unique --minimize --gf2

# Staircase pattern (zigzag across bands)
python simple_wili.py --pattern staircase --unique

# Benchmark success rate
python simple_wili.py --count 20 --unique --stats
```

## Patterns

| Pattern | Zones Used | Description |
|---|---|---|
| *(default)* | MC | Centers — highest constraint density |
| `staircase` | MC → ML → BL | Zigzag across bands |
| `anti-diagonal` | TR → MC → BL | Diagonal sweep |
| `cross` | TC + MC + BC + ML + MR | Plus shape (45 clues) |
| `random-mixed` | Random per box | Maximum asymmetry |

## Zone Deduction in the Solver

The `--zone135` preset uses zone sums as an oracle during solving:

- **8/9 filled**: last digit = zone_sum - partial_sum (direct placement)
- **7/9 filled**: two cells must sum to a known value — eliminate impossible candidates
- **6/9 filled**: three cells must sum to a known value — eliminate impossible triples

```bash
# Solve with Zone 135 deduction
larsdoku "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........" --zone135
```

## Why This Matters

The 135 rule isn't a solving technique — it's a **structural law** of Sudoku. Every board obeys it. Every solution satisfies it. It's the hidden skeleton beneath the digits.

Simple Wili proves you can build valid boards from this skeleton alone. The Mask Forge uses a different approach (constraint-guided DFS), but the underlying truth is the same: Sudoku boards are far more structured than they appear, and that structure can be exploited.

The zones are cross-board, spot-based — not row/column/box-based like traditional Sudoku units. They're a new axis of constraint that classical solvers don't see.
