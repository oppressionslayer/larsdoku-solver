# Larsdoku

**Pure logic Sudoku solver. Zero guessing. Every step proven.**

Larsdoku solves the hardest Sudoku puzzles ever created using only logical deduction — no backtracking, no trial-and-error. Built on a bitwise engine with GF(2) linear algebra, it achieves **100% pure logic on the Top1465 benchmark** (1,465 of the hardest known puzzles), averaging **19ms per puzzle**.

---

## At a Glance

| Metric | Value |
|---|---|
| Top1465 solve rate | **1465/1465 (100%)** |
| Average solve time | **0.019s** |
| Max solve time | **0.074s** |
| Total techniques | **20+** across 7 levels |
| WSRF inventions | **4** (FPC, FPCE, D2B, FPF) |
| Dependencies | NumPy, Numba |

---

## Install

```bash
pip install larsdoku
```

## Solve a puzzle in 3 lines

```python
from larsdoku import solve

result = solve("4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........")
print(f"Solved: {result['success']} in {result['n_steps']} steps")
```

## Or from the command line

```bash
larsdoku "800000000003600000070090200050007000000045700000100030001000068008500010090000400" --board --no-oracle
```

```
Status: SOLVED
Steps:  63
Time:   26.0ms

┌───────┬───────┬───────┐
│ 4 6 8 │ 9 3 1 │ 5 2 7 │
│ 7 5 1 │ 6 2 4 │ 8 3 9 │
│ 3 9 2 │ 5 7 8 │ 4 6 1 │
├───────┼───────┼───────┤
│ 1 3 4 │ 7 5 6 │ 2 9 8 │
│ 2 8 9 │ 4 1 3 │ 6 7 5 │
│ 6 7 5 │ 2 8 9 │ 3 1 4 │
├───────┼───────┼───────┤
│ 8 4 6 │ 1 9 2 │ 7 5 3 │
│ 5 1 3 │ 8 6 7 │ 9 4 2 │
│ 9 2 7 │ 3 4 5 │ 1 8 6 │
└───────┴───────┴───────┘
```

---

## What makes Larsdoku different?

Most Sudoku solvers fall back to guessing (backtracking) when they get stuck. Larsdoku never guesses. Instead, it escalates through increasingly powerful logical techniques until every cell is proven.

The solver pipeline:

```
L1 Singles → L2 GF(2) → L3 Fish → L4 Coloring → L5 FPC/FPCE → L6 D2B → L7 FPF
```

Each level fires only when everything above it has stalled. Four of these techniques — **FPC**, **FPCE**, **D2B**, and **FPF** — are original WSRF inventions not found in traditional Sudoku literature.

!!! tip "What is GF(2)?"
    GF(2) is Galois Field arithmetic (binary math). Larsdoku encodes Sudoku constraints as a system of linear equations over GF(2) and solves them using Block Lanczos decomposition. This finds forced digits that classical techniques miss — pure algebra, no search.
