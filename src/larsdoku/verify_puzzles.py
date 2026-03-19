#!/usr/bin/env python3
"""Verify a file of puzzles — count unique vs non-unique solutions."""

import sys
import time
from .engine import has_unique_solution, solve_backtrack


def verify_file(filepath, sample=None):
    puzzles = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if len(line) == 81 and all(c in '0123456789.' for c in line):
                puzzles.append(line)

    total = len(puzzles)
    print(f"File: {filepath}")
    print(f"Puzzles found: {total:,}")

    if sample and sample < total:
        import random
        random.seed(42)
        puzzles = random.sample(puzzles, sample)
        print(f"Sampling: {sample:,} random puzzles")

    check_count = len(puzzles)
    unique = 0
    multi = 0
    no_solution = 0
    t0 = time.perf_counter()

    for i, p in enumerate(puzzles):
        sol = solve_backtrack(p)
        if not sol:
            no_solution += 1
        elif has_unique_solution(p):
            unique += 1
        else:
            multi += 1

        if (i + 1) % 1000 == 0:
            el = time.perf_counter() - t0
            print(f"  ... {i+1:,}/{check_count:,} ({unique} unique, {multi} multi, {no_solution} none) {el:.0f}s")

    elapsed = time.perf_counter() - t0

    print(f"\n{'=' * 55}")
    print(f"  Checked:     {check_count:,}")
    print(f"  Unique:      {unique:,}")
    print(f"  Multi:       {multi:,}")
    print(f"  No solution: {no_solution:,}")
    print(f"  Time:        {elapsed:.1f}s")
    print(f"  Result:      {'PASS — all unique' if multi == 0 and no_solution == 0 else 'FAIL'}")
    print(f"{'=' * 55}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python verify_puzzles.py <file> [--sample N]")
        sys.exit(1)

    filepath = sys.argv[1]
    sample = None
    if '--sample' in sys.argv:
        idx = sys.argv.index('--sample')
        if idx + 1 < len(sys.argv):
            sample = int(sys.argv[idx + 1])

    verify_file(filepath, sample=sample)
