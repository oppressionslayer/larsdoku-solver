#!/usr/bin/env python3
"""
Mask Forge — Find unique-solution puzzles from any mask pattern.
Uses constraint-guided DFS instead of blind brute force.

Strategy:
1. Order clue positions by constraint connectivity (most shared units first)
2. Place digits one at a time, choosing the most constraining digit first
3. After each placement, propagate L1 constraints to prune the search
4. When all clues placed, verify uniqueness
5. Backtrack if contradiction or non-unique

The key insight: the solver itself guides digit placement. By placing
the most-constraining digit at the most-connected position first,
we converge on uniqueness in ~100 checks instead of ~250,000.

Then: digit permutation generates 362,880 more unique puzzles instantly,
all with the same mask, all guaranteed unique.
"""

import random
import sys
import time
from .engine import (BitBoard, solve_backtrack, has_unique_solution,
                    validate_sudoku, propagate_l1l2, BIT, POPCOUNT)


def parse_mask(mask_input):
    """Parse mask from various formats. x/X/1 = clue, 0/. = empty."""
    clean = mask_input.replace(' ', '').replace('\n', '')
    mask = []
    for c in clean:
        if c in ('x', 'X', '1'):
            mask.append(1)
        elif c in ('0', '.'):
            mask.append(0)
        elif c in '23456789':
            mask.append(1)
        else:
            mask.append(0)
    if len(mask) != 81:
        raise ValueError(f"Mask must be 81 chars, got {len(mask)}")
    return mask


def forge_unique(mask, max_seconds=60, verbose=True):
    """Find a unique-solution puzzle for the given mask.

    Constraint-guided DFS: place digits at clue positions one at a time,
    ordered by constraint connectivity, choosing the most constraining
    digit at each step. The solver guides every decision.
    """
    clue_positions = [i for i in range(81) if mask[i] == 1]
    n_clues = len(clue_positions)

    if verbose:
        print(f"Mask Forge: {n_clues} clues, constraint-guided DFS...")

    # Order clue positions by unit overlap with other clue positions
    # More overlap = more constraining = place first
    def unit_overlap(pos):
        r, c = pos // 9, pos % 9
        bx = (r // 3) * 3 + c // 3
        count = 0
        for other in clue_positions:
            if other == pos:
                continue
            or_, oc = other // 9, other % 9
            obx = (or_ // 3) * 3 + oc // 3
            if or_ == r or oc == c or obx == bx:
                count += 1
        return count

    ordered = sorted(clue_positions, key=unit_overlap, reverse=True)

    t0 = time.perf_counter()
    puzzle = ['0'] * 81
    checks = [0]
    found = [None]
    found_sol = [None]

    def dfs(idx):
        if time.perf_counter() - t0 > max_seconds:
            return False
        if found[0]:
            return True

        if idx == len(ordered):
            checks[0] += 1
            bd81 = ''.join(puzzle)
            sol = solve_backtrack(bd81)
            if sol and has_unique_solution(bd81):
                found[0] = bd81
                found_sol[0] = sol
                return True
            return False

        pos = ordered[idx]

        # Get current board state after propagation
        bd81 = ''.join(puzzle)
        bb = BitBoard.from_string(bd81)
        propagate_l1l2(bb)

        # If this position was already placed by propagation, skip
        if bb.board[pos] != 0:
            return dfs(idx + 1)

        # If contradiction, backtrack
        if bb.cands[pos] == 0:
            return False

        # Try each valid digit, scored by how much it constrains
        digit_scores = []
        for d in range(1, 10):
            if not (bb.cands[pos] & BIT[d - 1]):
                continue
            puzzle[pos] = str(d)
            test = ''.join(puzzle)
            tbb = BitBoard.from_string(test)
            propagate_l1l2(tbb)

            # Check for contradiction
            contra = False
            for i in range(81):
                if tbb.board[i] == 0 and tbb.cands[i] == 0:
                    contra = True
                    break
            if contra:
                puzzle[pos] = '0'
                continue

            # Score: total remaining candidates (lower = more constrained = try first)
            score = sum(POPCOUNT[tbb.cands[i]] for i in range(81) if tbb.board[i] == 0)
            digit_scores.append((score, d))
            puzzle[pos] = '0'

        # Sort: most constraining first
        digit_scores.sort()

        for _, d in digit_scores:
            puzzle[pos] = str(d)
            if dfs(idx + 1):
                return True
            puzzle[pos] = '0'

        return False

    dfs(0)
    elapsed = time.perf_counter() - t0

    if found[0]:
        if verbose:
            print(f"  UNIQUE found in {checks[0]} checks ({elapsed:.1f}s)")
        return found[0], found_sol[0], checks[0], elapsed
    else:
        if verbose:
            print(f"  No unique found in {checks[0]} checks ({elapsed:.1f}s)")
        return None, None, checks[0], elapsed


def forge_unique_randomized(mask, seed=0, max_seconds=60, verbose=False):
    """Like forge_unique but randomizes digit exploration order.

    Different seeds explore different paths through the search space,
    producing structurally different puzzles (not just digit permutations).
    This is key to finding puzzles that require advanced techniques.
    """
    import random as _rng
    rng = _rng.Random(seed)

    clue_positions = [i for i in range(81) if mask[i] == 1]
    n_clues = len(clue_positions)

    def unit_overlap(pos):
        r, c = pos // 9, pos % 9
        bx = (r // 3) * 3 + c // 3
        count = 0
        for other in clue_positions:
            if other == pos:
                continue
            or_, oc = other // 9, other % 9
            obx = (or_ // 3) * 3 + oc // 3
            if or_ == r or oc == c or obx == bx:
                count += 1
        return count

    ordered = sorted(clue_positions, key=unit_overlap, reverse=True)

    t0 = time.perf_counter()
    puzzle = ['0'] * 81
    checks = [0]
    found = [None]
    found_sol = [None]

    def dfs(idx):
        if time.perf_counter() - t0 > max_seconds:
            return False
        if found[0]:
            return True

        if idx == len(ordered):
            checks[0] += 1
            bd81 = ''.join(puzzle)
            sol = solve_backtrack(bd81)
            if sol and has_unique_solution(bd81):
                found[0] = bd81
                found_sol[0] = sol
                return True
            return False

        pos = ordered[idx]
        bd81 = ''.join(puzzle)
        bb = BitBoard.from_string(bd81)
        propagate_l1l2(bb)

        if bb.board[pos] != 0:
            return dfs(idx + 1)

        if bb.cands[pos] == 0:
            return False

        # Collect valid digits with scores
        digit_scores = []
        for d in range(1, 10):
            if not (bb.cands[pos] & BIT[d - 1]):
                continue
            puzzle[pos] = str(d)
            test = ''.join(puzzle)
            tbb = BitBoard.from_string(test)
            propagate_l1l2(tbb)

            contra = False
            for i in range(81):
                if tbb.board[i] == 0 and tbb.cands[i] == 0:
                    contra = True
                    break
            if contra:
                puzzle[pos] = '0'
                continue

            score = sum(POPCOUNT[tbb.cands[i]] for i in range(81) if tbb.board[i] == 0)
            digit_scores.append((score, d))
            puzzle[pos] = '0'

        # Randomize: shuffle digits with similar scores instead of strict sort
        rng.shuffle(digit_scores)

        for _, d in digit_scores:
            puzzle[pos] = str(d)
            if dfs(idx + 1):
                return True
            puzzle[pos] = '0'

        return False

    dfs(0)
    elapsed = time.perf_counter() - t0

    if found[0]:
        return found[0], found_sol[0], checks[0], elapsed
    else:
        return None, None, checks[0], elapsed


def digit_permutations(puzzle, count=10):
    """Generate unique puzzles by digit permutation (guaranteed unique if input is).

    Digit permutation preserves the constraint structure exactly:
    same mask, same constraint graph, same uniqueness.
    9! = 362,880 possible permutations per seed puzzle.
    """
    results = []
    seen = {puzzle}
    attempts = 0
    while len(results) < count and attempts < count * 10:
        attempts += 1
        perm = list(range(1, 10))
        random.shuffle(perm)
        mapping = {str(d): str(perm[d - 1]) for d in range(1, 10)}
        mapping['0'] = '0'
        shuffled = ''.join(mapping[c] for c in puzzle)
        if shuffled not in seen:
            seen.add(shuffled)
            results.append(shuffled)
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python mask_forge.py <mask> [--count N] [--timeout S]")
        print("  mask: 81 chars (x=clue, 0=empty) or quoted with spaces")
        print("  --count N: generate N unique puzzles (default 5)")
        print("  --timeout S: max seconds to search (default 60)")
        print()
        print("Example:")
        print('  python mask_forge.py "000 00x 00x 000 x0x 0x0 00x 0x0 x00 0x0 000 0x0 xx0 000 00x 000 000 xx0 00x 0x0 x00 0x0 x0x 000 x00 x00 000"')
        return

    # Parse args
    mask_input = sys.argv[1]
    count = 5
    timeout = 60

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--count' and i + 1 < len(sys.argv):
            count = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--timeout' and i + 1 < len(sys.argv):
            timeout = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    mask = parse_mask(mask_input)
    clue_positions = [i for i in range(81) if mask[i] == 1]

    print(f"{'=' * 65}")
    print(f"MASK FORGE — Constraint-Guided Unique Puzzle Generator")
    print(f"{'=' * 65}")
    print(f"  Clues: {len(clue_positions)}")
    print()

    # Find seed unique puzzle
    seed, sol, checks, elapsed = forge_unique(mask, max_seconds=timeout)

    if not seed:
        print(f"\n  Could not find unique puzzle in {timeout}s")
        print(f"  Try: --timeout 300")
        return

    print(f"\n  Seed puzzle: {seed}")
    print(f"  Solution:    {sol}")
    print(f"  Found in:    {checks} checks ({elapsed:.1f}s)")

    # Generate more via digit permutation
    # Verify seed
    print(f"\n  Verification:")
    print(f"    Unique solution:  {has_unique_solution(seed)}")
    print(f"    Mask preserved:   {all(seed[i] != '0' for i in clue_positions)}")
    print(f"    Valid Sudoku:     {validate_sudoku([int(c) for c in sol])}")

    if count > 1:
        print(f"\n  Generating {count - 1} more via digit permutation...")
        extras = digit_permutations(seed, count - 1)
        all_puzzles = [seed] + extras
        print(f"\n  {count} unique puzzles (same mask, ALL guaranteed unique-solution):")
        for i, p in enumerate(all_puzzles, 1):
            print(f"    {i}. {p}")

    print(f"""
  ── How It Works ──────────────────────────────────────────────
  1. Constraint-guided DFS places digits at clue positions,
     ordered by unit connectivity, choosing the most constraining
     digit first. The solver guides every placement.

  2. Once a seed puzzle is found, digit permutation (swapping all
     1s with 7s, all 3s with 9s, etc.) generates up to 9! = 362,880
     unique puzzles — ALL with the same mask, ALL guaranteed to
     have exactly one solution. No uniqueness check needed.

  3. This works because digit permutation preserves the constraint
     graph exactly. If the original has one solution, every
     permutation has exactly one solution.

  Mask uniqueness: brute force constraint search
  Constraint-guided forge + permutation proof: WSRF / Sir Lars
  ─────────────────────────────────────────────────────────────""")
    print(f"{'=' * 65}")


if __name__ == '__main__':
    main()
