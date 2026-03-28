# Research Tool

`larsdoku-research` is a **separate program** for exploring what techniques can do when guided by an oracle. It never touches the main solver's code.

## The Question It Answers

*"If I already know the solution, which legitimate Sudoku techniques could have gotten me there?"*

Every individual move in a super-sus solve is logically valid. The oracle just decides which valid moves to keep and which to skip. It's like having the answer key open while doing homework — the work is real, the selection is guided.

## Super-Sus Mode

```bash
larsdoku-research <puzzle> --super-sus --detail --board
```

### How It Works

1. **Backtrack first** — gets the solution upfront
2. **Run ALL techniques** — each makes eliminations and placements
3. **Oracle safety net** — checks each elimination: "does this remove the correct answer?" If yes → undo and try the next technique
4. **Report** — shows which techniques solved it, how many oracle saves occurred

### Oracle Saves

An oracle save means a technique tried to make a valid elimination that would have steered the solve toward a DIFFERENT solution. On unique puzzles, oracle saves = 0 (there's only one solution). On multi-solution puzzles, oracle saves reveal the "sus" — the places where the answer key guided the selection.

## Multi-Solution Puzzles

This is where `larsdoku-research` shines. Main `larsdoku` can't fully solve multi-solution puzzles because pure logic can't determine which solution is "correct" — they're ALL correct.

```bash
# Find all solutions
larsdoku --solutions 10 "000003020300080009000900300..."

# Solve to a specific one
larsdoku-research "000003020300080009000900300..." --trust-solve-to "179653824365284719..." --detail --board

# Or auto-pick solution #3
larsdoku-research "000003020300080009000900300..." --solution-num 3 --detail --board
```

### Testing Technique Legitimacy

The research tool reveals which techniques work differently on multi-solution puzzles:

- **0 oracle saves** → the technique naturally converges. It's legitimate regardless of which solution you target.
- **N oracle saves** → the technique needed the oracle N times. Those N moments are where the answer key steered the solve.

This lets you test: "Is my technique really finding the right answer, or is it accidentally assuming uniqueness?"

## Research-Only Techniques

Two techniques exist ONLY in `larsdoku-research`:

### FPC-Elim

FPC in elimination mode. Trial-places each candidate, propagates L1+L2. If the propagation produces a digit that disagrees with the oracle → eliminate that candidate.

On unique puzzles, "disagrees with oracle" = "Sudoku contradiction." On multi-solution puzzles, it means "leads to a different solution."

### FinnedPointingChain

Finned Pointing Chain with gold-filtered placement. Finds digit patterns where a pointing pair + fin cell force a placement.

## Rich Terminal Output

```bash
larsdoku-research <puzzle> --super-sus --detail --board
```

Uses `rich` for colored panels:

- **Cyan** — L1 techniques (crossHatch, nakedSingle)
- **Green** — FPC, FinnedPointingChain, ForcingChain
- **Red** — DeepResonance, D2B
- **Yellow** — ALS-XZ, ALS-XYWing
- **Magenta** — JuniorExocet, Template, BowmanBingo

Each step shows:
- Technique name with colored highlight
- Cell and placed digit
- Notes before → placed (with strikethrough on eliminated candidates)
- Technique-specific reason
- Oracle save warnings

## Constellation Forge

The `--forge-permute` command generates unique puzzles from any unique puzzle by relabeling digits 1-9. Every permutation of the digit mapping produces a structurally identical puzzle with different numbers.

```bash
# From a unique puzzle, generate 10 unique variants
larsdoku --forge-permute "000060010000300007000001300..." --forge-permute-count 10

# Generate all 362,880 (9!) permutations — pipe to file
larsdoku --forge-permute "000060010000300007000001300..." --forge-permute-count 362880 >> all.txt
```

**Key finding:** For well-formed masks (23-24 clues), **100% of digit permutations produce unique puzzles**. That's 362,880 unique puzzles from a single source puzzle, generated in under 8 minutes.

The HYPERSIRO Research HTML also includes a **Mask Forge** button in the Forge & Shuffle panel. Enter an 81-character mask (or leave empty to use the current puzzle's mask) and generate permuted puzzles instantly in the browser.

### The 135 Rule

Zone position sums across a solved board follow a strict mathematical identity:

- Each **row** of zone sums (TL+TC+TR, ML+MC+MR, BL+BC+BR) = **135**
- Each **column** of zone sums (TL+ML+BL, TC+MC+BC, TR+MR+BR) = **135**
- Total of all 9 zone sums = **405**

This holds for EVERY valid Sudoku — it's a mathematical guarantee (3 × 45 = 135). The individual zone sums vary per puzzle, but the row/column totals are invariant. This constraint can validate predictions and detect errors in HYPERSIRO cascades.

---

## Python API

All research tools are also available as Python imports.

### Super-Sus Solve

```python
from larsdoku.research import super_sus_solve

result = super_sus_solve(
    "000000000500020008000000000000000000300010004000000000000000000800070009000000000",
    solution="179348652536721948284569371912437586358916724467285193723194865845673219691852437",
    detail=True,
)

print(result['success'])            # True
print(result['n_steps'])            # 100
print(result['oracle_saves'])       # 0
print(result['technique_counts'])   # {'nakedSingle': 65, 'FPC-Elim': 28, 'crossHatch': 7}
```

If you omit `solution`, it backtracks to find one automatically:

```python
result = super_sus_solve("003000600900700010080005020...", detail=True)
```

### Uniqueness Checking

```python
from larsdoku.engine import has_unique_solution

has_unique_solution("980700000600050000004008300700000040002004003000500020060000001008001030000090408")
# True

has_unique_solution("980700000600050000004008300700000040002004003000500020060000001008001030000090400")
# False
```

### Forge Variant

```python
from larsdoku.cli import forge_variant

# Turn a multi-solution puzzle into unique ones
puzzles = forge_variant(
    "910700000200050000003001400700000030008003004000500080020000006001006040000090300",
    max_retries=20,
)
```

---

## What the Heck: Mind-Bending Experiments

These examples push the tools into territory that will make you do a double-take.

### 8-Clue Solve: Super Sus at the Edge

A valid Sudoku needs at least 17 clues for a unique solution.
With only 8, there are many solutions. Super Sus doesn't care --
hand it any solution and watch it solve the whole thing with basic techniques:

=== "CLI"

    ```bash
    larsdoku-research \
      --trust-solve-to 179348652536721948284569371912437586358916724467285193723194865845673219691852437 \
      --detail --board \
      000000000500020008000000000000000000300010004000000000000000000800070009000000000
    ```

=== "Python"

    ```python
    from larsdoku.research import super_sus_solve

    result = super_sus_solve(
        "000000000500020008000000000000000000300010004000000000000000000800070009000000000",
        solution="179348652536721948284569371912437586358916724467285193723194865845673219691852437",
        detail=True,
    )
    print(f"Solved: {result['success']}")
    print(f"Steps: {result['n_steps']}, Oracle saves: {result['oracle_saves']}")
    for tech, count in result['technique_counts'].items():
        print(f"  {tech}: {count}")
    ```

```
  Status: SOLVED
  Steps: 100
  Rounds: 29
  Time: 456.6ms
  Oracle saves: 0 (eliminations blocked)

  Techniques:
    nakedSingle           65 (65.0%)
    FPC-Elim              28 (28.0%)
    crossHatch             7 ( 7.0%)
```

!!! tip "Zero oracle saves"
    The oracle never had to block a single elimination. Every FPC-Elim
    that fired was already pointing at the right answer. The techniques
    did all the work -- the oracle just picked which order to run them.

The insight: **the solution space is reachable from the techniques alone**.
FPC-Elim prunes candidates aggressively enough that naked singles cascade
through the entire board. The oracle's only job is choosing *which*
eliminations to apply first. The techniques are the engine, the oracle is
the steering wheel.

### The One-Clue Cliff

Remove a single clue from a minimal puzzle and it shatters into multiple
solutions:

=== "CLI"

    ```bash
    # Unique (23 clues)
    larsdoku --unique 980700000600050000004008300700000040002004003000500020060000001008001030000090408

    # Remove R9C9 → multiple solutions (22 clues)
    larsdoku --unique 980700000600050000004008300700000040002004003000500020060000001008001030000090400
    ```

=== "Python"

    ```python
    from larsdoku.engine import has_unique_solution

    # Unique (23 clues)
    has_unique_solution("980700000600050000004008300700000040002004003000500020060000001008001030000090408")
    # True

    # Remove R9C9 → multiple solutions (22 clues)
    has_unique_solution("980700000600050000004008300700000040002004003000500020060000001008001030000090400")
    # False
    ```

One digit. That's the difference between a puzzle with exactly one answer
and a puzzle with many. In a minimal puzzle, every given is load-bearing.

### Forge: Same Skeleton, Different Puzzles

Take a non-unique puzzle and the forge reshuffles digits to produce unique,
solvable puzzles -- all keeping the same clue mask:

=== "CLI"

    ```bash
    larsdoku --forge-solve 910700000200050000003001400700000030008003004000500080020000006001006040000090300
    ```

=== "Python"

    ```python
    from larsdoku.cli import forge_variant

    puzzles = forge_variant(
        "910700000200050000003001400700000030008003004000500080020000006001006040000090300"
    )
    ```

```
  Forging seed puzzle...
  Seed forged in 107 checks (55ms)

    #  Puzzle                                             Status  Steps   Time
    1  450600000700030000001002800600000040002001008...  SOLVED     59    71ms
    2  590300000600080000004007100300000050007004001...  SOLVED     59   309ms
    3  710400000500060000008003200400000070003008002...  SOLVED     59    65ms
```

Same mask, different unique puzzles. Some need only basic techniques,
others pull in ALS-XZ -- same skeleton, different difficulty.

### Solution Steering Race

Take the same sparse puzzle, find multiple solutions, and Super Sus each one.
Which solutions are easier to steer toward?

```python
from larsdoku.engine import solve_backtrack
from larsdoku.research import super_sus_solve

puzzle = "000000000500020008000000000000000000300010004000000000000000000800070009000000000"

# Get a few different solutions
sol1 = solve_backtrack(puzzle)
# Use --solution-num from CLI for the Nth solution

result1 = super_sus_solve(puzzle, solution=sol1, detail=True)
print(f"Solution 1: {result1['n_steps']} steps, {result1['oracle_saves']} saves")
```

```bash
# Or from the CLI -- solve toward the 3rd solution found
larsdoku-research --solution-num 3 --detail --board \
  000000000500020008000000000000000000300010004000000000000000000800070009000000000
```

Different target solutions produce different technique profiles.
Some solutions are "nakedSingle-heavy", others need heavier machinery.
The solution itself has a difficulty signature.
