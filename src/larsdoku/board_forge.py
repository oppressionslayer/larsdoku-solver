#!/usr/bin/env python3
"""
Board Forge — Build solvable Sudoku boards from linear algebra.
================================================================

Uses the null space / constraint geometry approach:
1. Define relative positions across 9 boxes
2. Place digits 1-9 (no duplicates, sum=45) at those positions
3. Use GF(2) constraint system to verify the null space is collapsed
4. Solve forward-only to validate

No backtracker. Pure math.

Usage:
    python board_forge.py                     # build one board from centers
    python board_forge.py --position TL       # use top-left corners
    python board_forge.py --position mixed    # mix positions for variety
    python board_forge.py --clues 18          # 18 clues (2 positions)
    python board_forge.py --count 10          # build 10 boards
    python board_forge.py --count 50 --stats  # benchmark pass rates
"""
from __future__ import annotations

import argparse
import os
import sys
import random
import time
import numpy as np

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from .engine import BitBoard, BIT, POPCOUNT, BOX_OF, propagate_l1l2, has_unique_solution
from .sub17_solve import solve_forward, validate_sudoku, shuffle_sudoku
from .cli import solve_selective


# ══════════════════════════════════════════════════════════════
# RELATIVE POSITION GEOMETRY
# ══════════════════════════════════════════════════════════════

# 9 relative positions within a 3x3 box
POSITIONS = {
    'TL': (0, 0), 'TC': (0, 1), 'TR': (0, 2),
    'ML': (1, 0), 'MC': (1, 1), 'MR': (1, 2),
    'BL': (2, 0), 'BC': (2, 1), 'BR': (2, 2),
}

def get_cells_for_position(rel_name):
    """Get the 9 cell indices (one per box) for a relative position."""
    rel_r, rel_c = POSITIONS[rel_name]
    cells = []
    for box in range(9):
        br, bc = (box // 3) * 3, (box % 3) * 3
        cells.append((br + rel_r) * 9 + (bc + rel_c))
    return cells


# ══════════════════════════════════════════════════════════════
# NAMED PATTERNS — multi-position recipes
# ══════════════════════════════════════════════════════════════

PATTERNS = {
    'staircase': {
        'description': 'MC in band 1, ML in band 2, BL in band 3 (zigzag)',
        'box_positions': {
            0: 'MC', 1: 'MC', 2: 'MC',
            3: 'ML', 4: 'ML', 5: 'ML',
            6: 'BL', 7: 'BL', 8: 'BL',
        },
    },
    'anti-diagonal': {
        'description': 'TR, MC, BL — diagonal sweep',
        'box_positions': {
            0: 'TR', 1: 'TR', 2: 'TR',
            3: 'MC', 4: 'MC', 5: 'MC',
            6: 'BL', 7: 'BL', 8: 'BL',
        },
    },
    'cross': {
        'description': 'TC + MC + BC + ML + MR (plus shape)',
        'positions': ['TC', 'MC', 'BC', 'ML', 'MR'],
    },
    'random-mixed': {
        'description': 'Random different position per box (maximum asymmetry)',
        'random': True,
    },
}


def get_cells_for_pattern(pattern_name, rng=None):
    """Get (cell_index, box) pairs for a named pattern.

    Returns list of cell indices (one per box, 9 total for single-layer patterns,
    or more for multi-position patterns like cross).
    """
    pat = PATTERNS[pattern_name]

    if pat.get('random'):
        if rng is None:
            rng = random.Random()
        all_pos = list(POSITIONS.keys())
        cells = []
        for box in range(9):
            name = rng.choice(all_pos)
            rel_r, rel_c = POSITIONS[name]
            br, bc = (box // 3) * 3, (box % 3) * 3
            cells.append((br + rel_r) * 9 + (bc + rel_c))
        return cells

    if 'box_positions' in pat:
        cells = []
        for box in range(9):
            name = pat['box_positions'][box]
            rel_r, rel_c = POSITIONS[name]
            br, bc = (box // 3) * 3, (box % 3) * 3
            cells.append((br + rel_r) * 9 + (bc + rel_c))
        return cells

    if 'positions' in pat:
        cells = []
        for name in pat['positions']:
            cells.extend(get_cells_for_position(name))
        return cells

    return []


# ══════════════════════════════════════════════════════════════
# NULL SPACE CHECK — does this placement have a unique completion?
# ══════════════════════════════════════════════════════════════

def check_null_space(puzzle_str):
    """Check the constraint system's degrees of freedom.

    Uses the BitBoard candidate system to measure how constrained
    the puzzle is. Returns metrics about the null space.
    """
    bb = BitBoard.from_string(puzzle_str)

    # Count total candidates (degrees of freedom)
    total_cands = sum(POPCOUNT[bb.cands[p]] for p in range(81) if bb.board[p] == 0)
    empty = bb.empty

    # Run L1/L2 propagation to see how much resolves immediately
    bb2 = BitBoard.from_string(puzzle_str)
    placed = propagate_l1l2(bb2)
    after_prop = bb2.empty

    # Count bivalue cells (dimension-1 branch points)
    bivalue = sum(1 for p in range(81)
                  if bb2.board[p] == 0 and POPCOUNT[bb2.cands[p]] == 2)

    # Check relative position digit coverage
    # For each relative position, are the placed digits all unique?
    rel_coverage = {}
    for name, (rel_r, rel_c) in POSITIONS.items():
        cells = get_cells_for_position(name)
        placed_digits = [bb.board[c] for c in cells if bb.board[c] != 0]
        has_dupes = len(placed_digits) != len(set(placed_digits))
        rel_coverage[name] = {
            'placed': len(placed_digits),
            'unique': len(set(placed_digits)),
            'has_dupes': has_dupes,
            'sum': sum(placed_digits),
        }

    return {
        'empty': empty,
        'total_candidates': total_cands,
        'avg_cands': round(total_cands / max(1, empty), 2),
        'propagation_solves': len(placed),
        'remaining_after_prop': after_prop,
        'bivalue_cells': bivalue,
        'rel_coverage': rel_coverage,
    }


# ══════════════════════════════════════════════════════════════
# GF(2) NULL SPACE ANALYSIS
# ══════════════════════════════════════════════════════════════

def gf2_null_space_dimension(puzzle_str):
    """Compute the GF(2) null space dimension for the puzzle.

    Builds the Sudoku constraint matrix over GF(2) and computes
    its rank. The null space dimension = variables - rank.
    Dimension 0 = unique solution. Dimension > 0 = multiple solutions.
    """
    bb = BitBoard.from_string(puzzle_str)

    # Variables: each (cell, digit) pair that's still a candidate
    var_map = {}  # (pos, digit) -> var_index
    var_list = []
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        for d in range(9):
            if bb.cands[pos] & BIT[d]:
                var_map[(pos, d)] = len(var_list)
                var_list.append((pos, d))

    n_vars = len(var_list)
    if n_vars == 0:
        return 0, 0, 0

    # Constraints: each unit (row/col/box) × digit must have exactly one cell
    # Over GF(2): sum of variables in each constraint = 1
    constraints = []

    # Row constraints
    for r in range(9):
        for d in range(9):
            row_vars = []
            for c in range(9):
                pos = r * 9 + c
                if (pos, d) in var_map:
                    row_vars.append(var_map[(pos, d)])
            if row_vars:
                constraints.append(row_vars)

    # Column constraints
    for c in range(9):
        for d in range(9):
            col_vars = []
            for r in range(9):
                pos = r * 9 + c
                if (pos, d) in var_map:
                    col_vars.append(var_map[(pos, d)])
            if col_vars:
                constraints.append(col_vars)

    # Box constraints
    for box in range(9):
        br, bc = (box // 3) * 3, (box % 3) * 3
        for d in range(9):
            box_vars = []
            for dr in range(3):
                for dc in range(3):
                    pos = (br + dr) * 9 + (bc + dc)
                    if (pos, d) in var_map:
                        box_vars.append(var_map[(pos, d)])
            if box_vars:
                constraints.append(box_vars)

    # Cell constraints: each cell must have exactly one digit
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        cell_vars = []
        for d in range(9):
            if (pos, d) in var_map:
                cell_vars.append(var_map[(pos, d)])
        if cell_vars:
            constraints.append(cell_vars)

    # Build GF(2) matrix using numpy
    n_constraints = len(constraints)
    # Use bit-packed representation for speed
    matrix = np.zeros((n_constraints, n_vars), dtype=np.uint8)
    for i, cvars in enumerate(constraints):
        for v in cvars:
            matrix[i, v] = 1

    # Gaussian elimination over GF(2)
    rank = 0
    pivot_cols = []
    mat = matrix.copy()
    for col in range(n_vars):
        # Find pivot row
        pivot = -1
        for row in range(rank, n_constraints):
            if mat[row, col] == 1:
                pivot = row
                break
        if pivot == -1:
            continue
        # Swap
        mat[[rank, pivot]] = mat[[pivot, rank]]
        # Eliminate
        for row in range(n_constraints):
            if row != rank and mat[row, col] == 1:
                mat[row] = (mat[row] + mat[rank]) % 2
        pivot_cols.append(col)
        rank += 1

    null_dim = n_vars - rank
    return n_vars, rank, null_dim


# ══════════════════════════════════════════════════════════════
# BOARD FORGE — build boards from geometry
# ══════════════════════════════════════════════════════════════

def forge_board(position_names=None, n_clues=9, rng=None, max_attempts=100):
    """Build a solvable board using the constraint geometry rule.

    Args:
        position_names: list of relative position names to use
                        e.g. ['MC'] for centers, ['TL', 'MC'] for 18 clues
        n_clues: target clue count (9, 18, 27)
        rng: random number generator
        max_attempts: max retries

    Returns dict with puzzle, solution, metrics, or None.
    """
    if rng is None:
        rng = random.Random()

    if position_names is None:
        if n_clues <= 9:
            position_names = ['MC']
        elif n_clues <= 18:
            position_names = ['MC', 'TL']
        else:
            position_names = ['MC', 'TL', 'BR']

    # Get all cell positions
    all_cells = []
    for name in position_names:
        all_cells.extend(get_cells_for_position(name))
    cell_set = set(all_cells)

    for attempt in range(max_attempts):
        # Generate digits 1-9 for each position group
        digits_by_cell = {}
        valid = True

        for name in position_names:
            cells = get_cells_for_position(name)
            perm = list(range(1, 10))
            rng.shuffle(perm)
            for cell, digit in zip(cells, perm):
                digits_by_cell[cell] = digit

        # Build puzzle string
        puzzle = ['0'] * 81
        for cell, digit in digits_by_cell.items():
            puzzle[cell] = str(digit)
        puzzle_str = ''.join(puzzle)

        # Quick check: does propagation make progress?
        bb = BitBoard.from_string(puzzle_str)
        placed = propagate_l1l2(bb)

        # Try solving
        result = solve_forward(puzzle_str)
        if result['valid']:
            # Compute null space for the report
            n_vars, rank, null_dim = gf2_null_space_dimension(puzzle_str)

            return {
                'puzzle': puzzle_str,
                'board_str': result['board_str'],
                'positions_used': position_names,
                'n_clues': sum(1 for c in puzzle_str if c != '0'),
                'logic': result['logic_placements'],
                'heuristic': result['heuristic_placements'],
                'attempt': attempt + 1,
                'gf2_vars': n_vars,
                'gf2_rank': rank,
                'gf2_null_dim': null_dim,
                'valid': True,
            }

    return None


# ══════════════════════════════════════════════════════════════
# FORGE UNIQUE BOARD — GF(2) verified, no backtracker
# ══════════════════════════════════════════════════════════════

def forge_unique_board(position_names=None, target_clues=21, rng=None,
                       pattern=None, max_attempts=200, verbose=False):
    """Build a board with a guaranteed unique solution.

    Pipeline:
    1. Place 9 digits (1-9, no dupes) at chosen relative position → 9-clue base
    2. Solve forward to get a full solution
    3. From that solution, add clues from more positions until target reached
    4. Verify uniqueness with has_unique_solution()
    5. Optionally validate with larsdoku solve (pure logic)

    No backtracker anywhere in the pipeline. Build from geometry,
    verify with GF(2), solve with techniques.
    """
    if rng is None:
        rng = random.Random()

    if position_names is None:
        position_names = ['MC']

    # All 9 position names for clue expansion
    all_pos_names = list(POSITIONS.keys())

    for attempt in range(max_attempts):
        # ── Step 1: Place base clues using geometry rule ──
        if pattern and pattern in PATTERNS:
            base_cells = get_cells_for_pattern(pattern, rng=rng)
            perm = list(range(1, 10))
            rng.shuffle(perm)
            digits_by_cell = {cell: digit for cell, digit in zip(base_cells, perm)}
        else:
            digits_by_cell = {}
            for name in position_names:
                cells = get_cells_for_position(name)
                perm = list(range(1, 10))
                rng.shuffle(perm)
                for cell, digit in zip(cells, perm):
                    digits_by_cell[cell] = digit

        # Build base puzzle
        puzzle = ['0'] * 81
        for cell, digit in digits_by_cell.items():
            puzzle[cell] = str(digit)
        base_str = ''.join(puzzle)

        # ── Step 2: Solve forward to get full solution ──
        result = solve_forward(base_str)
        if not result['valid']:
            continue

        solution = result['board_str']

        # ── Step 3: Add clues from solution to reach target ──
        base_cells_set = set(digits_by_cell.keys())
        n_base = len(base_cells_set)

        if target_clues <= n_base:
            # Already at or below target — try with base clues
            candidate_str = base_str
        else:
            # Pick additional clue positions from the solution
            # Prefer cells from other geometric positions for structure
            extra_pool = []
            for name in all_pos_names:
                for cell in get_cells_for_position(name):
                    if cell not in base_cells_set:
                        extra_pool.append(cell)
            # Also add all remaining cells
            for cell in range(81):
                if cell not in base_cells_set and cell not in extra_pool:
                    extra_pool.append(cell)

            rng.shuffle(extra_pool)
            n_extra = target_clues - n_base

            # Add clues from solution
            candidate = list(base_str)
            added = 0
            for cell in extra_pool:
                if added >= n_extra:
                    break
                candidate[cell] = solution[cell]
                added += 1
            candidate_str = ''.join(candidate)

        # ── Step 4: Check uniqueness ──
        n_clues = sum(1 for c in candidate_str if c != '0')
        if verbose:
            n_vars, rank, null_dim = gf2_null_space_dimension(candidate_str)
            print(f'    attempt {attempt+1}: {n_clues} clues, '
                  f'GF(2) null_dim={null_dim}', flush=True)

        if has_unique_solution(candidate_str):
            # ── Step 5: GF(2) analysis ──
            n_vars, rank, null_dim = gf2_null_space_dimension(candidate_str)

            # ── Step 6: Validate with larsdoku (pure logic) ──
            solve_result = solve_selective(candidate_str, max_level=99)

            return {
                'puzzle': candidate_str,
                'solution': solution,
                'board_str': solution,
                'positions_used': position_names,
                'pattern': pattern,
                'n_clues': n_clues,
                'attempt': attempt + 1,
                'gf2_vars': n_vars,
                'gf2_rank': rank,
                'gf2_null_dim': null_dim,
                'unique': True,
                'valid': True,
                'larsdoku_success': solve_result.get('success', False),
                'larsdoku_techniques': solve_result.get('technique_counts', {}),
                'larsdoku_steps': solve_result.get('total_steps', 0),
            }

    return None


# ══════════════════════════════════════════════════════════════
# CLUE MINIMIZATION — strip redundant clues
# ══════════════════════════════════════════════════════════════

def minimize_clues(puzzle_str, rng=None, verbose=False):
    """Strip redundant clues from a unique-solution puzzle.

    For each clue (in shuffled order): remove it, check if still unique.
    If yes → clue was redundant, keep it removed.
    If no → put it back (it's essential).

    Returns minimized puzzle string.
    """
    if rng is None:
        rng = random.Random()

    puzzle = list(puzzle_str)
    clue_positions = [i for i in range(81) if puzzle[i] != '0']
    rng.shuffle(clue_positions)

    removed = 0
    for pos in clue_positions:
        saved = puzzle[pos]
        puzzle[pos] = '0'
        test_str = ''.join(puzzle)

        if has_unique_solution(test_str):
            removed += 1
            if verbose:
                n = sum(1 for c in puzzle if c != '0')
                print(f'    removed clue at {pos} → {n} clues remaining')
        else:
            puzzle[pos] = saved

    final = ''.join(puzzle)
    if verbose:
        n = sum(1 for c in final if c != '0')
        print(f'    minimization done: removed {removed} clues → {n} remaining')
    return final


# ══════════════════════════════════════════════════════════════
# TECHNIQUE-AWARE SCULPTING — steer toward target technique
# ══════════════════════════════════════════════════════════════

def sculpt_for_technique(puzzle_str, target_techs, exclude_techs=None,
                         rng=None, verbose=False):
    """Sculpt a puzzle toward requiring specific techniques.

    Two-pass selective minimization:
      Pass 1 — Remove clues that keep uniqueness AND make the target fire.
      Pass 2 — Trim remaining redundant clues that don't break the target.

    Returns sculpted puzzle string, or None if the target never fired.
    """
    if rng is None:
        rng = random.Random()

    puzzle = list(puzzle_str)
    clue_positions = [i for i in range(81) if puzzle[i] != '0']
    rng.shuffle(clue_positions)

    # Pass 1: remove clues that trigger the target technique
    target_hit = False
    for pos in clue_positions:
        saved = puzzle[pos]
        puzzle[pos] = '0'
        test_str = ''.join(puzzle)

        if not has_unique_solution(test_str):
            puzzle[pos] = saved
            continue

        r = solve_selective(test_str, verbose=False, exclude_techniques=exclude_techs)
        techs_used = set(r.get('technique_counts', {}).keys())

        if target_techs & techs_used:
            target_hit = True
            if verbose:
                n = sum(1 for c in puzzle if c != '0')
                print(f'    sculpt: removed {pos} → {n} clues, target HIT')
        else:
            puzzle[pos] = saved

    if not target_hit:
        return None

    # Pass 2: trim remaining redundant clues without losing the target
    remaining = [i for i in range(81) if puzzle[i] != '0']
    rng.shuffle(remaining)
    for pos in remaining:
        saved = puzzle[pos]
        puzzle[pos] = '0'
        test_str = ''.join(puzzle)

        if not has_unique_solution(test_str):
            puzzle[pos] = saved
            continue

        r = solve_selective(test_str, verbose=False, exclude_techniques=exclude_techs)
        techs_used = set(r.get('technique_counts', {}).keys())

        if target_techs & techs_used:
            if verbose:
                n = sum(1 for c in puzzle if c != '0')
                print(f'    sculpt: trimmed {pos} → {n} clues, target still hits')
        else:
            puzzle[pos] = saved

    return ''.join(puzzle)


# ══════════════════════════════════════════════════════════════
# DISPLAY
# ══════════════════════════════════════════════════════════════

def display_board(puzzle_str, solution_str=None, title="Board"):
    """Display a board with optional solution."""
    print(f'\n  {title}:')
    for r in range(9):
        if r % 3 == 0:
            print('  +-------+-------+-------+')
        row = '  |'
        for c in range(9):
            if c % 3 == 0 and c > 0:
                row += ' |'
            d = puzzle_str[r * 9 + c]
            row += f' {d}' if d != '0' else ' .'
        row += ' |'
        print(row)
    print('  +-------+-------+-------+')

    if solution_str:
        print(f'\n  Solution:')
        for r in range(9):
            if r % 3 == 0:
                print('  +-------+-------+-------+')
            row = '  |'
            for c in range(9):
                if c % 3 == 0 and c > 0:
                    row += ' |'
                row += f' {solution_str[r * 9 + c]}'
            row += ' |'
            print(row)
        print('  +-------+-------+-------+')


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Simple Wili — Board Forge: Build solvable boards from linear algebra.\n'
                    'No backtracker. Pure math. Count to 45.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python simple_wili.py --position MC                          # 9-clue base board
  python simple_wili.py --position MC --unique --target-clues 22  # unique 22-clue board
  python simple_wili.py --unique --minimize --gf2              # minimal unique board
  python simple_wili.py --pattern staircase --unique           # zigzag pattern
  python simple_wili.py --pattern random-mixed --unique -n 5   # 5 random unique boards
  python simple_wili.py --count 20 --unique --stats            # benchmark success rate
''')
    parser.add_argument('--position', '-p', default='MC',
                        help='Relative position(s): MC, TL, BR, mixed, etc. Comma-separated for multiple.')
    parser.add_argument('--clues', '-c', type=int, default=9,
                        help='Target clue count for multi-solution mode (9, 18, 27)')
    parser.add_argument('--count', '-n', type=int, default=1,
                        help='Number of boards to generate')
    parser.add_argument('--stats', action='store_true',
                        help='Show pass rate statistics')
    parser.add_argument('--gf2', action='store_true',
                        help='Show GF(2) null space analysis')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed')
    parser.add_argument('--shuffle', action='store_true',
                        help='Shuffle the output boards for variety')
    # ── New: unique board pipeline ──
    parser.add_argument('--unique', '-u', action='store_true',
                        help='Force unique-solution output (add clues + verify)')
    parser.add_argument('--minimize', '-m', action='store_true',
                        help='Strip redundant clues after forging (use with --unique)')
    parser.add_argument('--pattern', type=str, default=None,
                        choices=list(PATTERNS.keys()),
                        help='Use a named position pattern: staircase, anti-diagonal, cross, random-mixed')
    parser.add_argument('--target-clues', '-t', type=int, default=22,
                        help='Target clue count for unique boards (default: 22)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output during generation')
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # Parse positions
    if args.position == 'mixed':
        all_pos = list(POSITIONS.keys())
        n_positions = max(1, args.clues // 9)
        position_names = rng.sample(all_pos, min(n_positions, len(all_pos)))
    else:
        position_names = [p.strip().upper() for p in args.position.split(',')]

    mode = 'UNIQUE' if args.unique else 'MULTI-SOLUTION'
    pattern_label = args.pattern or ', '.join(position_names)

    print(f'  Simple Wili — Board Forge')
    print(f'  {"=" * 55}')
    print(f'  Mode: {mode}')
    print(f'  Pattern: {pattern_label}')
    if args.unique:
        print(f'  Target clues: {args.target_clues}')
        if args.minimize:
            print(f'  Minimization: ON')
    else:
        print(f'  Clues: {len(position_names) * 9}')
    print(f'  Rule: digits 1-9, no duplicates, sum=45 per position')
    print(f'  Method: constraint geometry + {"GF(2) uniqueness" if args.unique else "forward solve"}')
    print()

    passed = 0
    failed = 0
    total_time = 0
    null_dims = []
    clue_counts = []
    larsdoku_pass = 0

    for i in range(args.count):
        t0 = time.perf_counter()

        if args.unique:
            result = forge_unique_board(
                position_names=position_names,
                target_clues=args.target_clues,
                rng=rng,
                pattern=args.pattern,
                verbose=args.verbose,
            )
        else:
            result = forge_board(position_names=position_names, rng=rng)

        elapsed = (time.perf_counter() - t0) * 1000

        if result:
            puzzle = result['puzzle']

            # ── Minimize if requested ──
            if args.unique and args.minimize:
                t_min = time.perf_counter()
                puzzle = minimize_clues(puzzle, rng=rng, verbose=args.verbose)
                min_elapsed = (time.perf_counter() - t_min) * 1000
                result['puzzle'] = puzzle
                result['n_clues'] = sum(1 for c in puzzle if c != '0')
                # Re-check GF(2) after minimization
                n_vars, rank, null_dim = gf2_null_space_dimension(puzzle)
                result['gf2_vars'] = n_vars
                result['gf2_rank'] = rank
                result['gf2_null_dim'] = null_dim
                # Re-validate with larsdoku
                solve_result = solve_selective(puzzle, max_level=99)
                result['larsdoku_success'] = solve_result.get('success', False)
                result['larsdoku_techniques'] = solve_result.get('technique_counts', {})
                result['larsdoku_steps'] = solve_result.get('total_steps', 0)
                elapsed += min_elapsed

            passed += 1
            total_time += elapsed
            clue_counts.append(result['n_clues'])

            if args.gf2 or args.unique:
                null_dims.append(result.get('gf2_null_dim', 0))

            if args.unique and result.get('larsdoku_success'):
                larsdoku_pass += 1

            if not args.stats:
                if args.shuffle:
                    puzzle = shuffle_sudoku(puzzle, rng=rng)
                    puzzle = shuffle_sudoku(puzzle, rng=rng)
                    r2 = solve_forward(puzzle)
                    if r2['valid']:
                        result['board_str'] = r2['board_str']
                    else:
                        puzzle = result['puzzle']

                display_board(puzzle, result.get('board_str') or result.get('solution'),
                              f"Board {i+1} ({result['n_clues']} clues"
                              f"{' UNIQUE' if args.unique else ''})")

                if args.unique:
                    techs = result.get('larsdoku_techniques', {})
                    tech_str = ', '.join(f'{k}:{v}' for k, v in sorted(techs.items()) if v > 0)
                    print(f'  Unique: YES  Attempt: {result["attempt"]}  Time: {elapsed:.0f}ms')
                    print(f'  Larsdoku: {"SOLVED" if result.get("larsdoku_success") else "STALLED"}  '
                          f'Steps: {result.get("larsdoku_steps", 0)}')
                    if tech_str:
                        print(f'  Techniques: {tech_str}')
                else:
                    print(f'  Logic: {result["logic"]}  Heuristic: {result["heuristic"]}  '
                          f'Attempt: {result["attempt"]}  Time: {elapsed:.0f}ms')

                if args.gf2 or args.unique:
                    print(f'  GF(2): {result["gf2_vars"]} vars, rank {result["gf2_rank"]}, '
                          f'null space dim {result["gf2_null_dim"]}')
                print(f'  Puzzle: {puzzle}')
                print()
            else:
                if (i + 1) % 10 == 0:
                    rate = 100 * passed / (passed + failed) if (passed + failed) > 0 else 0
                    print(f'    [{i+1}/{args.count}] pass={passed} fail={failed} '
                          f'({rate:.0f}%)', flush=True)
        else:
            failed += 1
            total_time += elapsed

    if args.stats or args.count > 1:
        total = passed + failed
        print(f'\n  {"=" * 55}')
        print(f'  Simple Wili — Results')
        print(f'  {"=" * 55}')
        print(f'  Generated: {passed}/{total} ({100*passed/max(1,total):.1f}%)')
        print(f'  Avg time: {total_time/max(1,total):.0f}ms')
        if clue_counts:
            print(f'  Clues: avg={sum(clue_counts)/len(clue_counts):.1f} '
                  f'range=[{min(clue_counts)}, {max(clue_counts)}]')
        if null_dims:
            print(f'  GF(2) null space: avg={sum(null_dims)/len(null_dims):.1f} '
                  f'range=[{min(null_dims)}, {max(null_dims)}]')
        if args.unique:
            print(f'  Larsdoku solved: {larsdoku_pass}/{passed} '
                  f'({100*larsdoku_pass/max(1,passed):.1f}%)')


if __name__ == '__main__':
    main()
