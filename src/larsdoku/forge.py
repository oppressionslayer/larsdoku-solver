"""larsdoku-forge — overnight mask forger for larsdoku v4.0.

Generates random valid Sudoku grids, reduces each to a minimal unique
puzzle, classifies it by technique, and streams qualifying seeds to a file.
The output is in v4.0 mask+solution record format, ready to merge back into
the seed database.

Designed for long-running overnight sessions that contribute NEW masks to
the user's local seed registry — masks not in the shipped database.

Usage:
    larsdoku-forge 100                    # 100 D2B seeds (default tech)
    larsdoku-forge 200 --tech DeepResonance
    larsdoku-forge 500 --any-l5           # any L5+ seed
    larsdoku-forge 1000 --tech D2B --output my_masks.jsonl
    larsdoku-forge 10 --hours 8           # run for 8 hours regardless of count
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

from .engine import has_unique_solution
from .cli import solve_selective, TECHNIQUE_LEVELS
from .lars_forge import lars_instant_grid, lars_mask_hash
from .seed_schema import mask_from_puzzle, is_valid_mask, is_valid_solution, SCHEMA_VERSION


# ── Forge primitives ─────────────────────────────────────────────────────

def forge_minimal_puzzle(rng):
    """Generate a random valid grid and reduce to minimal unique puzzle.

    Returns (puzzle_bd81, solution_bd81) or (None, None) on failure.
    """
    g = lars_instant_grid(seed=rng.randint(0, 2**31))
    if not g:
        return None, None
    solution = g['grid']
    puzzle = list(solution)
    cells = list(range(81))
    rng.shuffle(cells)
    for cell in cells:
        old = puzzle[cell]
        puzzle[cell] = '0'
        if not has_unique_solution(''.join(puzzle)):
            puzzle[cell] = old
    return ''.join(puzzle), solution


def classify_puzzle(puzzle_str):
    """Solve with larsdoku, return dict or None if solve failed."""
    result = solve_selective(puzzle_str)
    if not result.get('success'):
        return None
    counts = result.get('technique_counts', {})
    max_lv = max((TECHNIQUE_LEVELS.get(t, 1) for t in counts), default=1)
    return {
        'clues': sum(1 for c in puzzle_str if c != '0'),
        'max_level': max_lv,
        'techniques': sorted(counts.keys()),
    }


# ── Main driver ──────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        prog='larsdoku-forge',
        description='Forge NEW mask+solution seeds via random grid + reduction + technique classification. '
                    'Designed for long-running overnight sessions contributing masks not in the shipped database.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Output format (one JSONL record per line):
  {"mask": "00010...", "solution": "48357...", "techniques": [...], "clues": 24, "mask_hash": "..."}

Merge back into seed DB later with scripts/merge_forge_output.py (TBD).''',
    )
    p.add_argument('batch_size', type=int,
                   help='Target number of qualifying seeds to generate (required)')
    p.add_argument('--tech', type=str, default=None,
                   help='Only save seeds requiring this technique '
                        '(e.g. D2B, DeepResonance, FPC, KrakenFish, FPCE). '
                        'Default: D2B (if neither --tech nor --any-l5 given)')
    p.add_argument('--any-l5', action='store_true',
                   help='Save any L5+ seed (not filtered by specific technique)')
    p.add_argument('--any-l6', action='store_true',
                   help='Save any L6+ seed (D2B/KrakenFish/Tridagon/JuniorExocet/etc. class)')
    p.add_argument('--any-l7', action='store_true',
                   help='Save any L7+ seed (DeepResonance/FPF class — rarest)')
    p.add_argument('--seed', type=int, default=None,
                   help='Random seed (default: time-based for non-repeatability)')
    p.add_argument('--output', type=str, default=None,
                   help='Output JSONL path (default: larsdoku_forge_<TECH>_<TIMESTAMP>.jsonl '
                        'in current directory)')
    p.add_argument('--max-attempts', type=int, default=1_000_000,
                   help='Hard cap on random-grid generation attempts (default 1,000,000)')
    p.add_argument('--hours', type=float, default=None,
                   help='Run for up to N hours instead of stopping at batch_size '
                        '(continues until both target hit AND hours elapsed)')
    p.add_argument('--min-clues', type=int, default=17,
                   help='Reject seeds below this clue count (default 17)')
    p.add_argument('--max-clues', type=int, default=40,
                   help='Reject seeds above this clue count (default 40)')
    args = p.parse_args()

    # Default filter
    if not args.tech and not args.any_l5 and not args.any_l6 and not args.any_l7:
        args.tech = 'D2B'

    # Resolve "any-lN" into a minimum-level threshold
    min_level = None
    if args.any_l7:
        min_level = 7
    elif args.any_l6:
        min_level = 6
    elif args.any_l5:
        min_level = 5

    seed_value = args.seed if args.seed is not None else int(time.time())
    rng = random.Random(seed_value)

    if args.output is None:
        ts = time.strftime('%Y%m%d_%H%M%S')
        if min_level is not None:
            tag = f'L{min_level}plus'
        else:
            tag = args.tech
        args.output = f'larsdoku_forge_{tag}_{ts}.jsonl'

    out_path = os.path.abspath(args.output)
    stop_time = time.time() + args.hours * 3600 if args.hours else None

    print(f'larsdoku-forge v{SCHEMA_VERSION} — mask forger')
    print(f'  Target:    {args.batch_size} seeds'
          + (f' OR {args.hours}h limit' if args.hours else ''))
    if min_level is not None:
        filter_desc = f'any L{min_level}+'
    else:
        filter_desc = f'requires {args.tech}'
    print(f'  Filter:    {filter_desc}')
    print(f'  Clues:     {args.min_clues}-{args.max_clues}')
    print(f'  RNG seed:  {seed_value}')
    print(f'  Output:    {out_path}')
    print()

    found = 0
    attempts = 0
    mask_hashes_seen = set()
    t_start = time.time()

    with open(out_path, 'w') as fout:
        # Header (JSONL comment — not strictly JSON but common)
        header = {
            'schema_version': SCHEMA_VERSION,
            'generator': 'larsdoku-forge',
            'filter': filter_desc,
            'rng_seed': seed_value,
            'started_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        fout.write(f'# {json.dumps(header)}\n')
        fout.flush()

        while attempts < args.max_attempts:
            # Stop when both target AND time window satisfied
            if found >= args.batch_size and (stop_time is None or time.time() >= stop_time):
                break
            # Also stop if time window exceeded even with unmet target
            if stop_time is not None and time.time() >= stop_time:
                break
            attempts += 1

            puzzle, solution = forge_minimal_puzzle(rng)
            if puzzle is None:
                continue

            n_clues = sum(1 for c in puzzle if c != '0')
            if n_clues < args.min_clues or n_clues > args.max_clues:
                continue

            info = classify_puzzle(puzzle)
            if info is None:
                continue

            # Filter
            if min_level is not None:
                if info['max_level'] < min_level:
                    continue
            else:
                if args.tech not in info['techniques']:
                    continue

            # Dedup by mask-hash
            mask = mask_from_puzzle(puzzle)
            if not is_valid_mask(mask) or not is_valid_solution(solution):
                continue
            try:
                mh = str(lars_mask_hash([int(c) for c in mask]))
            except Exception:
                mh = None
            if mh and mh in mask_hashes_seen:
                continue
            if mh:
                mask_hashes_seen.add(mh)

            record = {
                'mask': mask,
                'solution': solution,
                'techniques': info['techniques'],
                'clues': n_clues,
                'max_level': info['max_level'],
                'mask_hash': mh,
            }
            fout.write(json.dumps(record) + '\n')
            fout.flush()

            found += 1
            elapsed = time.time() - t_start
            rate = attempts / elapsed if elapsed > 0 else 0
            advanced = [t for t in info['techniques']
                        if TECHNIQUE_LEVELS.get(t, 1) >= 5]
            print(f'  [{found:5d}/{args.batch_size}] attempt {attempts:7d} '
                  f'{elapsed/60:5.1f}min ({rate:5.1f}/s) — '
                  f'{n_clues} clues L{info["max_level"]} {advanced}')

    elapsed = time.time() - t_start
    print()
    print(f'{"=" * 60}')
    print(f'DONE — {found} seeds saved in {elapsed/60:.1f} min ({attempts} attempts)')
    if attempts:
        print(f'Hit rate: {found/attempts*100:.2f}%')
    print(f'Saved: {out_path}')


if __name__ == '__main__':
    main()
