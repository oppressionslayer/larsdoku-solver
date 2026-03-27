# Python API

## solve()

The main entry point for solving puzzles programmatically.

```python
from larsdoku import solve
```

### Signature

```python
solve(puzzle, max_level=99, no_oracle=False, detail=False, gf2_extended=False)
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `puzzle` | `str` | required | 81-char puzzle string (`0` or `.` for empty) |
| `max_level` | `int` | `99` | Max technique level (1-7) |
| `no_oracle` | `bool` | `False` | Pure logic only — stop if stalled |
| `detail` | `bool` | `False` | Capture rich detail (candidates, explanations) |
| `gf2_extended` | `bool` | `False` | Use GF(2) Extended with probing + conjugates |

### Returns

A dictionary with the following keys:

```python
{
    'success': bool,           # True if puzzle fully solved
    'stalled': bool,           # True if engine stalled (with no_oracle=True)
    'board': str,              # Current board state (81 chars)
    'solution': str,           # Backtrack solution for verification
    'n_steps': int,            # Number of placement steps
    'steps': list,             # List of step dictionaries
    'technique_counts': dict,  # {technique_name: count}
    'empty_remaining': int,    # Unsolved cells (0 if success)
    'rounds': int,             # Solver rounds
    'elim_events': list,       # Elimination events (if detail=True)
}
```

### Step Dictionary

Each entry in `steps` looks like:

```python
{
    'step': 42,                # step number
    'pos': 35,                 # cell position (0-80)
    'digit': 7,                # placed digit
    'technique': 'crossHatch', # technique used
    'cell': 'R4C9',            # human-readable cell name
    'round': 5,                # which round this happened in
}
```

With `detail=True`, steps also include:

```python
{
    'cands_before': [3, 7, 9],  # candidates before placement
    'explanation': '...',        # human-readable explanation
}
```

### Examples

**Basic solve:**

```python
from larsdoku import solve

result = solve("4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........")
print(f"Solved in {result['n_steps']} steps")
```

**Pure logic with technique analysis:**

```python
result = solve(puzzle, no_oracle=True)

if result['success']:
    for tech, count in sorted(result['technique_counts'].items(), key=lambda x: -x[1]):
        print(f"  {tech}: {count}")
else:
    print(f"Stalled with {result['empty_remaining']} cells remaining")
```

**Detailed solve with elimination tracking:**

```python
result = solve(puzzle, detail=True, no_oracle=True)

for step in result['steps']:
    print(f"  #{step['step']:3d}  {step['cell']}={step['digit']}  [{step['technique']}]")
    if 'explanation' in step:
        print(f"         {step['explanation']}")
```

**Batch processing:**

```python
from larsdoku import solve
from larsdoku.puzzles import TOP1465

pure = 0
for puzzle in TOP1465:
    result = solve(puzzle, no_oracle=True)
    if result['success']:
        pure += 1

print(f"Pure logic: {pure}/{len(TOP1465)} ({100*pure/len(TOP1465):.1f}%)")
```

---

## Puzzle Collections

```python
from larsdoku.puzzles import FAMOUS_10, EXPERT_669, TOP1465
```

### FAMOUS_10

List of tuples: `(name, author, year, puzzle_string)`

```python
from larsdoku.puzzles import FAMOUS_10

for name, author, year, puzzle in FAMOUS_10:
    print(f"{name} by {author} ({year})")
```

### EXPERT_669

List of 81-character puzzle strings. 669 expert-level puzzles, box-shuffled.

```python
from larsdoku.puzzles import EXPERT_669
print(f"{len(EXPERT_669)} puzzles")
```

### TOP1465

List of 81-character puzzle strings (using `.` for empty cells). The canonical Stertenbrink/dukuso benchmark.

```python
from larsdoku.puzzles import TOP1465
print(f"{len(TOP1465)} puzzles")
```

---

## Web API (`--serve`)

When running `larsdoku --serve`, the engine exposes a REST API at `POST /api/solve`.

### Solve Request

```json
{
  "puzzle": "800000000003600000070090200...",
  "autotrust": true,
  "level": 7,
  "no_oracle": false,
  "gf2": false,
  "gf2x": false,
  "preset": "expert",
  "only": null,
  "exclude": null,
  "cell": null,
  "path": false
}
```

All fields except `puzzle` are optional.

| Field | Type | Default | Description |
|---|---|---|---|
| `puzzle` | `str` | required | 81-char puzzle string |
| `autotrust` | `bool` | `true` | Trust backtrack solution (enables DeepResonance) |
| `level` | `int` | `99` | Max technique level (1-7) |
| `no_oracle` | `bool` | `false` | Pure logic only |
| `gf2` | `bool` | `false` | Enable GF(2) Block Lanczos |
| `gf2x` | `bool` | `false` | Enable GF(2) Extended (implies gf2) |
| `preset` | `str` | `null` | `"expert"` or `"wsrf"` |
| `only` | `str` | `null` | Comma-separated technique list |
| `exclude` | `str` | `null` | Comma-separated exclusion list |
| `cell` | `str` | `null` | Cell query mode (e.g., `"R3C5"`) |
| `path` | `bool` | `false` | Include technique path (with `cell`) |

### Solve Response

```json
{
  "success": true,
  "steps": [
    {"step": 1, "pos": 14, "digit": 3, "technique": "crossHatch", "cell": "R2C6", "round": 1}
  ],
  "technique_counts": {"crossHatch": 42, "nakedSingle": 9},
  "elapsed_ms": 18.3,
  "solution": "812753649943682175...",
  "stalled": false,
  "empty_remaining": 0,
  "n_steps": 55,
  "elim_events": [
    {"round": 1, "technique": "SimpleColoring", "detail": "Simple Coloring: 5 eliminations", "count": 5}
  ]
}
```

### Cell Query Response

When `cell` is provided, the API calls `query_cell()` instead:

```json
{
  "cell": "R3C5",
  "answer": 9,
  "technique": "nakedSingle",
  "step": 48,
  "reachable": true,
  "candidates": [2, 9],
  "path": [{"step": 1, "pos": 14, "digit": 3, "technique": "crossHatch", "cell": "R2C6", "round": 1}],
  "elim_events": [...],
  "solve_status": "solved",
  "path_technique_counts": {"crossHatch": 22, "nakedSingle": 14},
  "elapsed_ms": 526.2,
  "message": "R3C5 = 9 via nakedSingle (step 48)"
}
```

---

## larsdoku-zs Board API

The `larsdoku-zs` package provides a higher-level `Board` class with zone intelligence and HYPERSIRO features.

```python
from larsdoku_zs import Board
```

### Board.solve_cascade()

Cascade solver: classifies each step as bottleneck (L3+) or cascade (L1-L2). Shows how the puzzle avalanches from a few hard moves.

```python
b = Board("980700600700000090006050000...")
result = b.solve_cascade()

print(f"Bottleneck depth: {result['bottleneck_depth']}")
print(f"Cascade placements: {result['cascade_count']}")
print(f"Ratio: 1:{result['cascade_count'] // max(1, result['bottleneck_depth'])}")

for m in result['bottleneck_moves']:
    print(f"  {m['cell']}={m['digit']} via {m['technique']}")
```

**Result:** On the 50 hardest puzzles, average bottleneck depth is 2.8 — just 3 hard moves, everything else cascades.

### Board.siro_solve()

Hybrid solver: techniques crack bottlenecks, SIRO predicts the rest.

```python
b = Board("980700600700000090006050000...")
result = b.siro_solve()

print(f"Predictions: {result['correct']}/{result['total_predictions']} ({result['accuracy']:.1%})")
print(f"Propagated: {result['propagated']} cells")
```

### Board.scandalous_exocet()

Post-solve validated Exocet scan. Solves with pure logic first, then checks if any Exocet patterns on the original board are valid.

```python
b = Board("980700600750000040003080070...")
results = b.scandalous_exocet(preset='larstech')

for r in results:
    print(f"{r['detail']}")
    print(f"Valid: {r['valid']}")
    print(f"Technique: {r['technique']}")  # 'ScandolousExocet'
```

**Why "Scandalous"?** It uses the solved board to validate — honest about the fact that it checked the answer first. Every validated pattern IS a real Exocet; the scandalous part is how we confirmed it.

---

## wsrf-zone-oracle (HYPERSIRO)

Zone-aware metrics across 10 dimensions for Sudoku prediction.

```python
from wsrf_zone_oracle import ZoneAnalyzer
```

### ZoneAnalyzer.analyze()

Full 10-zone analysis of a puzzle. Each cell gets metrics across row, col, box, band, stack, row-ML, col-ML, cross-band, cross-stack, and unconnected zones.

```python
analyzer = ZoneAnalyzer()
metrics = analyzer.analyze("980700600...", solution="985732641...")

cell = metrics.cells[pos]
for d, cm in cell.candidate_metrics.items():
    print(f"d={d}: row={cm.row_rivals} band={cm.band_rivals} "
          f"ML_confined={cm.row_ml_confined} chan={cm.band_boxes_placed+cm.stack_boxes_placed}")
```

### ZoneAnalyzer.hypersiro_cascade()

HYPERSIRO Cascade: channeling picks WHERE, SIRO picks WHAT. +16.2pp over standard SIRO on the hardest puzzles.

```python
result = analyzer.hypersiro_cascade("980700600...", solution="985732641...")
print(f"Accuracy: {result['accuracy']:.1%}")
print(f"Propagated: {result['propagated']} cells")
```

### ZoneAnalyzer.zone_hidden_singles()

Zone Position Hidden Singles — Lars's 11th dimension. Finds digits unique in their box-position group (TL/TC/TR/ML/MC/MR/BL/BC/BR). Zero overlap with standard hidden singles.

```python
zhs = analyzer.zone_hidden_singles("980700600...", solution="985732641...")
for z in zhs:
    print(f"R{z['row']+1}C{z['col']+1} d={z['digit']} {z['box_pos']} "
          f"{'PINNED' if z['pinned'] else 'unpinned'} ({z['confidence']:.1%})")
```

**Discovery:** 50.5% accuracy when pinned (row or col rivals ≤ 1). Zero overlap with any existing technique. A new constraint dimension.

---

## Engine Access

For advanced usage, you can access the bitwise engine directly:

```python
from larsdoku.engine import BitBoard, propagate_l1l2, solve_backtrack

# Create a board
bb = BitBoard.from_string("4...3.......6..8..........1....")

# Run L1+L2 propagation
placements = propagate_l1l2(bb)
print(f"L1+L2 placed {len(placements)} digits, {bb.empty} remaining")

# Get backtrack solution (for verification)
solution = solve_backtrack("4...3.......6..8..........1....")
```

!!! warning
    The engine API is lower-level and may change between versions. Use `solve()` for stable usage.
