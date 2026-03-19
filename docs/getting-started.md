# Getting Started

## Installation

```bash
pip install larsdoku
```

### Requirements

- Python >= 3.9
- NumPy >= 1.22
- Numba >= 0.56 (provides JIT compilation for the hot path)

## Your First Solve

### Python

```python
from larsdoku import solve

# Any 81-character string works (0 or . for empty cells)
puzzle = "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........"

result = solve(puzzle, no_oracle=True)

print(f"Solved: {result['success']}")
print(f"Steps:  {result['n_steps']}")
print(f"Board:  {result['board']}")

# See which techniques were used
for tech, count in sorted(result['technique_counts'].items(), key=lambda x: -x[1]):
    print(f"  {tech}: {count}")
```

### Command Line

```bash
# Basic solve with board output
larsdoku "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........" --board

# Watch the engine think step-by-step
larsdoku "100007090030020008009600500005300900010080002600004000300000010040000007007000300" --steps

# Detailed round-by-round trace with candidates
larsdoku "100000002090400050006000700050903000000070000000850040700000600030009080002000001" --detail --board
```

## Puzzle Format

Puzzles are 81 characters long, representing the board row by row, left to right, top to bottom.

- Use `0` or `.` for empty cells
- Digits `1-9` for given clues

```
Row 1: positions  1-9
Row 2: positions 10-18
...
Row 9: positions 73-81
```

Both formats are equivalent:

```
003000600900700010080005020600010900200807003004090005020500060010003002005000300
..3...6..9..7...1..8...5.2.6...1.9..2..8.7..3..4.9...5.2.5...6..1...3..2..5...3..
```

## Try the Famous Puzzles

```python
from larsdoku import solve
from larsdoku.puzzles import FAMOUS_10

for name, author, year, puzzle in FAMOUS_10:
    result = solve(puzzle, no_oracle=True)
    status = "SOLVED" if result['success'] else "STALLED"
    print(f"{name:30s} ({author}, {year})  {status}  {result['n_steps']} steps")
```

## Run Benchmarks

```bash
# All collections
larsdoku-bench

# Just the Top1465
larsdoku-bench --collection top1465

# Quick test (first 50)
larsdoku-bench --collection top1465 --limit 50
```
