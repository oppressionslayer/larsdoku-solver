#!/usr/bin/env python3
"""Top1465 benchmark runner for the WSRF bitwise engine.

Runs the canonical Top1465 collection (1465 hardest puzzles) and tracks:
- Solve rate: % of puzzles solved with pure logic (no oracle fallback)
- Technique frequency: which techniques fire most
- Timing: avg/max/total solve times
- Hardest puzzles: which ones needed the most steps or stalled

Usage:
    python run_top1465.py                        # run all 1465
    python run_top1465.py --limit 100            # first 100 only
    python run_top1465.py --start 500 --limit 50 # range
    python run_top1465.py --no-oracle            # pure logic only (no guessing)
    python run_top1465.py --level 5              # max technique level
    python run_top1465.py --gf2x                 # enable GF2 extended
"""
from __future__ import annotations

import os
import sys
import time
import argparse

# Path setup — local dir MUST be first so we get the right wsrf_solve
_DIR = os.path.dirname(os.path.abspath(__file__))

# Add puzzle data directories (after local dir)
_BENCH_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(_DIR)), 'CelestialsPartDeux', 'wsrf-spn', 'benchmarks'),
    os.path.join(os.path.dirname(os.path.dirname(_DIR)), 'CelestialsPartDeux', 'wsrf-spn_godogversion_forclaudesuse', 'benchmarks'),
]
for d in _BENCH_DIRS:
    if os.path.isdir(d):
        sys.path.append(d)  # append, not insert — keep local first

sys.path.insert(0, _DIR)

from wsrf_solve import solve_selective

try:
    from top1465_puzzles import TOP1465
except ImportError:
    TOP1465 = []


def main() -> None:
    parser = argparse.ArgumentParser(description="Top1465 benchmark — WSRF bitwise engine")
    parser.add_argument('--start', type=int, default=0, help='Start index')
    parser.add_argument('--limit', type=int, default=0, help='Max puzzles (0=all)')
    parser.add_argument('--no-oracle', action='store_true', help='Pure logic only, no oracle fallback')
    parser.add_argument('--level', type=int, default=99, help='Max technique level (1-7)')
    parser.add_argument('--gf2x', action='store_true', help='Enable GF2 Extended mode')
    parser.add_argument('--verbose', action='store_true', help='Print each step')
    args = parser.parse_args()

    if not TOP1465:
        print("ERROR: top1465_puzzles.py not found or empty.")
        print("       Looked in:", _BENCH_DIRS)
        sys.exit(1)

    puzzles = TOP1465[args.start:]
    if args.limit > 0:
        puzzles = puzzles[:args.limit]

    total = len(puzzles)
    print("=" * 72)
    print("  WSRF Bitwise Engine — Top1465 Benchmark")
    print("=" * 72)
    print(f"  Puzzles:    {total} (of {len(TOP1465)} total)")
    print(f"  Max level:  {args.level}")
    print(f"  No oracle:  {args.no_oracle}")
    print(f"  GF2 ext:    {args.gf2x}")
    print()

    pure_logic = 0
    oracle_used = 0
    stalled_count = 0
    total_steps = 0
    global_tech: dict[str, int] = {}
    solve_times: list[float] = []
    stalled_puzzles: list[tuple[int, int, float]] = []  # (idx, empty_remaining, time)
    hardest_by_steps: list[tuple[int, int, float]] = []  # (idx, n_steps, time)

    t_total = time.perf_counter()

    for i, puzzle_str in enumerate(puzzles):
        idx = args.start + i
        bd81 = puzzle_str.strip().replace('.', '0')

        t0 = time.perf_counter()
        result = solve_selective(
            bd81,
            max_level=args.level,
            no_oracle=args.no_oracle,
            verbose=args.verbose,
            gf2_extended=args.gf2x,
        )
        elapsed = time.perf_counter() - t0
        solve_times.append(elapsed)

        n_steps = result['n_steps']
        total_steps += n_steps
        tc = result['technique_counts']

        # Count oracle usage
        oracle_count = tc.get('ORACLE_ONLY', 0)
        if result.get('stalled'):
            stalled_count += 1
            stalled_puzzles.append((idx, result['empty_remaining'], elapsed))
        elif oracle_count > 0:
            oracle_used += 1
        else:
            pure_logic += 1

        for t, cnt in tc.items():
            global_tech[t] = global_tech.get(t, 0) + cnt

        hardest_by_steps.append((idx, n_steps, elapsed))

        # Progress every 50 puzzles
        if (i + 1) % 50 == 0 or i == total - 1:
            done = i + 1
            pct = pure_logic / done * 100
            avg_t = sum(solve_times) / len(solve_times)
            status = f"pure_logic={pure_logic}"
            if oracle_used:
                status += f" oracle={oracle_used}"
            if stalled_count:
                status += f" stalled={stalled_count}"
            print(f"  [{done:>5}/{total}] {status} ({pct:.1f}% pure), avg {avg_t:.4f}s/puzzle")

    elapsed_total = time.perf_counter() - t_total

    # ═══════════════════════════════════════════════════════════
    # REPORT
    # ═══════════════════════════════════════════════════════════
    print()
    print("=" * 72)
    print("  RESULTS")
    print("=" * 72)
    print(f"  Total puzzles:       {total}")
    print(f"  Pure logic solves:   {pure_logic}/{total} ({pure_logic/total*100:.1f}%)")
    if oracle_used:
        print(f"  Needed oracle:       {oracle_used}/{total}")
    if stalled_count:
        print(f"  Stalled (unsolved):  {stalled_count}/{total}")
    print(f"  Total steps:         {total_steps:,}")
    print(f"  Total time:          {elapsed_total:.1f}s")
    if solve_times:
        avg = sum(solve_times) / len(solve_times)
        print(f"  Avg time/puzzle:     {avg:.4f}s")
        print(f"  Max time/puzzle:     {max(solve_times):.4f}s")
        print(f"  Min time/puzzle:     {min(solve_times):.4f}s")
        under1 = sum(1 for t in solve_times if t < 1.0)
        under5 = sum(1 for t in solve_times if t < 5.0)
        print(f"  Under 1s:            {under1}/{total} ({under1/total*100:.1f}%)")
        print(f"  Under 5s:            {under5}/{total} ({under5/total*100:.1f}%)")

    print()
    print("TECHNIQUE FREQUENCY:")
    print("-" * 50)
    total_firings = sum(global_tech.values())
    for t, cnt in sorted(global_tech.items(), key=lambda x: -x[1]):
        pct = cnt / total_firings * 100 if total_firings else 0
        bar = "█" * int(pct / 2)
        print(f"  {t:<20} {cnt:>7,}x  ({pct:5.1f}%)  {bar}")

    print()
    print(f"  Total technique firings: {total_firings:,}")

    if stalled_puzzles:
        print()
        print(f"STALLED PUZZLES ({len(stalled_puzzles)}):")
        print("-" * 50)
        stalled_puzzles.sort(key=lambda x: -x[1])
        for idx, empty, t in stalled_puzzles[:20]:
            print(f"  #{idx}: {empty} cells remaining, {t:.3f}s")

    # Top 10 hardest by step count
    hardest_by_steps.sort(key=lambda x: -x[1])
    print()
    print("HARDEST PUZZLES (by step count, top 10):")
    print("-" * 50)
    for idx, n_steps, t in hardest_by_steps[:10]:
        print(f"  #{idx}: {n_steps} steps, {t:.3f}s")

    # Top 10 slowest
    slowest = sorted(enumerate(solve_times), key=lambda x: -x[1])[:10]
    print()
    print("SLOWEST PUZZLES (top 10):")
    print("-" * 50)
    for i, t in slowest:
        idx = args.start + i
        print(f"  #{idx}: {t:.3f}s")

    print()
    print("=" * 72)


if __name__ == "__main__":
    main()
