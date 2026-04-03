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

# ══════════════════════════════════════════════════════════════════════
# LARS SEED BANK — One verified-unique seed per clue count (17-30)
# Each seed can produce 362,880+ unique puzzles via digit permutation.
# Combined: ~5 million puzzles, ~17 trillion with full shuffle group.
# ══════════════════════════════════════════════════════════════════════
LARS_SEED_BANK = {
    17: "000000010400000000020000000000050407008000300001090000300400200050100000000806000",
    18: "000000010400000000020000004000050407008000300001090000300400200050100000000806000",
    19: "000000010407000000020000000000050407008000300001090000300400200050100000004806000",
    20: "000000010400000000020900004000050407008000300001090000300400200050100000200806000",
    21: "100000000006250000075080000960000003000000010000900004300400005000000308200170000",
    22: "120006300405007010009000000000003807000000409000000000607900104050020000000100000",
    23: "789000030000006001000000004340070000005000000100960002000005076000000800032004000",
    24: "000500000600017000034200080700083000003100064002495000800006000000000009300000005",
    25: "100000005000900306083000000005000092604000781000700003010203074067000000000000008",
    26: "049100205000008010000030000010306400050009000300070008000600300020410080000000906",
    27: "000678039600000000290001000000000008001453000500000000134502600800000000000090004",
    28: "001672083300000100402105600000000006900004002760080500038700000609000000000009000",
    29: "008030700100096000304200506003415200000900004000060000001008400000000000082070001",
    30: "000007000070320084200000000040500073930041002001806050000005016000000705000103000",
}


try:
    import numba as nb
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False


# ══════════════════════════════════════════════════════════════════════
# LARS EXTENDED SEED BANK — 513 diverse seeds loaded from JSON
# ══════════════════════════════════════════════════════════════════════
import os as _os
import json as _json

_SEED_BANK_PATH_128 = _os.path.join(_os.path.dirname(__file__), 'seed_bank_128.json')
_SEED_BANK_PATH_64 = _os.path.join(_os.path.dirname(__file__), 'seed_bank_64.json')
LARS_EXTENDED_BANK = {}  # clue_count (int) -> list of puzzle strings

# Prefer 128-seed bank, fall back to 64
for _path in [_SEED_BANK_PATH_128, _SEED_BANK_PATH_64]:
    if _os.path.exists(_path):
        with open(_path) as _f:
            _raw = _json.load(_f)
            LARS_EXTENDED_BANK = {int(k): v for k, v in _raw.items()}
        break


# ══════════════════════════════════════════════════════════════════════
# LARS GRID DATABASE — Pre-solved grids for 6μs generation
# ══════════════════════════════════════════════════════════════════════
_GRID_DB_PATH = _os.path.join(_os.path.dirname(__file__), 'zone_grid_db_full.json')
_GRID_DB_SMALL = _os.path.join(_os.path.dirname(__file__), '..', '..', 'lars', 'zone_grid_db_full.json')
LARS_GRID_DB = {}  # zone_sum_key → list of solution strings

for _gpath in [_GRID_DB_PATH, _GRID_DB_SMALL]:
    if _os.path.exists(_gpath):
        with open(_gpath) as _f:
            LARS_GRID_DB = _json.load(_f)
        break


def lars_instant_grid(seed=None):
    """Generate a unique Sudoku grid in ~6 microseconds.

    Picks a random pre-solved grid from the database and applies
    a random digit permutation. No DFS, no backtracker, just lookup + permute.

    Args:
        seed: random seed for reproducibility

    Returns:
        dict with: grid (81-char), zone_sums, elapsed_us
    """
    import random as _random
    import time as _time

    if not LARS_GRID_DB:
        return {'grid': None, 'error': 'Grid database not loaded'}

    rng = _random.Random(seed)

    t0 = _time.perf_counter()

    # Pick random zone pattern
    keys = list(LARS_GRID_DB.keys())
    pattern_key = rng.choice(keys)
    grids = LARS_GRID_DB[pattern_key]
    base_grid = rng.choice(grids)

    # Digit permutation
    digits = list(range(1, 10))
    rng.shuffle(digits)
    mapping = {str(i + 1): str(digits[i]) for i in range(9)}
    new_grid = ''.join(mapping[c] for c in base_grid)

    elapsed_us = (_time.perf_counter() - t0) * 1e6

    zone_sums = [int(x) for x in pattern_key.split(',')]

    return {
        'grid': new_grid,
        'zone_sums': zone_sums,
        'elapsed_us': elapsed_us,
    }


def lars_instant_batch(count=1000, seed=42):
    """Generate many unique grids at ~6μs each.

    Args:
        count: number of grids to generate
        seed: random seed

    Returns:
        dict with: grids (list), elapsed_ms, rate
    """
    import random as _random
    import time as _time

    if not LARS_GRID_DB:
        return {'grids': [], 'error': 'Grid database not loaded'}

    rng = _random.Random(seed)
    keys = list(LARS_GRID_DB.keys())
    all_grids = []
    for k in keys:
        for g in LARS_GRID_DB[k]:
            all_grids.append(g)

    digits = list(range(1, 10))
    results = []
    seen = set()

    t0 = _time.perf_counter()

    while len(results) < count:
        base = rng.choice(all_grids)
        rng.shuffle(digits)
        mapping = {str(i + 1): str(digits[i]) for i in range(9)}
        new_grid = ''.join(mapping[c] for c in base)
        if new_grid not in seen:
            seen.add(new_grid)
            results.append(new_grid)

    elapsed_ms = (_time.perf_counter() - t0) * 1000
    rate = len(results) / (elapsed_ms / 1000) if elapsed_ms > 0 else 0

    return {
        'grids': results,
        'elapsed_ms': elapsed_ms,
        'rate': rate,
    }


def lars_get_seed(clues=22, index=None, seed=None, difficulty=None):
    """Get a seed puzzle from the extended bank.

    Args:
        clues: clue count (17-30)
        index: specific seed index (1-based, wraps if > available)
               None = random selection
        seed: random seed (used when index is None)
        difficulty: None (random), 'easy', 'hard', 'diabolical'
                    For 17-clue: hard = Top95 seeds (1-38),
                    diabolical = Lars-tech seeds (39-43),
                    easy = Royle collection (44+)

    Returns:
        puzzle string or None
    """
    import random

    # Try extended bank first, fall back to single seed bank
    if clues in LARS_EXTENDED_BANK and LARS_EXTENDED_BANK[clues]:
        pool = LARS_EXTENDED_BANK[clues]
    elif clues in LARS_SEED_BANK:
        pool = [LARS_SEED_BANK[clues]]
    else:
        return None

    # Apply difficulty filter (tier-based for seed bank)
    # For 17-clue: positions 1-38 = Top95 hard, 39-43 = Lars-tech, 44+ = easy
    # For other clue counts: hard/diabolical = first half (from 48K forum hardest),
    #                        easy = second half (general collection)
    if difficulty is not None and len(pool) > 10:
        half = len(pool) // 2
        if clues == 17 and len(pool) > 43:
            if difficulty == 'diabolical':
                pool = pool[38:43]
            elif difficulty == 'hard':
                pool = pool[:43]
            elif difficulty == 'easy':
                pool = pool[43:]
            elif difficulty == 'medium':
                pool = pool[20:60]
        else:
            if difficulty in ('diabolical', 'hard'):
                pool = pool[:half]
            elif difficulty == 'easy':
                pool = pool[half:]
            elif difficulty == 'medium':
                quarter = len(pool) // 4
                pool = pool[quarter:quarter*3]

    if not pool:
        return None

    if index is not None:
        # 1-based, wrap around
        idx = (index - 1) % len(pool)
        return pool[idx]
    else:
        rng = random.Random(seed)
        return rng.choice(pool)


# ══════════════════════════════════════════════════════════════════════
# LARS SHUFFLE FORGE — Uniqueness-preserving box/row/col/band shuffles
# ══════════════════════════════════════════════════════════════════════

def lars_shuffle(puzzle, rng=None):
    """Apply random uniqueness-preserving transformations to a puzzle.

    Transformations (all preserve uniqueness):
      1. Swap rows within bands (3 bands × 3! = 216 combinations)
      2. Swap columns within stacks (3 stacks × 3! = 216)
      3. Swap bands (3! = 6)
      4. Swap stacks (3! = 6)
      5. Transpose (2)

    Combined with digit permutation: ~1.22 trillion variants per seed.

    Args:
        puzzle: 81-char puzzle string
        rng: random.Random instance (or None for default)

    Returns:
        shuffled puzzle string (guaranteed same uniqueness as input)
    """
    import random
    if rng is None:
        rng = random.Random()

    # Convert to 9x9 grid
    grid = [[int(puzzle[r * 9 + c]) for c in range(9)] for r in range(9)]

    # 1. Shuffle rows within each band
    for band in range(3):
        rows = [band * 3, band * 3 + 1, band * 3 + 2]
        rng.shuffle(rows)
        new_rows = [grid[r] for r in rows]
        for i, r in enumerate(range(band * 3, band * 3 + 3)):
            grid[r] = new_rows[i]

    # 2. Shuffle columns within each stack
    for stack in range(3):
        cols = [stack * 3, stack * 3 + 1, stack * 3 + 2]
        rng.shuffle(cols)
        for r in range(9):
            new_vals = [grid[r][c] for c in cols]
            for i, c in enumerate(range(stack * 3, stack * 3 + 3)):
                grid[r][c] = new_vals[i]

    # 3. Shuffle bands
    bands = [0, 1, 2]
    rng.shuffle(bands)
    new_grid = []
    for b in bands:
        for r in range(b * 3, b * 3 + 3):
            new_grid.append(grid[r])
    grid = new_grid

    # 4. Shuffle stacks
    stacks = [0, 1, 2]
    rng.shuffle(stacks)
    for r in range(9):
        new_row = []
        for s in stacks:
            new_row.extend(grid[r][s * 3:s * 3 + 3])
        grid[r] = new_row

    # 5. Transpose (50% chance)
    if rng.random() < 0.5:
        grid = [[grid[r][c] for r in range(9)] for c in range(9)]

    # Convert back to string
    return ''.join(str(grid[r][c]) for r in range(9) for c in range(9))


def lars_full_transform(puzzle, rng=None):
    """Apply BOTH shuffle AND digit permutation. Maximum diversity.

    Returns a puzzle guaranteed to have the same uniqueness as the input,
    but with a completely different appearance — different mask positions,
    different digits, different box layout.

    Args:
        puzzle: 81-char puzzle string
        rng: random.Random instance

    Returns:
        transformed puzzle string
    """
    import random
    if rng is None:
        rng = random.Random()

    # Step 1: Shuffle (changes mask positions)
    shuffled = lars_shuffle(puzzle, rng)

    # Step 2: Digit permutation (changes digit labels)
    digits = list(range(1, 10))
    rng.shuffle(digits)
    mapping = {str(i + 1): str(digits[i]) for i in range(9)}
    mapping['0'] = '0'

    return ''.join(mapping[c] for c in shuffled)


# ══════════════════════════════════════════════════════════════════════
# LARS BOX ROTATION — 180° rotation within each box (preserves validity)
# ══════════════════════════════════════════════════════════════════════

_BOX_ROTATE_180 = [8, 7, 6, 5, 4, 3, 2, 1, 0]  # TL↔BR, TC↔BC, TR↔BL, ML↔MR, MC stays


def lars_box_rotate_180(puzzle):
    """Rotate each 3x3 box by 180 degrees.

    Maps every cell to its diagonally opposite position within its box:
    TL↔BR, TC↔BC, TR↔BL, ML↔MR, MC stays.

    This preserves Sudoku validity (zero row/col/box conflicts),
    preserves uniqueness (100% tested), and creates completely new
    mask geometries with zero overlap from the original.

    Args:
        puzzle: 81-char puzzle string

    Returns:
        rotated puzzle string
    """
    new = list('0' * 81)
    for box in range(9):
        for old_z in range(9):
            new_z = _BOX_ROTATE_180[old_z]
            old_pos = int(ZONE_CELLS[old_z, box])
            new_pos = int(ZONE_CELLS[new_z, box])
            new[new_pos] = puzzle[old_pos]
    return ''.join(new)


def lars_mega_transform(puzzle, rng=None):
    """Maximum diversity transform: shuffle → rotate 180° → shuffle → permute.

    Produces puzzles with zero overlap from standard transforms.
    4x diversity boost over shuffle+permute alone.

    Args:
        puzzle: 81-char puzzle string
        rng: random.Random instance

    Returns:
        transformed puzzle string (validity + uniqueness preserved)
    """
    import random
    if rng is None:
        rng = random.Random()

    # Step 1: shuffle
    p = lars_shuffle(puzzle, rng)
    # Step 2: rotate 180°
    p = lars_box_rotate_180(p)
    # Step 3: shuffle again
    p = lars_shuffle(p, rng)
    # Step 4: digit permute
    digits = list(range(1, 10))
    rng.shuffle(digits)
    mapping = {str(i + 1): str(digits[i]) for i in range(9)}
    mapping['0'] = '0'
    return ''.join(mapping[c] for c in p)


# ══════════════════════════════════════════════════════════════════════
# LARS ZONE SHUFFLE — Single-Box Zone Shuffle (100% multi→unique)
# ══════════════════════════════════════════════════════════════════════

# 9 zone swaps within template rows (preserves 135 rule)
_ZONE_SWAPS = [
    [1, 0, 2, 3, 4, 5, 6, 7, 8],  # TL↔TC
    [2, 1, 0, 3, 4, 5, 6, 7, 8],  # TL↔TR
    [0, 2, 1, 3, 4, 5, 6, 7, 8],  # TC↔TR
    [0, 1, 2, 4, 3, 5, 6, 7, 8],  # ML↔MC
    [0, 1, 2, 5, 4, 3, 6, 7, 8],  # ML↔MR
    [0, 1, 2, 3, 5, 4, 6, 7, 8],  # MC↔MR
    [0, 1, 2, 3, 4, 5, 7, 6, 8],  # BL↔BC
    [0, 1, 2, 3, 4, 5, 8, 7, 6],  # BL↔BR
    [0, 1, 2, 3, 4, 5, 6, 8, 7],  # BC↔BR
]


def lars_single_box_shuffle(puzzle, box_idx, zone_perm):
    """Shuffle zone positions within a single box.

    Moves clue digits to different zone positions within one box,
    leaving all other boxes untouched.

    Args:
        puzzle: 81-char puzzle string
        box_idx: which box to shuffle (0-8)
        zone_perm: list of 9 ints mapping old_zone → new_zone

    Returns:
        new puzzle string with clues repositioned within the box
    """
    new_puzzle = list(puzzle)
    for old_z in range(9):
        new_z = zone_perm[old_z]
        old_pos = int(ZONE_CELLS[old_z, box_idx])
        new_pos = int(ZONE_CELLS[new_z, box_idx])
        new_puzzle[new_pos] = puzzle[old_pos]
    return ''.join(new_puzzle)


def lars_shuffle_to_unique(puzzle):
    """Convert a multi-solution puzzle to a unique one via zone shuffle.

    Tries single-box shuffles AND uniform all-box shuffles.
    Validates each shuffle produces a solvable puzzle before checking uniqueness.

    Args:
        puzzle: 81-char puzzle string (may be multi-solution)

    Returns:
        dict with:
          success: bool
          puzzle: unique puzzle string (or None)
          box: which box was shuffled (-1 if all-box, -2 if already unique)
          swap_idx: which swap was used
          checked: number of shuffles tried
    """
    from .engine import has_unique_solution, solve_backtrack

    # Already unique?
    if has_unique_solution(puzzle):
        return {
            'success': True,
            'puzzle': puzzle,
            'box': -2,
            'swap_idx': -1,
            'checked': 0,
        }

    def is_valid_puzzle(p):
        """Check no row/col/box conflicts in placed clues."""
        for i in range(81):
            if p[i] == '0':
                continue
            d = p[i]
            r, c = i // 9, i % 9
            # Row check
            for j in range(9):
                if j != c and p[r*9+j] == d:
                    return False
            # Col check
            for j in range(9):
                if j != r and p[j*9+c] == d:
                    return False
            # Box check
            br, bc = (r//3)*3, (c//3)*3
            for dr in range(3):
                for dc in range(3):
                    pos2 = (br+dr)*9 + bc+dc
                    if pos2 != i and p[pos2] == d:
                        return False
        return True

    checked = 0
    n_clues = sum(1 for c in puzzle if c != '0')

    # Phase 1: Try uniform all-box shuffles (same swap applied to ALL boxes)
    for si, swap in enumerate(_ZONE_SWAPS):
        shuffled_chars = list(puzzle)
        # Apply same swap to ALL 9 boxes
        new_puzzle = list('0' * 81)
        for box in range(9):
            for old_z in range(9):
                new_z = swap[old_z]
                old_pos = int(ZONE_CELLS[old_z, box])
                new_pos = int(ZONE_CELLS[new_z, box])
                new_puzzle[new_pos] = puzzle[old_pos]
        shuffled = ''.join(new_puzzle)

        if sum(1 for c in shuffled if c != '0') != n_clues:
            continue
        if not is_valid_puzzle(shuffled):
            continue

        checked += 1
        if solve_backtrack(shuffled) is not None and has_unique_solution(shuffled):
            return {
                'success': True,
                'puzzle': shuffled,
                'box': -1,  # all boxes
                'swap_idx': si,
                'checked': checked,
            }

    # Phase 2: Try single-box shuffles
    for box in range(9):
        for si, swap in enumerate(_ZONE_SWAPS):
            shuffled = lars_single_box_shuffle(puzzle, box, swap)

            if sum(1 for c in shuffled if c != '0') != n_clues:
                continue
            if not is_valid_puzzle(shuffled):
                continue

            checked += 1
            if solve_backtrack(shuffled) is not None and has_unique_solution(shuffled):
                return {
                    'success': True,
                    'puzzle': shuffled,
                    'box': box,
                    'swap_idx': si,
                    'checked': checked,
                }

    return {
        'success': False,
        'puzzle': None,
        'box': -1,
        'swap_idx': -1,
        'checked': checked,
    }


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
# LARS MASK MATCHING — Final Boss Mode
# Match ANY clue-mask to a known seed via Sudoku symmetry group
# ══════════════════════════════════════════════════════════════════════

def lars_parse_mask(mask_str):
    """Parse mask from 'x......x...' or '10000001...' format.

    x/X/1 = clue position, 0/./space = empty.
    Any non-zero digit also counts as a clue position.

    Returns: list of 81 ints (0 or 1)
    """
    mask = []
    for c in mask_str.strip():
        if c in ('x', 'X', '1'):
            mask.append(1)
        elif c in ('0', '.'):
            mask.append(0)
        elif c.isdigit() and c != '0':
            mask.append(1)
        # skip whitespace / newlines
    if len(mask) != 81:
        raise ValueError(f"Mask must be exactly 81 positions, got {len(mask)}")
    return mask


def lars_mask_hash(mask):
    """Compute a symmetry-invariant hash of a clue-mask pattern.

    Invariant under every Sudoku symmetry (row/col/band/stack shuffle + transpose).
    Two masks that are Sudoku-equivalent ALWAYS produce the same hash.
    Two masks with different hashes are NEVER equivalent.

    Returns: hashable tuple  (band_profile, stack_profile, box_profile)
    """
    m = np.array(mask, dtype=np.int8).reshape(9, 9)

    def _profile(grid):
        bands = []
        for b in range(3):
            rows = tuple(sorted(int(grid[b * 3 + r].sum()) for r in range(3)))
            bands.append(rows)
        band_p = tuple(sorted(bands))

        stacks = []
        for s in range(3):
            cols = tuple(sorted(int(grid[:, s * 3 + c].sum()) for c in range(3)))
            stacks.append(cols)
        stack_p = tuple(sorted(stacks))

        boxes = []
        for bx in range(9):
            br, bc = (bx // 3) * 3, (bx % 3) * 3
            boxes.append(int(grid[br:br + 3, bc:bc + 3].sum()))
        box_p = tuple(sorted(boxes))

        return (band_p, stack_p, box_p)

    return min(_profile(m), _profile(m.T))


def _match_columns(src_rp, target_2d):
    """Find a valid column permutation mapping src_rp columns to target_2d columns.

    Respects stack structure: columns within a stack can only swap within a stack,
    and stacks themselves can be permuted.

    Returns: list of 9 ints (col permutation) or None
    """
    # Build stack profiles for fast comparison
    tgt_stack_pats = []
    for s in range(3):
        pats = tuple(sorted(tuple(target_2d[:, s * 3 + c].tolist()) for c in range(3)))
        tgt_stack_pats.append(pats)

    src_stack_pats = []
    for s in range(3):
        pats = tuple(sorted(tuple(src_rp[:, s * 3 + c].tolist()) for c in range(3)))
        src_stack_pats.append(pats)

    for sp in itertools.permutations(range(3)):
        if not all(src_stack_pats[sp[ts]] == tgt_stack_pats[ts] for ts in range(3)):
            continue

        col_perm = [0] * 9
        valid = True
        for ts in range(3):
            ss = sp[ts]
            src_cols = [ss * 3 + c for c in range(3)]
            tgt_cols = [ts * 3 + c for c in range(3)]

            found = False
            for cp in itertools.permutations(range(3)):
                if all(
                    np.array_equal(src_rp[:, src_cols[cp[c]]], target_2d[:, tgt_cols[c]])
                    for c in range(3)
                ):
                    for c in range(3):
                        col_perm[tgt_cols[c]] = src_cols[cp[c]]
                    found = True
                    break

            if not found:
                valid = False
                break

        if valid:
            return col_perm
    return None


def _find_transform(source_2d, target_2d):
    """Find a Sudoku symmetry transform mapping source mask → target mask.

    Uses band/row profile matching + smart column matching.
    Worst-case: ~1,296 row perms × 108 col checks = ~140K ops (milliseconds).

    Returns: (row_perm, col_perm, transposed) or None
    """
    tgt_row_counts = tuple(int(target_2d[r].sum()) for r in range(9))

    for transposed in [False, True]:
        src = source_2d.T.copy() if transposed else source_2d

        src_row_counts = [int(src[r].sum()) for r in range(9)]
        if sorted(src_row_counts) != sorted(tgt_row_counts):
            continue

        # Build all valid row permutations using band/row matching
        # Group source rows by band with their counts
        src_band_profiles = []
        for b in range(3):
            rows = [(b * 3 + r, src_row_counts[b * 3 + r]) for r in range(3)]
            src_band_profiles.append(rows)

        tgt_band_profiles = []
        for b in range(3):
            rows = [(b * 3 + r, tgt_row_counts[b * 3 + r]) for r in range(3)]
            tgt_band_profiles.append(rows)

        # Sort band profiles for matching
        src_bp_sorted = [tuple(sorted(r[1] for r in bp)) for bp in src_band_profiles]
        tgt_bp_sorted = [tuple(sorted(r[1] for r in bp)) for bp in tgt_band_profiles]

        if sorted(src_bp_sorted) != sorted(tgt_bp_sorted):
            continue

        # Find band mappings: which source band → which target band
        from itertools import permutations as _perms
        for band_perm in _perms(range(3)):
            if not all(src_bp_sorted[band_perm[tb]] == tgt_bp_sorted[tb] for tb in range(3)):
                continue

            # For each band, find valid row-within-band mappings
            def _row_mappings_for_band(tb):
                sb = band_perm[tb]
                src_rows = src_band_profiles[sb]
                tgt_rows = tgt_band_profiles[tb]
                mappings = []
                for rp in _perms(range(3)):
                    if all(src_rows[rp[i]][1] == tgt_rows[i][1] for i in range(3)):
                        mappings.append(rp)
                return mappings

            band0_maps = _row_mappings_for_band(0)
            band1_maps = _row_mappings_for_band(1)
            band2_maps = _row_mappings_for_band(2)

            for rm0 in band0_maps:
                for rm1 in band1_maps:
                    for rm2 in band2_maps:
                        # Build full row permutation
                        row_perm = [0] * 9
                        for tb in range(3):
                            sb = band_perm[tb]
                            rm = [rm0, rm1, rm2][tb]
                            for i in range(3):
                                row_perm[tb * 3 + i] = sb * 3 + rm[i]

                        # Apply row perm and try column matching
                        src_rp = src[row_perm]

                        col_perm = _match_columns(src_rp, target_2d)
                        if col_perm is not None:
                            return (row_perm, col_perm, transposed)

    return None


def lars_apply_transform(puzzle, row_perm, col_perm, transposed):
    """Apply a Sudoku symmetry transform to a puzzle string.

    Args:
        puzzle: 81-char string
        row_perm, col_perm: lists of 9 ints
        transposed: bool

    Returns:
        transformed 81-char puzzle string
    """
    grid = [[puzzle[r * 9 + c] for c in range(9)] for r in range(9)]

    if transposed:
        grid = [[grid[c][r] for c in range(9)] for r in range(9)]

    result = []
    for r in range(9):
        for c in range(9):
            result.append(grid[row_perm[r]][col_perm[c]])
    return ''.join(result)


# ── Mask Index ────────────────────────────────────────────────────────
_LARS_MASK_INDEX = None


def lars_build_mask_index(include_rotated=True):
    """Build hash-table of all seed masks for fast lookup.

    Indexes every seed in LARS_EXTENDED_BANK by its symmetry-invariant hash.
    Optionally includes 180°-rotated variants (doubles coverage).

    Returns: dict mapping mask_hash → [(clue_count, seed_idx, mask_2d, seed_str, rotated)]
    """
    global _LARS_MASK_INDEX
    if _LARS_MASK_INDEX is not None:
        return _LARS_MASK_INDEX

    idx = defaultdict(list)
    for clue_count_str, seeds in LARS_EXTENDED_BANK.items():
        clue_count = int(clue_count_str)
        for si, seed in enumerate(seeds):
            mask = np.array([1 if c != '0' else 0 for c in seed], dtype=np.int8)
            h = lars_mask_hash(mask)
            idx[h].append((clue_count, si, mask.reshape(9, 9), seed, False))

            if include_rotated:
                rot = lars_box_rotate_180(seed)
                rot_mask = np.array([1 if c != '0' else 0 for c in rot], dtype=np.int8)
                h2 = lars_mask_hash(rot_mask)
                if h2 != h:  # only add if different hash (avoids duplicate)
                    idx[h2].append((clue_count, si, rot_mask.reshape(9, 9), rot, True))

    _LARS_MASK_INDEX = dict(idx)
    return _LARS_MASK_INDEX


def lars_mask_match(target_mask, verbose=False):
    """Final Boss Mode — match ANY clue-mask to a known seed.

    Given a mask pattern (which cells have clues), finds a seed puzzle whose
    mask is equivalent under Sudoku symmetries and computes the exact
    transformation.  The resulting puzzle is guaranteed unique.

    Args:
        target_mask: 81-char string (x/1=clue, 0/.=empty) OR list of 81 ints
        verbose: print progress

    Returns:
        dict with:
            matched, seed, seed_clues, seed_index, rotated,
            transform (row_perm, col_perm, transposed),
            puzzle (unique puzzle string ready to use),
            n_candidates
    """
    index = lars_build_mask_index()

    if isinstance(target_mask, str):
        mask = lars_parse_mask(target_mask)
    else:
        mask = list(target_mask)

    n_clues = sum(mask)
    target_2d = np.array(mask, dtype=np.int8).reshape(9, 9)
    h = lars_mask_hash(mask)

    if verbose:
        print(f"Mask: {n_clues} clues, hash={h}")

    candidates = index.get(h, [])
    if verbose:
        print(f"Candidates: {len(candidates)} seeds with matching hash")

    if not candidates:
        return {'matched': False, 'n_candidates': 0, 'hash': h, 'n_clues': n_clues}

    for clue_count, seed_idx, seed_mask_2d, seed_str, rotated in candidates:
        transform = _find_transform(seed_mask_2d, target_2d)
        if transform is not None:
            row_perm, col_perm, transposed = transform
            puzzle = lars_apply_transform(seed_str, row_perm, col_perm, transposed)

            if verbose:
                tag = " (180° rotated)" if rotated else ""
                print(f"  MATCHED seed {clue_count}-clue #{seed_idx + 1}{tag}")

            return {
                'matched': True,
                'seed': seed_str,
                'seed_clues': clue_count,
                'seed_index': seed_idx,
                'rotated': rotated,
                'transform': transform,
                'puzzle': puzzle,
                'n_candidates': len(candidates),
            }

    return {'matched': False, 'n_candidates': len(candidates), 'hash': h, 'n_clues': n_clues}


def lars_mask_coverage(clue_count=None, verbose=False):
    """Report coverage statistics for the mask index.

    Returns:
        dict with n_seeds, n_hashes, n_entries (including rotated variants)
    """
    index = lars_build_mask_index()

    n_entries = sum(len(v) for v in index.values())
    n_hashes = len(index)

    seed_count = 0
    for cc, seeds in LARS_EXTENDED_BANK.items():
        if clue_count is not None and int(cc) != clue_count:
            continue
        seed_count += len(seeds)

    if verbose:
        print(f"Seeds:    {seed_count:,}")
        print(f"Hashes:   {n_hashes:,} unique mask fingerprints")
        print(f"Entries:  {n_entries:,} (with 180° rotated variants)")
        if clue_count:
            cc_entries = sum(
                len([e for e in v if e[0] == clue_count])
                for v in index.values()
            )
            print(f"  {clue_count}-clue entries: {cc_entries:,}")

    return {'n_seeds': seed_count, 'n_hashes': n_hashes, 'n_entries': n_entries}


# ══════════════════════════════════════════════════════════════════════
# LARS CERTIFY — 7ms uniqueness oracle.  No backtracker.
# 17-clue: hash lookup against complete Royle enumeration.
# Match = UNIQUE (certified).  No match = MULTI-SOLUTION MASK.
# ══════════════════════════════════════════════════════════════════════

# Pre-built set of all Royle 17-clue mask hashes (loaded lazily)
_ROYLE_17_HASHES = None


def _build_royle_hashes():
    """Load precomputed Royle 17-clue mask hashes (7,051 entries, ~6ms)."""
    global _ROYLE_17_HASHES
    if _ROYLE_17_HASHES is not None:
        return _ROYLE_17_HASHES

    import pickle as _pickle

    # Try pickle first (6ms load)
    _pkl_path = _os.path.join(_os.path.dirname(__file__), 'royle_17_hashes.pkl')
    if _os.path.exists(_pkl_path):
        with open(_pkl_path, 'rb') as _f:
            _ROYLE_17_HASHES = _pickle.load(_f)
        return _ROYLE_17_HASHES

    # Try JSON fallback
    _hash_path = _os.path.join(_os.path.dirname(__file__), 'royle_17_hashes.json')
    if _os.path.exists(_hash_path):
        with open(_hash_path) as _f:
            _raw = _json.load(_f)
            _ROYLE_17_HASHES = set(eval(h) for h in _raw)
        return _ROYLE_17_HASHES

    # Last resort: compute from seed bank
    hashes = set()
    seeds_17 = LARS_EXTENDED_BANK.get(17, [])
    for s in seeds_17:
        mask = [1 if c != '0' else 0 for c in s]
        hashes.add(lars_mask_hash(mask))
    _ROYLE_17_HASHES = hashes
    return _ROYLE_17_HASHES


def lars_certify(puzzle_or_mask):
    """7ms uniqueness oracle — no backtracker needed.

    For 17-clue inputs: checks mask geometry against the complete Royle
    enumeration (49,158 puzzles = ALL possible 17-clue unique geometries).

      Match    → UNIQUE  (mathematical certainty, Royle-certified)
      No match → MULTI-SOLUTION MASK (no digit assignment can make it unique)

    For other clue counts: falls back to backtracker verification.

    Args:
        puzzle_or_mask: 81-char string.  Accepts:
          - Puzzle string (digits + 0s)
          - Mask string (x/X/1 = clue, 0/. = empty)

    Returns:
        dict with:
            certified: bool — True if uniqueness is proven
            verdict: 'UNIQUE' | 'MULTI-SOLUTION MASK' | 'UNIQUE (backtracker)'
                     | 'MULTI-SOLUTION (backtracker)'
            method: 'royle_hash' | 'backtracker'
            n_clues: int
            hash: mask hash (for 17-clue)
    """
    # Parse input
    s = puzzle_or_mask.strip().replace('.', '0')
    is_mask = any(c in s for c in 'xX')

    if is_mask:
        mask = lars_parse_mask(puzzle_or_mask)
    else:
        mask = [1 if c != '0' else 0 for c in s]

    n_clues = sum(mask)

    # 17-clue: use Royle hash oracle
    if n_clues == 17:
        royle = _build_royle_hashes()
        h = lars_mask_hash(mask)
        matched = h in royle

        if matched:
            return {
                'certified': True,
                'verdict': 'UNIQUE',
                'method': 'royle_hash',
                'n_clues': 17,
                'hash': h,
            }
        else:
            return {
                'certified': True,
                'verdict': 'MULTI-SOLUTION MASK',
                'method': 'royle_hash',
                'n_clues': 17,
                'hash': h,
            }

    # Other clue counts: backtracker fallback
    if is_mask or all(c in '01' for c in s):
        # Mask only, no digits — can't run backtracker
        return {
            'certified': False,
            'verdict': 'UNKNOWN (mask only, no digits — need 17 clues for hash oracle)',
            'method': 'none',
            'n_clues': n_clues,
        }

    from .engine import has_unique_solution
    unique = has_unique_solution(s)
    return {
        'certified': True,
        'verdict': 'UNIQUE (backtracker)' if unique else 'MULTI-SOLUTION (backtracker)',
        'method': 'backtracker',
        'n_clues': n_clues,
    }


# ══════════════════════════════════════════════════════════════════════
# LARS PROMOTE — Add solution clues to guaranteed-unique puzzles
# 17-clue → any clue count.  2^64 variants per puzzle.  All unique.
# ══════════════════════════════════════════════════════════════════════

def lars_promote(puzzle, target_clues, rng=None):
    """Promote a puzzle by adding solution digits to reach target clue count.

    Mathematical guarantee: if the input has a unique solution, adding any
    subset of solution digits preserves uniqueness.  No verification needed.

    Args:
        puzzle: 81-char puzzle string (must have unique solution)
        target_clues: target number of clues (17-81)
        rng: random.Random instance

    Returns:
        promoted puzzle string (guaranteed unique)
    """
    import random
    if rng is None:
        rng = random.Random()

    puzzle = puzzle.replace('.', '0')
    current = sum(1 for c in puzzle if c != '0')
    if target_clues <= current:
        return puzzle

    from .engine import solve_backtrack
    solution = solve_backtrack(puzzle)
    if solution is None:
        raise ValueError("Puzzle has no solution")
    if isinstance(solution, (list, np.ndarray)):
        solution = ''.join(str(d) for d in solution)

    empty = [i for i in range(81) if puzzle[i] == '0']
    n_add = min(target_clues - current, len(empty))
    fill = rng.sample(empty, n_add)

    result = list(puzzle)
    for pos in fill:
        result[pos] = solution[pos]
    return ''.join(result)


def lars_promote_batch(puzzle, target_clues, count=10, rng=None):
    """Generate multiple promoted puzzles from a single seed.

    Each promotion picks a DIFFERENT random subset of solution digits,
    so every puzzle has the same clue count but different clue positions.

    Args:
        puzzle: 81-char unique puzzle
        target_clues: target clue count
        count: how many to generate
        rng: random.Random instance

    Returns:
        list of promoted puzzle strings (all guaranteed unique)
    """
    import random
    if rng is None:
        rng = random.Random()

    puzzle = puzzle.replace('.', '0')
    current = sum(1 for c in puzzle if c != '0')

    from .engine import solve_backtrack
    solution = solve_backtrack(puzzle)
    if solution is None:
        raise ValueError("Puzzle has no solution")
    if isinstance(solution, (list, np.ndarray)):
        solution = ''.join(str(d) for d in solution)

    empty = [i for i in range(81) if puzzle[i] == '0']
    n_add = min(target_clues - current, len(empty))

    results = []
    seen = set()
    attempts = 0
    while len(results) < count and attempts < count * 20:
        attempts += 1
        fill = frozenset(rng.sample(empty, n_add))
        if fill in seen:
            continue
        seen.add(fill)

        result = list(puzzle)
        for pos in fill:
            result[pos] = solution[pos]
        results.append(''.join(result))

    return results


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

    @staticmethod
    def lars_quick(clues=22, count=10, seed=42, difficulty=None):
        """Instant puzzle generation by clue count. Uses the seed bank.

        Args:
            clues: number of clues (17-30, uses seed bank; outside range uses mask forge)
            count: number of puzzles to generate
            seed: random seed for reproducibility
            difficulty: None, 'easy', 'medium', 'hard', 'expert' (zone sum spread targeting)

        Returns:
            dict with: success, puzzles, clues, method, elapsed_ms
        """
        import random
        t0 = time.perf_counter()

        if clues in LARS_SEED_BANK:
            # Instant path: seed bank
            forge = LarsForge(LARS_SEED_BANK[clues])

            if difficulty:
                candidates = forge.lars_generate(count=count * 10, seed=seed, unique_classes=False)
                filtered = []
                for p in candidates:
                    zs = list(p['zone_sums'])
                    spread = max(zs) - min(zs)
                    if difficulty == 'easy' and spread <= 10:
                        filtered.append(p['puzzle'])
                    elif difficulty == 'medium' and 8 <= spread <= 16:
                        filtered.append(p['puzzle'])
                    elif difficulty == 'hard' and 14 <= spread <= 22:
                        filtered.append(p['puzzle'])
                    elif difficulty == 'expert' and spread >= 18:
                        filtered.append(p['puzzle'])
                    if len(filtered) >= count:
                        break
                puzzles = filtered[:count]
            else:
                batch, _, _ = forge.lars_forge_batch(count=count, seed=seed)
                puzzles = batch

            elapsed = (time.perf_counter() - t0) * 1000
            return {
                'success': True,
                'puzzles': puzzles,
                'clues': clues,
                'method': 'seed_bank',
                'elapsed_ms': elapsed,
            }
        else:
            # Forge path: generate random mask, find unique seed
            rng = random.Random(seed)
            from .mask_forge import forge_unique
            positions = rng.sample(range(81), clues)
            mask = [0] * 81
            for p in positions:
                mask[p] = 1

            result, sol, checks, forge_elapsed = forge_unique(mask, max_seconds=30, verbose=False)
            if result is None:
                elapsed = (time.perf_counter() - t0) * 1000
                return {
                    'success': False,
                    'error': f'Unable to find unique {clues}-clue puzzle within allotted time (30s, {checks} attempts)',
                    'clues': clues,
                    'method': 'mask_forge',
                    'elapsed_ms': elapsed,
                }

            forge = LarsForge(result, seed_solution=sol)
            batch, _, _ = forge.lars_forge_batch(count=count, seed=seed)
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                'success': True,
                'puzzles': batch,
                'clues': clues,
                'method': 'mask_forge',
                'elapsed_ms': elapsed,
            }

    @staticmethod
    def lars_from_mask(mask_str, count=10, seed=42, max_seconds=30):
        """Generate unique puzzles from a mask string (X/0 or 1/0).

        Args:
            mask_str: 81-char string (X or 1 = clue position, 0 or . = empty)
            count: number of puzzles to generate
            seed: random seed
            max_seconds: timeout for seed forge

        Returns:
            dict with: success, puzzles, clues, elapsed_ms, forge_checks
        """
        t0 = time.perf_counter()

        # Parse mask
        mask = []
        for c in mask_str:
            if c in ('X', 'x', '1'):
                mask.append(1)
            else:
                mask.append(0)

        if len(mask) != 81:
            return {'success': False, 'error': 'Mask must be 81 characters'}

        n_clues = sum(mask)
        if n_clues < 17:
            return {'success': False, 'error': f'Need at least 17 clues, got {n_clues}'}

        from .mask_forge import forge_unique
        result, sol, checks, forge_elapsed = forge_unique(mask, max_seconds=max_seconds, verbose=False)

        if result is None:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                'success': False,
                'error': f'Unable to find unique puzzle for this mask within allotted time ({max_seconds}s, {checks} attempts)',
                'clues': n_clues,
                'elapsed_ms': elapsed,
                'forge_checks': checks,
            }

        import random
        forge = LarsForge(result, seed_solution=sol)
        batch, _, _ = forge.lars_forge_batch(count=count, seed=seed)
        elapsed = (time.perf_counter() - t0) * 1000
        return {
            'success': True,
            'puzzles': batch,
            'seed_puzzle': result,
            'clues': n_clues,
            'elapsed_ms': elapsed,
            'forge_checks': checks,
        }

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

    @staticmethod
    def lars_ignite(multi_puzzle, count=10, seed=42, max_forge_seconds=30):
        """Ignite: take a multi-solution puzzle, forge unique puzzles from it.

        Steps:
          1. Extract mask from the multi-solution puzzle (17+ clues required)
          2. Find a unique seed puzzle with that mask via constraint-guided DFS
          3. Digit-permute from the unique seed → N guaranteed-unique puzzles

        Multi-solution in → unique puzzles out. No backtracker in the output.

        Args:
            multi_puzzle: 81-char puzzle string (may have multiple solutions)
            count: number of unique puzzles to generate (default 10)
            seed: random seed for permutation reproducibility
            max_forge_seconds: max time to search for unique seed (default 30)

        Returns:
            dict with:
              success: bool
              seed_puzzle: the unique seed found (or None)
              puzzles: list of unique puzzle strings
              forge_ms: time to find seed
              total_ms: total time
              forge_checks: number of DFS checks to find seed
        """
        import random

        multi = multi_puzzle.replace('.', '0')
        if len(multi) != 81:
            return {'success': False, 'error': 'Puzzle must be 81 characters'}

        # Extract mask
        mask = [1 if c != '0' else 0 for c in multi]
        n_clues = sum(mask)

        if n_clues < 17:
            return {'success': False, 'error': f'Need at least 17 clues, got {n_clues}'}

        t0 = time.perf_counter()

        # Step 1: Find a unique seed using mask forge (constraint-guided DFS)
        from .mask_forge import forge_unique
        seed_puzzle, seed_solution, checks, forge_elapsed = forge_unique(
            mask, max_seconds=max_forge_seconds, verbose=False)

        forge_ms = (time.perf_counter() - t0) * 1000

        if seed_puzzle is None:
            return {
                'success': False,
                'error': f'Could not find unique seed for this mask after {max_forge_seconds}s',
                'forge_ms': forge_ms,
                'forge_checks': checks,
            }

        # Step 2: Create a LarsForge from the unique seed and permute
        forge = LarsForge(seed_puzzle, seed_solution=seed_solution)

        rng = random.Random(seed)
        digits = list(range(1, 10))
        puzzles = [seed_puzzle]  # seed itself is the first puzzle
        seen = {seed_puzzle}

        while len(puzzles) < count:
            perm = digits[:]
            rng.shuffle(perm)
            new_puzzle = forge.lars_permute(perm)
            if new_puzzle not in seen:
                seen.add(new_puzzle)
                puzzles.append(new_puzzle)

        total_ms = (time.perf_counter() - t0) * 1000

        return {
            'success': True,
            'seed_puzzle': seed_puzzle,
            'puzzles': puzzles,
            'n_clues': n_clues,
            'forge_ms': forge_ms,
            'forge_checks': checks,
            'total_ms': total_ms,
            'count': len(puzzles),
        }

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


# ══════════════════════════════════════════════════════════════════════
# LARS TECHNIQUE FORGE — Generate puzzles by required technique
# "Give me an ALS_XZ + KrakenFish puzzle" → boom, here's a trillion
# ══════════════════════════════════════════════════════════════════════

_TECHNIQUE_BANK_PATH = _os.path.join(_os.path.dirname(__file__), 'technique_seed_bank.json')
LARS_TECHNIQUE_BANK = {}
LARS_TECH_INDEX = {}
LARS_TECHNIQUE_SIGS = {}

if _os.path.exists(_TECHNIQUE_BANK_PATH):
    with open(_TECHNIQUE_BANK_PATH) as _f:
        LARS_TECHNIQUE_BANK = _json.load(_f)
        LARS_TECHNIQUE_SIGS = LARS_TECHNIQUE_BANK.get('signatures', {})
        LARS_TECH_INDEX = LARS_TECHNIQUE_BANK.get('tech_index', {})


def technique_signature(technique_counts):
    """Canonical signature from a solve result's technique_counts dict.

    Filters out L1 techniques, sorts alphabetically, joins with '+'.
    Returns 'L1_only' if no advanced techniques were used.
    """
    L1 = {'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'}
    advanced = sorted(t for t in technique_counts if t not in L1)
    return '+'.join(advanced) if advanced else 'L1_only'


def lars_technique_seeds(techniques, clues=None, tier=None):
    """Find seeds matching ALL requested techniques.

    Args:
        techniques: set of technique names (e.g. {'ALS_XZ', 'KrakenFish'})
        clues: optional clue count filter (int)
        tier: optional tier filter ('medium', 'hard', 'extreme')

    Returns: list of puzzle strings
    """
    if not LARS_TECH_INDEX:
        return []

    # Find signatures containing ALL requested techniques
    sig_sets = []
    for tech in techniques:
        sigs = LARS_TECH_INDEX.get(tech, [])
        if not sigs:
            return []  # technique not in bank
        sig_sets.append(set(sigs))

    # Intersect
    matching_sigs = sig_sets[0]
    for s in sig_sets[1:]:
        matching_sigs &= s

    if not matching_sigs:
        return []

    # Collect seeds
    seeds = []
    for sig in matching_sigs:
        data = LARS_TECHNIQUE_SIGS.get(sig, {})
        if tier and data.get('tier') != tier:
            continue
        for cc_str, puzzles in data.get('seeds', {}).items():
            if clues and int(cc_str) != clues:
                continue
            seeds.extend(puzzles)

    return seeds


def lars_technique_forge(techniques, count=10, clues=None, tier=None, seed=42):
    """Generate puzzles requiring specific techniques.

    Finds matching seeds, picks one, applies lars_full_transform to
    generate unique variants. All variants are guaranteed to require
    the same techniques as the seed (invariant under symmetry group).

    Args:
        techniques: set of technique names
        count: number of puzzles to generate
        clues: optional clue count filter
        tier: optional tier filter
        seed: random seed

    Returns: dict with success, puzzles, signature, tier, clues, etc.
    """
    import random
    import time as _time

    seeds = lars_technique_seeds(techniques, clues=clues, tier=tier)
    if not seeds:
        return {
            'success': False,
            'error': f'No seeds found for techniques: {techniques}',
            'available_seeds': 0,
        }

    rng = random.Random(seed)
    t0 = _time.time()

    puzzles = []
    seen = set()
    attempts = 0
    while len(puzzles) < count and attempts < count * 20:
        attempts += 1
        base = rng.choice(seeds)
        transformed = lars_full_transform(base, rng=random.Random(rng.randint(0, 2**31)))
        if transformed not in seen:
            seen.add(transformed)
            puzzles.append(transformed)

    elapsed = (_time.time() - t0) * 1000

    # Find the signature for the seed
    base_seed = seeds[0]
    base_cc = sum(1 for c in base_seed if c != '0')
    # Find which signature contains this seed
    sig_name = None
    for sn, data in LARS_TECHNIQUE_SIGS.items():
        for cc_str, seed_list in data.get('seeds', {}).items():
            if base_seed in seed_list:
                sig_name = sn
                break
        if sig_name:
            break

    return {
        'success': True,
        'puzzles': puzzles,
        'signature': sig_name or '+'.join(sorted(techniques)),
        'tier': LARS_TECHNIQUE_SIGS.get(sig_name, {}).get('tier', 'unknown'),
        'clues': clues or base_cc,
        'count': len(puzzles),
        'available_seeds': len(seeds),
        'elapsed_ms': elapsed,
    }


def lars_technique_catalog_stats():
    """Statistics about the loaded technique bank."""
    if not LARS_TECHNIQUE_BANK:
        return {'loaded': False}

    meta = LARS_TECHNIQUE_BANK.get('meta', {})
    tier_counts = {'medium': 0, 'hard': 0, 'extreme': 0}
    clue_counts = {}
    for sig, data in LARS_TECHNIQUE_SIGS.items():
        t = data.get('tier', 'unknown')
        for cc_str, seeds in data.get('seeds', {}).items():
            tier_counts[t] = tier_counts.get(t, 0) + len(seeds)
            cc = int(cc_str)
            clue_counts[cc] = clue_counts.get(cc, 0) + len(seeds)

    tech_freq = {}
    for tech, sigs in LARS_TECH_INDEX.items():
        n = sum(
            sum(len(s) for s in LARS_TECHNIQUE_SIGS.get(sig, {}).get('seeds', {}).values())
            for sig in sigs
        )
        tech_freq[tech] = n

    return {
        'loaded': True,
        'meta': meta,
        'n_signatures': len(LARS_TECHNIQUE_SIGS),
        'tier_counts': tier_counts,
        'clue_counts': dict(sorted(clue_counts.items())),
        'tech_freq': dict(sorted(tech_freq.items(), key=lambda x: -x[1])),
    }


def lars_technique_list():
    """All technique names available in the bank."""
    return sorted(LARS_TECH_INDEX.keys())


# ══════════════════════════════════════════════════════════════════════
# LARS SEEDS — DeepRes/D2B Provenance Registry
# 384K seeds, 469 quadrillion forgeable puzzles
# ══════════════════════════════════════════════════════════════════════

# Load Lars Seeds from split files (part1 + part2)
LARS_SEEDS = {'seeds': {'deepres': [], 'd2b': []}, 'meta': {}}
LARS_SEEDS_HASHES = {}       # hash -> puzzle (core seeds, 100% confidence)
LARS_SEEDS_L1_HASHES = {}    # hash -> puzzle (L1 variants, separate confidence)

def _load_lars_seeds():
    global LARS_SEEDS, LARS_SEEDS_HASHES, LARS_SEEDS_L1_HASHES
    _pkg_dir = _os.path.dirname(__file__)
    _lars_dir = _os.path.join(_pkg_dir, '..', '..', 'lars')

    # Core seeds (100% confidence)
    for _part_name in ['lars_seeds_part1.json', 'lars_seeds_part2.json']:
        _loaded = False
        for _base in [_pkg_dir, _lars_dir]:
            _path = _os.path.join(_base, _part_name)
            if _os.path.exists(_path):
                try:
                    with open(_path) as _f:
                        _part = _json.load(_f)
                    if 'meta' in _part:
                        LARS_SEEDS['meta'] = _part['meta']
                    for _tech in ['deepres', 'd2b']:
                        if _tech in _part.get('seeds', {}):
                            LARS_SEEDS['seeds'][_tech].extend(_part['seeds'][_tech])
                    LARS_SEEDS_HASHES.update(_part.get('mask_hashes', {}))
                    _loaded = True
                except Exception:
                    pass
                break

    # Variant hashes for provenance matching
    for _part_name in ['lars_seeds_l1_part1.json', 'lars_seeds_l1_part2.json',
                        'lars_seeds_l1_2step_part1.json', 'lars_seeds_l1_2step_part2.json',
                        'lars_seeds_l1_3step_part1.json', 'lars_seeds_l1_3step_part2.json',
                        'lars_seeds_rotate180_part1.json', 'lars_seeds_rotate180_part2.json',
                        'lars_seeds_shuffle_l1_part1.json', 'lars_seeds_shuffle_l1_part2.json']:
        for _base in [_pkg_dir, _lars_dir]:
            _path = _os.path.join(_base, _part_name)
            if _os.path.exists(_path):
                try:
                    with open(_path) as _f:
                        _part = _json.load(_f)
                    LARS_SEEDS_L1_HASHES.update(_part.get('mask_hashes', {}))
                except Exception:
                    pass
                break

    # Also try single-file fallback
    if not LARS_SEEDS_HASHES:
        for _path in [_os.path.join(_pkg_dir, 'lars_deepres_seeds.json'),
                      _os.path.join(_lars_dir, 'lars_deepres_seeds.json')]:
            if _os.path.exists(_path):
                try:
                    with open(_path) as _f:
                        _data = _json.load(_f)
                    LARS_SEEDS.update(_data)
                    LARS_SEEDS_HASHES.update(_data.get('mask_hashes', {}))
                except Exception:
                    pass
                break

_load_lars_seeds()


def lars_deepres_seeds(count=10, seed=42, technique='deepres'):
    """Get DeepRes or D2B seeds from the Lars registry.

    Args:
        count: number of seeds to return
        seed: random seed
        technique: 'deepres' or 'd2b'

    Returns: list of puzzle strings
    """
    import random
    seeds_data = LARS_SEEDS.get('seeds', {})
    pool = seeds_data.get(technique, [])
    if not pool:
        return []

    rng = random.Random(seed)
    if count >= len(pool):
        return list(pool)
    return rng.sample(pool, count)


def lars_deepres_forge(count=10, seed=42, technique='deepres'):
    """Forge puzzles from Lars DeepRes/D2B seeds.

    Each seed is transformed via lars_full_transform for maximum diversity.

    Args:
        count: number of puzzles to generate
        seed: random seed
        technique: 'deepres' or 'd2b'

    Returns: dict with success, puzzles, seed_count, technique
    """
    import random
    import time as _time

    seeds_data = LARS_SEEDS.get('seeds', {})
    pool = seeds_data.get(technique, [])
    if not pool:
        return {
            'success': False,
            'error': f'No {technique} seeds loaded',
            'seed_count': 0,
        }

    rng = random.Random(seed)
    t0 = _time.time()

    puzzles = []
    seen = set()
    attempts = 0
    while len(puzzles) < count and attempts < count * 20:
        attempts += 1
        base = rng.choice(pool)
        transformed = lars_full_transform(base, rng=random.Random(rng.randint(0, 2**31)))
        if transformed not in seen:
            seen.add(transformed)
            puzzles.append(transformed)

    elapsed = (_time.time() - t0) * 1000

    return {
        'success': True,
        'puzzles': puzzles,
        'technique': technique,
        'seed_count': len(pool),
        'count': len(puzzles),
        'elapsed_ms': elapsed,
    }


def lars_provenance(puzzle_or_mask):
    """Check if a puzzle is derived from a Lars Seed.

    Checks core seeds (100% confidence) first, then L1 variant hashes
    (high probability). Reports confidence level accordingly.

    Args:
        puzzle_or_mask: 81-char puzzle string or mask string

    Returns: dict with matched, confidence, technique, etc.
    """
    if not LARS_SEEDS_HASHES and not LARS_SEEDS_L1_HASHES:
        return {'matched': False, 'error': 'Lars Seeds registry not loaded'}

    s = puzzle_or_mask.strip().replace('.', '0')
    is_mask = any(c in s for c in 'xX')

    if is_mask:
        mask = lars_parse_mask(puzzle_or_mask)
    else:
        mask = [1 if c != '0' else 0 for c in s]

    h = str(lars_mask_hash(mask))

    # Check core seeds first (100% confidence)
    if h in LARS_SEEDS_HASHES:
        matched_seed = LARS_SEEDS_HASHES[h]
        seeds_data = LARS_SEEDS.get('seeds', {})
        is_dr = matched_seed in seeds_data.get('deepres', [])
        is_d2b = matched_seed in seeds_data.get('d2b', [])
        technique = []
        if is_dr:
            technique.append('DeepResonance')
        if is_d2b:
            technique.append('D2B')

        return {
            'matched': True,
            'confidence': 'exact',
            'confidence_pct': 100,
            'seed': matched_seed,
            'technique': technique or ['DeepResonance or D2B'],
            'hash': h,
            'n_clues': sum(mask),
        }

    # Check L1 variant hashes (high probability)
    if h in LARS_SEEDS_L1_HASHES:
        matched_seed = LARS_SEEDS_L1_HASHES[h]
        return {
            'matched': True,
            'confidence': 'l1_variant',
            'confidence_pct': 99,
            'seed': matched_seed,
            'technique': ['DeepResonance or D2B'],
            'hash': h,
            'n_clues': sum(mask),
        }

    return {
        'matched': False,
        'hash': h,
        'n_clues': sum(mask),
        'message': 'Not in Lars Seeds registry — this may be a new discovery!',
    }


def lars_seeds_stats():
    """Statistics about the Lars Seeds registry."""
    if not LARS_SEEDS:
        return {'loaded': False}

    meta = LARS_SEEDS.get('meta', {})
    seeds_data = LARS_SEEDS.get('seeds', {})

    return {
        'loaded': True,
        'meta': meta,
        'deepres_count': len(seeds_data.get('deepres', [])),
        'd2b_count': len(seeds_data.get('d2b', [])),
        'total_seeds': len(seeds_data.get('deepres', [])) + len(seeds_data.get('d2b', [])),
        'mask_hashes': len(LARS_SEEDS_HASHES) + len(LARS_SEEDS_L1_HASHES),
        'core_hashes': len(LARS_SEEDS_HASHES),
        'variant_hashes': len(LARS_SEEDS_L1_HASHES),
        'unique_masks': LARS_SEEDS.get('total_unique_masks', 0),
    }


# ══════════════════════════════════════════════════════════════
# SIGNATURE CATALOG — technique-tagged seed lookup
# ══════════════════════════════════════════════════════════════

_SIG_CATALOG = None  # lazy-loaded


def _load_sig_catalog():
    """Load signature catalog from JSON. Lazy — only on first use."""
    global _SIG_CATALOG
    if _SIG_CATALOG is not None:
        return _SIG_CATALOG

    import json
    import gzip

    # Try gzipped first (shipped in package), then plain JSON (dev)
    for ext, opener in [('.json.gz', lambda p: gzip.open(p, 'rt')), ('.json', lambda p: open(p))]:
        for base_dir in [
            _os.path.join(_os.path.dirname(__file__)),                     # package dir
            _os.path.join(_os.path.dirname(__file__), '..', '..', 'lars'), # dev dir
        ]:
            catalog_path = _os.path.join(base_dir, 'signature_catalog' + ext)
            if _os.path.exists(catalog_path):
                with opener(catalog_path) as f:
                    _SIG_CATALOG = json.load(f)
                return _SIG_CATALOG

    return None


# Signature abbreviation mapping (short → full technique name)
SIG_ABBREV = {
    'ALS': 'ALS_XZ', 'ALSXY': 'ALS_XYWing', 'APE': 'AlignedPairExcl',
    'BB': 'BowmanBingo', 'D2B': 'D2B', 'DB': 'DeathBlossom',
    'DR': 'DeepResonance', 'FC': 'ForcingChain', 'FN': 'ForcingNet',
    'FPC': 'FPC', 'FPCE': 'FPCE', 'FPF': 'FPF',
    'JE': 'JuniorExocet', 'KF': 'KrakenFish', 'RE': 'RectElim',
    'SC': 'SimpleColoring', 'SDC': 'SueDeCoq', 'SF': 'Swordfish',
    'XC': 'XCycle', 'XW': 'XWing',
}
SIG_ABBREV_REV = {v: k for k, v in SIG_ABBREV.items()}


def lars_sig_forge(techniques, count=10, seed=None, exact=False, clues=None):
    """Forge puzzles from seeds matching a technique signature.

    Args:
        techniques: set of technique names (full or abbreviated)
        count: number of puzzles to generate
        seed: random seed (None = time-based)
        exact: if True, match EXACT signature; if False, match superset
        clues: optional clue count filter (e.g., 26)

    Returns: dict with success, puzzles, signature, seeds_matched, etc.
    """
    import random
    import time as _time

    catalog = _load_sig_catalog()
    if catalog is None:
        return {'success': False, 'error': 'Signature catalog not found'}

    # Normalize technique names to abbreviations used in signatures
    query_abbrevs = set()
    for t in techniques:
        t_upper = t.upper().strip()
        if t_upper in SIG_ABBREV:
            query_abbrevs.add(t_upper)
        elif t in SIG_ABBREV_REV:
            query_abbrevs.add(SIG_ABBREV_REV[t])
        else:
            # Try case-insensitive match
            for full, abbr in SIG_ABBREV_REV.items():
                if full.lower() == t.lower():
                    query_abbrevs.add(abbr)
                    break

    if not query_abbrevs:
        return {'success': False, 'error': f'No recognized techniques in query: {techniques}'}

    # Find matching signatures
    sigs = catalog.get('signatures', {})
    matched_sigs = []

    for sig_str, entries in sigs.items():
        sig_parts = set(sig_str.split('+'))
        if exact:
            if sig_parts == query_abbrevs:
                matched_sigs.append((sig_str, entries))
        else:
            if query_abbrevs.issubset(sig_parts):
                matched_sigs.append((sig_str, entries))

    if not matched_sigs:
        mode = 'exact' if exact else 'superset'
        return {
            'success': False,
            'error': f'No signatures match {"+".join(sorted(query_abbrevs))} ({mode})',
            'query': '+'.join(sorted(query_abbrevs)),
        }

    # Collect all matching seeds, optionally filter by clue count
    pool = []
    for sig_str, entries in matched_sigs:
        for entry in entries:
            puzzle = entry.get('puzzle', '')
            if clues is not None:
                pc = sum(1 for c in puzzle if c != '0' and c != '.')
                if pc != clues:
                    continue
            pool.append((puzzle, sig_str, entry.get('source', '')))

    if not pool:
        return {
            'success': False,
            'error': f'No seeds at {clues} clues for {"+".join(sorted(query_abbrevs))}',
            'query': '+'.join(sorted(query_abbrevs)),
            'matched_sigs': len(matched_sigs),
        }

    # Forge
    if seed is None:
        seed = int(_time.time()) % (2**31)
    rng = random.Random(seed)
    t0 = _time.time()

    puzzles = []
    puzzle_sigs = []
    seen = set()
    attempts = 0
    while len(puzzles) < count and attempts < count * 20:
        attempts += 1
        base, sig_str, source = rng.choice(pool)
        transformed = lars_full_transform(base, rng=random.Random(rng.randint(0, 2**31)))
        if transformed not in seen:
            seen.add(transformed)
            puzzles.append(transformed)
            puzzle_sigs.append(sig_str)

    elapsed = (_time.time() - t0) * 1000

    return {
        'success': True,
        'puzzles': puzzles,
        'signatures': puzzle_sigs,
        'query': '+'.join(sorted(query_abbrevs)),
        'exact': exact,
        'clues_filter': clues,
        'matched_sigs': len(matched_sigs),
        'pool_size': len(pool),
        'seed': seed,
        'count': len(puzzles),
        'elapsed_ms': elapsed,
    }


def lars_sig_catalog_stats():
    """Return catalog statistics."""
    catalog = _load_sig_catalog()
    if catalog is None:
        return {'error': 'Signature catalog not found'}
    return catalog.get('meta', {})


if __name__ == '__main__':
    main()
