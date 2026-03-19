# Puzzle Collections

Larsdoku ships with three built-in puzzle collections for testing, benchmarking, and exploration.

```python
from larsdoku.puzzles import FAMOUS_10, EXPERT_669, TOP1465
```

---

## Famous 10

The 10 hardest famous Sudoku puzzles ever published. Each has been verified to have exactly one solution.

```python
from larsdoku.puzzles import FAMOUS_10

for name, author, year, puzzle in FAMOUS_10:
    print(f"{name} by {author} ({year})")
    print(f"  {puzzle}")
```

### The Puzzles

| # | Name | Author | Year | Clues |
|---|---|---|---|---|
| 1 | AI Escargot | Arto Inkala | 2006 | 23 |
| 2 | Inkala's World's Hardest | Arto Inkala | 2012 | 23 |
| 3 | Golden Nugget | tarek | 2007 | 22 |
| 4 | Easter Monster | champagne | 2007 | 22 |
| 5 | Platinum Blonde | coloin | 2005 | 21 |
| 6 | Maze (17-clue) | tarek | 2007 | 17 |
| 7 | champagne's Burst | champagne | 2008 | 21 |
| 8 | Kolk's Reciprocal | gsfk (Kolk) | 2008 | 24 |
| 9 | Pearly Gates | coloin | 2006 | 22 |
| 10 | 17-clue Hardest (Royle #1) | Gordon Royle | 2005 | 17 |

### Solve them all

```python
from larsdoku import solve
from larsdoku.puzzles import FAMOUS_10

for name, author, year, puzzle in FAMOUS_10:
    result = solve(puzzle, no_oracle=True)
    status = "SOLVED" if result['success'] else f"STALLED ({result['empty_remaining']} remain)"
    print(f"{name:30s}  {status}")
```

---

## Expert 669

669 expert-level puzzles. Each puzzle has been:

- Verified to have exactly one solution
- Box-shuffled (row bands, column bands, rows within bands, columns within bands, digit relabeling, and random transposition) to ensure originality

```python
from larsdoku.puzzles import EXPERT_669

print(f"{len(EXPERT_669)} puzzles")
print(f"First puzzle: {EXPERT_669[0]}")
```

### Batch solve

```python
from larsdoku import solve
from larsdoku.puzzles import EXPERT_669

results = [solve(p, no_oracle=True) for p in EXPERT_669]
pure = sum(1 for r in results if r['success'])
print(f"Pure logic: {pure}/{len(EXPERT_669)}")
```

---

## Top1465

The canonical benchmark compiled by Guenter Stertenbrink (dukuso). 1,465 of the hardest Sudoku puzzles known, sorted by his suexrat9 difficulty rating. Hosted at magictour.free.fr/sudoku.htm since the mid-2000s.

This is the gold standard benchmark for evaluating Sudoku solvers. Most solvers cannot achieve 100% pure logic on this set.

```python
from larsdoku.puzzles import TOP1465

print(f"{len(TOP1465)} puzzles")
print(f"First puzzle: {TOP1465[0]}")
```

!!! note
    Top1465 puzzles use `.` for empty cells. Larsdoku handles both `.` and `0` formats automatically.

### The history

The Top1465 was assembled in the mid-2000s during the global Sudoku boom. Stertenbrink collected the hardest puzzles from various sources — including Gordon Royle's minimal 17-clue collection and contributions from the enjoysudoku.com forum community. He selected puzzles that were hardest for his backtracking solver and rated them using suexrat9.

The collection became the standard benchmark because it represents a genuine difficulty gradient — some puzzles yield to intermediate techniques, while others require the most sophisticated logic known.

---

## Using Collections from the CLI

```bash
# Benchmark all collections
larsdoku-bench

# Benchmark a specific collection
larsdoku-bench --collection top1465
larsdoku-bench --collection expert
larsdoku-bench --collection famous

# Quick test
larsdoku-bench --collection top1465 --limit 50
```
