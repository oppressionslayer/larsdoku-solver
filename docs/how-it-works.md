# How It Works

## No Backtracking — Really

Larsdoku uses **zero backtracking** at any point during solving. This is
not a marketing claim — it's a verifiable property of the code.

The engine works in a loop:

```
while cells_remain:
    1. Run L1/L2 techniques (cross-hatch, naked single, etc.)
    2. If progress → go to 1
    3. Try L3+ techniques (X-Wing, ALS, Forcing Chain, etc.)
    4. If any technique fires → go to 1
    5. If nothing fires → STALL (report honestly)
```

There is no step 6 that says "guess and retry." When the engine
exhausts its techniques, it stops.

## How to Verify

1. **Read the code** — `cli.py` contains `solve_selective()`, the main
   solve function. Search for `backtrack` — you won't find it.

2. **Test with multi-solution puzzles** — puzzles with more than one
   valid answer will stall, because logic alone can't choose. If the
   engine used backtracking, it would solve them.

3. **Run the oracle-free test** — `test_oracle_free.py` audits the
   code and verifies no oracle or backtracker is called during solving.

## Validation

After solving, the completed board is validated by Sudoku law:

- Every row contains digits 1-9 exactly once
- Every column contains digits 1-9 exactly once
- Every 3x3 box contains digits 1-9 exactly once

This validation uses **no answer key**. It's a pure constraint check
on the final board state.

## Architecture

```
BitBoard (bitmask representation)
    ↓
propagate_l1l2() — JIT-compiled L1/L2 drain
    ↓
Advanced technique detectors (35 functions)
    ↓
Placement or Elimination
    ↓
Back to L1/L2 drain (cascade)
    ↓
Repeat until solved or stalled
    ↓
validate_sudoku() — Sudoku law check
```

The `BitBoard` uses 9-bit candidate masks per cell, making technique
detection fast via bitwise operations. The L1/L2 drain is Numba
JIT-compiled for near-C performance.
