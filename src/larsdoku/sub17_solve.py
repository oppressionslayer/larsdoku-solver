#!/usr/bin/env python3
"""
Sub-17 Clue Sudoku Solver — Forward-Only with Zone Heuristic
=============================================================

Generates puzzles with 8-16 clues (multi-solution territory) and solves
them forward-only: pure logic techniques until stalled, then zone-guided
heuristic choice, then continue with logic. No backtracking ever.

The completed board is validated by Sudoku law (rows/cols/boxes = {1..9}).

Usage:
    python sub17_solve.py --clues 11 --count 100
    python sub17_solve.py --clues 8 --count 50 --verbose
    python sub17_solve.py --clues 13 --count 200 --sweep
    python sub17_solve.py --sweep                          # test 8-16 clues
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

from .engine import BitBoard, BIT, POPCOUNT, BOX_OF, solve_backtrack, has_unique_solution, propagate_l1l2
from .wsrf_zone import (compute_likely_map, sir_get_rank1, _grid05c_key,
                       would_be_illegal, sir_find_cross_digit_oracles, UNITS)


# ══════════════════════════════════════════════════════════════
# BOARD VALIDATION
# ══════════════════════════════════════════════════════════════

def validate_sudoku(board):
    """Check completed board by Sudoku law — every row/col/box has {1..9}."""
    FULL = {1, 2, 3, 4, 5, 6, 7, 8, 9}
    for i in range(9):
        row = set()
        col = set()
        box = set()
        br, bc = (i // 3) * 3, (i % 3) * 3
        for j in range(9):
            row.add(board[i * 9 + j])
            col.add(board[j * 9 + i])
            box.add(board[(br + j // 3) * 9 + bc + j % 3])
        if row != FULL or col != FULL or box != FULL:
            return False
    return True


# ══════════════════════════════════════════════════════════════
# MASK GENERATION — from cli.py
# ══════════════════════════════════════════════════════════════

def _mask_analysis(positions):
    """Compute coverage stats for a set of clue positions."""
    pos_set = set(positions)
    box_clues = [0] * 9
    row_clues = [0] * 9
    col_clues = [0] * 9
    for p in pos_set:
        r, c = p // 9, p % 9
        box_clues[BOX_OF[p]] += 1
        row_clues[r] += 1
        col_clues[c] += 1
    return {
        'n_clues': len(pos_set),
        'box_clues': box_clues,
        'row_clues': row_clues,
        'col_clues': col_clues,
        'empty_boxes': sum(1 for x in box_clues if x == 0),
        'empty_rows': sum(1 for x in row_clues if x == 0),
        'empty_cols': sum(1 for x in col_clues if x == 0),
    }


def _compute_mask_score(analysis):
    """Quality score 0.0-1.0 for a mask."""
    a = analysis
    box_cov = sum(1 for x in a['box_clues'] if x > 0) / 9
    rc_cov = (sum(1 for x in a['row_clues'] if x > 0) +
              sum(1 for x in a['col_clues'] if x > 0)) / 18
    mean_box = a['n_clues'] / 9
    variance = sum((x - mean_box) ** 2 for x in a['box_clues']) / 9
    stddev = variance ** 0.5
    max_std = max(a['n_clues'] / 3, 1)
    evenness = max(0, 1 - stddev / max_std)
    density = min(a['n_clues'] / 17, 1.0)
    score = box_cov * 0.40 + rc_cov * 0.30 + evenness * 0.20 + density * 0.10
    return score, stddev


def generate_random_mask(n_clues=11, min_score=0.70, max_attempts=1000, rng=None):
    """Generate a random clue mask with box/row/col coverage."""
    if rng is None:
        rng = random.Random()
    box_cells = []
    for b in range(9):
        br, bc = (b // 3) * 3, (b % 3) * 3
        box_cells.append([r * 9 + c for r in range(br, br + 3) for c in range(bc, bc + 3)])

    for _ in range(max_attempts):
        positions = set()
        # Phase 1: one per box
        for b in range(9):
            positions.add(rng.choice(box_cells[b]))
        # Phase 2: one per row
        for r in range(9):
            row_pos = [r * 9 + c for c in range(9)]
            if not any(p in positions for p in row_pos):
                positions.add(rng.choice(row_pos))
        # Phase 3: one per col
        for c in range(9):
            col_pos = [r * 9 + c for r in range(9)]
            if not any(p in positions for p in col_pos):
                positions.add(rng.choice(col_pos))
        # Phase 4: fill to n_clues (load-balanced)
        while len(positions) < n_clues:
            box_counts = [0] * 9
            for p in positions:
                box_counts[BOX_OF[p]] += 1
            min_bc = min(box_counts)
            underfilled = [b for b, cnt in enumerate(box_counts) if cnt == min_bc]
            tb = rng.choice(underfilled)
            cands = [p for p in box_cells[tb] if p not in positions]
            if cands:
                positions.add(rng.choice(cands))
            else:
                remaining = [p for p in range(81) if p not in positions]
                if remaining:
                    positions.add(rng.choice(remaining))
                else:
                    break
        # If coverage generated more than n_clues, trim
        if len(positions) > n_clues:
            # Keep the positions but that's fine — coverage may require > n_clues
            pass
        analysis = _mask_analysis(positions)
        score, stddev = _compute_mask_score(analysis)
        if score >= min_score and analysis['empty_boxes'] == 0:
            return sorted(positions), score, stddev, analysis
    return None


def shuffle_sudoku(bd81, rng=None):
    """Shuffle a Sudoku grid preserving validity (band/row/col/digit permutations)."""
    if rng is None:
        rng = random.Random()
    board = [[int(bd81[r * 9 + c]) for c in range(9)] for r in range(9)]

    # Swap row bands
    bands = list(range(3))
    rng.shuffle(bands)
    new = [board[bands[b] * 3 + r] for b in range(3) for r in range(3)]
    board = new

    # Swap col bands
    bands = list(range(3))
    rng.shuffle(bands)
    board = [[row[bands[b] * 3 + c] for b in range(3) for c in range(3)] for row in board]

    # Swap rows within bands
    for band in range(3):
        rows = [band * 3, band * 3 + 1, band * 3 + 2]
        rng.shuffle(rows)
        board[band * 3], board[band * 3 + 1], board[band * 3 + 2] = \
            board[rows[0]], board[rows[1]], board[rows[2]]

    # Swap cols within bands
    for band in range(3):
        cols = [band * 3, band * 3 + 1, band * 3 + 2]
        rng.shuffle(cols)
        board = [
            [row[cols[0] if j == band * 3 else
                 cols[1] if j == band * 3 + 1 else
                 cols[2] if j == band * 3 + 2 else j]
             for j in range(9)]
            for row in board
        ]

    # Relabel digits
    perm = list(range(1, 10))
    rng.shuffle(perm)
    mapping = {i + 1: perm[i] for i in range(9)}
    mapping[0] = 0
    board = [[mapping[cell] for cell in row] for row in board]

    # Transpose (50% chance)
    if rng.random() < 0.5:
        board = [[board[c][r] for c in range(9)] for r in range(9)]

    return ''.join(str(board[r][c]) for r in range(9) for c in range(9))


# ══════════════════════════════════════════════════════════════
# FORWARD-ONLY SOLVER — logic + propagation lookahead, NO backtracking
# ══════════════════════════════════════════════════════════════

def _copy_bb(bb):
    """Lightweight BitBoard copy for lookahead."""
    cp = BitBoard()
    cp.board = bb.board[:]
    cp.cands = bb.cands[:]
    cp.cross = bb.cross[:]
    cp.row_used = bb.row_used[:]
    cp.col_used = bb.col_used[:]
    cp.box_used = bb.box_used[:]
    cp.empty = bb.empty
    return cp


def _has_contradiction(bb):
    """Check if any empty cell has 0 candidates."""
    for p in range(81):
        if bb.board[p] == 0 and bb.cands[p] == 0:
            return True
    return False


def solve_forward(bd81, verbose=False):
    """Solve forward-only: full technique engine + propagation lookahead.

    1. Run full technique engine (35 detectors) until stalled
    2. At stall: for each candidate in most constrained cells, simulate
       place + propagate on a COPY. Reject contradictions. Pick the
       candidate that cascades the most placements.
    3. Place the choice, re-run techniques.
    4. Validate final board by Sudoku law.

    No backtracking. No tree search. Just analysis + commit.
    """
    from .cli import solve_selective

    # Phase 1: Full technique engine
    result = solve_selective(bd81)
    current = result['board']
    bb = BitBoard.from_string(current)
    logic_total = result['n_steps']
    heuristic_total = 0
    steps = []
    contradiction = False

    # Phase 2: Heuristic loop — propagation lookahead picks safest candidate
    while bb.empty > 0 and heuristic_total < 81:
        if _has_contradiction(bb):
            contradiction = True
            break

        # Collect empty cells sorted by candidate count
        cell_cands = []
        for pos in range(81):
            if bb.board[pos] != 0:
                continue
            cands = [d + 1 for d in range(9) if bb.cands[pos] & BIT[d]]
            if not cands:
                contradiction = True
                break
            cell_cands.append((len(cands), pos, cands))
        if contradiction:
            break
        cell_cands.sort()

        # Propagation lookahead: try each candidate, measure cascade + remaining tightness
        best_pos = -1
        best_digit = -1
        best_cascade = -1
        best_remaining_cands = 999
        best_method = ""

        for _, pos, cands in cell_cands[:8]:
            for digit in cands:
                test_bb = _copy_bb(bb)
                test_bb.place(pos, digit)
                if _has_contradiction(test_bb):
                    continue
                try:
                    placed = propagate_l1l2(test_bb)
                except Exception:
                    continue
                if _has_contradiction(test_bb):
                    continue
                cascade = len(placed)

                # Tiebreaker: when cascade is equal, prefer the candidate
                # that leaves the board MOST constrained (fewest total candidates)
                remaining = sum(POPCOUNT[test_bb.cands[p]]
                                for p in range(81) if test_bb.board[p] == 0)

                if (cascade > best_cascade or
                    (cascade == best_cascade and remaining < best_remaining_cands)):
                    best_pos = pos
                    best_digit = digit
                    best_cascade = cascade
                    best_remaining_cands = remaining
                    best_method = f"cascade={cascade}"

        # Fallback: zone rank-1
        if best_pos == -1 and cell_cands:
            lm = compute_likely_map(bb, threshold=3, mcl=7)
            _, pos, cands = cell_cands[0]
            r1 = sir_get_rank1(lm, bb, pos)
            if r1 in cands:
                best_pos, best_digit, best_method = pos, r1, "zone"
            else:
                best_pos, best_digit, best_method = pos, cands[0], "first"

        if best_pos == -1:
            contradiction = True
            break

        # Commit the choice
        r, c = best_pos // 9, best_pos % 9
        step_desc = f"HEURISTIC R{r+1}C{c+1}={best_digit} ({best_method})"
        steps.append(step_desc)
        if verbose:
            print(f"    {step_desc}")

        bb.place(best_pos, best_digit)
        heuristic_total += 1

        if _has_contradiction(bb):
            contradiction = True
            break

        # Propagate after heuristic choice
        new_p = propagate_l1l2(bb)
        logic_total += len(new_p)

        if _has_contradiction(bb):
            contradiction = True
            break

        # If still stalled, try full technique engine again
        if bb.empty > 0 and not new_p:
            board_str = ''.join(str(bb.board[i]) for i in range(81))
            result2 = solve_selective(board_str)
            bb2 = BitBoard.from_string(result2['board'])
            logic_total += bb.empty - bb2.empty
            bb = bb2

    # Final validation
    valid = validate_sudoku(bb.board) if bb.empty == 0 else False

    return {
        'board': bb.board,
        'board_str': ''.join(str(bb.board[i]) for i in range(81)),
        'valid': valid,
        'logic_placements': logic_total,
        'heuristic_placements': heuristic_total,
        'total_placements': logic_total + heuristic_total,
        'remaining': bb.empty,
        'contradiction': contradiction,
        'steps': steps,
    }


# ══════════════════════════════════════════════════════════════
# PUZZLE GENERATION — solved grid + mask
# ══════════════════════════════════════════════════════════════

def generate_sub17_puzzle(n_clues, rng=None):
    """Generate a sub-17 clue puzzle from a random solved grid + validated mask."""
    if rng is None:
        rng = random.Random()

    # Lower min_score for very low clue counts
    min_score = 0.60 if n_clues <= 10 else 0.70

    mask_result = generate_random_mask(n_clues=n_clues, min_score=min_score, rng=rng)
    if mask_result is None:
        return None

    positions, score, stddev, analysis = mask_result
    pos_set = set(positions)

    # Generate a random solved grid
    sol = solve_backtrack('0' * 81)
    sol = shuffle_sudoku(sol, rng=rng)

    # Apply mask
    puzzle = ''.join(sol[p] if p in pos_set else '0' for p in range(81))
    actual_clues = sum(1 for ch in puzzle if ch != '0')

    return {
        'puzzle': puzzle,
        'solution': sol,
        'n_clues': actual_clues,
        'mask_score': score,
        'mask_stddev': stddev,
        'unique': has_unique_solution(puzzle),
    }


# ══════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════

def print_board(bd81, label=""):
    """Print a Sudoku board."""
    if label:
        print(f"  {label}")
    for r in range(9):
        if r % 3 == 0:
            print("  +---------+---------+---------+")
        row = ""
        for c in range(9):
            if c % 3 == 0:
                row += "  | "
            ch = bd81[r * 9 + c]
            row += (ch if ch != '0' else '.') + "  "
        row += "|"
        print(row)
    print("  +---------+---------+---------+")


# ══════════════════════════════════════════════════════════════
# MASK STUDY — fixed mask, varying fills, save all state to JSON
# ══════════════════════════════════════════════════════════════

def run_mask_study(n_clues=11, n_fills=25, seed=42, output_path=None):
    """Fixed mask, N different solved-grid fills. Returns and saves all state.

    Each trial uses the SAME clue positions but a DIFFERENT solved grid.
    Saves everything needed for pattern analysis:
    - mask positions
    - per-trial: puzzle, full solution, clue digits, solve result,
      heuristic steps with cascade depths, digit frequency stats
    """
    import json

    rng = random.Random(seed)
    mask_result = generate_random_mask(n_clues=n_clues, min_score=0.70, rng=rng)
    if mask_result is None:
        # Try with lower threshold
        mask_result = generate_random_mask(n_clues=n_clues, min_score=0.60,
                                           max_attempts=5000, rng=rng)
    if mask_result is None:
        print("ERROR: Could not generate a valid mask")
        return None

    positions, score, stddev, analysis = mask_result
    pos_set = set(positions)
    actual_clues = len(positions)

    # Mask as 81-char string
    mask_str = ''.join('1' if i in pos_set else '0' for i in range(81))

    print(f"  MASK STUDY — {actual_clues} clues, {n_fills} fills, seed={seed}")
    print(f"  {'═' * 60}")
    print(f"  Mask score: {score:.2f}  stddev: {stddev:.2f}")
    print(f"  Positions: {positions}")
    print()

    # Show mask visually
    for r in range(9):
        if r % 3 == 0:
            print("  +---------+---------+---------+")
        row = "  |"
        for c in range(9):
            if c % 3 == 0 and c > 0:
                row += " |"
            row += " X" if (r * 9 + c) in pos_set else " ."
        row += " |"
        print(row)
    print("  +---------+---------+---------+")
    print()

    trials = []
    for i in range(n_fills):
        sol = solve_backtrack('0' * 81)
        sol = shuffle_sudoku(sol, rng=rng)
        puzzle = ''.join(sol[p] if p in pos_set else '0' for p in range(81))

        t0 = time.perf_counter()
        result = solve_forward(puzzle)
        elapsed = (time.perf_counter() - t0) * 1000

        status = 'PASS' if result['valid'] else ('CONTR' if result['contradiction'] else 'FAIL')
        clue_digits = [int(sol[p]) for p in positions]

        # Digit frequency in clues
        digit_freq = [0] * 10  # index 1-9
        for d in clue_digits:
            digit_freq[d] += 1
        unique_digits = sum(1 for d in range(1, 10) if digit_freq[d] > 0)
        max_repeat = max(digit_freq[1:])

        # Cascade depths from heuristic steps
        cascades = []
        for step in result['steps']:
            # Parse "cascade=N" from step description
            if 'cascade=' in step:
                try:
                    c = int(step.split('cascade=')[1].split(')')[0])
                    cascades.append(c)
                except (ValueError, IndexError):
                    cascades.append(-1)

        # ── Zone math properties of the SOLVED board ──
        # Row/col/box digit distributions relative to clue positions
        sol_ints = [int(ch) for ch in sol]

        # Per-box: which digits are clues vs hidden
        box_clue_digits = [[] for _ in range(9)]
        box_hidden_digits = [[] for _ in range(9)]
        for p in range(81):
            b = BOX_OF[p]
            if p in pos_set:
                box_clue_digits[b].append(sol_ints[p])
            else:
                box_hidden_digits[b].append(sol_ints[p])

        # Per-row and per-col: clue vs hidden
        row_clue_digits = [[] for _ in range(9)]
        col_clue_digits = [[] for _ in range(9)]
        for p in positions:
            r, c = p // 9, p % 9
            row_clue_digits[r].append(sol_ints[p])
            col_clue_digits[c].append(sol_ints[p])

        # Cross-constraint: how many clue-clue peer pairs share the same digit?
        # (This would be illegal and indicates a problem, should be 0)
        peer_conflicts = 0
        for i_p, p1 in enumerate(positions):
            for p2 in positions[i_p + 1:]:
                r1, c1, b1 = p1 // 9, p1 % 9, BOX_OF[p1]
                r2, c2, b2 = p2 // 9, p2 % 9, BOX_OF[p2]
                if (r1 == r2 or c1 == c2 or b1 == b2) and sol_ints[p1] == sol_ints[p2]:
                    peer_conflicts += 1

        # Constraint coverage: for each empty cell, how many of its candidates
        # are eliminated by clues? Higher = more constrained = easier to solve
        bb_puzzle = BitBoard.from_string(puzzle)
        total_cands = 0
        total_eliminated = 0
        cell_constraint_scores = []
        for p in range(81):
            if p in pos_set:
                continue
            cands = POPCOUNT[bb_puzzle.cands[p]]
            eliminated = 9 - cands
            total_cands += cands
            total_eliminated += eliminated
            cell_constraint_scores.append(eliminated)
        avg_constraint = round(total_eliminated / max(1, 81 - actual_clues), 2)

        # Digit scarcity in solution: for each digit 1-9, count how many
        # of the 9 instances are given as clues (higher = more visible)
        digit_visibility = []
        for d in range(1, 10):
            total_in_sol = sum(1 for x in sol_ints if x == d)  # always 9
            given = sum(1 for p in positions if sol_ints[p] == d)
            digit_visibility.append(given)

        # Box interaction: for each pair of boxes that share a band/stack,
        # do the clues create cross-hatching opportunities?
        xhatch_potential = 0
        for band in range(3):
            for d in range(1, 10):
                boxes_with_d_clue = set()
                for b in range(band * 3, band * 3 + 3):
                    br, bc = (b // 3) * 3, (b % 3) * 3
                    for dr in range(3):
                        for dc in range(3):
                            p = (br + dr) * 9 + bc + dc
                            if p in pos_set and sol_ints[p] == d:
                                boxes_with_d_clue.add(b)
                if len(boxes_with_d_clue) >= 2:
                    xhatch_potential += 1
        # Same for column stacks
        for stack in range(3):
            for d in range(1, 10):
                boxes_with_d_clue = set()
                for b in [stack, stack + 3, stack + 6]:
                    br, bc = (b // 3) * 3, (b % 3) * 3
                    for dr in range(3):
                        for dc in range(3):
                            p = (br + dr) * 9 + bc + dc
                            if p in pos_set and sol_ints[p] == d:
                                boxes_with_d_clue.add(b)
                if len(boxes_with_d_clue) >= 2:
                    xhatch_potential += 1

        trial = {
            'idx': i,
            'puzzle': puzzle,
            'solution': sol,
            'status': status,
            'logic_placements': result['logic_placements'],
            'heuristic_placements': result['heuristic_placements'],
            'remaining': result['remaining'],
            'elapsed_ms': round(elapsed, 1),
            'clue_digits': clue_digits,
            'unique_digits': unique_digits,
            'max_digit_repeat': max_repeat,
            'digit_freq': digit_freq[1:],  # [freq_of_1, ..., freq_of_9]
            'heuristic_steps': result['steps'],
            'cascade_depths': cascades,
            'avg_cascade': round(sum(cascades) / max(1, len(cascades)), 1) if cascades else 0,
            'board_result': result['board_str'],
            # Zone math properties
            'zone': {
                'box_clue_digits': box_clue_digits,
                'box_hidden_digits': box_hidden_digits,
                'row_clue_digits': row_clue_digits,
                'col_clue_digits': col_clue_digits,
                'digit_visibility': digit_visibility,  # [clue_count_for_d1, ..., d9]
                'avg_constraint': avg_constraint,  # avg candidates eliminated per empty cell
                'total_candidates': total_cands,
                'total_eliminated': total_eliminated,
                'xhatch_potential': xhatch_potential,  # cross-hatch opportunities from clues
                'peer_conflicts': peer_conflicts,  # should be 0
            },
        }
        trials.append(trial)

        clue_str = '|'.join(str(d) for d in clue_digits)
        casc_str = ','.join(str(c) for c in cascades[:6])
        if len(cascades) > 6:
            casc_str += f'...({len(cascades)})'
        print(f"  #{i+1:2d} {status:5s}  L={trial['logic_placements']:2d} H={trial['heuristic_placements']:2d}  "
              f"uniq={unique_digits} max_rep={max_repeat}  cascade=[{casc_str}]  "
              f"clues=[{clue_str}]")

    # Summary
    passes = [t for t in trials if t['status'] == 'PASS']
    fails = [t for t in trials if t['status'] != 'PASS']
    print(f"\n  {'═' * 60}")
    print(f"  PASS: {len(passes)}/{n_fills}  FAIL: {len(fails)}/{n_fills}")

    if passes and fails:
        avg_uniq_pass = sum(t['unique_digits'] for t in passes) / len(passes)
        avg_uniq_fail = sum(t['unique_digits'] for t in fails) / len(fails)
        avg_maxrep_pass = sum(t['max_digit_repeat'] for t in passes) / len(passes)
        avg_maxrep_fail = sum(t['max_digit_repeat'] for t in fails) / len(fails)
        avg_casc_pass = sum(t['avg_cascade'] for t in passes) / len(passes)
        avg_casc_fail = sum(t['avg_cascade'] for t in fails) / len(fails)
        avg_constraint_pass = sum(t['zone']['avg_constraint'] for t in passes) / len(passes)
        avg_constraint_fail = sum(t['zone']['avg_constraint'] for t in fails) / len(fails)
        avg_xhatch_pass = sum(t['zone']['xhatch_potential'] for t in passes) / len(passes)
        avg_xhatch_fail = sum(t['zone']['xhatch_potential'] for t in fails) / len(fails)
        avg_vis_pass = sum(sum(t['zone']['digit_visibility']) for t in passes) / len(passes)
        avg_vis_fail = sum(sum(t['zone']['digit_visibility']) for t in fails) / len(fails)
        print(f"\n  Signal comparison (PASS vs FAIL):")
        print(f"    {'':30s}  {'PASS':>6s}  {'FAIL':>6s}")
        print(f"    {'─' * 30}  {'─' * 6}  {'─' * 6}")
        print(f"    {'Unique digits in clues':30s}  {avg_uniq_pass:6.1f}  {avg_uniq_fail:6.1f}")
        print(f"    {'Max digit repetition':30s}  {avg_maxrep_pass:6.1f}  {avg_maxrep_fail:6.1f}")
        print(f"    {'Avg cascade depth':30s}  {avg_casc_pass:6.1f}  {avg_casc_fail:6.1f}")
        print(f"    {'Avg constraint (elims/cell)':30s}  {avg_constraint_pass:6.2f}  {avg_constraint_fail:6.2f}")
        print(f"    {'Cross-hatch potential':30s}  {avg_xhatch_pass:6.1f}  {avg_xhatch_fail:6.1f}")
        print(f"    {'Total digit visibility':30s}  {avg_vis_pass:6.1f}  {avg_vis_fail:6.1f}")

    # Build the full dataset
    dataset = {
        'meta': {
            'n_clues': actual_clues,
            'n_fills': n_fills,
            'seed': seed,
            'mask_positions': positions,
            'mask_string': mask_str,
            'mask_score': score,
            'mask_stddev': stddev,
            'mask_analysis': analysis,
        },
        'trials': trials,
        'summary': {
            'total': n_fills,
            'passed': len(passes),
            'failed': len(fails),
            'pass_rate': round(100 * len(passes) / n_fills, 1),
        },
    }

    # Save to JSON
    if output_path is None:
        output_path = f'sub17_study_{actual_clues}clues_seed{seed}.json'
    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)
    print(f"\n  Saved to {output_path}")
    print(f"  Load with: json.load(open('{output_path}'))")

    return dataset


# ══════════════════════════════════════════════════════════════
# MAIN — CLI
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Sub-17 Clue Solver — forward-only with zone heuristic")
    parser.add_argument('--clues', '-c', type=int, default=11,
                        help='Target clue count (default 11)')
    parser.add_argument('--count', '-n', type=int, default=25,
                        help='Number of puzzles to generate and solve (default 25)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show each puzzle and heuristic steps')
    parser.add_argument('--sweep', action='store_true',
                        help='Sweep from 8-16 clues')
    parser.add_argument('--study', action='store_true',
                        help='Mask study: fixed mask, N fills, save JSON for analysis')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output path for --study JSON (auto-generated if omitted)')
    parser.add_argument('--seed', type=int, default=None,
                        help='Random seed for reproducibility')
    args = parser.parse_args()

    rng = random.Random(args.seed)

    if args.study:
        run_mask_study(
            n_clues=args.clues,
            n_fills=args.count,
            seed=args.seed or 42,
            output_path=args.output,
        )
        return

    if args.sweep:
        print("=" * 70)
        print("  SUB-17 CLUE SWEEP — Forward-Only Zone Solver")
        print("=" * 70)
        print(f"  {args.count} puzzles per clue count | seed={args.seed}")
        print()
        print(f"  {'Clues':>5s}  {'Pass':>5s}  {'Fail':>5s}  {'Contr':>5s}  "
              f"{'Rate':>6s}  {'Logic%':>6s}  {'Heur%':>6s}  {'Avg ms':>7s}")
        print(f"  {'─'*5}  {'─'*5}  {'─'*5}  {'─'*5}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*7}")

        for n_clues in range(8, 17):
            passed = 0
            failed = 0
            contras = 0
            total_logic = 0
            total_heur = 0
            total_placed = 0
            total_time = 0
            gen_fails = 0

            for i in range(args.count):
                gen = generate_sub17_puzzle(n_clues, rng=rng)
                if gen is None:
                    gen_fails += 1
                    continue

                t0 = time.perf_counter()
                result = solve_forward(gen['puzzle'])
                elapsed = (time.perf_counter() - t0) * 1000
                total_time += elapsed

                if result['valid']:
                    passed += 1
                    total_logic += result['logic_placements']
                    total_heur += result['heuristic_placements']
                    total_placed += result['total_placements']
                elif result['contradiction']:
                    contras += 1
                    failed += 1
                else:
                    failed += 1

            attempted = passed + failed
            rate = 100 * passed / attempted if attempted > 0 else 0
            avg_logic = 100 * total_logic / total_placed if total_placed > 0 else 0
            avg_heur = 100 * total_heur / total_placed if total_placed > 0 else 0
            avg_ms = total_time / attempted if attempted > 0 else 0

            note = f"  ({gen_fails} gen fails)" if gen_fails > 0 else ""
            print(f"  {n_clues:5d}  {passed:5d}  {failed:5d}  {contras:5d}  "
                  f"{rate:5.1f}%  {avg_logic:5.1f}%  {avg_heur:5.1f}%  {avg_ms:6.0f}ms{note}")

        print()
        return

    # Single clue count mode
    print("=" * 70)
    print(f"  SUB-17 CLUE SOLVER — {args.clues} clues, {args.count} puzzles")
    print(f"  Forward-only: pure logic + zone heuristic | No backtracking")
    print("=" * 70)

    passed = 0
    failed = 0
    contras = 0
    total_logic = 0
    total_heur = 0
    total_time = 0
    gen_fails = 0
    fail_puzzles = []

    for i in range(args.count):
        gen = generate_sub17_puzzle(args.clues, rng=rng)
        if gen is None:
            gen_fails += 1
            continue

        t0 = time.perf_counter()
        result = solve_forward(gen['puzzle'], verbose=args.verbose)
        elapsed = (time.perf_counter() - t0) * 1000
        total_time += elapsed

        status = "VALID" if result['valid'] else ("CONTRADICTION" if result['contradiction'] else "INCOMPLETE")
        logic_pct = 100 * result['logic_placements'] / max(1, result['total_placements'])
        heur_n = result['heuristic_placements']

        if result['valid']:
            passed += 1
            total_logic += result['logic_placements']
            total_heur += result['heuristic_placements']
        else:
            failed += 1
            if result['contradiction']:
                contras += 1
            fail_puzzles.append(gen['puzzle'])

        if args.verbose:
            print(f"\n  Puzzle {i+1}: {gen['n_clues']} clues (mask score {gen['mask_score']:.2f})")
            print_board(gen['puzzle'])
            print(f"  Result: {status} | {result['logic_placements']} logic + "
                  f"{heur_n} heuristic = {result['total_placements']} placements | {elapsed:.0f}ms")
            if result['valid']:
                print_board(result['board_str'], "Completed board:")
            print()
        else:
            mark = "+" if result['valid'] else "X"
            if (i + 1) % 10 == 0 or i == args.count - 1:
                print(f"  [{i+1:4d}/{args.count}] pass={passed} fail={failed} "
                      f"({100*passed/max(1,passed+failed):.0f}%)", flush=True)

    attempted = passed + failed
    rate = 100 * passed / attempted if attempted > 0 else 0
    avg_ms = total_time / attempted if attempted > 0 else 0

    print()
    print("=" * 70)
    print(f"  RESULTS — {args.clues} clues")
    print("=" * 70)
    print(f"  Attempted:     {attempted}")
    print(f"  Valid solves:  {passed}/{attempted} ({rate:.1f}%)")
    print(f"  Contradictions: {contras}")
    if gen_fails:
        print(f"  Gen failures:  {gen_fails} (mask couldn't meet quality threshold)")
    if passed > 0:
        avg_logic_pct = 100 * total_logic / (total_logic + total_heur)
        avg_heur_pct = 100 * total_heur / (total_logic + total_heur)
        print(f"  Avg logic:     {avg_logic_pct:.1f}% of placements")
        print(f"  Avg heuristic: {avg_heur_pct:.1f}% of placements")
    print(f"  Avg time:      {avg_ms:.0f}ms/puzzle")
    if fail_puzzles and len(fail_puzzles) <= 5:
        print(f"\n  Failed puzzles:")
        for p in fail_puzzles:
            print(f"    {p}")
    print("=" * 70)


if __name__ == '__main__':
    main()
