#!/usr/bin/env python3
"""Larsdoku — Built-in benchmark runner.

Usage:
    larsdoku-bench                           # run all 3 collections
    larsdoku-bench --collection top1465      # Top1465 only
    larsdoku-bench --collection expert       # Expert 669 only
    larsdoku-bench --collection famous       # Famous 10 only
    larsdoku-bench --limit 100               # first N puzzles only
"""
from __future__ import annotations

import argparse
import time
import sys

from larsdoku.cli import solve_selective, normalize_puzzle


def run_collection(name, puzzles, limit=0):
    """Run benchmark on a puzzle collection. Returns stats dict."""
    if limit > 0:
        puzzles = puzzles[:limit]

    total = len(puzzles)
    pure_logic = 0
    total_steps = 0
    global_tech = {}
    solve_times = []
    hardest = []

    t_total = time.perf_counter()

    for i, puzzle_data in enumerate(puzzles):
        # Handle both tuple format (famous) and string format
        if isinstance(puzzle_data, tuple):
            name_str, _, _, bd81 = puzzle_data
        else:
            bd81 = puzzle_data
            name_str = None

        bd81 = bd81.strip().replace('.', '0')

        t0 = time.perf_counter()
        result = solve_selective(bd81, no_oracle=True)
        elapsed = time.perf_counter() - t0
        solve_times.append(elapsed)

        n_steps = result['n_steps']
        total_steps += n_steps

        if result['success'] and not result.get('stalled'):
            pure_logic += 1
        else:
            hardest.append((i, result.get('empty_remaining', 0), elapsed, name_str))

        for t, cnt in result['technique_counts'].items():
            global_tech[t] = global_tech.get(t, 0) + cnt

        if (i + 1) % 50 == 0 or i == total - 1:
            done = i + 1
            pct = pure_logic / done * 100
            avg_t = sum(solve_times) / len(solve_times)
            print(f"  [{done:>5}/{total}] pure_logic={pure_logic} ({pct:.1f}%), avg {avg_t:.4f}s/puzzle")

    elapsed_total = time.perf_counter() - t_total

    return {
        'total': total,
        'pure_logic': pure_logic,
        'total_steps': total_steps,
        'elapsed_total': elapsed_total,
        'solve_times': solve_times,
        'global_tech': global_tech,
        'hardest': hardest,
    }


def print_report(name, stats):
    """Print benchmark report for a collection."""
    total = stats['total']
    pure = stats['pure_logic']
    times = stats['solve_times']

    print()
    print("=" * 72)
    print(f"  {name}")
    print("=" * 72)
    print(f"  Total puzzles:       {total}")
    print(f"  Pure logic solves:   {pure}/{total} ({pure/total*100:.1f}%)")
    if stats['hardest']:
        print(f"  Stalled:             {len(stats['hardest'])}")
    print(f"  Total steps:         {stats['total_steps']:,}")
    print(f"  Total time:          {stats['elapsed_total']:.1f}s")
    if times:
        avg = sum(times) / len(times)
        print(f"  Avg time/puzzle:     {avg:.4f}s")
        print(f"  Max time/puzzle:     {max(times):.4f}s")
        print(f"  Min time/puzzle:     {min(times):.4f}s")

    print()
    print("  TECHNIQUE FREQUENCY:")
    print("  " + "-" * 50)
    total_firings = sum(stats['global_tech'].values())
    for t, cnt in sorted(stats['global_tech'].items(), key=lambda x: -x[1]):
        pct = cnt / total_firings * 100 if total_firings else 0
        bar = "#" * int(pct / 2)
        print(f"    {t:<20} {cnt:>7,}x  ({pct:5.1f}%)  {bar}")
    print(f"    Total: {total_firings:,}")
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Larsdoku benchmark runner")
    parser.add_argument('--collection', '-c',
                       choices=['top1465', 'expert', 'famous', 'all'],
                       default='all', help='Which collection to benchmark')
    parser.add_argument('--limit', '-l', type=int, default=0,
                       help='Max puzzles per collection (0=all)')
    args = parser.parse_args()

    print()
    print("  Larsdoku Benchmark Suite")
    print("  Pure logic Sudoku solving — zero guessing")
    print()

    collections = []

    if args.collection in ('famous', 'all'):
        from larsdoku.puzzles import FAMOUS_10
        collections.append(("Famous 10 — Hardest Known Puzzles", FAMOUS_10))

    if args.collection in ('expert', 'all'):
        from larsdoku.puzzles import EXPERT_669
        collections.append(("Expert 669 — Shuffled Expert Collection", EXPERT_669))

    if args.collection in ('top1465', 'all'):
        from larsdoku.puzzles import TOP1465
        collections.append(("Top1465 — Stertenbrink/dukuso Canonical Benchmark", TOP1465))

    for name, puzzles in collections:
        print(f"\n  Running: {name}")
        stats = run_collection(name, puzzles, limit=args.limit)
        print_report(name, stats)

    print()


if __name__ == "__main__":
    main()
