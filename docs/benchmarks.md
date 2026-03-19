# Benchmarks

## Results Summary

| Collection | Puzzles | Pure Logic | Avg Time | Max Time | Total |
|---|---|---|---|---|---|
| **Top1465** | 1,465 | **100% (1465/1465)** | 0.019s | 0.074s | 28s |
| **Expert 669** | 669 | **100% (669/669)** | 0.036s | 0.374s | 24s |
| **Famous 10** | 10 | **70% (7/10)** | 0.50s | 1.65s | 5s |

---

## Top1465

The canonical benchmark. 1,465 of the hardest known Sudoku puzzles, compiled by Guenter Stertenbrink (dukuso) and rated by his suexrat9 program. These are the puzzles that break most solvers.

**Larsdoku result: 1465/1465 — 100% pure logic. Zero guessing.**

```
========================================================================
  WSRF Bitwise Engine — Top1465 Benchmark
========================================================================
  Total puzzles:       1465
  Pure logic solves:   1465/1465 (100.0%)
  Total steps:         86,289
  Total time:          28.1s
  Avg time/puzzle:     0.0192s
  Max time/puzzle:     0.0740s
  Under 1s:            1465/1465 (100.0%)

TECHNIQUE FREQUENCY:
  crossHatch            42,852x  ( 49.4%)
  nakedSingle           21,382x  ( 24.6%)
  lastRemaining         13,510x  ( 15.6%)
  FPC                    4,050x  (  4.7%)
  fullHouse              3,826x  (  4.4%)
  FPCE                     453x  (  0.5%)
  SimpleColoring           354x  (  0.4%)
  GF2_Lanczos              216x  (  0.2%)
  XWing                     90x  (  0.1%)
  Swordfish                 44x  (  0.1%)
```

### Run it yourself

```bash
larsdoku-bench --collection top1465
```

---

## Famous 10

The 10 hardest famous Sudoku puzzles ever published.

| Puzzle | Author | Year | Result |
|---|---|---|---|
| AI Escargot | Arto Inkala | 2006 | SOLVED |
| Inkala's World's Hardest | Arto Inkala | 2012 | SOLVED |
| Golden Nugget | tarek | 2007 | SOLVED |
| Easter Monster | champagne | 2007 | SOLVED |
| Maze (17-clue) | tarek | 2007 | SOLVED |
| champagne's Burst | champagne | 2008 | SOLVED |
| Kolk's Reciprocal | gsfk (Kolk) | 2008 | SOLVED |
| Platinum Blonde | coloin | 2005 | stalled |
| Pearly Gates | coloin | 2006 | stalled |
| 17-clue Hardest (Royle #1) | Gordon Royle | 2005 | stalled |

The 3 stalled puzzles are minimal-clue puzzles (17-21 clues) that require techniques beyond the current L7 pipeline. These represent the frontier for future technique development.

```bash
larsdoku-bench --collection famous
```

---

## Expert 669

669 expert-level puzzles, box-shuffled from a curated collection. All verified unique-solution. **100% pure logic solve rate.**

```bash
larsdoku-bench --collection expert
```

---

## Context: How Other Solvers Compare

For perspective on the Top1465:

| Solver Type | Typical Pure Logic Rate | Guesses Needed |
|---|---|---|
| Basic backtracker | 0% | All puzzles need guessing |
| Probabilistic solver | ~33% | Frequent guessing |
| Traditional logic solver | ~60-80% | Moderate guessing |
| Advanced solver (w/ chains) | ~92-95% | Occasional guessing |
| **Larsdoku** | **100%** | **Zero** |

---

## Reproducing Results

All benchmarks can be reproduced:

```bash
# Full suite
larsdoku-bench

# Individual collections
larsdoku-bench --collection top1465
larsdoku-bench --collection expert
larsdoku-bench --collection famous

# Quick verification (first 50 of Top1465)
larsdoku-bench --collection top1465 --limit 50
```

Results may vary slightly in timing depending on hardware, but solve rates should be identical.
