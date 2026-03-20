# Larsdoku

**Pure logic Sudoku solver. Zero guessing. Every step proven.**

**Documentation: [larsdoku-docs.netlify.app](https://larsdoku-docs.netlify.app/)**

**Web App (WIP): [larsdoku.netlify.app](https://larsdoku.netlify.app/)** — click Expert mode tab to open the Top-N Solver

**New techniques `--preset larstech` from:** [wsrf-sudoku-solved-series](https://github.com/oppressionslayer/wsrf-sudoku-solved-series)

Larsdoku solves the hardest Sudoku puzzles ever created using only logical deduction — no backtracking, no trial-and-error. Built on a bitwise engine with GF(2) linear algebra, it achieves **100% pure logic on the Top1465 benchmark** (1,465 of the hardest known puzzles), averaging **19ms per puzzle**.

```
pip install larsdoku
```

### Troubleshooting

If `larsdoku` fails on startup with a Numba cache error (`no locator available`):

```bash
export NUMBA_CACHE_DIR="$HOME/.cache/numba"
mkdir -p "$NUMBA_CACHE_DIR"
larsdoku "<puzzle>" --board
```

Or as a one-liner:

```bash
NUMBA_CACHE_DIR="$HOME/.cache/numba" larsdoku "<puzzle>" --board
```

---

## Quick Start

### Python API

```python
from larsdoku import solve

result = solve("4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........")

print(result['success'])           # True
print(result['n_steps'])           # 63
print(result['technique_counts'])  # {'crossHatch': 42, 'nakedSingle': 9, ...}
print(result['board'])             # solved 81-char string
```

### Command Line

```bash
# Solve and print the board
larsdoku "800000000003600000070090200050007000000045700000100030001000068008500010090000400" --board

# Pure logic only (no oracle fallback)
larsdoku "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........" --board --no-oracle

# Step-by-step trace
larsdoku "100007090030020008009600500005300900010080002600004000300000010040000007007000300" --steps

# Detailed round-by-round solve log
larsdoku "100000002090400050006000700050903000000070000000850040700000600030009080002000001" --detail --board

# Trace the full solution path to a specific cell
larsdoku "000004006000201090001070800060000020350000008000000370009080500040302000700100000" --cell R7C4 --path --preset expert
```

```
  ✦ Sudoku Expert Approved Techniques ✦

  R7C4 = 4 via lastRemaining (step 8)
  Candidates: [4, 6, 7]
  Full solve: 58 steps, COMPLETE
  Time: 697.2ms

  Verify: All techniques are Sudoku Expert Approved ✓
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

  Techniques used:
    ALS_XZ                10  L5
    ALS_XYWing             5  L5
    ForcingChain           3  L5
    crossHatch             3  L1
    lastRemaining          2  L1
    KrakenFish             1  L6

  Solution path (8 placements, 16 elimination rounds):
       ~elim~  [ALS_XZ L5] 1 eliminations
     #  1  R1C4=8  [lastRemaining L1]
     #  2  R3C8=5  [ForcingChain L5]
       ~elim~  [ALS_XZ L5] 1 eliminations
     #  3  R9C6=5  [crossHatch L1]
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [KrakenFish L6] 1 eliminations
     #  4  R1C8=1  [ForcingChain L5]
     #  5  R7C8=3  [ForcingChain L5]
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
     #  6  R4C6=3  [crossHatch L1]
     #  7  R6C6=8  [crossHatch L1]
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
   → #  8  R7C4=4  [lastRemaining L1]
```

### Board Forge — Generate Puzzles by Technique

```bash
# Generate a ForcingChain puzzle
larsdoku --board-forge MC --require ForcingChain --exclude als,alsxy,ape,fpc,fpce --board-forge-count 1

# Generate a DeathBlossom puzzle
larsdoku --board-forge MC --require DeathBlossom --exclude als,alsxy --board-forge-count 1

# Generate a KrakenFish puzzle
larsdoku --board-forge MC --require KrakenFish --board-forge-count 1 --require-attempts 200

# Generate pure ALS puzzles
larsdoku --board-forge MC --require ALS_XZ --board-forge-count 5

```

**The flex:** Puzzles generated with `--require ForcingChain` need FC to solve *when ALS is excluded*. But with the full solver, ALS-XZ handles what ForcingChain does — making FC unnecessary. The solver is sometimes rendering puzzles where ForcingChain is obsolete on its own generated puzzles. Just a note. Something for me to work on. but you can try the below command to see FC to show up!

```bash
# See ForcingChain in action — solve with ALS excluded so FC fires
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --steps --exclude als,alsxy,ape,fpc,fpce

# Now solve the same puzzle with the full solver — no FC needed
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --steps --preset expert
```

### More Tools

```bash
# Parse a SudokuWiki packed string directly
larsdoku "S9B8283024j..." --cell R1C1 --path

# Quick backtrack solution
larsdoku "000809000014020090000040006..." --solution

# Parse a forum grid (paste, then Ctrl+D)
echo "+---+---+---+
|.5.|12.|.93|
|..7|...|8.1|
|.2.|..9|...|
+---+---+---+" | larsdoku --parse
```

---

## Benchmark Results

Tested against every major Sudoku benchmark collection:

| Collection | Puzzles | Pure Logic | Avg Time | Total |
|---|---|---|---|---|
| **Top1465** (Stertenbrink) | 1,465 | **100%** | 0.019s | 28s |
| **Expert 669** (shuffled) | 669 | **100%** | 0.036s | 24s |
| **Famous 10** (hardest known) | 10 | **70%** | 0.50s | 5s |

Run benchmarks yourself:

```bash
# Full benchmark suite
larsdoku-bench

# Individual collections
larsdoku-bench --collection top1465
larsdoku-bench --collection expert
larsdoku-bench --collection famous
```

### Top1465 Technique Breakdown

```
crossHatch            42,852x  ( 49.4%)
nakedSingle           21,382x  ( 24.6%)
lastRemaining         13,510x  ( 15.6%)
FPC                    4,050x  (  4.7%)  <-- WSRF invention
fullHouse              3,826x  (  4.4%)
FPCE                     453x  (  0.5%)  <-- WSRF invention
SimpleColoring           354x  (  0.4%)
GF2_Lanczos              216x  (  0.2%)
XWing                     90x  (  0.1%)
Swordfish                 44x  (  0.1%)
```

---

## Techniques

Larsdoku implements **35 detectors** across 7 levels of escalation:

### L1 — Foundation
- **Full House** — last empty cell in a unit
- **Naked Single** — cell with only one candidate
- **Hidden Single** (crossHatch / lastRemaining) — digit possible in only one cell

### L2 — Linear Algebra
- **GF(2) Block Lanczos** — Gaussian elimination over GF(2) to find forced digits via parity constraints
- **GF(2) Extended** — probing, conjugate analysis, and band/stack decomposition

### L3 — Fish
- **X-Wing** — row/column digit elimination via 2x2 pattern
- **Swordfish** — 3x3 generalization of X-Wing

### L4 — Chains
- **Simple Coloring** — single-digit conjugate chain contradictions
- **X-Cycles** — single-digit alternating inference chains (Rules 1/2/3)

### L5 — Set Logic & Forcing
- **ALS-XZ** — Almost Locked Set pair with restricted common
- **ALS-XY Wing** — three-ALS chain elimination
- **Sue De Coq** — box/line intersection set partitioning
- **Aligned Pair Exclusion** — combination validation against common peers
- **Death Blossom** — stem cell with ALS petals
- **FPC (Finned Pointing Chain)** — WSRF invention. Pointing patterns with a fin cell
- **FPCE (FPC Elimination)** — WSRF invention. Contradiction testing via propagation
- **Forcing Chain** — bivalue cell branching with convergence proof
- **Forcing Net** — wider branching through the constraint network

### L6 — Advanced
- **BUG+1** — Bivalue Universal Grave plus one extra candidate
- **Unique Rectangle** (Type 2 & 4) — deadly pattern avoidance
- **Junior Exocet** — minirow-based digit placement (3-empty minirows, Double Exocet)
- **Template** — full-board digit template matching
- **Bowman's Bingo** — deep contradiction chains
- **Kraken Fish** — finned fish with forcing chain verification
- **SK Loop** — Stephen Kurzhal's Loop (massive eliminations)
- **D2B (Depth-2 Bilateral)** — WSRF invention. Branch on bivalue cell, run FPCE on both branches

### L7 — Final Backstop
- **DeepResonance** — WSRF invention. Full-stack proof-by-contradiction (requires Autotrust)
- **FPF (Full Pipeline Forcing)** — WSRF invention. Branch on each candidate, run entire pipeline per branch

---

## CLI Reference

```bash
# Basic solve
larsdoku <puzzle>                              # auto-solve, show summary
larsdoku <puzzle> --board                      # print solved grid
larsdoku <puzzle> --steps                      # step-by-step trace
larsdoku <puzzle> --detail                     # rich round-by-round log

# Technique control
larsdoku <puzzle> --no-oracle                  # pure logic only
larsdoku <puzzle> --level 2                    # L1+L2+GF(2) only
larsdoku <puzzle> --preset expert              # standard techniques only (no WSRF)
larsdoku <puzzle> --only fpc,gf2               # specific techniques only
larsdoku <puzzle> --exclude d2b,fpf            # exclude specific techniques

# Cell analysis
larsdoku <puzzle> --cell R3C5                  # how is R3C5 solved?
larsdoku <puzzle> --cell R3C5 --path           # full technique path to R3C5

# Benchmarking
larsdoku <puzzle> --bench 250                  # benchmark 250 shuffled variants
larsdoku <puzzle> --bench 100 --preset expert  # benchmark with expert-only techniques

# Output
larsdoku <puzzle> --json                       # JSON output
larsdoku <puzzle> --json | python -m json.tool # pretty-printed JSON

# GF(2) extended
larsdoku <puzzle> --gf2x                       # probing + conjugates + band/stack

# Web UI
larsdoku --serve                               # full-featured web solver at localhost:8765
```

### Puzzle Format

Puzzles are 81-character strings, row by row, left to right. Use `0` or `.` for empty cells.

```
003000600900700010080005020600010900200807003004090005020500060010003002005000300
4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........
```

---

## Built-in Puzzle Collections

Larsdoku ships with three puzzle collections for testing and benchmarking:

```python
from larsdoku.puzzles import FAMOUS_10, EXPERT_669, TOP1465
```

### Famous 10

The 10 hardest famous Sudoku puzzles ever published, including AI Escargot (Arto Inkala, 2006), Easter Monster (champagne, 2007), and Golden Nugget (tarek, 2007). Each has a unique solution.

```python
for name, author, year, puzzle in FAMOUS_10:
    print(f"{name} by {author} ({year})")
```

### Expert 669

669 expert-level puzzles, box-shuffled for originality. All verified to have unique solutions. 100% pure logic solve rate.

### Top1465

The canonical benchmark collection compiled by Guenter Stertenbrink (dukuso). 1,465 of the hardest Sudoku puzzles, sorted by difficulty rating. The gold standard for solver evaluation since the mid-2000s.

---

## Python API

```python
from larsdoku import solve

# Basic solve
result = solve("4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........")

# Pure logic only5
result = solve(puzzle, no_oracle=True)

# Limit technique level
result = solve(puzzle, max_level=5)

# Rich detail mode
result = solve(puzzle, detail=True)

# GF(2) extended
result = solve(puzzle, gf2_extended=True)
```

### Result Dictionary

```python
{
    'success': True,              # puzzle solved?
    'stalled': False,             # did the engine stall?
    'board': '468931527...',      # solved board (81-char)
    'solution': '468931527...',   # backtrack solution for verification
    'n_steps': 63,                # number of placement steps
    'steps': [...],               # list of step dicts
    'technique_counts': {         # technique frequency
        'crossHatch': 42,
        'nakedSingle': 9,
        ...
    },
    'empty_remaining': 0,         # cells unsolved
    'rounds': 12,                 # solver rounds
}
```

---

## How It Works

Larsdoku uses a **dual-representation bitwise architecture**:

- **Cell-centric**: `cands[81]` — each cell is a 9-bit mask (bit *i* = digit *i+1* is a candidate)
- **Digit-centric**: `cross[9]` — each digit is an 81-bit mask (bit *i* = cell *i* has this digit)

Both representations are kept in sync. Cell-centric is fast for per-cell operations (naked single, placement). Digit-centric is fast for per-digit operations (hidden single, X-Wing, pointing).

The solver pipeline escalates from simple to profound:

```
L1 Singles → L2 GF(2) → L3 Fish → L4 Chains → L5 ALS/FPC/Forcing → L6 Exotic → L7 DeepResonance/FPF
```

Each technique fires only when everything above it has stalled. The pipeline never needs to guess.

### WSRF Inventions

Five techniques in Larsdoku are original WSRF contributions, not found in traditional Sudoku solving literature:

| Technique | Type | Impact on Top1465 |
|---|---|---|
| **FPC** | Placement | 4,050 placements (4.7% of all steps) |
| **FPCE** | Elimination | 453 eliminations |
| **D2B** | Bilateral proof | Unlocks puzzles that stall L5 |
| **DeepResonance** | Full-stack contradiction | Autotrust-powered proof-by-exhaustion |
| **FPF** | Full pipeline forcing | Final backstop, eliminates all remaining |

---

## Web UI

Larsdoku ships with a full-featured web interface — a dark-themed, mobile-friendly Sudoku board with step-by-step playback, technique breakdown, and candidate notes.

```bash
larsdoku --serve
# Open http://localhost:8765
```

### Features

- **Dual engine**: standalone JS solver (client-side) or full Python engine (all 35 detectors)
- **Options panel**: Level slider (L1-L7), preset selection (Expert/WSRF), No Oracle, Autotrust, GF(2) toggles
- **Step-by-step playback**: walk through the solve with Back/Next, see each technique fire
- **Candidate notes**: toggle pencil marks on the board — watch candidates shrink as techniques eliminate them
- **Cell query**: tap any unsolved cell and query the engine for the exact technique path to solve it, with elimination events interleaved
- **Elimination trace**: `~elim~ [SimpleColoring] 5 eliminations` events interleaved in the step trace
- **Export**: `bd81` (original puzzle), `bdp` (S9B packed format with candidates), PNG snapshot
- **Famous puzzles**: built-in collection of the hardest known puzzles, plus difficulty-graded pools

### Autotrust Mode — The Backtracker Doesn't Deserve Your Trust

Every traditional Sudoku solver has the same skeleton in its closet: a **backtracker**. It brute-forces through possibilities, one cell at a time, until something sticks. It doesn't understand *why* a 7 goes in R3C5 — it just tried 1 through 6 and they all crashed. It returns *a* solution, proclaims victory, and moves on. But here's what nobody talks about: **for puzzles with symmetric or near-degenerate configurations, the backtracker's solution is arbitrary.** Its branching order — left to right, top to bottom, lowest digit first — is a coin flip masquerading as truth. It doesn't find *the* answer. It finds *an* answer. And that answer may have nothing to do with what logical deduction would prove.

Larsdoku's **Autotrust** mode exposes this gap — and then transcends it.

When Autotrust is enabled, the engine takes the backtracker's proposed solution and uses it as a verification oracle — a hypothesis to test, not a gospel to follow. Every single placement is still proven through pure logic: naked singles, forcing chains, GF(2) linear algebra, contradiction testing. The backtracker didn't solve the puzzle. **The logic engine solved the puzzle.** The backtracker just gave it a target to aim at.

And here's where it gets interesting: **Autotrust unlocks techniques the pure-logic pipeline can't reach alone.** The L7 detector **DeepResonance** works by assuming a candidate and running the entire technique stack against it — if every technique in the arsenal fails to resolve the board, that candidate is proven invalid by exhaustion. This is rigorous proof-by-contradiction, not guessing. But it needs to know what "correct" looks like to verify it isn't eliminating the actual answer. Autotrust provides that safety net, letting DeepResonance eliminate with absolute confidence.

The result: puzzles that stall at L6 in pure-logic mode **solve cleanly with Autotrust**, because the engine was always capable of proving the answer — it just needed permission to swing the full weight of its arsenal. The backtracker is scaffolding. The logic is the building.

**The backtracker finds a solution. Larsdoku proves why it's right — or finds a better one.**

---

## Requirements

- Python >= 3.9
- NumPy >= 1.22
- Numba >= 0.56

---

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE) for details.

---

## Author

**Lars** ([oppressionslayer](https://github.com/oppressionslayer))

Built with the WSRF (Wiliam's Statistical Reasoning Framework) methodology.
