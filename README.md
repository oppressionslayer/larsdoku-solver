# Larsdoku

**Pure logic Sudoku solver. Zero guessing. Every step proven.**

 ## The Anthem                                                                                                                                                     
                                                            
  [Just Another Tuesday — Larsdoku Style (Country Epic Anthem)](https://suno.com/s/nyShx2dKO3Qd3s3C)                                                                
   
  *"Solved the whole damn game like it's just another Tuesday"*    
  
800900005007080010020006400005000030070004600900800002002070000100200000030001000
**Documentation: [larsdoku-docs.netlify.app](https://larsdoku-docs.netlify.app/)**

**Web App (WIP): [larsdoku.netlify.app](https://larsdoku.netlify.app/)** — click Expert mode tab to open the Top-N Solver

**New techniques `--preset larstech` from:** [wsrf-sudoku-solved-series](https://github.com/oppressionslayer/wsrf-sudoku-solved-series)

**Sittin' on the Throne of Euler:** [Listen Now! They said NP Complete, i said check out my zones brother Euler! ](https://suno.com/s/ABPiCLAgaZLNmGko)  


Larsdoku solves the hardest Sudoku puzzles ever created using only logical deduction — no backtracking, no trial-and-error. Built on a bitwise engine with GF(2) linear algebra, it achieves **100% pure logic on the Top1465 benchmark** (1,465 of the hardest known puzzles), averaging **19ms per puzzle*.

> **Note:** There is a rare bug where JuniorExocet can cause a stall on a very very very small number of puzzles  If you encounter a STALL, try running with `--exclude JuniorExocet` as a workaround. A fix is in progress.

## LarsForge: 60 Quadrillion Indestructible Puzzles

LarsForge generates **60 quadrillion unique 17-clue puzzles** from the complete Royle enumeration (49,158 seeds). Every puzzle is backed by a mathematically proven 17-clue skeleton — the minimum information needed to determine a unique Sudoku solution.

**Why this matters:** Traditional puzzle generators use backtrackers to verify uniqueness for one configuration. LarsForge puzzles are **dimensionally unique** — unique across ALL states. Add solution digits to create 24-clue puzzles, remove any of the added clues in any order, and uniqueness holds. The 17-clue core is bedrock. Everything above it is armor.

We are building toward forging all puzzles from an **18-clue minimum base** — one clue above the mathematical floor. At 17 clues, 90% of puzzles solve with basic techniques alone. At 18 clues, the extra clue opens the door to harder, more interesting puzzles while still guaranteeing dimensional uniqueness. When a 24-clue puzzle is built on the forge, removing any clue above the 18-clue base never leads to multiple solutions. Boards that break when reduced to their minimum base are, in our view, backtracker-unreliable — verified at one snapshot, but fragile under interaction. We prefer puzzles with structural integrity all the way down.

```bash
# 6ms uniqueness oracle — no backtracker needed
larsdoku --lars-800900005007080010020006400005000030070004600900800002002070000100200000030001000certify "000000010400000000020000000000050407008000300001090000300400200050100000000806000"
# >>> UNIQUE <<<  Royle-certified

# Match ANY mask to a seed in 7ms (Final Boss Mode)
larsdoku --lars-forge-mask-match "...x..x.x....."

# Promote to any clue count — guaranteed unique, remove any added clue
larsdoku "000000010..." --lars-forge-promote 24

# Technique-targeted generation — "give me a KrakenFish puzzle"
larsdoku --lforge-attempt kraken --lforge-clues 23 --lforge-count 5

# See all available technique tags
larsdoku --lforge-stats
```800900005007080010020006400005000030070004600900800002002070000100200000030001000

| Feature | What it does |
|---------|-------------|
| `--lars-certify` | 6ms uniqueness oracle (Royle hash lookup) |
| `--lars-forge-mask-match` | Match any 17-clue mask to a seed (7ms) |
| `--lars-forge-promote N` | 17-clue → any clue count, all unique |
| `--lforge-attempt TECHS` | Generate by technique (684 seeds, 16 techniques) |
| `--include TECHS` | Add techniques to presets |

**The numbers:** 49,196 seeds × 362,880 digit perms × 3,359,232 symmetries = **60 quadrillion** unique 17-clue puzzles. With promote (2^64 variants per seed): **1 undecillion** (10^36) across all clue counts.

## Lars Seeds: 384K DeepRes/D2B Seeds — 469 Quadrillion Hard Puzzles

The **Lars Seeds Registry** contains 384,505 seeds for the hardest Sudoku techniques (DeepResonance & D2B), forged via a novel swap technique. Every puzzle is confirmed by the solver before output.

### Forge DeepRes Puzzles (confirmed by solver)
```
$ larsdoku --lforge-deepres 3

  LForge — DeepRes Puzzle Forge
  =============800900005007080010020006400005000030070004600900800002002070000100200000030001000==========================================
  Lars Seeds: 209,762 DeepRes seeds
  Confirmed: 3/3 in 722ms

  000200000200000046039000200000010000006008015900400600075000008000007000400600300  [ALS_XZ, D2B, DeepResonance, FPC, FPCE, JuniorExocet]
  700600010000005009400000300102000800040200060607000002004100023000090008000003500  [D2B, DeepResonance, FPCE]
  080900007200000050004000300800700000010096000000001009300800020070600008000040500  [ALS_XYWing, AlignedPairExcl, DeepResonance, FPC, FPCE, JuniorExocet]

  # 3 DeepRes puzzles (confirmed by solver)
```

### Forge D2B Puzzles (confirmed by solver)
```
$ larsdoku --lfo800900005007080010020006400005000030070004600900800002002070000100200000030001000rge-d2b 3

  LForge — D2B Puzzle Forge
  =======================================================
  Lars Seeds: 174,745 D2B seeds
  Confirmed: 3/3 in 934ms

  000000000500020068030879400000010600060208015100500080270080046004000000000700000  [ALS_XYWing, ALS_XZ, D2B, FPC, KrakenFish]
  700009300040050000001700040100000800070200060602000009400600010007005000000030708  [ALS_XZ, AlignedPairExcl, D2B, DeepResonance, FPC, FPCE, JuniorExocet]
  090001020003709500000000007030640000200003600056010030002070000060305200005000080  [ALS_XYWing, ALS_XZ, D2B, FPC, FPCE, KrakenFish]

  # 3 D2B puzzles (confirmed by solver)
```

### Elite Mode — Puzzles That Stall Expert Solvers

If you have a really good solver and want puzzles that will challenge it, use `--elite`. These puzzles should be harder for those of you with solvers that as close to 100% as you can get like larsdoku — only DeepResonance/D2B and other really good solvers like this one should be able to crack them.

```bash
larsdoku --lforge-d2b 25 --lforge-seed 777 --elite
```

### Lars Provenance — "Is this puzzle a Lars Database Seed?"
```
$ larsdoku --lars-provenance "700009300040050000001700040100000800070200060602000009400600010007005000000030708"

  Lars Provenance Registry
  =======================================================
  Input: 700009300040050000001700040100000800070200060602000009400600...
  Clues: 24
  Time:  4.5ms

  >>> LARS DATABASE SEED MATCH <<<
  Confidence: Very high (core seed match)
  Techniques: ALS_XZ, AlignedPairExcl, D2B, DeepResonance, FPC, FPCE, JuniorExocet
  Hash: (((2, 2, 3), (2, 3, 3), (2, 3, 4)), ((2, 3, 3), (2, 3, 3), (2, 3, 3)), (1, 2, 2, 3, 3, 3, 3, 3, 4))
  This puzzle is derived from a Lars Seed.
```

### Lars Certify — 6ms Uniqueness Oracle
```
$ larsdoku --lars-certify "000000010400000000020000000000050407008000300001090000300400200050100000000806000"

  Lars Certify — Uniqueness Oracle
  ═══════════════════════════════════════════════════════
  Input:   000000010400000000020000000000050407008000300001090000300400...
  Clues:   17
  Method:  royle_hash
  Time:    15.0ms

  >>> UNIQUE <<<
  Royle-certified: this mask geometry is in the complete
  enumeration of all 49,158 valid 17-clue patterns.
```

| Command | What it does |
|---------|-------------|
| `--lforge-deepres N` | Forge N DeepRes puzzles (confirmed by solver) |
| `--lforge-d2b N` | Forge N D2B puzzles (confirmed by solver) |
| `--lforge-no-confirm` | Skip solver verification (fast mode) |
| `--lars-provenance "puzzle"` | Check if puzzle is a Lars Seed (4.5ms) |
| `--lars-seeds-stats` | Registry statistics (384K seeds, 469 quadrillion) |

** USE --preset expert  first, and --preset larstech for the new techniques listed at the gihub New Techniques site! 

** --preset larstech are new techniques i created that the community should review and comment on before i put them in as expert techniques


```
# Run --warmup to save JIT conmpilations for 109-1000x speedups!! Seriously, run once, it compiles and saves, and it's fast for every run thereafter without the nee for --warmup
pip install larsdoku==3.1.9
larsdoku --warmup 
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

Or

## Temporary workaround for Numba cache error

If `larsdoku` fails at startup with a Numba cache error, run:

```bash
  mkdir -p /tmp/numba_cache
  export NUMBA_CACHE_DIR=/tmp/numba_cache
```
Then run larsdoku normally.

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
```text
Status: SOLVED
Steps:  53
Time:   65.7ms
Verify: All techniques are Sudoku Expert Approved ✓

  Board validated: every row, column, and box contains
  digits 1-9 exactly once per international Sudoku rules.
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

Techniques:
  nakedSingle             22 ( 36.1%)  L1  ████████████
  crossHatch              17 ( 27.9%)  L1  █████████
  lastRemaining            8 ( 13.1%)  L1  ████
  DeathBlossom             5 (  8.2%)  L5  ██
  fullHouse                5 (  8.2%)  L1  ██
  KrakenFish               2 (  3.3%)  L6  █
  SimpleColoring           1 (  1.6%)  L4  █
  ForcingChain             1 (  1.6%)  L5  █
```
# Generate pure ALS puzzles
larsdoku --board-forge MC --require ALS_XZ --board-forge-count 5
```

**The flex:** Puzzles generated with `--require ForcingChain` need FC to solve *when ALS is excluded*. But with the full solver, ALS-XZ handles what ForcingChain does — making FC unnecessary. The solver is quite good so it renders ForcingChain obsolete on its own generated puzzles so it's hard to do. but check out --like if you really want similar puzzles!

```bash
# See ForcingChain in action — solve with ALS excluded so FC fires
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --steps --exclude als,alsxy,ape,fpc,fpce

# Now solve the same puzzle with the full solver — no FC needed
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --steps --preset expert
```

### Like — Generate Similar Puzzles

Find a puzzle you enjoy and generate more like it. `--like` analyzes the technique profile and shuffles until it finds puzzles that require the same advanced techniques:

```bash
larsdoku --like "005000903906000500080000010020060080000510400000008007100006000040000090003702000" --like-count 5
```

```
════════════════════════════════════════════════════════════
  LIKE — Generate Similar Puzzles
  Reference: 005000903906000500080000010020060080000510400000008007100006000040000090003702000
  Clues: 23 | SOLVED
  Techs: nakedSingle=26, crossHatch=22, lastRemaining=7, fullHouse=2, ALS_XZ=1, FPCE=1, SimpleColoring=1
  Profile: ALS_XZ, FPCE, SimpleColoring
  Count: 5
════════════════════════════════════════════════════════════

  [1/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 000500600000004803070010020002807000580000000300009000100000306020060050009000004
  Techs:  crossHatch=34, lastRemaining=12, nakedSingle=11, ALS_XZ=1, FPCE=1

  [2/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 300400090020000506001000800000501000070006000045090000000003608000070002800900010
  Techs:  crossHatch=28, lastRemaining=14, nakedSingle=10, fullHouse=5, ALS_XZ=1

  [3/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 000900002000040105008007000100000006070000390006005020009006000030820000480030000
  Techs:  crossHatch=28, lastRemaining=14, nakedSingle=10, fullHouse=5, ALS_XZ=1

  [4/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 001200000507060000000305000004000205300000008090007060000010400000900802080006030
  Techs:  crossHatch=37, nakedSingle=13, lastRemaining=6, ALS_XZ=1, FPCE=1

  [5/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 900000027010080500003000060000100076000004009060050300802005000000320000400700000
  Techs:  crossHatch=36, nakedSingle=12, lastRemaining=9, ALS_XZ=1, FPCE=1

════════════════════════════════════════════════════════════
  RESULTS: 5/5 similar puzzles in 6 shuffles
```

# Cell Path — Trace the Solution to Any Cell

Want to know exactly how a specific cell was solved? Use `--cell` with `--path` to see every step the engine took to reach that placement.

```bash
larsdoku "300002590600008070040050001009100030000000008070060040010080400000000003008700200" --cell R1C3 --path --preset expert
```

```
  ✦ Sudoku Expert Approved Techniques ✦

  R1C3 = 1 via ForcingChain (step 5)
  Candidates: [1, 7]
  Full solve: 57 steps, COMPLETE
  Time: 416.9ms

  Verify: All techniques are Sudoku Expert Approved ✓
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

  Techniques used:
    nakedSingle            2  L1
    crossHatch             2  L1
    ForcingChain           1  L5
    XWing                  1  L3

  Solution path (5 placements, 1 elimination rounds):
       ~elim~  [XWing L3] 4 eliminations
     #  1  R1C2=8  [nakedSingle L1]
     #  2  R2C7=3  [nakedSingle L1]
     #  3  R4C1=8  [crossHatch L1]
     #  4  R6C4=8  [crossHatch L1]
   → #  5  R1C3=1  [ForcingChain L5]
```

The full puzzle took 57 steps to solve, but R1C3 only needed 5 — an X-Wing elimination to clear the path, four foundation placements, and then a ForcingChain to prove R1C3 = 1. Every step is deterministic logic. No guessing.

## Still Solves When Key Techniques Are Removed

Larsdoku is not dependent on one narrow family of advanced techniques.

Even with several known techniques disabled, it can still reroute through other expert-approved logic and finish the board cleanly — with **no backtracking, no guessing, and no trial-and-error**.

### Example

```bash
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --exclude als,alsxy,ape,fpc,fpce

```text
Status: SOLVED
Steps:  53
Time:   65.7ms
Verify: All techniques are Sudoku Expert Approved ✓

  Board validated: every row, column, and box contains
  digits 1-9 exactly once per international Sudoku rules.
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

Techniques:
  nakedSingle             22 ( 36.1%)  L1  ████████████
  crossHatch              17 ( 27.9%)  L1  █████████
  lastRemaining            8 ( 13.1%)  L1  ████
  DeathBlossom             5 (  8.2%)  L5  ██
  fullHouse                5 (  8.2%)  L1  ██
  KrakenFish               2 (  3.3%)  L6  █
  SimpleColoring           1 (  1.6%)  L4  █
  ForcingChain             1 (  1.6%)  L5  █
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

# Pure logic only
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
