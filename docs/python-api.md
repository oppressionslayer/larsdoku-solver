# Python API

## Quick Start

```python
from larsdoku import solve

result = solve("806090207040705090701000405080000050500000004020000010208000906030609070109070503")
```

## `solve(puzzle, **kwargs)`

Main entry point. Solves a puzzle using pure logic techniques.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `puzzle` | str | required | 81-character puzzle string |
| `max_level` | int | 99 | Maximum technique level (1-7) |
| `only_techniques` | set | None | Restrict to these techniques only |
| `detail` | bool | False | Capture elimination events |
| `verbose` | bool | False | Print each step as it happens |

### Returns

Dictionary with:

| Key | Type | Description |
|-----|------|-------------|
| `success` | bool | True if fully solved |
| `stalled` | bool | True if solver ran out of techniques |
| `n_steps` | int | Number of placements made |
| `board` | str | 81-char string of final board state |
| `empty_remaining` | int | Cells still empty (0 if solved) |
| `technique_counts` | dict | `{technique_name: count}` |
| `steps` | list | Step-by-step placement records |
| `rounds` | int | Number of solve rounds |
| `elim_events` | list | Elimination events (if `detail=True`) |

### Example

```python
from larsdoku import solve
from larsdoku.cli import EXPERT_APPROVED

# Solve with expert techniques only
result = solve(
    "806090207040705090701000405080000050500000004020000010208000906030609070109070503",
    only_techniques=EXPERT_APPROVED,
    detail=True
)

if result['success']:
    print(f"Solved in {result['n_steps']} steps")
    for tech, count in sorted(result['technique_counts'].items(), key=lambda x: -x[1]):
        print(f"  {tech}: {count}")
else:
    print(f"Stalled with {result['empty_remaining']} cells remaining")
```

## `validate_sudoku(board)`

Check a completed board by Sudoku law.

```python
from larsdoku import validate_sudoku

board = [int(c) for c in result['board']]
assert validate_sudoku(board)  # True if valid
```

## `BitBoard`

Low-level board representation with bitmask candidates.

```python
from larsdoku import BitBoard

bb = BitBoard.from_string("806090207...")
print(bb.empty)        # number of empty cells
print(bb.board[0])     # digit at position 0 (0 = empty)
print(bb.cands[0])     # 9-bit candidate mask for position 0
```
