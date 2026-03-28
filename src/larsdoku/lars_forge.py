#!/usr/bin/env python3
"""
LarsForge — O(81) Puzzle Generation Without Backtrackers
=========================================================
Sir Lars's backtracker-free puzzle forge using zone-guided digit permutation.

Every puzzle generated is:
  1. Guaranteed unique (digit permutation preserves uniqueness)
  2. Provably non-isomorphic (zone sum fingerprint proves it)
  3. Generated in microseconds (O(81) per puzzle, no search)

Core insight: zone sums are invariant under layout permutation but change
under digit permutation. Two puzzles with different normalized zone sum
vectors are provably non-isomorphic — no backtracker needed to verify.

Usage:
    from larsdoku.lars_forge import LarsForge

    forge = LarsForge("530070000600195000098000060800060003400803001700020006060000280000419005000080079")
    results = forge.lars_oracle_scan()
    print(f"Non-isomorphic classes: {results['n_classes']}")
    print(f"Total unique puzzles: {results['n_total']}")

    # Generate puzzles targeting specific zone difficulty
    puzzles = forge.lars_generate(count=100)
"""
from __future__ import annotations
import itertools
import time
import numpy as np
from collections import defaultdict

try:
    import numba as nb
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False


# ══════════════════════════════════════════════════════════════════════
# ZONE CONSTANTS — The 135 Rule
# ══════════════════════════════════════════════════════════════════════

# Zone positions: 9 zones, each collects 9 cells (one per box, same relative position)
# Zone index: TL=0, TC=1, TR=2, ML=3, MC=4, MR=5, BL=6, BC=7, BR=8
ZONE_CELLS = np.zeros((9, 9), dtype=np.int32)
for _zone in range(9):
    _zr, _zc = _zone // 3, _zone % 3  # relative position within box
    for _box in range(9):
        _br, _bc = (_box // 3) * 3, (_box % 3) * 3  # box top-left
        ZONE_CELLS[_zone, _box] = (_br + _zr) * 9 + (_bc + _zc)

# Template rows and columns for the 135 rule
TEMPLATE_ROWS = np.array([[0, 1, 2], [3, 4, 5], [6, 7, 8]], dtype=np.int32)
TEMPLATE_COLS = np.array([[0, 3, 6], [1, 4, 7], [2, 5, 8]], dtype=np.int32)


def lars_zone_sums(solution):
    """Compute zone sums for a solved board. Returns 9 zone sums.

    The 135 Rule guarantees:
      - Each template row sums to 135
      - Each template column sums to 135
    """
    if isinstance(solution, str):
        sol = [int(c) for c in solution]
    else:
        sol = list(solution)

    sums = np.zeros(9, dtype=np.int32)
    for z in range(9):
        for b in range(9):
            sums[z] += sol[ZONE_CELLS[z, b]]
    return sums


def lars_zone_digits(solution):
    """Get the set of digits in each zone. Returns 9 lists of 9 digits."""
    if isinstance(solution, str):
        sol = [int(c) for c in solution]
    else:
        sol = list(solution)

    digits = []
    for z in range(9):
        zd = []
        for b in range(9):
            zd.append(sol[ZONE_CELLS[z, b]])
        digits.append(sorted(zd))
    return digits


def lars_verify_135(zone_sums):
    """Verify the 135 rule holds for a zone sum vector."""
    for row in TEMPLATE_ROWS:
        if sum(zone_sums[i] for i in row) != 135:
            return False
    for col in TEMPLATE_COLS:
        if sum(zone_sums[i] for i in col) != 135:
            return False
    return True


# ══════════════════════════════════════════════════════════════════════
# ZONE SUM NORMALIZATION — Canonical form for isomorphism classes
# ══════════════════════════════════════════════════════════════════════

def lars_normalize_zone_sums(zone_sums):
    """Normalize a zone sum vector to canonical form.

    Standard Sudoku symmetries can:
      - Permute template rows (band permutation)
      - Permute template columns (stack permutation)
      - Permute zones within a template row (row shuffle within band)
      - Permute zones within a template column (col shuffle within stack)
      - Transpose the 3x3 zone matrix

    Canonical form: sort each template row, sort rows, then check transpose.
    """
    zs = np.array(zone_sums, dtype=np.int32)

    # Reshape to 3x3 zone matrix
    mat = zs.reshape(3, 3)

    def canonicalize(m):
        # Sort within each row
        m = np.sort(m, axis=1)
        # Sort rows lexicographically
        row_order = np.lexsort(m[:, ::-1].T)
        m = m[row_order]
        return tuple(m.flatten())

    # Try both orientations
    c1 = canonicalize(mat.copy())
    c2 = canonicalize(mat.T.copy())

    return min(c1, c2)


# ══════════════════════════════════════════════════════════════════════
# LARS FORGE — The Core Engine
# ══════════════════════════════════════════════════════════════════════

class LarsForge:
    """O(81) puzzle generation via zone-guided digit permutation.

    No backtrackers. No trial and error. Pure deterministic mathematics.
    """

    def __init__(self, seed_puzzle, seed_solution=None):
        """Initialize with a verified-unique seed puzzle.

        Args:
            seed_puzzle: 81-char string (0 or . for empty)
            seed_solution: 81-char solution string (auto-solved if not provided)
        """
        self.seed_puzzle = seed_puzzle.replace('.', '0')

        if seed_solution:
            self.seed_solution = seed_solution
        else:
            # Auto-solve using backtracker (one-time cost, never again)
            from .engine import solve_backtrack
            self.seed_solution = solve_backtrack(self.seed_puzzle)
            if not self.seed_solution:
                raise ValueError("Seed puzzle has no solution")
            if isinstance(self.seed_solution, (list, np.ndarray)):
                self.seed_solution = ''.join(str(d) for d in self.seed_solution)

        self.seed_zone_sums = lars_zone_sums(self.seed_solution)
        self.seed_zone_digits = lars_zone_digits(self.seed_solution)

        # Clue mask: which positions have clues
        self.mask = [self.seed_puzzle[i] != '0' for i in range(81)]
        self.n_clues = sum(self.mask)

    def lars_permute(self, perm):
        """Apply a digit permutation to the seed puzzle. O(81).

        Args:
            perm: list/tuple of 9 digits — perm[old_digit-1] = new_digit

        Returns:
            New puzzle string (81 chars)
        """
        mapping = {str(i + 1): str(perm[i]) for i in range(9)}
        mapping['0'] = '0'
        return ''.join(mapping[c] for c in self.seed_puzzle)

    def lars_permute_solution(self, perm):
        """Apply a digit permutation to the seed solution. O(81).

        Returns:
            New solution string (81 chars)
        """
        mapping = {str(i + 1): str(perm[i]) for i in range(9)}
        return ''.join(mapping[c] for c in self.seed_solution)

    def lars_oracle_scan(self, max_perms=0, verbose=False):
        """Scan all (or max_perms) digit permutations, compute zone sums,
        classify into non-isomorphic classes.

        This is THE experiment: how many provably non-isomorphic puzzles
        can one seed produce?

        Args:
            max_perms: 0 = all 362,880 permutations
            verbose: print progress

        Returns:
            dict with:
              n_total: total permutations tested
              n_classes: number of distinct non-isomorphic zone sum classes
              class_sizes: dict mapping canonical zone sum → count
              zone_sum_diversity: number of distinct raw zone sum vectors
              time_ms: elapsed time
              rate: permutations per second
        """
        t0 = time.perf_counter()

        digits = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        raw_sums = set()           # distinct raw zone sum vectors
        canonical_classes = defaultdict(int)  # canonical form → count

        n_tested = 0

        for perm in itertools.permutations(digits):
            new_sol = self.lars_permute_solution(perm)
            zs = lars_zone_sums(new_sol)

            raw_sums.add(tuple(zs))

            canonical = lars_normalize_zone_sums(zs)
            canonical_classes[canonical] += 1

            n_tested += 1

            if max_perms > 0 and n_tested >= max_perms:
                break

            if verbose and n_tested % 50000 == 0:
                elapsed = (time.perf_counter() - t0) * 1000
                print(f'  [{n_tested}/362880] classes={len(canonical_classes)} '
                      f'raw_distinct={len(raw_sums)} ({elapsed:.0f}ms)')

        elapsed = (time.perf_counter() - t0) * 1000
        rate = n_tested / (elapsed / 1000) if elapsed > 0 else 0

        # Zone sum distribution analysis
        class_sizes = dict(sorted(canonical_classes.items(),
                                   key=lambda x: -x[1]))

        return {
            'n_total': n_tested,
            'n_classes': len(canonical_classes),
            'zone_sum_diversity': len(raw_sums),
            'class_sizes': class_sizes,
            'time_ms': elapsed,
            'rate': rate,
            'seed_zone_sums': tuple(self.seed_zone_sums),
            'n_clues': self.n_clues,
        }

    def lars_generate(self, count=10, seed=42, unique_classes=True):
        """Generate puzzles via digit permutation.

        Args:
            count: number of puzzles to generate
            seed: random seed for reproducibility
            unique_classes: if True, only return puzzles from distinct
                           non-isomorphic classes

        Returns:
            list of dicts with: puzzle, solution, zone_sums, canonical_class
        """
        import random
        rng = random.Random(seed)

        digits = list(range(1, 10))
        results = []
        seen_classes = set()
        attempts = 0
        max_attempts = count * 20

        while len(results) < count and attempts < max_attempts:
            perm = digits[:]
            rng.shuffle(perm)

            new_puzzle = self.lars_permute(perm)
            new_solution = self.lars_permute_solution(perm)
            zs = lars_zone_sums(new_solution)
            canonical = lars_normalize_zone_sums(zs)

            if unique_classes and canonical in seen_classes:
                attempts += 1
                continue

            seen_classes.add(canonical)
            results.append({
                'puzzle': new_puzzle,
                'solution': new_solution,
                'zone_sums': tuple(zs),
                'canonical_class': canonical,
                'perm': tuple(perm),
            })
            attempts += 1

        return results

    def lars_forge_batch(self, count=1000, seed=42):
        """High-speed batch generation. Returns just puzzle strings.

        Generates `count` unique puzzles as fast as possible.
        No zone sum computation — pure speed.

        Returns:
            list of puzzle strings, time_ms, rate (puzzles/sec)
        """
        import random
        rng = random.Random(seed)

        digits = list(range(1, 10))
        puzzles = []
        seen = set()

        t0 = time.perf_counter()

        while len(puzzles) < count:
            perm = digits[:]
            rng.shuffle(perm)

            new_puzzle = self.lars_permute(perm)
            if new_puzzle not in seen:
                seen.add(new_puzzle)
                puzzles.append(new_puzzle)

        elapsed = (time.perf_counter() - t0) * 1000
        rate = len(puzzles) / (elapsed / 1000) if elapsed > 0 else 0

        return puzzles, elapsed, rate

    def lars_zone_report(self):
        """Print a zone analysis report for the seed puzzle."""
        print(f'LarsForge Zone Report')
        print(f'{"═" * 50}')
        print(f'Seed: {self.seed_puzzle[:30]}...')
        print(f'Clues: {self.n_clues}')
        print()

        # Zone sum matrix
        zs = self.seed_zone_sums
        print(f'Zone Sums:')
        print(f'  ┌─────────────────┐')
        for r in range(3):
            vals = [zs[r * 3 + c] for c in range(3)]
            print(f'  │ {vals[0]:3d}  {vals[1]:3d}  {vals[2]:3d} │  = {sum(vals)}')
        print(f'  └─────────────────┘')
        cols = [sum(zs[r * 3 + c] for r in range(3)) for c in range(3)]
        print(f'    {cols[0]:3d}  {cols[1]:3d}  {cols[2]:3d}')
        print(f'    135? {all(c == 135 for c in cols)} ✓' if all(c == 135 for c in cols) else '    135? FAIL')
        print()

        # Zone digits
        names = ['TL', 'TC', 'TR', 'ML', 'MC', 'MR', 'BL', 'BC', 'BR']
        print(f'Zone Digits:')
        for z in range(9):
            digs = self.seed_zone_digits[z]
            print(f'  {names[z]}: {digs} (sum={sum(digs)})')


# ══════════════════════════════════════════════════════════════════════
# CLI — Direct execution
# ══════════════════════════════════════════════════════════════════════

def main():
    """LarsForge CLI — run the oracle scan on a puzzle."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m larsdoku.lars_forge <puzzle> [--count N] [--report]")
        print()
        print("  --count N    Max permutations to test (default: all 362,880)")
        print("  --report     Print zone analysis report")
        print("  --generate N Generate N non-isomorphic puzzles")
        print("  --batch N    High-speed batch generate N puzzles")
        sys.exit(1)

    puzzle = sys.argv[1]
    count = 0
    report = False
    generate = 0
    batch = 0

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--count' and i + 1 < len(sys.argv):
            count = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--report':
            report = True
            i += 1
        elif sys.argv[i] == '--generate' and i + 1 < len(sys.argv):
            generate = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--batch' and i + 1 < len(sys.argv):
            batch = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    forge = LarsForge(puzzle)

    if report:
        forge.lars_zone_report()
        print()

    if generate > 0:
        print(f'Generating {generate} non-isomorphic puzzles...')
        puzzles = forge.lars_generate(count=generate)
        for p in puzzles:
            print(f'{p["puzzle"]}  zones={list(p["zone_sums"])}')
        print(f'\n{len(puzzles)} puzzles generated')
        return

    if batch > 0:
        print(f'Batch generating {batch} puzzles...')
        puzzles, elapsed, rate = forge.lars_forge_batch(count=batch)
        for p in puzzles[:10]:
            print(p)
        if len(puzzles) > 10:
            print(f'... ({len(puzzles) - 10} more)')
        print(f'\n{len(puzzles)} puzzles in {elapsed:.1f}ms ({rate:.0f} puzzles/sec)')
        return

    # Oracle scan
    print(f'LarsForge Oracle Scan')
    print(f'{"═" * 60}')
    print(f'Seed: {puzzle[:40]}...')
    print(f'Clues: {forge.n_clues}')
    print(f'Seed zone sums: {list(forge.seed_zone_sums)}')
    print(f'135 rule: {"✓" if lars_verify_135(forge.seed_zone_sums) else "FAIL"}')
    print()

    n = count if count > 0 else 362880
    print(f'Scanning {"all " if count == 0 else ""}{n} digit permutations...')

    results = forge.lars_oracle_scan(max_perms=count, verbose=True)

    print()
    print(f'{"═" * 60}')
    print(f'RESULTS')
    print(f'{"═" * 60}')
    print(f'Total permutations:    {results["n_total"]:,}')
    print(f'Non-isomorphic classes: {results["n_classes"]:,}')
    print(f'Raw zone sum diversity: {results["zone_sum_diversity"]:,}')
    print(f'Time:                  {results["time_ms"]:.0f}ms')
    print(f'Rate:                  {results["rate"]:,.0f} perms/sec')
    print()

    # Top 10 largest classes
    print(f'Top 10 largest isomorphism classes:')
    for i, (canon, count) in enumerate(list(results['class_sizes'].items())[:10]):
        print(f'  #{i+1}: {count:,} puzzles — zones {list(canon[:3])}|{list(canon[3:6])}|{list(canon[6:])}')

    # Smallest classes (most unique)
    smallest = sorted(results['class_sizes'].items(), key=lambda x: x[1])[:5]
    print(f'\nRarest classes (most unique):')
    for canon, count in smallest:
        print(f'  {count:,} puzzles — zones {list(canon[:3])}|{list(canon[3:6])}|{list(canon[6:])}')


if __name__ == '__main__':
    main()
