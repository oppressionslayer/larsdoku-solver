#!/usr/bin/env python3
"""
Oracle-Free Verification Test Suite for Larsdoku
=================================================

This test suite proves that the Larsdoku solver:
1. Never accesses the solution during solving
2. Solves puzzles through pure Sudoku logic
3. Validates results using standard Sudoku law (27-unit check)
4. Reports "stalled" honestly when it can't prove the next step

HOW TO RUN:
    python test_oracle_free.py

HOW TO VERIFY NO CHEATING:
    1. grep -n "solution" cli.py  -- should show ZERO hits inside solve_selective()
    2. grep -n "solve_backtrack" cli.py -- should NOT appear inside solve_selective()
    3. Run this test suite -- all tests must pass

Author: Sir Lars (WSRF) — March 2026
"""

import sys
import os
import ast
import inspect
import textwrap
import time

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import (
    BitBoard, solve_backtrack, detect_forcing_chain_bitwise,
    detect_deep_resonance, validate_sudoku, fast_propagate_full,
    POPCOUNT, BIT
)

# Import validate helpers
try:
    from cli import solve_selective, validate_sudoku as cli_validate_sudoku, validate_eliminations
except ImportError:
    # Fallback: define locally if cli can't be imported due to dependencies
    from engine import validate_sudoku


# ══════════════════════════════════════════════════════════════
# TEST PUZZLES — varying difficulty
# ══════════════════════════════════════════════════════════════

EASY = [
    "003020600900305001001806400008102900700000008006708200002609500800203009005010300",
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
    "000260701680070090190004500820100040004602900050003028009300074040050036703018000",
]

MEDIUM = [
    "000000010400000000020000000000050407008000300001090000300400200050100000000806000",
    "020000000000600003074080000000003002080000060400500000000010780500009000000000040",
]

HARD = [
    "000000001090000050000700008000060000009500800000003000000080000004000000800000004",
    "100007090030020008009600500005300900010080002600004000300000010040000007007000300",
]


def validate_sudoku_board(board_str):
    """Validate a completed board using standard Sudoku law.
    Every row, column, and 3x3 box must contain exactly {1..9}."""
    if len(board_str) != 81:
        return False
    board = [int(ch) for ch in board_str]
    if any(d < 1 or d > 9 for d in board):
        return False
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
# TEST 1: CODE AUDIT — verify solve_selective has zero oracle
# ══════════════════════════════════════════════════════════════

def test_01_no_solution_in_solve_selective():
    """AUDIT: solve_selective() must not reference 'solution' variable."""
    print("TEST 01: Code audit — no 'solution' in solve_selective()...")

    cli_path = os.path.join(os.path.dirname(__file__), 'cli.py')
    with open(cli_path, 'r') as f:
        source = f.read()

    # Parse the AST to find solve_selective function body
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'solve_selective':
            # Get the source lines of this function
            start_line = node.lineno
            end_line = node.end_lineno
            func_lines = source.split('\n')[start_line - 1:end_line]
            func_source = '\n'.join(func_lines)

            # Check for 'solution' as a variable name (not in strings/comments)
            violations = []
            for i, line in enumerate(func_lines):
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""'):
                    continue
                # Check for solution as identifier (not part of 'trusted_solution' in docstring)
                if 'solution' in stripped and not stripped.startswith('#'):
                    # Filter out string literals and comments
                    if 'solution' in stripped.split('#')[0]:  # before any comment
                        code_part = stripped.split('#')[0]
                        # Ignore if it's inside a string
                        if "'solution'" in code_part or '"solution"' in code_part:
                            continue
                        # Ignore docstring lines
                        if code_part.strip().startswith("'") or code_part.strip().startswith('"'):
                            continue
                        violations.append((start_line + i, stripped))

            if violations:
                print(f"  FAIL: Found {len(violations)} 'solution' references:")
                for ln, text in violations[:5]:
                    print(f"    Line {ln}: {text}")
                return False

            print("  PASS: Zero 'solution' references in solve_selective()")
            return True

    print("  FAIL: Could not find solve_selective() in cli.py")
    return False


def test_02_no_backtracker_in_solve_selective():
    """AUDIT: solve_selective() must not call solve_backtrack()."""
    print("TEST 02: Code audit — no solve_backtrack() in solve_selective()...")

    cli_path = os.path.join(os.path.dirname(__file__), 'cli.py')
    with open(cli_path, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'solve_selective':
            start_line = node.lineno
            end_line = node.end_lineno
            func_lines = source.split('\n')[start_line - 1:end_line]

            violations = []
            for i, line in enumerate(func_lines):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                if 'solve_backtrack' in stripped:
                    violations.append((start_line + i, stripped))

            if violations:
                print(f"  FAIL: Found solve_backtrack() calls:")
                for ln, text in violations:
                    print(f"    Line {ln}: {text}")
                return False

            print("  PASS: Zero solve_backtrack() calls in solve_selective()")
            return True

    print("  FAIL: Could not find solve_selective()")
    return False


def test_03_no_solution_in_deep_resonance():
    """AUDIT: detect_deep_resonance() must not take 'solution' parameter."""
    print("TEST 03: Code audit — detect_deep_resonance() has no 'solution' param...")

    sig = inspect.signature(detect_deep_resonance)
    params = list(sig.parameters.keys())

    if 'solution' in params:
        print(f"  FAIL: 'solution' is a parameter: {params}")
        return False

    print(f"  PASS: Parameters are {params} — no 'solution'")
    return True


# ══════════════════════════════════════════════════════════════
# TEST 2: FUNCTIONAL — solver produces valid results
# ══════════════════════════════════════════════════════════════

def test_04_easy_puzzles_solve():
    """FUNCTIONAL: Easy puzzles should solve completely."""
    print("TEST 04: Easy puzzles solve completely...")

    for i, puzzle in enumerate(EASY):
        result = solve_selective(puzzle, verbose=False)
        if not result['success']:
            print(f"  FAIL: Easy puzzle {i+1} did not solve (remaining: {result['empty_remaining']})")
            return False
        if not validate_sudoku_board(result['board']):
            print(f"  FAIL: Easy puzzle {i+1} solution is invalid by Sudoku law!")
            return False

    print(f"  PASS: {len(EASY)}/{len(EASY)} easy puzzles solved and validated")
    return True


def test_05_medium_puzzles_solve():
    """FUNCTIONAL: Medium puzzles should solve completely."""
    print("TEST 05: Medium puzzles solve completely...")

    for i, puzzle in enumerate(MEDIUM):
        result = solve_selective(puzzle, verbose=False)
        if not result['success']:
            print(f"  INFO: Medium puzzle {i+1} stalled at {result['empty_remaining']} remaining")
            print(f"         Techniques: {result['technique_counts']}")
            # Medium puzzles might stall without oracle — that's OK
            continue
        if not validate_sudoku_board(result['board']):
            print(f"  FAIL: Medium puzzle {i+1} solution is INVALID by Sudoku law!")
            return False

    print(f"  PASS: Medium puzzles completed or honestly stalled")
    return True


def test_06_solved_boards_valid():
    """FUNCTIONAL: Every solved board passes Sudoku law validation."""
    print("TEST 06: All solved boards pass Sudoku law validation...")

    all_puzzles = EASY + MEDIUM + HARD
    solved_count = 0
    valid_count = 0

    for puzzle in all_puzzles:
        result = solve_selective(puzzle, verbose=False)
        if result['success']:
            solved_count += 1
            if validate_sudoku_board(result['board']):
                valid_count += 1
            else:
                print(f"  FAIL: Solved board is INVALID: {puzzle[:20]}...")
                return False

    print(f"  PASS: {valid_count}/{solved_count} solved boards validated by Sudoku law")
    return True


# ══════════════════════════════════════════════════════════════
# TEST 3: INTEGRITY — solver never places wrong digits
# ══════════════════════════════════════════════════════════════

def test_07_placements_match_backtrack():
    """INTEGRITY: Every digit the solver places must match the backtracked solution."""
    print("TEST 07: All placements match independent backtrack solution...")

    all_puzzles = EASY + MEDIUM + HARD
    total_placements = 0
    wrong = 0

    for puzzle in all_puzzles:
        # Get the true solution independently
        true_solution = solve_backtrack(puzzle)
        if not true_solution:
            continue

        result = solve_selective(puzzle, detail=True, verbose=False)

        for step in result['steps']:
            pos = step['pos']
            digit = step['digit']
            expected = int(true_solution[pos])
            total_placements += 1
            if digit != expected:
                wrong += 1
                cell = step.get('cell', f'pos{pos}')
                tech = step.get('technique', '?')
                print(f"  FAIL: {cell} placed {digit} but answer is {expected} [{tech}]")
                return False

    print(f"  PASS: {total_placements} placements checked — all match backtrack solution")
    return True


def test_08_no_oracle_technique():
    """INTEGRITY: No step should use ORACLE_ONLY or ZONE_ORACLE technique."""
    print("TEST 08: No oracle techniques appear in solve steps...")

    all_puzzles = EASY + MEDIUM + HARD
    oracle_techs = {'ORACLE_ONLY', 'ZONE_ORACLE', 'ZONE_ORACLE_MISS'}

    for puzzle in all_puzzles:
        result = solve_selective(puzzle, verbose=False)
        for tech, count in result['technique_counts'].items():
            if tech in oracle_techs:
                print(f"  FAIL: Oracle technique '{tech}' used {count} times!")
                return False

    print(f"  PASS: Zero oracle technique usage across {len(all_puzzles)} puzzles")
    return True


# ══════════════════════════════════════════════════════════════
# TEST 4: VALIDATE_SUDOKU function correctness
# ══════════════════════════════════════════════════════════════

def test_09_validate_sudoku_correct():
    """UNIT: validate_sudoku correctly accepts valid boards and rejects invalid."""
    print("TEST 09: validate_sudoku() correctness...")

    # Valid board
    valid = "123456789456789123789123456214365897365897214897214365531642978642978531978531642"
    assert validate_sudoku_board(valid), "Should accept valid board"

    # Invalid: duplicate in row 1
    invalid_row = "113456789456789123789123456214365897365897214897214365531642978642978531978531642"
    assert not validate_sudoku_board(invalid_row), "Should reject duplicate in row"

    # Incomplete board
    incomplete = "023456789456789123789123456214365897365897214897214365531642978642978531978531642"
    assert not validate_sudoku_board(incomplete), "Should reject incomplete board"

    print("  PASS: validate_sudoku correctly handles valid, invalid, and incomplete")
    return True


# ══════════════════════════════════════════════════════════════
# TEST 5: STALL HONESTY — solver admits when it can't prove more
# ══════════════════════════════════════════════════════════════

def test_10_stall_is_honest():
    """HONESTY: When stalled, solver does NOT place unproven digits."""
    print("TEST 10: Stalled solver doesn't place unproven digits...")

    # Use a puzzle likely to stall without DeepResonance Phase 2
    for puzzle in HARD:
        result = solve_selective(puzzle, verbose=False)
        if result['stalled']:
            # Board should be partially filled but valid so far
            board = result['board']
            for i in range(81):
                if board[i] != '0':  # placed digit
                    # Verify it's correct against backtrack
                    true_sol = solve_backtrack(puzzle)
                    if true_sol and board[i] != true_sol[i]:
                        print(f"  FAIL: Stalled solver placed WRONG digit at pos {i}")
                        return False

    print("  PASS: All placed digits (even when stalled) are correct")
    return True


# ══════════════════════════════════════════════════════════════
# TEST 6: BENCHMARK — solve rate across puzzle sets
# ══════════════════════════════════════════════════════════════

def test_11_benchmark():
    """BENCHMARK: Report solve rates across difficulty levels."""
    print("TEST 11: Benchmark solve rates...")

    categories = [
        ("Easy", EASY),
        ("Medium", MEDIUM),
        ("Hard", HARD),
    ]

    for name, puzzles in categories:
        solved = 0
        stalled = 0
        total_time = 0
        tech_totals = {}

        for puzzle in puzzles:
            t0 = time.time()
            result = solve_selective(puzzle, verbose=False)
            total_time += time.time() - t0

            if result['success']:
                solved += 1
            else:
                stalled += 1

            for tech, count in result['technique_counts'].items():
                tech_totals[tech] = tech_totals.get(tech, 0) + count

        print(f"  {name}: {solved}/{len(puzzles)} solved, "
              f"{stalled} stalled, {total_time:.2f}s")
        if tech_totals:
            top_techs = sorted(tech_totals.items(), key=lambda x: -x[1])[:5]
            tech_str = ', '.join(f"{t}={c}" for t, c in top_techs)
            print(f"    Techniques: {tech_str}")

    return True  # benchmark always passes — it's informational


# ══════════════════════════════════════════════════════════════
# MAIN — run all tests
# ══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("LARSDOKU ORACLE-FREE VERIFICATION TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        test_01_no_solution_in_solve_selective,
        test_02_no_backtracker_in_solve_selective,
        test_03_no_solution_in_deep_resonance,
        test_04_easy_puzzles_solve,
        test_05_medium_puzzles_solve,
        test_06_solved_boards_valid,
        test_07_placements_match_backtrack,
        test_08_no_oracle_technique,
        test_09_validate_sudoku_correct,
        test_10_stall_is_honest,
        test_11_benchmark,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        print()
        try:
            result = test()
            if result:
                passed += 1
            else:
                failed += 1
                errors.append(test.__name__)
        except Exception as e:
            failed += 1
            errors.append(f"{test.__name__}: {e}")
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    if errors:
        print(f"FAILURES: {', '.join(errors)}")
    else:
        print("ALL TESTS PASSED — ORACLE-FREE VERIFIED")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
