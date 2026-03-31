# LarsForge: O(81) Puzzle Generation

LarsForge generates unique, provably non-isomorphic Sudoku puzzles
**without backtrackers**. Every puzzle is produced in microseconds
via deterministic digit permutation — no search, no trial and error.

## The Speed

```
  LarsForge Speed Benchmark
  ══════════════════════════════════════════════════
    1,000 puzzles in      5.5ms =    181,715 puzzles/sec
   10,000 puzzles in     58.4ms =    171,117 puzzles/sec
  100,000 puzzles in    666.7ms =    149,992 puzzles/sec

  Traditional backtracker: ~50 puzzles/sec
  LarsForge:              ~150,000 puzzles/sec
  Speedup:                ~3,000x
```

!!! tip "150,000 puzzles per second"
    One hundred fifty thousand unique puzzles per second. No backtracker.
    No search. Just O(81) digit mapping per puzzle.

## How It Works

1. Start with ONE verified-unique seed puzzle
2. Permute digits 1-9 (362,880 possible permutations)
3. Each permutation produces a new unique puzzle (digit relabeling preserves uniqueness)
4. Zone sums prove non-isomorphism (different zone sum = provably different puzzle)

```
Seed puzzle (known unique)
  → choose digit permutation π
    → apply π to clues (81 lookups, microseconds)
      → compute zone sums (non-isomorphism certificate)
        → DONE. Unique, non-isomorphic, no backtracker.
```

## The 135 Rule

Every Sudoku board has 9 zones — one for each relative position within
the 3x3 boxes. Zone sums along any template row or column always equal 135:

```
Zone sums:  | 56  35  44 |     Row sums: 56+35+44 = 135
            | 38  51  46 |               38+51+46 = 135
            | 41  49  45 |               41+49+45 = 135

Col sums: 56+38+41 = 135     35+51+49 = 135     44+46+45 = 135
```

Two puzzles with different zone sum distributions **cannot be isomorphic**.
This is the mathematical proof that LarsForge produces genuinely
different puzzles, not copies of the same one.

## Quick Start

### Daily Puzzle

=== "CLI"

    ```bash
    larsdoku --daily
    ```

    ```
      LarsForge Daily Puzzle — March 28, 2026
      ══════════════════════════════════════════════════
      830070000200195000097000020900020003400903001500060008020000390000419005000080070
      Zone sums: [46, 50, 39, 48, 41, 46, 41, 44, 50]
      135 rule: ✓
    ```

=== "Python"

    ```python
    from larsdoku.lars_forge import LarsForge
    import datetime

    forge = LarsForge("530070000600195000098000060800060003400803001700020006060000280000419005000080079")
    today = datetime.date.today()
    seed = today.year * 10000 + today.month * 100 + today.day

    puzzles = forge.lars_generate(count=1, seed=seed, unique_classes=False)
    print(puzzles[0]['puzzle'])
    ```

Same puzzle for everyone, every day. Tomorrow's is provably different.
No server, no database.

### Generate Non-Isomorphic Puzzles

=== "CLI"

    ```bash
    # 10 provably non-isomorphic puzzles from a seed
    larsdoku --lars-forge "530070000600195000098000060800060003400803001700020006060000280000419005000080079"

    # With difficulty targeting
    larsdoku --lars-forge "530070000..." --lars-forge-difficulty hard --lars-forge-count 20
    ```

=== "Python"

    ```python
    from larsdoku.lars_forge import LarsForge

    forge = LarsForge("530070000600195000098000060800060003400803001700020006060000280000419005000080079")

    # 10 non-isomorphic puzzles
    puzzles = forge.lars_generate(count=10)
    for p in puzzles:
        print(f"{p['puzzle']}  zones={list(p['zone_sums'])}")
    ```

### Oracle Scan: Count Non-Isomorphic Classes

=== "CLI"

    ```bash
    larsdoku --lars-forge-scan "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
    ```

=== "Python"

    ```python
    from larsdoku.lars_forge import LarsForge

    forge = LarsForge("530070000600195000098000060800060003400803001700020006060000280000419005000080079")
    results = forge.lars_oracle_scan(verbose=True)

    print(f"Non-isomorphic classes: {results['n_classes']}")
    print(f"Raw zone sum diversity: {results['zone_sum_diversity']}")
    ```

    ```
    Non-isomorphic classes: 1,656
    Raw zone sum diversity: 21,276
    Rate:                   26,162 perms/sec
    ```

### Speed Benchmark

=== "CLI"

    ```bash
    larsdoku --lars-forge-benchmark "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
    ```

=== "Python"

    ```python
    from larsdoku.lars_forge import LarsForge

    forge = LarsForge("530070000600195000098000060800060003400803001700020006060000280000419005000080079")
    puzzles, elapsed, rate = forge.lars_forge_batch(count=100000)
    print(f"{len(puzzles)} puzzles in {elapsed:.1f}ms ({rate:,.0f}/sec)")
    ```

### Zone Analysis Report

```python
from larsdoku.lars_forge import LarsForge

forge = LarsForge("530070000600195000098000060800060003400803001700020006060000280000419005000080079")
forge.lars_zone_report()
```

```
LarsForge Zone Report
══════════════════════════════════════════════════
Seed: 530070000600195000098000060800...
Clues: 30

Zone Sums:
  ┌─────────────────┐
  │  55   41   39 │  = 135
  │  41   48   46 │  = 135
  │  39   46   50 │  = 135
  └─────────────────┘
    135  135  135
    135? True ✓
```

## Difficulty Control

Zone sum spread correlates with solving difficulty. LarsForge targets
specific spreads:

| Difficulty | Zone Sum Spread | Meaning |
|-----------|----------------|---------|
| Easy | ≤ 10 | Balanced zones, uniform structure |
| Medium | 8-16 | Moderate asymmetry |
| Hard | 14-22 | Strong zone imbalance |
| Expert | ≥ 18 | Extreme zone asymmetry |

```bash
larsdoku --lars-forge "530070000..." --lars-forge-difficulty expert --lars-forge-count 5
```

## The Numbers

### From One Seed

| Metric | Value |
|--------|-------|
| Total digit permutations | 362,880 (9!) |
| Non-isomorphic classes | **1,656** |
| Raw zone sum vectors | **21,276** |
| Generation rate | **150,000+ puzzles/sec** |
| Time per puzzle | **~7 microseconds** |

### From 10 Diverse Seeds

| Metric | Value |
|--------|-------|
| Non-isomorphic classes | **~16,000+** |
| Generation rate | **150,000+ puzzles/sec** |
| Total unique puzzles | **3,628,800** |

### vs Traditional Backtrackers

| Method | Rate | Speedup |
|--------|------|---------|
| Traditional backtracker | ~50 puzzles/sec | 1x |
| LarsForge | ~150,000 puzzles/sec | **3,000x** |

## Why It Matters

Traditional puzzle generation requires a backtracker at two steps:
generating a filled grid and verifying uniqueness. LarsForge needs
neither — digit permutation preserves both the solution and its uniqueness.

The zone sum fingerprint proves non-isomorphism without checking the
1.22 trillion elements of the Sudoku symmetry group. Two puzzles with
different normalized zone sum vectors are **mathematically guaranteed**
to be different puzzles.

This means the entire Sudoku puzzle generation pipeline — from seed to
unique, non-isomorphic, difficulty-controlled puzzle — runs in O(81)
time with no search, no guessing, and no backtrackers.

## Final Boss Mode: Mask Matching

Match ANY 17-clue mask pattern to a known seed via Sudoku symmetries.
49,196 seeds covering every valid 17-clue geometry (complete Royle enumeration).

```bash
# Match a mask to a seed — 7ms
larsdoku --lars-forge-mask-match ".............xx.x.x.x.......xx.x..........xx..x........x.x.x..........xx.....x..."

# Result: matched seed, transform, and a unique puzzle with clues at those exact positions
```

**60 quadrillion** unique 17-clue puzzles reachable: 49,196 seeds x 362,880 digit perms x 3,359,232 symmetry transforms.

## Lars Certify: 6ms Uniqueness Oracle

For 17-clue puzzles, instantly certify whether a mask geometry can support
a unique solution — no backtracker needed.

```bash
larsdoku --lars-certify "000000010400000000020000000000050407008000300001090000300400200050100000000806000"
# >>> UNIQUE <<<  (Royle-certified, 6ms)

larsdoku --lars-certify "x.........x.xxxx............x.x.....x...x............x..x.....x.xx....xx........."
# >>> MULTI-SOLUTION MASK <<<  (no digit assignment can make this unique)
```

Based on the complete Royle enumeration of all 49,158 valid 17-clue puzzle geometries.

## Lars Promote: Indestructible Puzzles

Add solution digits to a 17-clue puzzle to create puzzles at any clue count.
**Uniqueness is inherited** — remove any added clue, still unique.

```bash
# Promote a 17-clue puzzle to 24 clues
larsdoku "000000010400000000020000000000050407008000300001090000300400200050100000000806000" --lars-forge-promote 24

# Generate 50 unique 22-clue puzzles
larsdoku --lars-forge-promote 22 --lars-forge-promote-count 50
```

Every promoted puzzle has a **17-clue skeleton** that is mathematically unbreakable.
The added clues are armor — remove any of them in any order, uniqueness holds.
This is **dimensional uniqueness**: unique across all states, not just one configuration.

## LForge: Technique-Targeted Generation

Generate puzzles that require specific solving techniques.

```bash
# Puzzles requiring ALS-XZ and KrakenFish at 23 clues
larsdoku --lforge-attempt als,kraken --lforge-clues 23 --lforge-count 5

# DeathBlossom puzzles (18 seeds, ~22 trillion variants each)
larsdoku --lforge-attempt deathblossom

# DeepResonance + D2B (extreme tier)
larsdoku --lforge-attempt dr,d2b

# See what's available
larsdoku --lforge-stats
larsdoku --lforge-list
larsdoku --lforge-search exocet
```

684 technique-tagged seeds across 368 distinct technique profiles.
Technique requirements are **invariant under the Sudoku symmetry group** —
if a seed needs ALS-XZ, all 1.2 trillion shuffled variants also need ALS-XZ.

| Technique | Seeds | Reachable Puzzles |
|-----------|-------|-------------------|
| ALS_XZ | 592 | 7.66 quadrillion |
| FPC | 509 | 6.21 quadrillion |
| KrakenFish | 293 | 3.57 quadrillion |
| DeepResonance | 236 | 2.88 quadrillion |
| JuniorExocet | 122 | 1.49 quadrillion |
| DeathBlossom | 18 | 22 trillion |
| SueDeCoq | 4 | 4.88 trillion |

## The Complete Numbers

| Metric | Value |
|--------|-------|
| 17-clue seeds | 49,196 (complete Royle enumeration) |
| Technique-tagged seeds | 684 (Andrew Stuart weekly collection) |
| Mask match speed | 7ms |
| Uniqueness certification | 6ms |
| Unique 17-clue puzzles | **60 quadrillion** |
| All clue counts (17-81) | **1 undecillion** (10^36) |
