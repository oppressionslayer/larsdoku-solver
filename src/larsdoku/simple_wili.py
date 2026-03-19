#!/usr/bin/env python3
"""
Simple Wili — Board Forge
=========================
Build solvable Sudoku boards from pure linear algebra.
No backtracker. Pure math. Count to 45.

Sir Lars discovered: place digits 1-9 (no duplicates, sum=45) at the
same relative position across all 9 boxes → the constraint geometry
collapses the null space. Centers give 94-100% solve rate with just 9 clues.

Two modes:
  UNIQUE      — GF(2) verified unique solution, validated by larsdoku
  MULTI       — forward solve, no uniqueness check (sparse challenge fun)

Usage:
    python simple_wili.py                                    # 9-clue base board
    python simple_wili.py --unique --target-clues 22         # unique 22-clue board
    python simple_wili.py --unique --minimize --gf2          # minimal unique board
    python simple_wili.py --pattern staircase --unique       # zigzag pattern
    python simple_wili.py --count 20 --unique --stats        # benchmark success rate

    # ── but but but, at 17 clues it should be zero! ──
    # please see the --simple-wili documentation, good sir :-)
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

    # Strategy: overshoot with ~45 clues to guarantee uniqueness,
    # then minimize down to target. This works because:
    #   - forward solve is expensive (~5s) but gives us the full solution
    #   - has_unique_solution() is fast (~0ms)
    #   - minimize_clues() strips redundant clues fast (~2ms)
    # The geometry provides the base, minimize finds the essential clues.

    OVERSHOOT = 36  # extra clues from solution to start with

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

        # ── Step 3: Overshoot — add lots of clues from solution ──
        base_cells_set = set(digits_by_cell.keys())
        extra_all = [i for i in range(81) if i not in base_cells_set]

        # Try a few different random overshoot selections
        for clue_try in range(20):
            rng.shuffle(extra_all)
            candidate = list(base_str)
            for cell in extra_all[:OVERSHOOT]:
                candidate[cell] = solution[cell]
            fat_str = ''.join(candidate)

            if not has_unique_solution(fat_str):
                continue

            # ── Step 4: Minimize down toward target ──
            minimized = minimize_clues(fat_str, rng=rng, verbose=verbose)
            n_clues = sum(1 for c in minimized if c != '0')

            if verbose:
                print(f'    attempt {attempt+1}.{clue_try+1}: '
                      f'minimized to {n_clues} clues', flush=True)

            # ── Step 5: GF(2) analysis ──
            n_vars, rank, null_dim = gf2_null_space_dimension(minimized)

            # ── Step 6: Validate with larsdoku (pure logic) ──
            solve_result = solve_selective(minimized, max_level=99)

            return {
                'puzzle': minimized,
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
# MULTIVERSE — tiered solves across multiple solution universes
# ══════════════════════════════════════════════════════════════

def multiverse_solve(puzzle_str, max_solutions=100, verbose=False):
    """Multiverse tiered solve — find all solutions, solve each with trust.

    Uses unnecessary.py (the backtracker) to find all universes,
    then runs larsdoku on each to show technique profiles.
    """
    from unnecessary import find_solutions

    t0 = time.perf_counter()
    solutions = find_solutions(puzzle_str, max_solutions=max_solutions)
    find_elapsed = (time.perf_counter() - t0) * 1000

    n_clues = sum(1 for c in puzzle_str if c != '0')
    unique = len(solutions) == 1

    results = []
    for i, sol in enumerate(solutions):
        t1 = time.perf_counter()
        solve_result = solve_selective(puzzle_str, max_level=99)
        solve_elapsed = (time.perf_counter() - t1) * 1000

        results.append({
            'universe': i + 1,
            'solution': sol,
            'success': solve_result.get('success', False),
            'techniques': solve_result.get('technique_counts', {}),
            'steps': solve_result.get('total_steps', 0),
            'time_ms': solve_elapsed,
        })

    return {
        'puzzle': puzzle_str,
        'n_clues': n_clues,
        'n_solutions': len(solutions),
        'unique': unique,
        'find_time_ms': find_elapsed,
        'universes': results,
    }


# ══════════════════════════════════════════════════════════════
# MULTIVERSE TRAP — board that breaks every solver
# ══════════════════════════════════════════════════════════════

# L1-L3 techniques a human can do with pencil and paper
HUMAN_TECHNIQUES = {
    'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining',  # L1
    'XWing', 'Swordfish', 'EmptyRectangle',                      # L3
}


def _classify_multiverse_pocket(unstable_cells, solutions):
    """Classify the pattern of the multiverse pocket.

    Returns (pattern_type, description).
    """
    if not unstable_cells:
        return 'none', 'No unstable cells'

    n = len(unstable_cells)

    # Get rows, cols, boxes of unstable cells
    rows = set(p // 9 for p in unstable_cells)
    cols = set(p % 9 for p in unstable_cells)
    boxes = set((p // 9 // 3) * 3 + (p % 9 // 3) for p in unstable_cells)

    # Check for deadly rectangle: exactly 4 cells, 2 rows, 2 cols, 2 boxes
    if n == 4 and len(rows) == 2 and len(cols) == 2 and len(boxes) == 2:
        # Verify: 2 digits swap
        digits_at = {}
        for pos in unstable_cells:
            digits_at[pos] = set(sol[pos] for sol in solutions)
        all_digits = set()
        for ds in digits_at.values():
            all_digits |= ds
        if len(all_digits) == 2:
            d1, d2 = sorted(all_digits)
            r1, r2 = sorted(rows)
            c1, c2 = sorted(cols)
            return 'deadly_rectangle', (
                f'Deadly Rectangle: R{r1+1}C{c1+1}/R{r1+1}C{c2+1}/'
                f'R{r2+1}C{c1+1}/R{r2+1}C{c2+1} — digits {d1}/{d2} swap')

    # Check for digit swap: exactly 2 cells, same unit
    if n == 2:
        p1, p2 = sorted(unstable_cells)
        r1, c1 = p1 // 9, p1 % 9
        r2, c2 = p2 // 9, p2 % 9
        same_row = r1 == r2
        same_col = c1 == c2
        same_box = (r1 // 3 == r2 // 3) and (c1 // 3 == c2 // 3)
        if same_row or same_col or same_box:
            digits = set(sol[p1] for sol in solutions) | set(sol[p2] for sol in solutions)
            if len(digits) == 2:
                d1, d2 = sorted(digits)
                return 'digit_swap', (
                    f'Digit Swap: R{r1+1}C{c1+1} & R{r2+1}C{c2+1} — '
                    f'digits {d1}/{d2} interchange')

    # Pocket: all in 1-2 boxes
    if len(boxes) <= 2:
        return 'pocket', f'Pocket: {n} cells in {len(boxes)} box(es)'

    # Scattered
    return 'scattered', f'Scattered: {n} cells across {len(boxes)} boxes'


def forge_multiverse_trap(target_solutions=2, max_unstable=6,
                          rng=None, max_attempts=50, verbose=False):
    """Forge a Multiverse Trap — a board that breaks every solver.

    Creates a board that:
    1. Looks like a normal puzzle (23 clues, clean layout)
    2. Is human-solvable with L1-L3 techniques (stable cells)
    3. Has multiple valid solutions (multiverse pocket)
    4. Breaks any solver that assumes uniqueness

    Strategy: start with a unique board, surgically remove 1 clue
    to open the smallest possible multiverse pocket.
    """
    from unnecessary import find_solutions

    if rng is None:
        rng = random.Random()

    from unnecessary import find_solutions

    # Use non-minimized boards (~34 clues) — more clues means each removal
    # creates a smaller, cleaner multiverse pocket.
    TRAP_BASE_CLUES = 34

    for attempt in range(max_attempts):
        if verbose:
            print(f'  Attempt {attempt + 1}: forging unique base...', flush=True)

        # Step 1: Forge a NON-minimized unique base board
        # We overshoot with extra clues and DON'T minimize — that's the key.
        base = forge_board(position_names=['MC'], rng=rng)
        if not base:
            continue

        solution = base['board_str']
        base_puzzle = base['puzzle']
        base_cells = {i for i in range(81) if base_puzzle[i] != '0'}
        extra_all = [i for i in range(81) if i not in base_cells]
        n_extra = TRAP_BASE_CLUES - len(base_cells)

        # Try to find a unique board at this clue count
        unique_puzzle = None
        for _ in range(30):
            rng.shuffle(extra_all)
            cand = list(base_puzzle)
            for cell in extra_all[:n_extra]:
                cand[cell] = solution[cell]
            cand_str = ''.join(cand)
            if has_unique_solution(cand_str):
                unique_puzzle = cand_str
                break

        if unique_puzzle is None:
            continue

        clue_positions = [i for i in range(81) if unique_puzzle[i] != '0']
        rng.shuffle(clue_positions)

        if verbose:
            n = len(clue_positions)
            print(f'    Base: {n} clues, testing each removal...', flush=True)

        # Step 2: Test each clue removal
        best = None
        best_score = (999, 999)  # (n_unstable, n_boxes) — lower is better

        for pos in clue_positions:
            test = list(unique_puzzle)
            test[pos] = '0'
            test_str = ''.join(test)

            solutions = find_solutions(test_str, max_solutions=target_solutions + 5)
            n_sol = len(solutions)

            if n_sol < 2 or n_sol > target_solutions + 3:
                continue

            # Compute stable/unstable
            stable = []
            unstable = []
            unstable_digits = {}
            for cell in range(81):
                if test_str[cell] != '0':
                    continue
                vals = set(sol[cell] for sol in solutions)
                if len(vals) == 1:
                    stable.append(cell)
                else:
                    unstable.append(cell)
                    unstable_digits[cell] = vals

            if len(unstable) > max_unstable:
                continue

            # Score: fewer unstable cells, fewer boxes involved
            n_boxes = len(set((p // 9 // 3) * 3 + (p % 9 // 3) for p in unstable))
            score = (len(unstable), n_boxes)

            if verbose:
                print(f'    Remove R{pos//9+1}C{pos%9+1}: '
                      f'{n_sol} solutions, {len(unstable)} unstable, '
                      f'{n_boxes} boxes', flush=True)

            if score < best_score:
                best_score = score
                best = {
                    'test_str': test_str,
                    'removed_pos': pos,
                    'solutions': solutions,
                    'stable': stable,
                    'unstable': unstable,
                    'unstable_digits': unstable_digits,
                }

        if best is None:
            if verbose:
                print(f'    No clean pocket found, retrying...', flush=True)
            continue

        trap_puzzle = best['test_str']
        solutions = best['solutions']
        stable = best['stable']
        unstable = best['unstable']

        # Step 3: Validate with L1-L3 human solve
        solve_result = solve_selective(
            trap_puzzle, max_level=3, only_techniques=HUMAN_TECHNIQUES)
        l1l3_success = solve_result.get('success', False)
        l1l3_steps = solve_result.get('total_steps', 0)
        l1l3_techniques = solve_result.get('technique_counts', {})

        # Count how many stable cells L1-L3 placed
        if l1l3_success:
            l1l3_solved = len(stable)
        else:
            # Check partial progress — count placed cells that match stable
            placed = solve_result.get('placements', 0)
            l1l3_solved = placed if placed else l1l3_steps

        stable_pct = 100 * len(stable) / max(1, len(stable) + len(unstable))

        if verbose:
            print(f'    L1-L3: {"SOLVED" if l1l3_success else "PARTIAL"} '
                  f'stable={len(stable)}, unstable={len(unstable)}, '
                  f'{stable_pct:.0f}% stable', flush=True)

        # Step 4: Classify the pattern
        pattern_type, pattern_desc = _classify_multiverse_pocket(
            unstable, solutions)

        # Step 5: GF(2) analysis
        n_vars, rank, null_dim = gf2_null_space_dimension(trap_puzzle)

        n_clues = sum(1 for c in trap_puzzle if c != '0')

        return {
            'puzzle': trap_puzzle,
            'solutions': solutions,
            'n_solutions': len(solutions),
            'n_clues': n_clues,
            'stable_cells': stable,
            'unstable_cells': unstable,
            'unstable_digits': best['unstable_digits'],
            'stable_pct': stable_pct,
            'l1l3_success': l1l3_success,
            'l1l3_solved': l1l3_solved,
            'l1l3_steps': l1l3_steps,
            'l1l3_techniques': l1l3_techniques,
            'pattern_type': pattern_type,
            'pattern_desc': pattern_desc,
            'gf2_vars': n_vars,
            'gf2_rank': rank,
            'gf2_null_dim': null_dim,
            'removed_clue': best['removed_pos'],
            'original_unique_puzzle': unique_puzzle,
            'attempt': attempt + 1,
        }

    return None


def display_multiverse_trap(result):
    """Display a Multiverse Trap board with full analysis."""
    puzzle = result['puzzle']
    solutions = result['solutions']
    unstable = set(result['unstable_cells'])
    unstable_digits = result['unstable_digits']

    # 1. The puzzle (looks normal)
    print(f'\n  Simple Wili — Multiverse Trap')
    print(f'  {"=" * 55}')
    display_board(puzzle, title=f'Puzzle ({result["n_clues"]} clues)')

    # 2. L1-L3 solve progress — stable cells filled, unstable as ?
    stable_board = list('0' * 81)
    for i in range(81):
        if puzzle[i] != '0':
            stable_board[i] = puzzle[i]
    # Fill stable cells from any solution (they all agree)
    ref = solutions[0]
    for pos in result['stable_cells']:
        stable_board[pos] = ref[pos]
    for pos in result['unstable_cells']:
        stable_board[pos] = '?'
    stable_str = ''.join(stable_board)

    print(f'\n  L1-L3 Human Solve (? = multiverse pocket):')
    for r in range(9):
        if r % 3 == 0:
            print('  +-------+-------+-------+')
        row = '  |'
        for c in range(9):
            if c % 3 == 0 and c > 0:
                row += ' |'
            ch = stable_str[r * 9 + c]
            if ch == '?':
                row += ' ?'
            elif ch == '0':
                row += ' .'
            else:
                row += f' {ch}'
        row += ' |'
        print(row)
    print('  +-------+-------+-------+')

    # 3. Multiverse pocket details
    print(f'\n  Multiverse Pocket:')
    print(f'    Pattern: {result["pattern_desc"]}')
    print(f'    Unstable cells: {len(result["unstable_cells"])}')
    for pos in sorted(result['unstable_cells']):
        digits = sorted(unstable_digits[pos])
        print(f'      R{pos//9+1}C{pos%9+1}: could be {" or ".join(digits)}')

    # 4. All solutions
    print(f'\n  Universes ({result["n_solutions"]} valid solutions):')
    for i, sol in enumerate(solutions):
        diffs = sum(1 for a, b in zip(solutions[0], sol) if a != b) if i > 0 else 0
        label = '' if i == 0 else f'  ({diffs} cells differ)'
        print(f'    U{i+1}: {sol}{label}')

    # 5. Statistics
    print(f'\n  Analysis:')
    print(f'    Clues: {result["n_clues"]}')
    print(f'    Solutions: {result["n_solutions"]}')
    print(f'    Stable cells: {len(result["stable_cells"])}/{len(result["stable_cells"])+len(result["unstable_cells"])} '
          f'({result["stable_pct"]:.1f}%)')
    print(f'    L1-L3 solve: {"COMPLETE" if result["l1l3_success"] else "PARTIAL"} '
          f'({result["l1l3_steps"]} steps)')
    techs = result.get('l1l3_techniques', {})
    if techs:
        tech_str = ', '.join(f'{k}:{v}' for k, v in sorted(techs.items()) if v > 0)
        print(f'    Techniques: {tech_str}')
    print(f'    GF(2): {result["gf2_vars"]} vars, rank {result["gf2_rank"]}, '
          f'null dim {result["gf2_null_dim"]}')
    print(f'    Removed clue: R{result["removed_clue"]//9+1}C{result["removed_clue"]%9+1}')

    # 6. The trap report
    print(f'\n  {"─" * 55}')
    print(f'  Trap Report:')
    print(f'  {"─" * 55}')
    print(f'  This board has {result["n_solutions"]} valid solutions.')
    print(f'  A human with L1-L3 skills solves {len(result["stable_cells"])} cells with pure logic.')
    print(f'  The remaining {len(result["unstable_cells"])} cells have {result["n_solutions"]} valid completions.')
    print(f'  Any solver that assumes uniqueness will:')
    print(f'    - Reject it as "invalid"')
    print(f'    - Pick one solution arbitrarily (why that one?)')
    print(f'    - Stall completely')
    print(f'  The backtracker is unnecessary, good sir.')
    print()


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
  python simple_wili.py --multiverse <puzzle> --max-solutions 50  # multiverse solve
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
    # ── Multiverse: multi-solution exploration ──
    parser.add_argument('--multiverse', type=str, default=None, metavar='PUZZLE',
                        help='Find solutions of a multi-solution board and solve each')
    parser.add_argument('--max-solutions', type=int, default=100,
                        help='Max solutions to find in multiverse mode (default: 100)')
    # ── Multiverse Trap: board that breaks every solver ──
    parser.add_argument('--multiverse-trap', action='store_true',
                        help='Forge a Multiverse Trap board (human-solvable, multi-solution)')
    parser.add_argument('--trap-solutions', type=int, default=2,
                        help='Target solution count for trap (default: 2)')
    parser.add_argument('--trap-max-unstable', type=int, default=6,
                        help='Max unstable cells in trap (default: 6)')
    args = parser.parse_args()

    # ── Multiverse mode: separate flow ──
    if args.multiverse:
        from unnecessary import find_solutions

        puzzle = args.multiverse
        n_clues = sum(1 for c in puzzle if c != '0')

        print(f'  Simple Wili — Multiverse Solve')
        print(f'  {"=" * 55}')
        print(f'  Puzzle: {puzzle[:30]}...')
        print(f'  Clues: {n_clues}')
        print(f'  Max universes: {args.max_solutions}')
        print()

        t0 = time.perf_counter()
        solutions = find_solutions(puzzle, max_solutions=args.max_solutions)
        find_elapsed = (time.perf_counter() - t0) * 1000

        # GF(2) solution estimate
        n_vars, rank, null_dim = gf2_null_space_dimension(puzzle)
        gf2_upper = 2 ** null_dim if null_dim < 30 else float('inf')

        print(f'  Universes found: {len(solutions)}'
              f'{"  (limit reached)" if len(solutions) >= args.max_solutions else ""}')
        print(f'  Unique: {"YES" if len(solutions) == 1 else "NO"}')
        print(f'  Search time: {find_elapsed:.1f}ms')
        print()
        print(f'  GF(2) Analysis:')
        print(f'    Variables: {n_vars}  Rank: {rank}  Null dim: {null_dim}')
        print(f'    Upper bound: 2^{null_dim} = {gf2_upper if gf2_upper != float("inf") else "huge"}')
        if len(solutions) > 0 and gf2_upper != float('inf'):
            density = len(solutions) / gf2_upper * 100
            print(f'    Solution density: {len(solutions)}/{gf2_upper} '
                  f'({density:.4f}% of GF(2) space)')
        print()

        # List all universes
        for i, sol in enumerate(solutions):
            # Find which cells differ from universe 1
            if i == 0:
                ref = sol
                print(f'  Universe {i+1}: {sol}')
            else:
                diffs = sum(1 for a, b in zip(ref, sol) if a != b)
                print(f'  Universe {i+1}: {sol}  ({diffs} cells differ from U1)')

            if args.verbose:
                display_board(puzzle, sol, f'Universe {i+1}')

        # Analyze: which cells are stable across ALL universes?
        if len(solutions) > 1:
            stable = []
            unstable = []
            for pos in range(81):
                if puzzle[pos] != '0':
                    continue  # given clue, skip
                vals = set(sol[pos] for sol in solutions)
                if len(vals) == 1:
                    stable.append(pos)
                else:
                    unstable.append(pos)

            print()
            print(f'  Cell Stability Analysis:')
            print(f'    Stable cells (same in all universes): {len(stable)}')
            print(f'    Unstable cells (differ across universes): {len(unstable)}')
            if unstable:
                unstable_names = [f'R{p//9+1}C{p%9+1}' for p in unstable[:20]]
                print(f'    Unstable: {", ".join(unstable_names)}'
                      f'{"..." if len(unstable) > 20 else ""}')

        print()
        print(f'  {"=" * 55}')
        print(f'  Simple Wili — Multiverse Results')
        print(f'  {"=" * 55}')
        print(f'  Universes: {len(solutions)}')
        print(f'  GF(2) null dim: {null_dim}  (2^{null_dim} upper bound)')
        if len(solutions) > 1:
            import math
            dof = math.log2(len(solutions))
            print(f'  Effective DOF: {dof:.2f} bits '
                  f'(actual solutions ≈ 2^{dof:.1f})')
            if stable:
                print(f'  Stable cells: {len(stable)}/{len(stable)+len(unstable)} '
                      f'({100*len(stable)/(len(stable)+len(unstable)):.1f}%)')
        return

    # ── Multiverse Trap mode: separate flow ──
    if args.multiverse_trap:
        rng = random.Random(args.seed)
        result = forge_multiverse_trap(
            target_solutions=args.trap_solutions,
            max_unstable=args.trap_max_unstable,
            rng=rng,
            verbose=args.verbose,
        )
        if result:
            display_multiverse_trap(result)
            print(f'  Puzzle: {result["puzzle"]}')
        else:
            print('  Failed to forge Multiverse Trap after max attempts.')
        return

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
