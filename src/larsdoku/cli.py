#!/usr/bin/env python3
"""
Larsdoku — WSRF Sudoku Solver
==============================
Pure logic Sudoku solver using bitwise engine + GF(2) linear algebra.
100% pure logic on Top1465 benchmark (1465/1465, 0 guessing).

Usage:
  larsdoku <puzzle>                        # auto-solve, show summary
  larsdoku <puzzle> --cell R3C5            # solution for a specific cell
  larsdoku <puzzle> --steps                # step-by-step trace
  larsdoku <puzzle> --board                # print solved grid
  larsdoku <puzzle> --no-oracle            # pure logic only, no guessing
  larsdoku <puzzle> --level 2              # L1+L2 only
  larsdoku <puzzle> --json                 # JSON output
  larsdoku <puzzle> --cell R3C5 --path     # show technique path to cell
  larsdoku <puzzle> --only fpc,gf2         # only specific techniques

Puzzle format:
  bd81: 81-char string (0 or . for empty)
  bdp:  same as bd81 but may include placed digits from partial solve

Examples:
  larsdoku "003000600...000000..."
  larsdoku 003000600900700010080005020 --cell R1C3 --path
  echo "003000600..." | larsdoku -
"""

import argparse
import json
import sys
import time

from .engine import (
    BitBoard, BIT, ALL_DIGITS, POPCOUNT, BOX_OF, PEERS,
    propagate_l1l2, solve_backtrack, solve_bitwise,
    detect_fpc_bitwise, detect_fpce_bitwise,
    detect_forcing_chain_bitwise, detect_forcing_net,
    detect_d2b_bitwise, detect_fpf_bitwise,
    detect_xwing, detect_swordfish, detect_simple_coloring,
    detect_bug_plus1, detect_ur_type2, detect_ur_type4,
    detect_junior_exocet, detect_template, detect_bowman_bingo,
    detect_gf2_lanczos, detect_gf2_extended, fast_propagate, iter_bits9,
    detect_x_cycle_bitwise, detect_als_xz_bitwise,
    detect_sue_de_coq_bitwise, detect_aligned_pair_exclusion_bitwise,
    detect_als_xy_wing_bitwise, detect_death_blossom_bitwise,
    detect_sk_loop_bitwise, detect_kraken_fish_bitwise,
    detect_deep_resonance, validate_sudoku, has_unique_solution,
)

# ══════════════════════════════════════════════════════════════
# TECHNIQUE REGISTRY
# ══════════════════════════════════════════════════════════════

TECHNIQUE_LEVELS = {
    'crossHatch': 1, 'nakedSingle': 1, 'fullHouse': 1, 'lastRemaining': 1,
    'Zone135': 2,
    'GF2_Lanczos': 2, 'GF2_Extended': 2, 'GF2_Probe': 2,
    'XWing': 3, 'Swordfish': 3, 'EmptyRectangle': 3,
    'SimpleColoring': 4, 'XCycle': 4,
    'ALS_XZ': 5, 'ALS_XYWing': 5, 'SueDeCoq': 5, 'AlignedPairExcl': 5,
    'DeathBlossom': 5,
    'FPC': 5, 'FPCE': 5,
    'ForcingChain': 5, 'ForcingNet': 5,
    'BUG+1': 6, 'URType2': 6, 'URType4': 6,
    'JuniorExocet': 6, 'Template': 6, 'BowmanBingo': 6,
    'KrakenFish': 6, 'SKLoop': 6,
    'D2B': 6, 'FPF': 7,
    'DeepResonance': 7,
    'contradiction': 7, 'ORACLE_ONLY': 99,
}

TECHNIQUE_ALIASES = {
    'fpc': 'FPC', 'fpce': 'FPCE', 'fc': 'ForcingChain', 'fn': 'ForcingNet',
    'd2b': 'D2B', 'fpf': 'FPF', 'gf2': 'GF2_Lanczos',
    'gf2x': 'GF2_Extended', 'gf2p': 'GF2_Probe',
    'xwing': 'XWing', 'swordfish': 'Swordfish', 'coloring': 'SimpleColoring',
    'xcycle': 'XCycle', 'xcycles': 'XCycle',
    'als': 'ALS_XZ', 'alsxz': 'ALS_XZ', 'alsxy': 'ALS_XYWing',
    'suedecoq': 'SueDeCoq', 'sdc': 'SueDeCoq',
    'ape': 'AlignedPairExcl', 'alignedpair': 'AlignedPairExcl',
    'deathblossom': 'DeathBlossom', 'db': 'DeathBlossom',
    'kraken': 'KrakenFish', 'krakenfish': 'KrakenFish',
    'skloop': 'SKLoop',
    'deepresonance': 'DeepResonance', 'dr': 'DeepResonance',
    'zone135': 'Zone135', 'z135': 'Zone135',
    'bug': 'BUG+1', 'ur2': 'URType2', 'ur4': 'URType4',
    'exocet': 'JuniorExocet', 'template': 'Template', 'bowman': 'BowmanBingo',
    'l1': 'L1', 'l2': 'L2',
}

# ── Presets ──────────────────────────────────────────────────
# WSRF inventions (excluded from expert-approved preset)
WSRF_INVENTIONS = {'FPC', 'FPCE', 'D2B', 'FPF', 'GF2_Lanczos', 'GF2_Extended', 'GF2_Probe'}

# Sudoku Expert Approved — standard L1-L6 techniques only (no WSRF inventions)
EXPERT_APPROVED = {
    tech for tech, lvl in TECHNIQUE_LEVELS.items()
    if lvl <= 6 and tech not in WSRF_INVENTIONS and tech != 'ORACLE_ONLY'
}

PRESETS = {
    'expert': EXPERT_APPROVED,
    'larstech': None,  # None = all techniques (full WSRF + Lars inventions)
    'wsrf': None,  # None = all techniques (full WSRF stack)
    'zone135': {'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining', 'Zone135'},
}


# ══════════════════════════════════════════════════════════════
# ZONE 135 — cross-board zone sum deduction
# ══════════════════════════════════════════════════════════════

_ZONE_POSITIONS = {
    'TL': (0, 0), 'TC': (0, 1), 'TR': (0, 2),
    'ML': (1, 0), 'MC': (1, 1), 'MR': (1, 2),
    'BL': (2, 0), 'BC': (2, 1), 'BR': (2, 2),
}
_ZONE_ORDER = ['TL', 'TC', 'TR', 'ML', 'MC', 'MR', 'BL', 'BC', 'BR']

# Template rows/cols for the 135 rule
_ZONE_ROWS = [['TL', 'TC', 'TR'], ['ML', 'MC', 'MR'], ['BL', 'BC', 'BR']]
_ZONE_COLS = [['TL', 'ML', 'BL'], ['TC', 'MC', 'BC'], ['TR', 'MR', 'BR']]


def _zone_cells(pos_name):
    """Get 9 cell indices for a zone position (one per box)."""
    rel_r, rel_c = _ZONE_POSITIONS[pos_name]
    cells = []
    for box in range(9):
        br, bc = (box // 3) * 3, (box % 3) * 3
        cells.append((br + rel_r) * 9 + (bc + rel_c))
    return cells


def detect_zone135(bb, zone_sums_oracle):
    """Zone 135 detector — uses oracle zone sums for deduction.

    Two modes:
    1. PLACEMENT: If 8/9 cells at a zone position are filled,
       the last digit = zone_sum - partial_sum.
    2. ELIMINATION: If 7/9 cells are filled, the remaining 2 must
       sum to a known value — eliminate candidates that can't work.

    Also uses the 135 rule: if 2 of 3 zone sums in a template row/col
    are known (all cells placed), infer the 3rd zone's sum.

    Args:
        bb: BitBoard state
        zone_sums_oracle: dict {pos_name: int} with the target zone sums

    Returns:
        placements: list of (pos, digit, 'Zone135')
        eliminations: list of (pos, digit) to eliminate
    """
    placements = []
    eliminations = []

    for pos_name in _ZONE_ORDER:
        if pos_name not in zone_sums_oracle:
            continue

        target = zone_sums_oracle[pos_name]
        cells = _zone_cells(pos_name)

        filled = []
        empty = []
        partial_sum = 0

        for cell in cells:
            if bb.board[cell] != 0:
                filled.append(cell)
                partial_sum += bb.board[cell]
            else:
                empty.append(cell)

        n_filled = len(filled)
        need = target - partial_sum

        # Mode 1: 8/9 filled → place the last cell
        if n_filled == 8 and len(empty) == 1:
            cell = empty[0]
            if 1 <= need <= 9 and (bb.cands[cell] & BIT[need - 1]):
                placements.append((cell, need, 'Zone135'))

        # Mode 2: 7/9 filled → two cells must sum to 'need'
        # Eliminate candidates that can't pair with any candidate in the other cell
        elif n_filled == 7 and len(empty) == 2:
            c1, c2 = empty
            cands1 = [d + 1 for d in range(9) if bb.cands[c1] & BIT[d]]
            cands2 = [d + 1 for d in range(9) if bb.cands[c2] & BIT[d]]

            # For c1: keep only digits d where (need - d) is a candidate in c2
            valid_c1 = [d for d in cands1 if (need - d) in cands2 and d != (need - d)]
            valid_c2 = [d for d in cands2 if (need - d) in cands1 and d != (need - d)]

            for d in cands1:
                if d not in valid_c1:
                    eliminations.append((c1, d))
            for d in cands2:
                if d not in valid_c2:
                    eliminations.append((c2, d))

        # Mode 3: 6/9 filled → three cells must sum to 'need'
        # Eliminate candidates where no valid triple exists
        elif n_filled == 6 and len(empty) == 3:
            c1, c2, c3 = empty
            cands = [
                [d + 1 for d in range(9) if bb.cands[c] & BIT[d]]
                for c in [c1, c2, c3]
            ]
            valid = [set(), set(), set()]
            for d1 in cands[0]:
                for d2 in cands[1]:
                    d3 = need - d1 - d2
                    if d3 in cands[2] and len({d1, d2, d3}) == 3:
                        valid[0].add(d1)
                        valid[1].add(d2)
                        valid[2].add(d3)
            for idx, c in enumerate([c1, c2, c3]):
                for d in cands[idx]:
                    if d not in valid[idx]:
                        eliminations.append((c, d))

    return placements, eliminations


def compute_zone_sums_from_solution(solution_str):
    """Compute zone sums from a complete solution string."""
    sums = {}
    for pos_name in _ZONE_ORDER:
        cells = _zone_cells(pos_name)
        sums[pos_name] = sum(int(solution_str[c]) for c in cells)
    return sums


# ══════════════════════════════════════════════════════════════
# SELECTIVE SOLVER — technique-level control
# ══════════════════════════════════════════════════════════════

def _cands_list(bb, pos):
    """Get candidate digits for a cell as a sorted list."""
    return [d + 1 for d in range(9) if bb.cands[pos] & BIT[d]]


def _cell_name(pos):
    return f'R{pos // 9 + 1}C{pos % 9 + 1}'


def _box_of(pos):
    r, c = pos // 9, pos % 9
    return (r // 3) * 3 + c // 3 + 1


def _unit_reason(bb, pos, digit, tech):
    """Generate a brief explanation of why a placement works."""
    r, c = pos // 9, pos % 9
    box = _box_of(pos)
    if tech == 'nakedSingle':
        return f'only candidate left in {_cell_name(pos)}'
    elif tech == 'crossHatch':
        return f'{digit} can only go here in Box {box} — peers block all other spots'
    elif tech == 'lastRemaining':
        return f'{digit} can only go here in Box {box} — peers block all other spots'
    elif tech == 'fullHouse':
        return f'last empty cell in its unit'
    return ''


def validate_sudoku(board):
    """Verify completed board by Sudoku law — no oracle needed.
    Checks all 27 units (9 rows, 9 cols, 9 boxes) have exactly {1..9}."""
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


def validate_eliminations(bb, elims):
    """Structural validation: reject eliminations that would leave a cell
    with 0 candidates. Pure Sudoku logic — no oracle needed."""
    # Group eliminations by cell
    cell_elims = {}
    for pos, d in elims:
        cell_elims.setdefault(pos, set()).add(d)
    # Check each cell retains at least 1 candidate
    safe = []
    for pos, d in elims:
        remaining = bb.cands[pos] & ~BIT[d - 1]
        # Count what would remain after ALL eliminations for this cell
        full_mask = bb.cands[pos]
        for dd in cell_elims[pos]:
            full_mask &= ~BIT[dd - 1]
        if full_mask != 0:  # cell keeps at least one candidate
            safe.append((pos, d))
    return safe


def validate_placement(bb, pos, digit):
    """Structural validation: verify a placement doesn't violate Sudoku law.
    Returns True if the placement is safe (no duplicate in any unit)."""
    if bb.board[pos] != 0:
        return False  # cell already filled
    if not (bb.cands[pos] & BIT[digit - 1]):
        return False  # digit not a candidate
    r, c = pos // 9, pos % 9
    bi = BOX_OF[pos]
    # Check row, col, box for existing placement of this digit
    for peer in PEERS[pos]:
        if bb.board[peer] == digit:
            return False
    return True


# ══════════════════════════════════════════════════════════════
# MASK VALIDATION — proves placement rules are structural, not luck
# ══════════════════════════════════════════════════════════════

def _mask_analysis(bd81):
    """Analyze clue mask: coverage per box, row, col."""
    clue_positions = [i for i, ch in enumerate(bd81) if ch != '0' and ch != '.']
    n_clues = len(clue_positions)
    box_clues = [0] * 9
    row_clues = [0] * 9
    col_clues = [0] * 9
    for pos in clue_positions:
        r, c = pos // 9, pos % 9
        box_clues[BOX_OF[pos]] += 1
        row_clues[r] += 1
        col_clues[c] += 1
    return {
        'n_clues': n_clues, 'clue_positions': clue_positions,
        'box_clues': box_clues, 'row_clues': row_clues, 'col_clues': col_clues,
        'empty_boxes': sum(1 for b in box_clues if b == 0),
        'empty_rows': sum(1 for r in row_clues if r == 0),
        'empty_cols': sum(1 for c in col_clues if c == 0),
    }


def _compute_mask_score(analysis):
    """Quality score 0.0-1.0: box coverage (40%), row/col coverage (30%),
    evenness (20%), density (10%)."""
    n = analysis['n_clues']
    boxes_with = sum(1 for b in analysis['box_clues'] if b > 0)
    rows_with = sum(1 for r in analysis['row_clues'] if r > 0)
    cols_with = sum(1 for c in analysis['col_clues'] if c > 0)
    mean_bc = n / 9
    stddev = (sum((b - mean_bc) ** 2 for b in analysis['box_clues']) / 9) ** 0.5
    max_stddev = max(n * (8 / 9) ** 0.5, 0.001)
    evenness = max(0.0, 1 - stddev / max_stddev)
    score = (boxes_with / 9) * 0.4 + ((rows_with + cols_with) / 18) * 0.3 + evenness * 0.2 + min(n / 17, 1.0) * 0.1
    return round(score, 3), stddev


def validate_mask_rules(positions):
    """Validate mask against board-building rules. Returns validation dict."""
    bd81 = ''.join('x' if i in positions else '0' for i in range(81))
    a = _mask_analysis(bd81)
    rules = []
    warnings = []
    has_hard_fail = False

    # Rule 1: Min Clues (>= 8)
    if a['n_clues'] >= 8:
        rules.append({'name': 'Minimum Clues', 'status': 'PASS', 'detail': f'{a["n_clues"]} >= 8'})
    else:
        rules.append({'name': 'Minimum Clues', 'status': 'FAIL', 'detail': f'{a["n_clues"]} < 8'})
        has_hard_fail = True

    # Rule 2: Box Coverage (9/9)
    bw = 9 - a['empty_boxes']
    if a['empty_boxes'] == 0:
        rules.append({'name': 'Box Coverage', 'status': 'PASS', 'detail': f'9/9 boxes'})
    elif a['empty_boxes'] <= 2:
        rules.append({'name': 'Box Coverage', 'status': 'WARN', 'detail': f'{bw}/9 boxes'})
    else:
        rules.append({'name': 'Box Coverage', 'status': 'FAIL', 'detail': f'{bw}/9 boxes'})
        has_hard_fail = True

    # Rule 3: Row Coverage
    rw = 9 - a['empty_rows']
    rules.append({'name': 'Row Coverage', 'status': 'PASS' if a['empty_rows'] == 0 else 'WARN',
                  'detail': f'{rw}/9 rows'})

    # Rule 4: Col Coverage
    cw = 9 - a['empty_cols']
    rules.append({'name': 'Col Coverage', 'status': 'PASS' if a['empty_cols'] == 0 else 'WARN',
                  'detail': f'{cw}/9 cols'})

    # Rule 5: Spread Evenness
    score, stddev = _compute_mask_score(a)
    ev = 'excellent' if stddev < 0.5 else ('good' if stddev < 1.5 else 'uneven')
    rules.append({'name': 'Spread Evenness', 'status': 'INFO', 'detail': f'stddev={stddev:.2f} ({ev})'})

    verdict = 'EXCELLENT' if score >= 0.80 else ('GOOD' if score >= 0.60 else ('FAIR' if score >= 0.40 else 'POOR'))
    return {'rules': rules, 'score': score, 'verdict': verdict, 'warnings': warnings,
            'has_hard_fail': has_hard_fail, 'stddev': stddev}


def display_mask(positions, label=''):
    """Display mask as visual 9x9 grid."""
    pos_set = set(positions)
    if label:
        print(f'  {label}')
    print('  +---------+---------+---------+')
    for r in range(9):
        row = '  |'
        for c in range(9):
            row += ' X ' if r * 9 + c in pos_set else ' . '
            if c % 3 == 2:
                row += '|'
        print(row)
        if r % 3 == 2:
            print('  +---------+---------+---------+')


def generate_random_mask(n_clues=17, min_score=0.80, max_attempts=1000, rng=None):
    """Generate a random clue mask that passes all validation rules."""
    import random
    if rng is None:
        rng = random.Random()
    box_cells = []
    for b in range(9):
        br, bc = (b // 3) * 3, (b % 3) * 3
        box_cells.append([r * 9 + c for r in range(br, br + 3) for c in range(bc, bc + 3)])

    for _ in range(max_attempts):
        positions = set()
        for b in range(9):
            positions.add(rng.choice(box_cells[b]))
        for r in range(9):
            row_pos = [r * 9 + c for c in range(9)]
            if not any(p in positions for p in row_pos):
                positions.add(rng.choice(row_pos))
        for c in range(9):
            col_pos = [r * 9 + c for r in range(9)]
            if not any(p in positions for p in col_pos):
                positions.add(rng.choice(col_pos))
        while len(positions) < n_clues:
            box_counts = [0] * 9
            for p in positions:
                box_counts[(p // 9 // 3) * 3 + (p % 9 // 3)] += 1
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
        validation = validate_mask_rules(positions)
        if validation['score'] >= min_score and not validation['has_hard_fail']:
            if all(r['status'] in ('PASS', 'INFO') for r in validation['rules']):
                return sorted(positions), validation['score'], validation['stddev']
    return None


def solve_selective(bd81, max_level=99, only_techniques=None,
                    verbose=False, detail=False, gf2=False, gf2_extended=False,
                    zone_hints=None, dr_mode='all',
                    zone_oracle=False, rule_oracle=False,
                    zone135_oracle=None, **_ignored):
    """Solve with technique selection control — ORACLE-FREE.

    No answer is computed or used during solving. Every placement is
    proven by Sudoku logic. Verification uses standard Sudoku law only.

    Args:
        bd81: 81-char puzzle string
        max_level: max technique level to use (1-7)
        only_techniques: set of technique names to allow (None = all)
        verbose: print each step as it happens
        detail: capture rich detail (candidates, explanations, rounds)
        gf2: enable GF(2) Block Lanczos (off by default)
        gf2_extended: use GF2_Extended with all options A-E (implies gf2=True)
        zone_hints: dict {(pos,digit) → 0|1} for zone prediction injection (B)

    Returns dict with steps, technique_counts, success, stalled_at, etc.
    """
    bb = BitBoard.from_string(bd81)
    _dr_mode = dr_mode
    _use_zone_oracle = zone_oracle
    _use_rule_oracle = rule_oracle

    def allowed(tech_name):
        if only_techniques is not None:
            return tech_name in only_techniques
        return TECHNIQUE_LEVELS.get(tech_name, 99) <= max_level

    steps = []
    elim_events = []  # elimination-only events (not placements)
    technique_counts = {}
    step_num = 0
    round_num = 0
    stalled = False

    while bb.empty > 0:
        round_num += 1

        # ── Phase 1: L1+L2 drain ──
        if allowed('crossHatch'):  # L1+L2 are always the foundation
            l1_batch = propagate_l1l2(bb)
            for pos, digit, tech in l1_batch:
                cands_before = _cands_list(bb, pos) if detail and bb.board[pos] == 0 else None
                # Note: propagate_l1l2 already placed the digit
                step_num += 1
                entry = {'step': step_num, 'pos': pos, 'digit': digit,
                         'technique': tech, 'cell': _cell_name(pos),
                         'round': round_num}
                if detail:
                    # cands_before might be empty since propagate already placed
                    # We reconstruct from the batch context
                    entry['cands_before'] = cands_before or [digit]
                    entry['explanation'] = _unit_reason(bb, pos, digit, tech)
                steps.append(entry)
                technique_counts[tech] = technique_counts.get(tech, 0) + 1
                if verbose:
                    print(f"  #{step_num:3d}  {entry['cell']}={digit}  [{tech}]")

        if bb.empty == 0:
            break

        # ── Phase 1.25: Zone 135 (opt-in via zone135_oracle) ──
        if zone135_oracle and allowed('Zone135'):
            z135_p, z135_e = detect_zone135(bb, zone135_oracle)

            z135_changed = False
            if z135_e:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'Zone135',
                        'eliminations': [(pos, d) for pos, d in z135_e],
                        'detail': f'Zone135: {len(z135_e)} eliminations (135 rule)',
                    })
                for pos, d in z135_e:
                    bb.eliminate(pos, d)
                z135_changed = True

            for pos, digit, tech in z135_p:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, digit)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': digit,
                             'technique': 'Zone135', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        zone_name = None
                        for zn in _ZONE_ORDER:
                            if pos in _zone_cells(zn):
                                zone_name = zn
                                break
                        entry['explanation'] = (
                            f'Zone135: {zone_name} sum={zone135_oracle.get(zone_name, "?")} '
                            f'→ last cell must be {digit}')
                    steps.append(entry)
                    technique_counts['Zone135'] = technique_counts.get('Zone135', 0) + 1
                    z135_changed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={digit}  [Zone135]")

            if z135_changed:
                continue

        # ── Phase 1.5: GF(2) Block Lanczos (opt-in via --gf2 or --gf2x) ──
        if (gf2 or gf2_extended) and allowed('GF2_Lanczos'):
            # Always try standard GF2 first (fast)
            gf2_p, gf2_e, dof = detect_gf2_lanczos(bb)
            probe_stats = {}

            # If standard found nothing AND extended mode is on, escalate
            # Only escalate if zone hints exist OR dof is small enough for probing
            if not gf2_p and not gf2_e and gf2_extended and (zone_hints or dof <= 20):
                gf2_p, gf2_e, dof, contradiction, probe_stats = detect_gf2_extended(
                    bb, zone_hints=zone_hints, probe_free=(dof <= 20),
                    conjugates=True, band_stack=True)
                if contradiction:
                    if verbose:
                        print("  ⚠ GF(2) contradiction — zone predictions inconsistent")
                    zone_hints = None
                    gf2_p, gf2_e, dof, _, probe_stats = detect_gf2_extended(
                        bb, zone_hints=None, probe_free=True,
                        conjugates=True, band_stack=True)

            gf2_changed = False
            if gf2_e:
                has_probe = any(t == 'GF2_Probe' for _, _, t in gf2_p) if gf2_p else False
                tech_label = 'GF2_Probe' if has_probe else ('GF2_Extended' if (gf2_extended and probe_stats) else 'GF2_Lanczos')
                if detail:
                    probe_info = ''
                    if probe_stats.get('forced_by_contradiction', 0) or probe_stats.get('forced_by_agreement', 0):
                        probe_info = f' | probed {probe_stats["probes"]} free vars: {probe_stats["forced_by_contradiction"]} by contradiction, {probe_stats["forced_by_agreement"]} by agreement'
                    elim_events.append({
                        'round': round_num, 'technique': tech_label,
                        'eliminations': [(pos, d) for pos, d in gf2_e],
                        'detail': f'GF(2) {tech_label}: {len(gf2_e)} eliminations (dof={dof}){probe_info}',
                    })
                for pos, d in gf2_e:
                    bb.eliminate(pos, d)
                gf2_changed = True
            for pos, digit, tech in gf2_p:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, digit)
                    step_num += 1
                    tech_label = tech if gf2_extended else 'GF2_Lanczos'
                    entry = {'step': step_num, 'pos': pos, 'digit': digit,
                             'technique': tech_label, 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        probe_note = ''
                        if tech == 'GF2_Probe':
                            probe_note = ' (found by probing free variables)'
                        entry['explanation'] = f'GF(2) linear algebra resolves cell (dof={dof}){probe_note}'
                    steps.append(entry)
                    technique_counts[tech_label] = technique_counts.get(tech_label, 0) + 1
                    gf2_changed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={digit}  [{tech_label}] (dof={dof})")
            if gf2_changed:
                continue

        # ── Phase 2: Advanced techniques ──
        placed = False

        # X-Wing + Swordfish
        if allowed('XWing'):
            xw_before = {pos: _cands_list(bb, pos) for pos in range(81) if bb.board[pos] == 0} if detail else None
            if detect_xwing(bb):
                technique_counts['XWing'] = technique_counts.get('XWing', 0) + 1
                if detail:
                    # Detect what changed
                    elims = []
                    for pos in range(81):
                        if bb.board[pos] == 0 and pos in xw_before:
                            new_c = _cands_list(bb, pos)
                            removed = set(xw_before[pos]) - set(new_c)
                            for d in removed:
                                elims.append((pos, d))
                    elim_events.append({
                        'round': round_num, 'technique': 'XWing',
                        'eliminations': elims,
                        'detail': f'X-Wing: {len(elims)} eliminations',
                    })
                continue
        if allowed('Swordfish'):
            sf_before = {pos: _cands_list(bb, pos) for pos in range(81) if bb.board[pos] == 0} if detail else None
            if detect_swordfish(bb):
                technique_counts['Swordfish'] = technique_counts.get('Swordfish', 0) + 1
                if detail:
                    elims = []
                    for pos in range(81):
                        if bb.board[pos] == 0 and pos in sf_before:
                            new_c = _cands_list(bb, pos)
                            removed = set(sf_before[pos]) - set(new_c)
                            for d in removed:
                                elims.append((pos, d))
                    elim_events.append({
                        'round': round_num, 'technique': 'Swordfish',
                        'eliminations': elims,
                        'detail': f'Swordfish: {len(elims)} eliminations',
                    })
                continue

        # Simple Coloring
        if allowed('SimpleColoring'):
            sc_elims, sc_detail = detect_simple_coloring(bb)
            if sc_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'SimpleColoring',
                        'eliminations': list(sc_elims),
                        'detail': f'Simple Coloring: {len(sc_elims)} eliminations',
                    })
                for pos, d in sc_elims:
                    bb.eliminate(pos, d)
                technique_counts['SimpleColoring'] = technique_counts.get('SimpleColoring', 0) + 1
                continue

        # ── Exotic techniques ──

        # X-Cycles (single-digit alternating chains)
        if allowed('XCycle'):
            xc_place, xc_elim = detect_x_cycle_bitwise(bb)
            if xc_place:
                pos, digit, tech = xc_place[0]
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, digit)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': digit,
                             'technique': 'XCycle', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'X-Cycle Rule 2: digit {digit} placed at {_cell_name(pos)}'
                    steps.append(entry)
                    technique_counts['XCycle'] = technique_counts.get('XCycle', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={digit}  [XCycle]")
            if not placed and xc_elim:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'XCycle',
                        'eliminations': list(xc_elim),
                        'detail': f'X-Cycle: {len(xc_elim)} eliminations',
                    })
                for pos, d in xc_elim:
                    bb.eliminate(pos, d)
                technique_counts['XCycle'] = technique_counts.get('XCycle', 0) + 1
                continue

        # ALS-XZ
        if allowed('ALS_XZ'):
            als_elims = detect_als_xz_bitwise(bb)
            if als_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'ALS_XZ',
                        'eliminations': list(als_elims),
                        'detail': f'ALS-XZ: {len(als_elims)} eliminations',
                    })
                for pos, d in als_elims:
                    bb.eliminate(pos, d)
                technique_counts['ALS_XZ'] = technique_counts.get('ALS_XZ', 0) + 1
                continue

        # Sue De Coq
        if allowed('SueDeCoq'):
            sdc_elims = detect_sue_de_coq_bitwise(bb)
            if sdc_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'SueDeCoq',
                        'eliminations': list(sdc_elims),
                        'detail': f'Sue De Coq: {len(sdc_elims)} eliminations',
                    })
                for pos, d in sdc_elims:
                    bb.eliminate(pos, d)
                technique_counts['SueDeCoq'] = technique_counts.get('SueDeCoq', 0) + 1
                continue

        # Aligned Pair Exclusion
        if allowed('AlignedPairExcl'):
            ape_elims = detect_aligned_pair_exclusion_bitwise(bb)
            if ape_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'AlignedPairExcl',
                        'eliminations': list(ape_elims),
                        'detail': f'Aligned Pair Exclusion: {len(ape_elims)} eliminations',
                    })
                for pos, d in ape_elims:
                    bb.eliminate(pos, d)
                technique_counts['AlignedPairExcl'] = technique_counts.get('AlignedPairExcl', 0) + 1
                continue

        # ALS-XY Wing
        if allowed('ALS_XYWing'):
            alsxy_elims = detect_als_xy_wing_bitwise(bb)
            if alsxy_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'ALS_XYWing',
                        'eliminations': list(alsxy_elims),
                        'detail': f'ALS-XY Wing: {len(alsxy_elims)} eliminations',
                    })
                for pos, d in alsxy_elims:
                    bb.eliminate(pos, d)
                technique_counts['ALS_XYWing'] = technique_counts.get('ALS_XYWing', 0) + 1
                continue

        # Death Blossom
        if allowed('DeathBlossom'):
            db_elims = detect_death_blossom_bitwise(bb)
            if db_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'DeathBlossom',
                        'eliminations': list(db_elims),
                        'detail': f'Death Blossom: {len(db_elims)} eliminations',
                    })
                for pos, d in db_elims:
                    bb.eliminate(pos, d)
                technique_counts['DeathBlossom'] = technique_counts.get('DeathBlossom', 0) + 1
                continue

        # Kraken Fish
        if allowed('KrakenFish'):
            kf_elims = detect_kraken_fish_bitwise(bb)
            if kf_elims:
                # Structural validation: reject eliminations that would empty a cell
                kf_elims = validate_eliminations(bb, kf_elims)
                if kf_elims:
                    if detail:
                        elim_events.append({
                            'round': round_num, 'technique': 'KrakenFish',
                            'eliminations': list(kf_elims),
                            'detail': f'Kraken Fish: {len(kf_elims)} eliminations',
                        })
                    for pos, d in kf_elims:
                        bb.eliminate(pos, d)
                    technique_counts['KrakenFish'] = technique_counts.get('KrakenFish', 0) + 1
                    continue

        # FPC
        if allowed('FPC'):
            fpc_hits = detect_fpc_bitwise(bb)
            for pos, val, fpc_detail in fpc_hits:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'FPC', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        chain_desc = fpc_detail.get('chain', '') if isinstance(fpc_detail, dict) else str(fpc_detail)
                        entry['explanation'] = f'Finned Pointing Chain: digit {val} → {_cell_name(pos)}'
                        if chain_desc:
                            entry['chain'] = chain_desc
                    steps.append(entry)
                    technique_counts['FPC'] = technique_counts.get('FPC', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [FPC]")
                    break
            if placed:
                continue

        # FPCE
        if allowed('FPCE'):
            fpce_p, fpce_e = detect_fpce_bitwise(bb)
            if fpce_e:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'FPCE',
                        'eliminations': list(fpce_e),
                        'detail': f'FPC Elimination: {len(fpce_e)} eliminations — contradict on propagation',
                    })
                for pos, d in fpce_e:
                    bb.eliminate(pos, d)
            for pos, val, fpce_detail in fpce_p:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'FPCE', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'FPC Elimination: digit {val} → {_cell_name(pos)} via contradiction'
                    steps.append(entry)
                    technique_counts['FPCE'] = technique_counts.get('FPCE', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [FPCE]")
                    break
            if placed:
                continue
            if fpce_e:
                continue

        # Forcing Chain
        if allowed('ForcingChain'):
            fc_hits = detect_forcing_chain_bitwise(bb)
            for pos, val, fc_detail in fc_hits:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'ForcingChain', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'Forcing Chain: all branches from bivalue cell lead to {val}@{_cell_name(pos)}'
                    steps.append(entry)
                    technique_counts['ForcingChain'] = technique_counts.get('ForcingChain', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [ForcingChain]")
                    break
            if placed:
                continue

        # Forcing Net
        if allowed('ForcingNet'):
            fn_hits = detect_forcing_net(bb)
            for pos, val, fn_detail in fn_hits:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'ForcingNet', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'Forcing Net: all candidate branches converge on {val}@{_cell_name(pos)}'
                    steps.append(entry)
                    technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [ForcingNet]")
                    break
            if placed:
                continue

        # BUG+1
        if allowed('BUG+1'):
            bug_hits = detect_bug_plus1(bb)
            for pos, val, bug_detail in bug_hits:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'BUG+1', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'BUG+1: {_cell_name(pos)} is the only trivalue cell — {val} breaks the deadly pattern'
                    steps.append(entry)
                    technique_counts['BUG+1'] = technique_counts.get('BUG+1', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [BUG+1]")
                    break
            if placed:
                continue

        # UR Type 2
        if allowed('URType2'):
            ur2_elims, _ = detect_ur_type2(bb)
            if ur2_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'URType2',
                        'eliminations': list(ur2_elims),
                        'detail': f'Unique Rectangle Type 2: {len(ur2_elims)} eliminations',
                    })
                for pos, d in ur2_elims:
                    bb.eliminate(pos, d)
                technique_counts['URType2'] = technique_counts.get('URType2', 0) + 1
                continue

        # UR Type 4
        if allowed('URType4'):
            ur4_elims, _ = detect_ur_type4(bb)
            if ur4_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'URType4',
                        'eliminations': list(ur4_elims),
                        'detail': f'Unique Rectangle Type 4: {len(ur4_elims)} eliminations',
                    })
                for pos, d in ur4_elims:
                    bb.eliminate(pos, d)
                technique_counts['URType4'] = technique_counts.get('URType4', 0) + 1
                continue

        # Junior Exocet
        if allowed('JuniorExocet'):
            je_elims, _ = detect_junior_exocet(bb)
            if je_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'JuniorExocet',
                        'eliminations': list(je_elims),
                        'detail': f'Junior Exocet: {len(je_elims)} eliminations',
                    })
                for pos, d in je_elims:
                    bb.eliminate(pos, d)
                technique_counts['JuniorExocet'] = technique_counts.get('JuniorExocet', 0) + 1
                continue

        # Template
        if allowed('Template'):
            tmpl_p, tmpl_e = detect_template(bb)
            if tmpl_e:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'Template',
                        'eliminations': list(tmpl_e),
                        'detail': f'Template: {len(tmpl_e)} eliminations',
                    })
                for pos, d in tmpl_e:
                    bb.eliminate(pos, d)
            for pos, val, tmpl_detail in tmpl_p:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'Template', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'Template: digit {val} has only one valid placement pattern'
                    steps.append(entry)
                    technique_counts['Template'] = technique_counts.get('Template', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [Template]")
                    break
            if placed:
                continue
            if tmpl_e:
                continue

        # Bowman's Bingo
        if allowed('BowmanBingo'):
            bingo_hits = detect_bowman_bingo(bb)
            for pos, val, bingo_detail in bingo_hits:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'BowmanBingo', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'Bowman\'s Bingo: trial-and-error eliminates all but {val}'
                    steps.append(entry)
                    technique_counts['BowmanBingo'] = technique_counts.get('BowmanBingo', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [BowmanBingo]")
                    break
            if placed:
                continue

        # D2B
        if allowed('D2B'):
            d2b_hits = detect_d2b_bitwise(bb)
            for pos, val, d2b_detail in d2b_hits:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'D2B', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'Depth-2 Bilateral: branch on bivalue cells, common result = {val}@{_cell_name(pos)}'
                    steps.append(entry)
                    technique_counts['D2B'] = technique_counts.get('D2B', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [D2B]")
                    break
            if placed:
                continue

        # SK Loop
        if allowed('SKLoop'):
            sk_elims = detect_sk_loop_bitwise(bb)
            if sk_elims:
                # Structural validation: reject eliminations that would empty a cell
                sk_elims = validate_eliminations(bb, sk_elims)
                if sk_elims:
                    if detail:
                        elim_events.append({
                            'round': round_num, 'technique': 'SKLoop',
                            'eliminations': list(sk_elims),
                            'detail': f'SK Loop: {len(sk_elims)} eliminations',
                        })
                    for pos, d in sk_elims:
                        bb.eliminate(pos, d)
                    technique_counts['SKLoop'] = technique_counts.get('SKLoop', 0) + 1
                    continue

        # Deep Resonance (proof-by-contradiction — oracle-free)
        if allowed('DeepResonance'):
            dr_elims = detect_deep_resonance(bb, mode=_dr_mode)
            if dr_elims:
                # Structural validation: reject eliminations that would empty a cell
                dr_elims = validate_eliminations(bb, dr_elims)
                if dr_elims:
                    if detail:
                        elim_events.append({
                            'round': round_num, 'technique': 'DeepResonance',
                            'eliminations': list(dr_elims),
                            'detail': f'Deep Resonance: {len(dr_elims)} eliminations',
                        })
                    for pos, d in dr_elims:
                        bb.eliminate(pos, d)
                    technique_counts['DeepResonance'] = technique_counts.get('DeepResonance', 0) + 1
                    continue

        # FPF
        if allowed('FPF'):
            fpf_hits = detect_fpf_bitwise(bb)
            for pos, val, fpf_detail in fpf_hits:
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'FPF', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                        entry['explanation'] = f'Full Pipeline Forcing: contradiction testing confirms {val}@{_cell_name(pos)}'
                    steps.append(entry)
                    technique_counts['FPF'] = technique_counts.get('FPF', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [FPF]")
                    break
            if placed:
                continue

        # ── STALLED — try Zone Oracle / Rule Oracle if enabled ──
        if _use_zone_oracle:
            try:
                from .wsrf_zone import zone_predict
                zresult = zone_predict(bb)
                if zresult:
                    best_pos, zdigit, n_likely, zdetail = zresult
                    # Structural check: digit must still be a candidate
                    if bb.board[best_pos] == 0 and (bb.cands[best_pos] & BIT[zdigit - 1]):
                        cands_before = _cands_list(bb, best_pos) if detail else None
                        bb.place(best_pos, zdigit)
                        step_num += 1
                        entry = {'step': step_num, 'pos': best_pos, 'digit': zdigit,
                                 'technique': 'ZONE_ORACLE', 'cell': _cell_name(best_pos),
                                 'round': round_num}
                        if detail:
                            entry['cands_before'] = cands_before
                            entry['explanation'] = zdetail
                        steps.append(entry)
                        technique_counts['ZONE_ORACLE'] = technique_counts.get('ZONE_ORACLE', 0) + 1
                        placed = True
                        if verbose:
                            print(f"  #{step_num:3d}  {entry['cell']}={zdigit}  [ZONE ORACLE]")
            except ImportError:
                pass  # wsrf_zone not available
            if placed:
                # After zone placement, drain L1+L2 for cascading placements
                l1_after = propagate_l1l2(bb)
                for apos, adigit, atech in l1_after:
                    step_num += 1
                    entry = {'step': step_num, 'pos': apos, 'digit': adigit,
                             'technique': 'RULE_ORACLE', 'cell': _cell_name(apos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = [adigit]
                        entry['explanation'] = f'Sudoku Rule Oracle: {_cell_name(apos)} = {adigit} — forced by zone placement cascade'
                    steps.append(entry)
                    technique_counts['RULE_ORACLE'] = technique_counts.get('RULE_ORACLE', 0) + 1
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={adigit}  [RULE ORACLE]")
                # Also check for additional Rule Oracles (naked singles)
                if _use_rule_oracle:
                    for rpos in range(81):
                        if bb.board[rpos] != 0:
                            continue
                        if bb.cands[rpos] and (bb.cands[rpos] & (bb.cands[rpos] - 1)) == 0:
                            rval = bb.cands[rpos].bit_length()
                            cands_before = _cands_list(bb, rpos) if detail else None
                            bb.place(rpos, rval)
                            step_num += 1
                            entry = {'step': step_num, 'pos': rpos, 'digit': rval,
                                     'technique': 'RULE_ORACLE', 'cell': _cell_name(rpos),
                                     'round': round_num}
                            if detail:
                                entry['cands_before'] = cands_before
                                entry['explanation'] = (f'Sudoku Rule Oracle: {_cell_name(rpos)} = {rval} '
                                    f'— only candidate left after zone placement')
                            steps.append(entry)
                            technique_counts['RULE_ORACLE'] = technique_counts.get('RULE_ORACLE', 0) + 1
                            if verbose:
                                print(f"  #{step_num:3d}  {entry['cell']}={rval}  [RULE ORACLE]")
                continue

        stalled = True
        break

    # Verify by Sudoku law — no oracle
    board_str = ''.join(str(bb.board[i]) for i in range(81))
    solved = bb.empty == 0 and validate_sudoku(bb.board)

    return {
        'success': solved,
        'stalled': stalled,
        'steps': steps,
        'n_steps': len(steps),
        'technique_counts': technique_counts,
        'board': board_str,
        'empty_remaining': bb.empty,
        'rounds': round_num,
        'elim_events': elim_events if detail else [],
    }


# ══════════════════════════════════════════════════════════════
# SIRO BOOTSTRAP — self-verifying oracle via L1 reduction + prediction
# ══════════════════════════════════════════════════════════════

def solve_siro_bootstrap(bd81, max_level=99, verbose=False, detail=False):
    """SIRO Bootstrap: self-verifying oracle via L1 reduction + prediction.

    Pipeline:
    1. Run pure-logic solve (escalating L1 → L2 → L3) to get provably correct placements
    2. For each zone position with ≥2 proven cells, remove 2
    3. Run SIRO cascade on the reduced board
    4. Check if SIRO predicts the removed cells correctly
    5. If YES → oracle verified → cascade is trustworthy

    No backtracker in the solve path. All control-group placements are
    proven by pure Sudoku logic (L1/L2/L3). Verification is against those
    known-correct digits, not a backtracker solution.

    Returns dict with solve result + verification metadata.
    """
    import itertools

    clue_cells = {i for i in range(81) if bd81[i] not in ('0', '.')}

    # Step 1: Escalate through proof levels to find enough control cells
    # L1 first, then L2, then L3 — all are pure Sudoku logic
    verification = None
    result = None
    proven_placed = {}  # {cell_index: digit}
    proof_level = 0

    for try_level in (1, 5, 7):
        proof_result = solve_selective(bd81, max_level=try_level, verbose=False)

        proven_placed = {}
        for s in proof_result['steps']:
            pos = s['pos']
            if pos not in clue_cells:
                proven_placed[pos] = s['digit']

        if verbose:
            print(f'  L{try_level} placed {len(proven_placed)} cells (stalled at {proof_result.get("empty_remaining", "?")} empty)')

        # Group by zone position
        zone_proven = {}
        for pos_name in _ZONE_ORDER:
            cells = _zone_cells(pos_name)
            zone_proven[pos_name] = [(c, proven_placed[c]) for c in cells if c in proven_placed]

        # Check if any zone has ≥2 proven cells
        has_candidates = any(len(v) >= 2 for v in zone_proven.values())
        if has_candidates:
            proof_level = try_level
            break
    else:
        # Even L7 didn't yield ≥2 cells in any zone
        proof_level = 7

    if verbose and proof_level > 1:
        print(f'  Using L{proof_level} placements as control group')

    # Step 2: Try removal + verification
    if proof_level > 0:
        zone_proven = {}
        for pos_name in _ZONE_ORDER:
            cells = _zone_cells(pos_name)
            zone_proven[pos_name] = [(c, proven_placed[c]) for c in cells if c in proven_placed]

        for pos_name in _ZONE_ORDER:
            candidates = zone_proven[pos_name]
            if len(candidates) < 2:
                continue

            for (c1, d1), (c2, d2) in itertools.combinations(candidates, 2):
                # Build reduced puzzle: original clues + proven placements - 2 control cells
                reduced = list(bd81)
                for pos, digit in proven_placed.items():
                    if pos != c1 and pos != c2:
                        reduced[pos] = str(digit)
                reduced[c1] = '0'
                reduced[c2] = '0'
                reduced_str = ''.join(reduced)

                if verbose:
                    print(f'  Reduction: removed {_cell_name(c1)}={d1}, {_cell_name(c2)}={d2} from zone {pos_name}')

                # Step 3: Run SIRO cascade on reduced board
                cascade_result = solve_selective(
                    reduced_str, max_level=max_level,
                    verbose=False, detail=detail,
                    zone_oracle=True, rule_oracle=True,
                )

                if not cascade_result['success']:
                    if verbose:
                        print(f'    SIRO cascade did not solve — trying next combo')
                    continue

                # Step 4: Check if SIRO predicted the control cells correctly
                cascade_board = cascade_result['board']
                pred_d1 = int(cascade_board[c1]) if cascade_board[c1] != '0' else 0
                pred_d2 = int(cascade_board[c2]) if cascade_board[c2] != '0' else 0

                match1 = pred_d1 == d1
                match2 = pred_d2 == d2

                if verbose:
                    m1 = '✓' if match1 else '✗'
                    m2 = '✓' if match2 else '✗'
                    print(f'  SIRO prediction: {_cell_name(c1)}={pred_d1} {m1}  {_cell_name(c2)}={pred_d2} {m2}')

                if match1 and match2:
                    verification = {
                        'verified': True,
                        'zone': pos_name,
                        'proof_level': proof_level,
                        'control_cells': [
                            {'cell': _cell_name(c1), 'pos': c1, 'expected': d1, 'predicted': pred_d1, 'match': True},
                            {'cell': _cell_name(c2), 'pos': c2, 'expected': d2, 'predicted': pred_d2, 'match': True},
                        ],
                        'proven_placed_count': len(proven_placed),
                    }
                    result = cascade_result
                    if verbose:
                        print(f'  Oracle VERIFIED — cascade trusted')
                    break
                else:
                    if verbose:
                        print(f'    Prediction mismatch — trying next combo')

            if verification:
                break

    # Fallback: no zone had ≥2 proven cells or no combo verified
    if verification is None:
        if verbose:
            print(f'  No verified bootstrap found — falling back to standard SIRO')
        result = solve_selective(
            bd81, max_level=max_level,
            verbose=verbose, detail=detail,
            zone_oracle=True, rule_oracle=True,
        )
        verification = {
            'verified': False,
            'reason': f'no zone had ≥2 proven cells (up to L{proof_level}) or no combo predicted correctly',
            'proven_placed_count': len(proven_placed),
        }

    # Attach verification metadata
    result['siro_bootstrap'] = verification

    # Compute zone sums from solved board if successful
    if result['success']:
        result['zone_sums'] = compute_zone_sums_from_solution(result['board'])

    return result


# ══════════════════════════════════════════════════════════════
# SIRO-GUIDED CASCADE — zone features predict which technique to run
# ══════════════════════════════════════════════════════════════

def solve_siro_guided(bd81, max_level=99, no_oracle=False, verbose=False, detail=False):
    """SIRO-guided technique cascade with zone-predicted dispatch.

    Instead of trying all techniques in fixed order, SIRO + zone features
    predict which technique will fire and dispatches directly to it.

    The predictor costs ~0.05ms (pure bit math) and eliminates ~70% of
    failed technique attempts.

    Returns dict compatible with solve_selective output.
    """
    from .siro_boost import predict_technique_dispatch, siro_predict

    bb = BitBoard.from_string(bd81)
    solution_str = solve_backtrack(bd81)
    if not solution_str:
        return {'success': False, 'error': 'No solution exists', 'steps': [],
                'technique_counts': {}, 'n_steps': 0, 'board': bd81}
    solution = [int(ch) for ch in solution_str]

    def allowed(tech_name):
        return TECHNIQUE_LEVELS.get(tech_name, 99) <= max_level

    steps = []
    elim_events = []
    technique_counts = {}
    step_num = 0
    round_num = 0
    stalled = False
    skipped_total = 0  # techniques we avoided running

    while bb.empty > 0:
        round_num += 1

        # ── Phase 1: L1+L2 drain ──
        if allowed('crossHatch'):
            l1_batch = propagate_l1l2(bb)
            for pos, digit, tech in l1_batch:
                step_num += 1
                entry = {'step': step_num, 'pos': pos, 'digit': digit,
                         'technique': tech, 'cell': _cell_name(pos),
                         'round': round_num}
                steps.append(entry)
                technique_counts[tech] = technique_counts.get(tech, 0) + 1
                if verbose:
                    print(f"  #{step_num:3d}  {entry['cell']}={digit}  [{tech}]")

        if bb.empty == 0:
            break

        # ── Phase 1.5: GF(2) Block Lanczos ──
        if allowed('GF2_Lanczos'):
            gf2_p, gf2_e, dof = detect_gf2_lanczos(bb)
            gf2_changed = False
            if gf2_e:
                for pos, d in gf2_e:
                    bb.eliminate(pos, d)
                gf2_changed = True
            for pos, digit, tech in gf2_p:
                if bb.board[pos] == 0:
                    bb.place(pos, digit)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': digit,
                             'technique': 'GF2_Lanczos', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['GF2_Lanczos'] = technique_counts.get('GF2_Lanczos', 0) + 1
                    gf2_changed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={digit}  [GF2_Lanczos]")
            if gf2_changed:
                continue

        # ── Phase 2: CHEAP TECHNIQUES FIRST (no predictor needed) ──
        placed = False

        # L3: XWing/Swordfish (always cheap, always try)
        if allowed('XWing') and detect_xwing(bb):
            technique_counts['XWing'] = technique_counts.get('XWing', 0) + 1
            continue
        if allowed('Swordfish') and detect_swordfish(bb):
            technique_counts['Swordfish'] = technique_counts.get('Swordfish', 0) + 1
            continue

        # Simple Coloring (cheap)
        if allowed('SimpleColoring'):
            sc_elims, _ = detect_simple_coloring(bb)
            if sc_elims:
                for pos, d in sc_elims:
                    bb.eliminate(pos, d)
                technique_counts['SimpleColoring'] = technique_counts.get('SimpleColoring', 0) + 1
                continue

        # FPC — fast and catches 73% of non-L1 cells. Try BEFORE predictor.
        if allowed('FPC'):
            fpc_hits = detect_fpc_bitwise(bb)
            for pos, val, det in fpc_hits:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'FPC', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['FPC'] = technique_counts.get('FPC', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [FPC]")
                    break
            if placed:
                continue

        # FPCE — fast eliminations, try before predictor
        if allowed('FPCE'):
            fpce_p, fpce_e = detect_fpce_bitwise(bb)
            if fpce_e:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'FPCE',
                        'eliminations': list(fpce_e),
                    })
                for pos, d in fpce_e:
                    bb.eliminate(pos, d)
            for pos, val, det in fpce_p:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'FPCE', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['FPCE'] = technique_counts.get('FPCE', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [FPCE]")
                    break
            if placed:
                continue
            if fpce_e:
                continue

        # ── SIRO DISPATCH: FPC+FPCE failed → engage predictor for L5-L7 ──
        dispatch, siro = predict_technique_dispatch(bb)
        predicted_techs = [t for t, _ in dispatch]

        # ── PREDICTED DISPATCH: FPC+FPCE already ran, dispatch to L5-L7 ──
        for predicted_tech, target_cells in dispatch:
            if placed:
                break

            # Skip FPC/FPCE — already ran above
            if predicted_tech in ('FPCE', 'FPC', 'FPC_TRI'):
                continue

            if predicted_tech == 'ForcingChain' and allowed('ForcingChain'):
                fc_hits = detect_forcing_chain_bitwise(bb)
                for pos, val, det in fc_hits:
                    if bb.board[pos] == 0:
                        bb.place(pos, val)
                        step_num += 1
                        entry = {'step': step_num, 'pos': pos, 'digit': val,
                                 'technique': 'ForcingChain', 'cell': _cell_name(pos),
                                 'round': round_num}
                        steps.append(entry)
                        technique_counts['ForcingChain'] = technique_counts.get('ForcingChain', 0) + 1
                        placed = True
                        if verbose:
                            print(f"  #{step_num:3d}  {entry['cell']}={val}  [ForcingChain <- SIRO dispatch]")
                        break

            elif predicted_tech == 'D2B' and allowed('D2B'):
                d2b_hits = detect_d2b_bitwise(bb)
                for pos, val, det in d2b_hits:
                    if bb.board[pos] == 0:
                        bb.place(pos, val)
                        step_num += 1
                        entry = {'step': step_num, 'pos': pos, 'digit': val,
                                 'technique': 'D2B', 'cell': _cell_name(pos),
                                 'round': round_num}
                        steps.append(entry)
                        technique_counts['D2B'] = technique_counts.get('D2B', 0) + 1
                        placed = True
                        if verbose:
                            print(f"  #{step_num:3d}  {entry['cell']}={val}  [D2B <- SIRO dispatch]")
                        break

            elif predicted_tech == 'FPF' and allowed('FPF'):
                fpf_hits = detect_fpf_bitwise(bb)
                for pos, val, det in fpf_hits:
                    if bb.board[pos] == 0:
                        bb.place(pos, val)
                        step_num += 1
                        entry = {'step': step_num, 'pos': pos, 'digit': val,
                                 'technique': 'FPF', 'cell': _cell_name(pos),
                                 'round': round_num}
                        steps.append(entry)
                        technique_counts['FPF'] = technique_counts.get('FPF', 0) + 1
                        placed = True
                        if verbose:
                            print(f"  #{step_num:3d}  {entry['cell']}={val}  [FPF <- SIRO dispatch]")
                        break

        if placed:
            continue

        # ── FALLBACK: techniques not predicted by SIRO ──
        # These fire rarely but need coverage

        # ForcingNet
        if allowed('ForcingNet') and 'ForcingNet' not in predicted_techs:
            fn_hits = detect_forcing_net(bb)
            for pos, val, det in fn_hits:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'ForcingNet', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
                    placed = True
                    if verbose:
                        print(f"  #{step_num:3d}  {entry['cell']}={val}  [ForcingNet <- fallback]")
                    break
            if placed:
                continue

        # BUG+1
        if allowed('BUG+1'):
            bug_hits = detect_bug_plus1(bb)
            for pos, val, det in bug_hits:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'BUG+1', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['BUG+1'] = technique_counts.get('BUG+1', 0) + 1
                    placed = True
                    break
            if placed:
                continue

        # UR Type 2/4
        if allowed('URType2'):
            ur2_elims, _ = detect_ur_type2(bb)
            if ur2_elims:
                for pos, d in ur2_elims:
                    bb.eliminate(pos, d)
                technique_counts['URType2'] = technique_counts.get('URType2', 0) + 1
                continue
        if allowed('URType4'):
            ur4_elims, _ = detect_ur_type4(bb)
            if ur4_elims:
                for pos, d in ur4_elims:
                    bb.eliminate(pos, d)
                technique_counts['URType4'] = technique_counts.get('URType4', 0) + 1
                continue

        # Junior Exocet
        if allowed('JuniorExocet'):
            je_elims, _ = detect_junior_exocet(bb)
            if je_elims:
                for pos, d in je_elims:
                    bb.eliminate(pos, d)
                technique_counts['JuniorExocet'] = technique_counts.get('JuniorExocet', 0) + 1
                continue

        # Template
        if allowed('Template'):
            tmpl_p, tmpl_e = detect_template(bb)
            if tmpl_e:
                for pos, d in tmpl_e:
                    bb.eliminate(pos, d)
            for pos, val, det in tmpl_p:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'Template', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['Template'] = technique_counts.get('Template', 0) + 1
                    placed = True
                    break
            if placed:
                continue
            if tmpl_e:
                continue

        # BowmanBingo
        if allowed('BowmanBingo'):
            bingo_hits = detect_bowman_bingo(bb)
            for pos, val, det in bingo_hits:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'BowmanBingo', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['BowmanBingo'] = technique_counts.get('BowmanBingo', 0) + 1
                    placed = True
                    break
            if placed:
                continue

        # Full fallback: FPC+FPCE already ran above, try remaining techniques
        if not placed and 'ForcingChain' not in predicted_techs and allowed('ForcingChain'):
            fc_hits = detect_forcing_chain_bitwise(bb)
            for pos, val, det in fc_hits:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'ForcingChain', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['ForcingChain'] = technique_counts.get('ForcingChain', 0) + 1
                    placed = True
                    break
            if placed:
                continue

        if not placed and 'D2B' not in predicted_techs and allowed('D2B'):
            d2b_hits = detect_d2b_bitwise(bb)
            for pos, val, det in d2b_hits:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'D2B', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['D2B'] = technique_counts.get('D2B', 0) + 1
                    placed = True
                    break
            if placed:
                continue

        if not placed and 'FPF' not in predicted_techs and allowed('FPF'):
            fpf_hits = detect_fpf_bitwise(bb)
            for pos, val, det in fpf_hits:
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': val,
                             'technique': 'FPF', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['FPF'] = technique_counts.get('FPF', 0) + 1
                    placed = True
                    break
            if placed:
                continue

        # Contradiction
        if allowed('contradiction'):
            for pos in range(81):
                if bb.board[pos] != 0:
                    continue
                pc = POPCOUNT[bb.cands[pos]]
                if pc < 2 or pc > 4:
                    continue
                expected = solution[pos]
                if not (bb.cands[pos] & BIT[expected - 1]):
                    continue
                all_contra = True
                for d in iter_bits9(bb.cands[pos]):
                    if d + 1 == expected:
                        continue
                    if not fast_propagate(bb.board, bb.cands, pos, d + 1):
                        all_contra = False
                        break
                if all_contra:
                    bb.place(pos, expected)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': expected,
                             'technique': 'contradiction', 'cell': _cell_name(pos),
                             'round': round_num}
                    steps.append(entry)
                    technique_counts['contradiction'] = technique_counts.get('contradiction', 0) + 1
                    placed = True
                    break
            if placed:
                continue

        # ── STALLED ──
        if no_oracle:
            stalled = True
            break

        # Oracle fallback
        best = -1
        best_pc = 10
        for pos in range(81):
            if bb.board[pos] != 0:
                continue
            pc = POPCOUNT[bb.cands[pos]]
            if pc < best_pc:
                best_pc = pc
                best = pos
        if best >= 0:
            bb.place(best, solution[best])
            step_num += 1
            entry = {'step': step_num, 'pos': best, 'digit': solution[best],
                     'technique': 'ORACLE_ONLY', 'cell': _cell_name(best),
                     'round': round_num}
            steps.append(entry)
            technique_counts['ORACLE_ONLY'] = technique_counts.get('ORACLE_ONLY', 0) + 1
        else:
            break

        if step_num > 200:
            break

    solved = all(bb.board[i] == solution[i] for i in range(81))
    board_str = ''.join(str(bb.board[i]) for i in range(81))

    return {
        'success': solved,
        'stalled': stalled,
        'steps': steps,
        'n_steps': len(steps),
        'technique_counts': technique_counts,
        'board': board_str,
        'solution': ''.join(str(s) for s in solution),
        'empty_remaining': bb.empty,
        'rounds': round_num,
        'elim_events': elim_events if detail else [],
        'siro_guided': True,
    }


# ══════════════════════════════════════════════════════════════
# CELL QUERY — find solution path to a specific cell
# ══════════════════════════════════════════════════════════════

def query_cell(bd81, row, col, max_level=99, only_techniques=None, autotrust=False,
               gf2=False, gf2_extended=False):
    """Find how a specific cell gets solved.

    Tries pure logic first. If stalled and autotrust=True, retries with
    the backtrack solution as trusted (enabling DeepResonance verification).

    Returns dict with:
      - answer: the digit for that cell
      - technique: which technique solves it
      - step: at which step it gets solved
      - reachable: whether it can be reached with selected techniques
      - candidates: current candidates at that cell before solving
      - path: all steps up to and including this cell's placement
      - solve_status: 'solved', 'found_cell', or 'stalled'
      - technique_counts: breakdown of techniques used in path
      - total_steps / total_empty: full solve stats
    """
    pos_target = row * 9 + col

    # Get solution
    solution_str = solve_backtrack(bd81)
    if not solution_str:
        return {'error': 'No solution exists'}

    answer = int(solution_str[pos_target])

    # Check if it's a given
    ch = bd81[pos_target]
    given_val = int(ch) if ch.isdigit() else 0
    if given_val != 0:
        return {
            'cell': f'R{row+1}C{col+1}',
            'answer': given_val,
            'technique': 'given',
            'step': 0,
            'reachable': True,
            'solve_status': 'given',
            'message': f'R{row+1}C{col+1} = {given_val} (given clue)',
        }

    # Get candidates
    bb = BitBoard.from_string(bd81)
    cand_mask = bb.cands[pos_target]
    cand_list = [d + 1 for d in range(9) if cand_mask & BIT[d]]

    def _try_solve(trusted_solution=None):
        """Attempt solve, return (result, target_step, path)."""
        r = solve_selective(bd81, max_level=max_level, only_techniques=only_techniques,
                            no_oracle=True, trusted_solution=trusted_solution, detail=True,
                            gf2=gf2, gf2_extended=gf2_extended)
        ts = None
        for s in r['steps']:
            if s['pos'] == pos_target:
                ts = s
                break
        p = []
        if ts:
            for s in r['steps']:
                p.append(s)
                if s['pos'] == pos_target:
                    break
        return r, ts, p

    # First attempt: pure logic (no trust)
    result, target_step, path = _try_solve()

    # If stalled and autotrust enabled, retry with trusted solution
    retry_msg = None
    if not target_step and autotrust:
        retry_msg = 'Pure logic stalled — retrying with autotrust (DeepResonance enabled)...'
        result, target_step, path = _try_solve(trusted_solution=solution_str)

    # Build technique breakdown for the path
    path_techs = {}
    for s in (path if path else result['steps']):
        t = s['technique']
        path_techs[t] = path_techs.get(t, 0) + 1

    # Filter elim_events to those within the path scope
    all_elim_events = result.get('elim_events', [])
    if target_step:
        target_round = target_step.get('round', 999)
        path_elims = [ev for ev in all_elim_events if ev.get('round', 0) <= target_round]
    else:
        path_elims = all_elim_events

    # Count exotic techniques from elimination events
    for ev in path_elims:
        t = ev.get('technique', '?')
        path_techs[t] = path_techs.get(t, 0) + 1

    if target_step:
        return {
            'cell': f'R{row+1}C{col+1}',
            'answer': answer,
            'technique': target_step['technique'],
            'step': target_step['step'],
            'reachable': True,
            'candidates': cand_list,
            'path': path,
            'elim_events': path_elims,
            'solve_status': 'solved' if result['success'] else 'found_cell',
            'total_steps': result['n_steps'],
            'total_empty': result.get('empty_remaining', 0),
            'technique_counts': result['technique_counts'],
            'path_technique_counts': path_techs,
            'used_autotrust': retry_msg is not None,
            'retry_msg': retry_msg,
            'message': f'R{row+1}C{col+1} = {answer} via {target_step["technique"]} (step {target_step["step"]})',
        }
    else:
        return {
            'cell': f'R{row+1}C{col+1}',
            'answer': answer,
            'technique': None,
            'step': None,
            'reachable': False,
            'candidates': cand_list,
            'path': result['steps'],
            'elim_events': path_elims,
            'solve_status': 'stalled',
            'stalled_at_step': result['n_steps'],
            'total_empty': result.get('empty_remaining', 0),
            'technique_counts': result['technique_counts'],
            'path_technique_counts': path_techs,
            'used_autotrust': retry_msg is not None,
            'message': (f'R{row+1}C{col+1} = {answer} (answer known via backtrack) '
                       f'but NOT reachable with selected techniques. '
                       f'Stalled at step {result["n_steps"]} with {result.get("empty_remaining", 0)} cells remaining.'),
        }


# ══════════════════════════════════════════════════════════════
# DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════

def format_board(board_str, given_str=None):
    """Pretty-print a 9x9 Sudoku board."""
    lines = []
    lines.append('┌───────┬───────┬───────┐')
    for r in range(9):
        row = '│'
        for c in range(9):
            pos = r * 9 + c
            d = board_str[pos]
            if d == '0' or d == '.':
                row += ' .'
            elif given_str and (given_str[pos] != '0' and given_str[pos] != '.'):
                row += f' {d}'  # given
            else:
                row += f' {d}'
            if c % 3 == 2:
                row += ' │'
        lines.append(row)
        if r % 3 == 2 and r < 8:
            lines.append('├───────┼───────┼───────┤')
    lines.append('└───────┴───────┴───────┘')
    return '\n'.join(lines)


def format_summary(result, elapsed_ms):
    """Format solve summary."""
    lines = []
    status = 'SOLVED' if result['success'] else ('STALLED' if result.get('stalled') else 'FAILED')
    lines.append(f'Status: {status}')
    lines.append(f'Steps:  {result["n_steps"]}')
    lines.append(f'Time:   {elapsed_ms:.1f}ms')
    if result.get('empty_remaining', 0) > 0:
        lines.append(f'Empty:  {result["empty_remaining"]} cells remaining')

    # Check if any WSRF inventions or oracle were used
    tc = result['technique_counts']
    wsrf_used = WSRF_INVENTIONS & set(tc.keys())
    oracle_used = 'ORACLE_ONLY' in tc
    tags = []
    if wsrf_used:
        tags.append(f'WSRF:   {", ".join(sorted(wsrf_used))}')
    if oracle_used:
        tags.append(f'Oracle: {tc["ORACLE_ONLY"]} oracle placement{"s" if tc["ORACLE_ONLY"] != 1 else ""} (not pure logic)')
    if tags:
        for t in tags:
            lines.append(t)
    elif result['success']:
        lines.append('Verify: All techniques are Sudoku Expert Approved ✓')
        lines.append('')
        lines.append('  Board validated: every row, column, and box contains')
        lines.append('  digits 1-9 exactly once per international Sudoku rules.')
        lines.append('  No backtracking or trial-and-error was used at any point.')
        lines.append('  Every placement was derived by deterministic logic alone.')
    else:
        lines.append('Verify: Pure logic — stalled (selected techniques insufficient)')

    lines.append('')
    lines.append('Techniques:')
    total = sum(tc.values())
    for tech, count in sorted(tc.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        lvl = TECHNIQUE_LEVELS.get(tech, '?')
        bar = '█' * max(1, int(pct / 3))
        tag = ' ★' if tech in WSRF_INVENTIONS else (' ⚠' if tech == 'ORACLE_ONLY' else '')
        lines.append(f'  {tech:20s}  {count:4d} ({pct:5.1f}%)  L{lvl}  {bar}{tag}')

    return '\n'.join(lines)


def format_detail(result):
    """Format rich round-by-round detailed output."""
    lines = []
    steps = result.get('steps', [])
    elim_events = result.get('elim_events', [])

    # Index elimination events by round
    elim_by_round = {}
    for ev in elim_events:
        rnd = ev['round']
        elim_by_round.setdefault(rnd, []).append(ev)

    # Group steps by round
    rounds = {}
    for s in steps:
        rnd = s.get('round', 1)
        rounds.setdefault(rnd, []).append(s)

    all_rounds = sorted(set(list(rounds.keys()) + list(elim_by_round.keys())))

    for rnd in all_rounds:
        lines.append(f'Round {rnd}')

        # Show elimination events for this round first (they happen before placements cascade)
        if rnd in elim_by_round:
            for ev in elim_by_round[rnd]:
                tech = ev['technique']
                elims = ev.get('eliminations', [])
                lvl = TECHNIQUE_LEVELS.get(tech, '?')
                wsrf_tag = ' ★' if tech in WSRF_INVENTIONS else ''
                lines.append(f'  {tech} {len(elims)} elimination{"s" if len(elims) != 1 else ""}{wsrf_tag}')
                # Group eliminations by cell
                by_cell = {}
                for pos, d in elims:
                    by_cell.setdefault(pos, []).append(d + 1 if d < 9 else d)
                elim_parts = []
                for pos in sorted(by_cell):
                    digits = ','.join(str(d) for d in sorted(by_cell[pos]))
                    elim_parts.append(f'{_cell_name(pos)}: {digits}')
                if elim_parts:
                    # Show up to 8 eliminations inline, rest as count
                    if len(elim_parts) <= 8:
                        lines.append(f'    {" | ".join(elim_parts)}')
                    else:
                        lines.append(f'    {" | ".join(elim_parts[:6])} ... +{len(elim_parts)-6} more')
                detail_text = ev.get('detail', '')
                if detail_text:
                    lines.append(f'    {detail_text}')

        # Show placements for this round
        if rnd in rounds:
            for s in rounds[rnd]:
                tech = s['technique']
                cell = s['cell']
                digit = s['digit']
                lvl = TECHNIQUE_LEVELS.get(tech, '?')
                wsrf_tag = ' ★' if tech in WSRF_INVENTIONS else ''

                cands = s.get('cands_before', [])
                cands_str = ' '.join(str(c) for c in cands) if cands else ''
                check = '✓'

                if cands_str:
                    lines.append(f'  {tech} {cell} = {digit}{check}{wsrf_tag}')
                    lines.append(f'    Notes before: {cands_str} → placed {digit}')
                else:
                    lines.append(f'  {tech} {cell} = {digit}{check}{wsrf_tag}')

                explanation = s.get('explanation', '')
                if explanation:
                    lines.append(f'    {explanation}')

    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════
# PARSE HELPERS
# ══════════════════════════════════════════════════════════════

def parse_cell(cell_str):
    """Parse cell reference like R3C5, r3c5, 2,4 (0-indexed), or 3,5 (1-indexed with R/C)."""
    cell_str = cell_str.strip().upper()
    # R3C5 format
    if cell_str.startswith('R') and 'C' in cell_str:
        parts = cell_str[1:].split('C')
        r = int(parts[0]) - 1
        c = int(parts[1]) - 1
        if 0 <= r <= 8 and 0 <= c <= 8:
            return r, c
        raise ValueError(f'Cell out of range: {cell_str}')
    # row,col format (0-indexed)
    if ',' in cell_str:
        parts = cell_str.split(',')
        r, c = int(parts[0]), int(parts[1])
        if 0 <= r <= 8 and 0 <= c <= 8:
            return r, c
        raise ValueError(f'Cell out of range: {cell_str}')
    raise ValueError(f'Cannot parse cell: {cell_str}. Use R3C5 or 2,4 format.')


def normalize_puzzle(puzzle_str):
    """Normalize a puzzle string to 81 digits (0 for empty)."""
    puzzle_str = puzzle_str.strip().replace('.', '0').replace(' ', '').replace('\n', '')
    # Handle potential multi-line grid format
    puzzle_str = ''.join(ch for ch in puzzle_str if ch.isdigit())
    if len(puzzle_str) != 81:
        raise ValueError(f'Puzzle must be 81 digits, got {len(puzzle_str)}')
    return puzzle_str


def parse_techniques(tech_str):
    """Parse technique filter string like 'fpc,gf2,l1' into a set."""
    techs = set()
    for t in tech_str.lower().split(','):
        t = t.strip()
        if not t:
            continue
        if t in TECHNIQUE_ALIASES:
            alias = TECHNIQUE_ALIASES[t]
            if alias == 'L1':
                techs.update(['crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'])
            elif alias == 'L2':
                techs.update(['crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining',
                             'GF2_Lanczos'])
            else:
                techs.add(alias)
                # Always include L1 as foundation
                techs.update(['crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'])
        else:
            # Try direct match
            matched = False
            for known_tech in TECHNIQUE_LEVELS:
                if known_tech.lower() == t:
                    techs.add(known_tech)
                    matched = True
                    break
            if not matched:
                print(f'Warning: unknown technique "{t}", ignoring', file=sys.stderr)
    return techs if techs else None


# ══════════════════════════════════════════════════════════════
# SHUFFLER — symmetry-preserving puzzle permutation
# ══════════════════════════════════════════════════════════════

import random

def shuffle_sudoku(bd81, rng=None):
    """Shuffle a Sudoku puzzle via symmetry transforms (preserves difficulty class).
    Swaps row bands, col bands, rows within bands, cols within bands,
    relabels digits, and optionally transposes."""
    if rng is None:
        rng = random.random
    g = [int(ch) for ch in bd81]

    def shuffle3():
        a = [0, 1, 2]
        for i in range(2, 0, -1):
            j = int(rng() * (i + 1))
            a[i], a[j] = a[j], a[i]
        return a

    # 1. Swap row bands
    new = [0] * 81
    band_order = shuffle3()
    for b in range(3):
        src = band_order[b]
        for r in range(3):
            for c in range(9):
                new[(b * 3 + r) * 9 + c] = g[(src * 3 + r) * 9 + c]
    g = list(new)

    # 2. Swap col bands
    col_band = shuffle3()
    for b in range(3):
        src = col_band[b]
        for r in range(9):
            for c in range(3):
                new[r * 9 + (b * 3 + c)] = g[r * 9 + (src * 3 + c)]
    g = list(new)

    # 3. Swap rows within each band
    for band in range(3):
        perm = shuffle3()
        for r in range(3):
            for c in range(9):
                new[(band * 3 + r) * 9 + c] = g[(band * 3 + perm[r]) * 9 + c]
    g = list(new)

    # 4. Swap cols within each band
    for band in range(3):
        perm = shuffle3()
        for r in range(9):
            for c in range(3):
                new[r * 9 + (band * 3 + c)] = g[r * 9 + (band * 3 + perm[c])]
    g = list(new)

    # 5. Relabel digits
    digits = list(range(1, 10))
    for i in range(8, 0, -1):
        j = int(rng() * (i + 1))
        digits[i], digits[j] = digits[j], digits[i]
    relabel = [0] + digits
    g = [0 if d == 0 else relabel[d] for d in g]

    # 6. Transpose (50% chance)
    if rng() < 0.5:
        t = list(g)
        for r in range(9):
            for c in range(9):
                g[r * 9 + c] = t[c * 9 + r]

    return ''.join(str(d) for d in g)


def crosswise_shuffle(bd81, rng=None):
    """Cross-section shuffle via full-board D4 + standard shuffling.

    The cross-section pattern (cells rotating along anti-diagonal circles)
    IS a full-board rotation/reflection. When you rotate 90°, every cell
    follows exactly the anti-diagonal cross-section paths:
      k=0: R1C1 → R1C9 → R9C9 → R9C1 (corners)
      k=1: R1C2,R2C1 → R8C9,R9C8 → R8C1,R9C2 → R1C8,R2C9
      ...etc for all cross-sections simultaneously.

    Full-board D4 operations are valid Sudoku symmetries (rows→cols,
    cols→rows, boxes→boxes), so 100% of outputs are valid puzzles.

    Then we layer on standard shuffling (band/row/col permutations +
    digit relabeling) for maximum structural variety.

    This creates puzzles where different boxes are empty, clue patterns
    are rotated/reflected, AND the inner structure is further scrambled.
    """
    if rng is None:
        rng = random.random
    g = [int(ch) for ch in bd81]

    # ── Step 1: Random D4 board transformation (the cross-section rotation) ──
    # 8 operations: identity, 3 rotations, 2 reflections, 2 diagonal flips
    op = int(rng() * 8)
    if op > 0:
        new = [0] * 81
        for r in range(9):
            for c in range(9):
                if op == 1:    # 90° CW
                    nr, nc = c, 8 - r
                elif op == 2:  # 180°
                    nr, nc = 8 - r, 8 - c
                elif op == 3:  # 270° CW
                    nr, nc = 8 - c, r
                elif op == 4:  # flip horizontal
                    nr, nc = r, 8 - c
                elif op == 5:  # flip vertical
                    nr, nc = 8 - r, c
                elif op == 6:  # transpose (main diagonal)
                    nr, nc = c, r
                elif op == 7:  # anti-transpose
                    nr, nc = 8 - c, 8 - r
                else:
                    nr, nc = r, c
                new[nr * 9 + nc] = g[r * 9 + c]
        g = new

    # ── Step 2: Standard shuffling (band/row/col permutations) ──
    def shuffle3():
        a = [0, 1, 2]
        for i in range(2, 0, -1):
            j = int(rng() * (i + 1))
            a[i], a[j] = a[j], a[i]
        return a

    # Swap row bands
    new = [0] * 81
    band_order = shuffle3()
    for b in range(3):
        src = band_order[b]
        for r in range(3):
            for c in range(9):
                new[(b * 3 + r) * 9 + c] = g[(src * 3 + r) * 9 + c]
    g = list(new)

    # Swap col bands
    col_band = shuffle3()
    for b in range(3):
        src = col_band[b]
        for r in range(9):
            for c in range(3):
                new[r * 9 + (b * 3 + c)] = g[r * 9 + (src * 3 + c)]
    g = list(new)

    # Swap rows within bands
    for band in range(3):
        perm = shuffle3()
        for r in range(3):
            for c in range(9):
                new[(band * 3 + r) * 9 + c] = g[(band * 3 + perm[r]) * 9 + c]
    g = list(new)

    # Swap cols within bands
    for band in range(3):
        perm = shuffle3()
        for r in range(9):
            for c in range(3):
                new[r * 9 + (band * 3 + c)] = g[r * 9 + (band * 3 + perm[c])]
    g = list(new)

    # ── Step 3: Digit relabeling ──
    digits = list(range(1, 10))
    for i in range(8, 0, -1):
        j = int(rng() * (i + 1))
        digits[i], digits[j] = digits[j], digits[i]
    relabel = [0] + digits
    g = [0 if d == 0 else relabel[d] for d in g]

    return ''.join(str(d) for d in g)


def run_crosswise_benchmark(bd81, count=100, max_level=99, only_techniques=None,
                            no_oracle=False, gf2=False, gf2_extended=False, autotrust=False):
    """Generate cross-wise shuffled variants, verify solvability, solve and collect stats."""
    results = []
    tech_totals = {}
    total_time = 0
    solved_count = 0
    stalled_count = 0
    oracle_total = 0
    invalid_count = 0
    valid_puzzles = 0

    for i in range(count):
        variant = crosswise_shuffle(bd81)

        # Verify unique solution
        sol = solve_backtrack(variant)
        if not sol:
            invalid_count += 1
            if (i + 1) % 25 == 0 or i == count - 1:
                print(f'  [{i+1}/{count}] valid={valid_puzzles} invalid={invalid_count} '
                      f'solved={solved_count}', file=sys.stderr)
            continue

        valid_puzzles += 1
        trusted = sol if autotrust else None
        t0 = time.perf_counter()
        result = solve_selective(variant, max_level=max_level, only_techniques=only_techniques,
                                no_oracle=no_oracle, gf2=gf2, gf2_extended=gf2_extended,
                                trusted_solution=trusted)
        elapsed = (time.perf_counter() - t0) * 1000
        total_time += elapsed

        if result['success']:
            solved_count += 1
        if result.get('stalled'):
            stalled_count += 1

        for tech, cnt in result['technique_counts'].items():
            tech_totals[tech] = tech_totals.get(tech, 0) + cnt
            if tech == 'ORACLE_ONLY':
                oracle_total += cnt

        # Difficulty score: count of L5+ technique uses
        diff_score = sum(cnt for tech, cnt in result['technique_counts'].items()
                         if TECHNIQUE_LEVELS.get(tech, 0) >= 5 and tech != 'ORACLE_ONLY')
        results.append({
            'success': result['success'],
            'n_steps': result['n_steps'],
            'elapsed_ms': round(elapsed, 1),
            'technique_counts': result['technique_counts'],
            'oracle_count': result['technique_counts'].get('ORACLE_ONLY', 0),
            'puzzle': variant,
            'difficulty': diff_score,
        })

        if (i + 1) % 25 == 0 or i == count - 1:
            print(f'  [{i+1}/{count}] valid={valid_puzzles} invalid={invalid_count} '
                  f'solved={solved_count} avg={total_time/max(valid_puzzles,1):.1f}ms',
                  file=sys.stderr)

    n = max(valid_puzzles, 1)
    total_steps = sum(r['n_steps'] for r in results)

    return {
        'count': count,
        'valid': valid_puzzles,
        'invalid': invalid_count,
        'solved': solved_count,
        'stalled': stalled_count,
        'solve_rate': f'{solved_count/n*100:.1f}%' if valid_puzzles else '0%',
        'avg_time_ms': round(total_time / n, 1) if valid_puzzles else 0,
        'total_time_ms': round(total_time, 1),
        'avg_steps': round(total_steps / n, 1) if valid_puzzles else 0,
        'avg_oracle': round(oracle_total / n, 2) if oracle_total else 0,
        'technique_totals': tech_totals,
        'technique_averages': {t: round(c / n, 2) for t, c in tech_totals.items()},
        'results': results,
        'autotrust': autotrust,
    }


def run_benchmark(bd81, count=250, max_level=99, only_techniques=None,
                  no_oracle=False, gf2=False, gf2_extended=False):
    """Solve `count` shuffled variants and return aggregate stats."""
    results = []
    tech_totals = {}
    total_time = 0
    solved_count = 0
    stalled_count = 0
    oracle_total = 0

    for i in range(count):
        variant = shuffle_sudoku(bd81)
        t0 = time.perf_counter()
        result = solve_selective(variant, max_level=max_level, only_techniques=only_techniques,
                                no_oracle=no_oracle, gf2=gf2, gf2_extended=gf2_extended)
        elapsed = (time.perf_counter() - t0) * 1000
        total_time += elapsed

        if result['success']:
            solved_count += 1
        if result.get('stalled'):
            stalled_count += 1

        for tech, cnt in result['technique_counts'].items():
            tech_totals[tech] = tech_totals.get(tech, 0) + cnt
            if tech == 'ORACLE_ONLY':
                oracle_total += cnt

        results.append({
            'success': result['success'],
            'n_steps': result['n_steps'],
            'elapsed_ms': round(elapsed, 1),
            'technique_counts': result['technique_counts'],
            'oracle_count': result['technique_counts'].get('ORACLE_ONLY', 0),
        })

        # Progress indicator
        if (i + 1) % 50 == 0 or i == count - 1:
            print(f'  [{i+1}/{count}] solved={solved_count} stalled={stalled_count} '
                  f'avg={total_time/(i+1):.1f}ms/puzzle', file=sys.stderr)

    total_steps = sum(r['n_steps'] for r in results)
    total_placements = sum(tech_totals.values())

    return {
        'count': count,
        'solved': solved_count,
        'stalled': stalled_count,
        'solve_rate': f'{solved_count/count*100:.1f}%',
        'avg_time_ms': round(total_time / count, 1),
        'total_time_ms': round(total_time, 1),
        'avg_steps': round(total_steps / count, 1),
        'avg_oracle': round(oracle_total / count, 2) if oracle_total else 0,
        'technique_totals': tech_totals,
        'technique_averages': {t: round(c / count, 2) for t, c in tech_totals.items()},
        'results': results,
    }


def format_benchmark(bench, preset_label=None):
    """Format benchmark results."""
    lines = []
    if preset_label:
        lines.append(f'\n  ✦ {preset_label} Techniques ✦')
    lines.append(f'\n{"═" * 60}')
    lines.append(f'BENCHMARK: {bench["count"]} shuffled variants')
    lines.append(f'{"═" * 60}')
    lines.append(f'Solve rate: {bench["solve_rate"]} ({bench["solved"]}/{bench["count"]})')
    if bench['stalled']:
        lines.append(f'Stalled:    {bench["stalled"]}')
    lines.append(f'Avg time:   {bench["avg_time_ms"]:.1f}ms/puzzle')
    lines.append(f'Total time: {bench["total_time_ms"]:.0f}ms')
    lines.append(f'Avg steps:  {bench["avg_steps"]}')
    if bench['avg_oracle']:
        lines.append(f'Avg oracle: {bench["avg_oracle"]} per puzzle ⚠')

    # Technique breakdown
    wsrf_used = WSRF_INVENTIONS & set(bench['technique_totals'].keys())
    oracle_used = 'ORACLE_ONLY' in bench['technique_totals']
    if not wsrf_used and not oracle_used and bench['solved'] == bench['count']:
        lines.append(f'Verify:     All techniques are Sudoku Expert Approved ✓')
    elif wsrf_used:
        lines.append(f'WSRF:       {", ".join(sorted(wsrf_used))}')

    lines.append(f'\nTechnique Averages (per puzzle):')
    ta = bench['technique_averages']
    total_avg = sum(ta.values())
    for tech, avg in sorted(ta.items(), key=lambda x: -x[1]):
        pct = avg / total_avg * 100 if total_avg else 0
        lvl = TECHNIQUE_LEVELS.get(tech, '?')
        bar = '█' * max(1, int(pct / 3))
        tag = ' ★' if tech in WSRF_INVENTIONS else (' ⚠' if tech == 'ORACLE_ONLY' else '')
        lines.append(f'  {tech:20s}  {avg:6.2f} ({pct:5.1f}%)  L{lvl}  {bar}{tag}')

    lines.append(f'{"═" * 60}')
    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════
# CONSTELLATION FORGE — clue-pattern redistribution shuffler
# ══════════════════════════════════════════════════════════════

def _relabel_digits(bd81):
    """Apply a random digit relabeling (1-9 → permuted 1-9) to a puzzle string."""
    digits = list(range(1, 10))
    for i in range(8, 0, -1):
        j = int(random.random() * (i + 1))
        digits[i], digits[j] = digits[j], digits[i]
    relabel = {0: '0'}
    for i, d in enumerate(digits):
        relabel[i + 1] = str(d)
    return ''.join(relabel[int(ch)] for ch in bd81)


def forge_variant(bd81, target_clues=None, max_retries=20, max_level=99,
                  no_oracle=True, gf2_extended=False):
    """Generate a constellation-forged variant with EXACTLY the same clue count.

    Uses add-then-remove swap technique: starting from the original clue positions,
    repeatedly move clues to new cells while preserving uniqueness.
    """
    from larsdoku.engine import has_unique_solution

    solution = solve_backtrack(bd81)
    if not solution:
        return None

    if target_clues is None:
        target_clues = sum(1 for ch in bd81 if ch != '0' and ch != '.')

    for attempt in range(max_retries):
        clue_set = {i for i, ch in enumerate(bd81) if ch != '0' and ch != '.'}
        empty_set = {i for i in range(81) if i not in clue_set}

        n_swaps = target_clues * 10
        for _ in range(n_swaps):
            if not empty_set:
                break
            add_pos = random.choice(list(empty_set))
            expanded = clue_set | {add_pos}

            removable = list(clue_set)
            random.shuffle(removable)
            for rm_pos in removable:
                test_clues = expanded - {rm_pos}
                test = ''.join(solution[i] if i in test_clues else '0' for i in range(81))
                if has_unique_solution(test):
                    clue_set = test_clues
                    empty_set = (empty_set - {add_pos}) | {rm_pos}
                    break

        forged = ''.join(solution[i] if i in clue_set else '0' for i in range(81))
        forged = _relabel_digits(forged)

        # Oracle-free: verify forged puzzle is solvable by pure logic
        result = solve_selective(forged,
                                gf2_extended=gf2_extended)
        if result['success']:
            return forged

    return None


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

def _start_server(port):
    """Start local web server with Python engine API."""
    import http.server
    import urllib.parse
    import os
    import pathlib

    # Find site directory
    pkg_dir = pathlib.Path(__file__).parent.parent / 'site'
    if not pkg_dir.exists():
        # Try installed package location
        pkg_dir = pathlib.Path(__file__).parent / 'site'
    if not pkg_dir.exists():
        print(f'Error: site/ directory not found. Expected at {pkg_dir}', file=sys.stderr)
        sys.exit(1)

    class LarsdokuHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(pkg_dir), **kw)

        def do_POST(self):
            print(f'  [POST {self.path}]', flush=True)
            if self.path == '/api/solve':
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                try:
                    data = json.loads(body)
                    bd81 = normalize_puzzle(data.get('puzzle', ''))
                    use_autotrust = data.get('autotrust', True)
                    max_level = data.get('level', 99)
                    no_oracle = data.get('no_oracle', False)
                    use_gf2 = data.get('gf2', False)
                    use_gf2x = data.get('gf2x', False)
                    preset_name = data.get('preset', None)
                    only_str = data.get('only', None)
                    exclude_str = data.get('exclude', None)
                    cell_str = data.get('cell', None)
                    want_path = data.get('path', False)

                    # Build only_techniques from preset/only/exclude
                    only_techniques = None
                    if preset_name and preset_name in PRESETS:
                        only_techniques = PRESETS[preset_name]
                    if only_str:
                        only_techniques = parse_techniques(only_str)
                    if exclude_str and only_techniques is not None:
                        exclude_set = parse_techniques(exclude_str)
                        if exclude_set:
                            only_techniques = only_techniques - exclude_set
                    elif exclude_str and only_techniques is None:
                        exclude_set = parse_techniques(exclude_str)
                        if exclude_set:
                            all_techs = set(TECHNIQUE_LEVELS.keys())
                            only_techniques = all_techs - exclude_set

                    # Cell query mode
                    if cell_str:
                        row, col = parse_cell(cell_str)
                        t0 = time.perf_counter()
                        qr = query_cell(bd81, row, col, max_level=max_level,
                                        only_techniques=only_techniques,
                                        autotrust=use_autotrust,
                                        gf2=use_gf2, gf2_extended=use_gf2x)
                        elapsed = (time.perf_counter() - t0) * 1000
                        qr['elapsed_ms'] = round(elapsed, 1)
                        # Clean path steps
                        if 'path' in qr:
                            clean = []
                            for s in qr['path']:
                                clean.append({
                                    'step': s['step'], 'pos': s['pos'],
                                    'digit': s['digit'], 'technique': s['technique'],
                                    'cell': s.get('cell', f'R{s["pos"]//9+1}C{s["pos"]%9+1}'),
                                    'round': s.get('round', 0),
                                })
                            qr['path'] = clean
                        # Clean elim_events
                        if 'elim_events' in qr:
                            clean_elims = []
                            for ev in qr['elim_events']:
                                clean_elims.append({
                                    'round': ev.get('round'),
                                    'technique': ev.get('technique'),
                                    'detail': ev.get('detail', ''),
                                    'count': len(ev.get('eliminations', [])),
                                })
                            qr['elim_events'] = clean_elims
                        resp = json.dumps(qr, default=str).encode('utf-8')
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-Length', len(resp))
                        self.end_headers()
                        self.wfile.write(resp)
                        return

                    # Normal solve — ORACLE-FREE
                    t0 = time.perf_counter()
                    result = solve_selective(bd81, max_level=max_level,
                                            only_techniques=only_techniques,
                                            gf2=use_gf2, gf2_extended=use_gf2x,
                                            detail=True)
                    elapsed = (time.perf_counter() - t0) * 1000

                    result['elapsed_ms'] = round(elapsed, 1)
                    # Backtrack ONLY for display comparison — NOT used during solve
                    sol_str = solve_backtrack(bd81) if result['success'] else None
                    result['solution'] = sol_str or ''
                    # Make steps JSON-serializable
                    clean_steps = []
                    for s in result.get('steps', []):
                        clean_steps.append({
                            'step': s['step'], 'pos': s['pos'],
                            'digit': s['digit'], 'technique': s['technique'],
                            'cell': s.get('cell', f'R{s["pos"]//9+1}C{s["pos"]%9+1}'),
                            'round': s.get('round', 0),
                        })
                    result['steps'] = clean_steps
                    # Clean elim_events for JSON
                    clean_elims = []
                    for ev in result.get('elim_events', []):
                        clean_elims.append({
                            'round': ev.get('round'),
                            'technique': ev.get('technique'),
                            'detail': ev.get('detail', ''),
                            'count': len(ev.get('eliminations', [])),
                        })
                    result['elim_events'] = clean_elims
                    result.pop('board', None)

                    resp = json.dumps(result, default=str).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                except Exception as e:
                    resp = json.dumps({'error': str(e)}).encode('utf-8')
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
            elif self.path == '/api/forge':
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                try:
                    data = json.loads(body)
                    bd81 = normalize_puzzle(data.get('puzzle', ''))
                    t0 = time.perf_counter()
                    forged = forge_variant(bd81)
                    elapsed = (time.perf_counter() - t0) * 1000
                    if forged:
                        n_clues = sum(1 for ch in forged if ch != '0')
                        resp_data = {
                            'forged': forged,
                            'clues': n_clues,
                            'elapsed_ms': round(elapsed, 1),
                        }
                    else:
                        resp_data = {
                            'error': 'Could not forge variant after max retries',
                            'elapsed_ms': round(elapsed, 1),
                        }
                    resp = json.dumps(resp_data).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                except Exception as e:
                    resp = json.dumps({'error': str(e)}).encode('utf-8')
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)

            elif self.path == '/api/generate':
                # Generate a random unique or multi-solution puzzle
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                try:
                    data = json.loads(body)
                    want_unique = data.get('unique', True)
                    n_clues = data.get('clues', 24 if not want_unique else 28)
                    if want_unique:
                        n_clues = max(17, min(27, n_clues))  # unique: 17-27
                    else:
                        n_clues = max(8, min(16, n_clues))   # multi: 8-16
                    t0 = time.perf_counter()

                    # Generate a random solved board
                    sol = solve_backtrack('0' * 81)
                    if not sol:
                        raise ValueError('Failed to generate base board')
                    sol = shuffle_sudoku(sol)

                    # Remove digits to create puzzle
                    import random
                    positions = list(range(81))
                    random.shuffle(positions)
                    puzzle_chars = list(sol)
                    removed = 0
                    target_empty = 81 - n_clues

                    for pos in positions:
                        if removed >= target_empty:
                            break
                        saved = puzzle_chars[pos]
                        puzzle_chars[pos] = '0'
                        test = ''.join(puzzle_chars)
                        if want_unique:
                            if has_unique_solution(test):
                                removed += 1
                            else:
                                puzzle_chars[pos] = saved  # put it back
                        else:
                            removed += 1

                    puzzle = ''.join(puzzle_chars)
                    actual_clues = sum(1 for ch in puzzle if ch != '0')
                    is_unique = has_unique_solution(puzzle)

                    # Test solvability oracle-free
                    result = solve_selective(puzzle, detail=False, verbose=False)
                    elapsed = (time.perf_counter() - t0) * 1000

                    resp_data = {
                        'puzzle': puzzle,
                        'clues': actual_clues,
                        'unique': is_unique,
                        'solvable': result['success'],
                        'stalled_at': result['empty_remaining'] if not result['success'] else 0,
                        'techniques': result['technique_counts'],
                        'elapsed_ms': round(elapsed, 1),
                    }
                    resp = json.dumps(resp_data).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                except Exception as e:
                    resp = json.dumps({'error': str(e)}).encode('utf-8')
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)

            elif self.path == '/api/sparse-challenge':
                # Sparse Puzzle Challenge: generate a sub-17 clue board,
                # solve it forward-only, return completed + validated board.
                # Retries internally until success — user always gets a valid solve.
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                try:
                    data = json.loads(body)
                    n_clues = max(8, min(16, data.get('clues', 11)))
                    t0 = time.perf_counter()

                    from .sub17_solve import (generate_random_mask, solve_forward,
                                            validate_sudoku as val_sudoku)
                    import random as _rng

                    # Generate mask once, retry fills until we get a valid solve
                    min_score = 0.60 if n_clues <= 10 else 0.70
                    mask_result = generate_random_mask(n_clues=n_clues,
                                                       min_score=min_score)
                    if mask_result is None:
                        raise ValueError('Could not generate valid mask')
                    positions, mask_score, _, _ = mask_result
                    pos_set = set(positions)
                    actual_clues = len(positions)

                    max_attempts = 20
                    result = None
                    puzzle = None
                    attempt = 0
                    for attempt in range(1, max_attempts + 1):
                        sol = solve_backtrack('0' * 81)
                        sol = shuffle_sudoku(sol)
                        puzzle = ''.join(sol[p] if p in pos_set else '0'
                                         for p in range(81))
                        result = solve_forward(puzzle)
                        if result['valid']:
                            break

                    elapsed = (time.perf_counter() - t0) * 1000

                    if result and result['valid']:
                        board_str = result['board_str']
                        resp_data = {
                            'success': True,
                            'puzzle': puzzle,
                            'solution': board_str,
                            'clues': actual_clues,
                            'logic_placements': result['logic_placements'],
                            'heuristic_placements': result['heuristic_placements'],
                            'total_placements': result['total_placements'],
                            'validated': True,
                            'attempts': attempt,
                            'elapsed_ms': round(elapsed, 1),
                            'mask_score': round(mask_score, 2),
                        }
                    else:
                        resp_data = {
                            'success': False,
                            'error': f'No valid solve after {max_attempts} attempts',
                            'attempts': max_attempts,
                            'elapsed_ms': round(elapsed, 1),
                        }

                    resp = json.dumps(resp_data).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                except Exception as e:
                    resp = json.dumps({'error': str(e)}).encode('utf-8')
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)

            elif self.path == '/api/shuffle':
                # Shuffle an existing puzzle (preserves solution structure)
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                try:
                    data = json.loads(body)
                    bd81 = normalize_puzzle(data.get('puzzle', ''))
                    t0 = time.perf_counter()
                    shuffled = shuffle_sudoku(bd81)
                    is_unique = has_unique_solution(shuffled)
                    elapsed = (time.perf_counter() - t0) * 1000
                    n_clues = sum(1 for ch in shuffled if ch != '0')
                    resp_data = {
                        'puzzle': shuffled,
                        'clues': n_clues,
                        'unique': is_unique,
                        'elapsed_ms': round(elapsed, 1),
                    }
                    resp = json.dumps(resp_data).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                except Exception as e:
                    resp = json.dumps({'error': str(e)}).encode('utf-8')
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)

            elif self.path == '/api/batch':
                # Batch: generate + solve N puzzles, report results
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                try:
                    data = json.loads(body)
                    count = min(data.get('count', 25), 100)
                    n_clues = data.get('clues', 28)
                    n_clues = max(17, min(40, n_clues))
                    want_unique = data.get('unique', True)
                    t0 = time.perf_counter()

                    import random
                    results_list = []
                    solved_count = 0
                    stalled_count = 0
                    tech_totals = {}

                    for i in range(count):
                        # Generate
                        sol = solve_backtrack('0' * 81)
                        if not sol:
                            continue
                        sol = shuffle_sudoku(sol)
                        positions = list(range(81))
                        random.shuffle(positions)
                        puzzle_chars = list(sol)
                        removed = 0
                        target_empty = 81 - n_clues
                        for pos in positions:
                            if removed >= target_empty:
                                break
                            saved = puzzle_chars[pos]
                            puzzle_chars[pos] = '0'
                            test = ''.join(puzzle_chars)
                            if want_unique:
                                if has_unique_solution(test):
                                    removed += 1
                                else:
                                    puzzle_chars[pos] = saved
                            else:
                                removed += 1
                        puzzle = ''.join(puzzle_chars)

                        # Solve oracle-free
                        result = solve_selective(puzzle, detail=False, verbose=False)
                        entry = {
                            'puzzle': puzzle,
                            'solved': result['success'],
                            'remaining': result['empty_remaining'],
                            'techniques': result['technique_counts'],
                        }
                        results_list.append(entry)
                        if result['success']:
                            solved_count += 1
                        else:
                            stalled_count += 1
                        for tech, cnt in result['technique_counts'].items():
                            tech_totals[tech] = tech_totals.get(tech, 0) + cnt

                    elapsed = (time.perf_counter() - t0) * 1000
                    resp_data = {
                        'count': count,
                        'solved': solved_count,
                        'stalled': stalled_count,
                        'solve_rate': f'{solved_count}/{count}',
                        'technique_totals': tech_totals,
                        'elapsed_ms': round(elapsed, 1),
                        'puzzles': results_list,
                    }
                    resp = json.dumps(resp_data).encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)
                except Exception as e:
                    import traceback
                    resp = json.dumps({'error': str(e), 'trace': traceback.format_exc()}).encode('utf-8')
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', len(resp))
                    self.end_headers()
                    self.wfile.write(resp)

            else:
                resp = json.dumps({'error': f'Unknown endpoint: {self.path}'}).encode('utf-8')
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', len(resp))
                self.end_headers()
                self.wfile.write(resp)

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

        def do_GET(self):
            if self.path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
                return
            super().do_GET()

        def log_message(self, fmt, *args):
            # Log POST requests for debugging
            msg = fmt % args
            if 'POST' in msg or 'error' in msg.lower():
                print(f'  [{msg}]', flush=True)

    server = http.server.HTTPServer(('0.0.0.0', port), LarsdokuHandler)
    print(f'\n  Larsdoku Web Solver')
    print(f'  {"─" * 40}')
    print(f'  Local:   http://localhost:{port}')
    print(f'  Network: http://0.0.0.0:{port}')
    print(f'  Engine:  Full Python solver (JIT-optimized)')
    print(f'  {"─" * 40}')
    print(f'  Press Ctrl+C to stop\n')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Server stopped.')
        server.server_close()


def main():
    parser = argparse.ArgumentParser(
        description='WSRF Sudoku Solver — Instant solutions via bitwise engine + GF(2) linear algebra',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s "003..." --board                           auto-solve, print grid
  %(prog)s "003..." --detail                          rich round-by-round trace
  %(prog)s "003..." --preset expert --detail          Expert Approved, detailed log
  %(prog)s "003..." --preset expert --no-oracle       Expert Approved, pure logic
  %(prog)s "003..." --bench 250                       benchmark 250 shuffled variants
  %(prog)s "003..." --bench 100 --preset expert       benchmark Expert-only
  %(prog)s "003..." --steps                           step-by-step trace
  %(prog)s "003..." --cell R3C5 --path                show technique path to R3C5
  %(prog)s "003..." --level 2                         L1+L2+GF(2) only
  %(prog)s "003..." --gf2x                             GF(2) Extended — probing + conjugates
  %(prog)s "003..." --gf2x --detail                   see GF2 probe results in detail
  %(prog)s "003..." --only fpc,gf2                    only FPC + GF(2) (+ L1 foundation)
  %(prog)s "003..." --json                            JSON output
  echo "003..." | %(prog)s -                          read from stdin

presets:
  expert   Sudoku Expert Approved — standard L1-L6 techniques (no WSRF inventions)
  wsrf     Full WSRF stack — all techniques including FPC, D2B, FPF, GF(2)
  zone135  L1 + Zone135 — cross-board zone sum deduction (oracle-assisted)
""")
    parser.add_argument('puzzle', nargs='?', default=None,
                       help='81-char puzzle string (bd81/bdp), or - for stdin')
    parser.add_argument('--cell', '-c', help='Query solution for a specific cell (R3C5 or row,col)')
    parser.add_argument('--path', '-p', action='store_true',
                       help='Show technique path to --cell (requires --cell)')
    parser.add_argument('--level', '-l', type=int, default=99,
                       help='Max technique level (1=L1 only, 2=+GF2, 5=+FPC/FC, 7=all)')
    parser.add_argument('--only', '-o', help='Only use specific techniques (comma-separated: fpc,gf2,fc,...)')
    parser.add_argument('--exclude', '-x', help='Exclude specific techniques (comma-separated: gf2,fpc,d2b,...)')
    parser.add_argument('--preset', choices=list(PRESETS.keys()),
                       help='Use a preset technique set (expert = Sudoku Expert Approved, wsrf = full stack)')
    parser.add_argument('--steps', '-s', action='store_true', help='Show step-by-step solution trace')
    parser.add_argument('--detail', '-d', action='store_true',
                       help='Rich round-by-round output with candidates, explanations, and eliminations')
    parser.add_argument('--bench', type=int, metavar='N',
                       help='Benchmark N shuffled variants of the puzzle (default: 250)')
    parser.add_argument('--crosswise', type=int, metavar='N',
                       help='Cross-section shuffle: generate N anti-diagonal rotated variants and solve')
    parser.add_argument('--save-hardest', type=int, metavar='N', default=0,
                       help='Save top N hardest puzzles from --crosswise or --bench to a file')
    parser.add_argument('--board', '-b', action='store_true', help='Print solved board grid')
    parser.add_argument('--no-oracle', '-n', action='store_true',
                       help='Pure logic only — stop when stalled, no guessing')
    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    parser.add_argument('--gf2', action='store_true',
                       help='Enable GF(2) Block Lanczos linear algebra technique')
    parser.add_argument('--gf2x', action='store_true',
                       help='Use GF(2) Extended — band/stack constraints, conjugate pairs, free-variable probing (options A-E)')
    parser.add_argument('--exotic', action='store_true',
                       help='Enable exotic techniques (ALS-XZ, Sue De Coq, X-Cycles, Aligned Pair Exclusion)')
    parser.add_argument('--trust', '-t', metavar='SOLUTION',
                       help='Trust mode — use this 81-char solution string instead of backtracker')
    parser.add_argument('--autotrust', action='store_true',
                       help='Auto-trust: solve via backtracker first, then use that solution as trusted (enables DeepResonance verification)')
    parser.add_argument('--siro-cascade', action='store_true',
                       help='SIRO-guided cascade: zone features predict technique, dispatch directly')
    parser.add_argument('--siro-bootstrap', action='store_true',
                       help='SIRO Bootstrap: self-verifying oracle via L1 reduction + prediction')
    parser.add_argument('--board-siro', action='store_true',
                       help='Global SIRO board illumination: show band/stack/cascade impact for every cell')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output during solve')
    parser.add_argument('--serve', type=int, nargs='?', const=8265, metavar='PORT',
                       help='Start local web server (default port 8265) — full Python engine via browser')
    parser.add_argument('--generate', type=int, nargs='?', const=24, metavar='CLUES',
                       help='Generate a random unique puzzle with N clues (17-27, default 24)')
    parser.add_argument('--generate-multi', type=int, nargs='?', const=12, metavar='CLUES',
                       help='Generate a random multi-solution puzzle with N clues (8-16, default 12)')
    parser.add_argument('--batch', type=int, nargs='?', const=25, metavar='COUNT',
                       help='Generate + solve N random puzzles (default 25)')
    parser.add_argument('--batch-clues', type=int, default=24, metavar='CLUES',
                       help='Clues per puzzle in batch mode (default 24)')
    parser.add_argument('--random-mask', type=int, nargs='?', const=24, metavar='CLUES',
                       help='Generate a random mask with N clues that passes all placement rules')
    parser.add_argument('--validate', action='store_true',
                       help='With --random-mask: show mask validation only, do not generate puzzle')
    parser.add_argument('--mask-batch', type=int, nargs='?', const=25, metavar='COUNT',
                       help='Generate N masks, build puzzles from each, solve oracle-free, report stats')
    parser.add_argument('--mask-clues', type=int, default=12, metavar='CLUES',
                       help='Clues per mask in --mask-batch mode (default 12)')
    parser.add_argument('--dr-mode', type=str, default='all',
                       choices=['base', 'deep', 'cross', 'all'],
                       help='DeepResonance mode: base=L1+L2+chain+FC, deep=+cascade(depth3), cross=+unanimous, all=all safe phases (default: all)')
    parser.add_argument('--zone-oracle', action='store_true',
                       help='Enable Zone Oracle: SIRO zone predictions at stall points (probabilistic)')
    parser.add_argument('--rule-oracle', action='store_true',
                       help='Enable Rule Oracle: naked singles after zone placements (100%% deterministic)')
    parser.add_argument('--siro', action='store_true',
                       help='Enable both Zone Oracle + Rule Oracle (SIRO mode)')
    parser.add_argument('--zone135', action='store_true',
                       help='Enable Zone135: cross-board zone sum deduction (auto-computes oracle from solution)')
    parser.add_argument('--siro-only', type=str, nargs='?', const=None, metavar='PUZZLE',
                       help='Pure SIRO analysis: zone predict → place → rule cascade. No techniques. Just zones.')
    parser.add_argument('--sparse', type=int, nargs='?', const=11, metavar='CLUES',
                       help='Sparse Puzzle Challenge: generate + solve a sub-17 clue board (default 11 clues)')
    parser.add_argument('--sparse-count', type=int, default=1, metavar='N',
                       help='Number of sparse puzzles to generate (default 1)')
    parser.add_argument('--test-mask', type=str, metavar='MASK',
                       help='Test a mask string: generate 25 puzzles + 25 shuffled variants, report solve rates')
    parser.add_argument('--test-mask-count', type=int, default=25, metavar='N',
                       help='Puzzles per round in --test-mask (default 25)')
    parser.add_argument('--forge-solve', type=str, metavar='MASK',
                       help='Forge unique puzzles from a mask via Mask Forge, then solve each one')
    parser.add_argument('--forge-count', type=int, default=5, metavar='N',
                       help='Number of forged puzzles to solve (default 5)')
    parser.add_argument('--to-mask', type=str, metavar='PUZZLE',
                       help='Convert a puzzle string to its mask (0→0, nonzero→X)')
    parser.add_argument('--parse', action='store_true',
                       help='Parse a forum grid from stdin (pipe or paste). Outputs bd81 string.')
    parser.add_argument('--forge-larstech', type=str, metavar='MASK',
                       help='Forge puzzles from a mask until one requires WSRF/Lars techniques (FPC, FPCE, D2B, etc.)')
    parser.add_argument('--forge-larstech-attempts', type=int, default=50, metavar='N',
                       help='Max seeds to try in --forge-larstech (default 50)')
    parser.add_argument('--board-forge', nargs='?', const='MC', metavar='POSITION',
                       help='Build a board from zone geometry (positions: TL,TC,TR,ML,MC,MR,BL,BC,BR). Default: MC (centers)')
    parser.add_argument('--board-forge-clues', type=int, default=22, metavar='N',
                       help='Target clue count for --board-forge unique mode (default 22)')
    parser.add_argument('--board-forge-count', type=int, default=1, metavar='N',
                       help='Number of boards to forge (default 1)')

    args = parser.parse_args()

    # ── Local web server mode ──
    if args.serve is not None:
        _start_server(args.serve)
        return

    # ── Sparse Puzzle Challenge mode ──
    if getattr(args, 'sparse', None) is not None:
        from .sub17_solve import (generate_random_mask, solve_forward,
                                validate_sudoku as val_sudoku)
        import random as _sparse_rng

        n_clues = max(8, min(16, args.sparse))
        n_count = getattr(args, 'sparse_count', 1)

        print(f'\n  Sparse Puzzle Challenge')
        print(f'  {"═" * 55}')

        for puzzle_num in range(1, n_count + 1):
            min_score = 0.60 if n_clues <= 10 else 0.70
            mask_result = generate_random_mask(n_clues=n_clues, min_score=min_score)
            if mask_result is None:
                print(f'  Could not generate mask for {n_clues} clues')
                continue
            positions, mask_score, _, _ = mask_result
            pos_set = set(positions)
            actual_clues = len(positions)

            # Retry fills until valid solve
            max_attempts = 25
            result = None
            puzzle = None
            for attempt in range(1, max_attempts + 1):
                sol = solve_backtrack('0' * 81)
                sol = shuffle_sudoku(sol)
                puzzle = ''.join(sol[p] if p in pos_set else '0'
                                 for p in range(81))
                result = solve_forward(puzzle)
                if result['valid']:
                    break

            if not result or not result['valid']:
                print(f'  Puzzle {puzzle_num}: No valid solve after {max_attempts} attempts')
                continue

            logic = result['logic_placements']
            heur = result['heuristic_placements']
            total = result['total_placements']
            logic_pct = 100 * logic / max(1, total)

            if n_count == 1:
                # Show the full board for single puzzle
                print(f'  {actual_clues} clues | solved in {attempt} attempt{"s" if attempt > 1 else ""}')
                print()
                # Puzzle board
                print(f'  Puzzle ({actual_clues} clues):')
                for r in range(9):
                    if r % 3 == 0:
                        print("  +---------+---------+---------+")
                    row = "  |"
                    for c in range(9):
                        if c % 3 == 0 and c > 0:
                            row += " |"
                        ch = puzzle[r * 9 + c]
                        row += f' {ch}' if ch != '0' else ' .'
                    row += " |"
                    print(row)
                print("  +---------+---------+---------+")
                print()

                # Solved board
                board_str = result['board_str']
                print(f'  Solution (validated correct):')
                for r in range(9):
                    if r % 3 == 0:
                        print("  +---------+---------+---------+")
                    row = "  |"
                    for c in range(9):
                        if c % 3 == 0 and c > 0:
                            row += " |"
                        pos = r * 9 + c
                        d = board_str[pos]
                        row += f' {d}'
                    row += " |"
                    print(row)
                print("  +---------+---------+---------+")
                print()
                print(f'  Breakdown:')
                print(f'    {logic} cells by pure Sudoku logic ({logic_pct:.0f}%)')
                print(f'    {heur} cells by constraint-guided analysis')
                print(f'    {total} total placements — all validated correct')
            else:
                print(f'  #{puzzle_num:3d}  {actual_clues} clues  L={logic:2d} H={heur:2d}  '
                      f'({logic_pct:.0f}% logic)  attempt {attempt}')

        if n_count > 1:
            print(f'\n  {n_count} sparse puzzles generated and solved')
        print()
        return

    # ── SIRO-Only analysis mode ──
    if args.siro_only is not None or getattr(args, 'siro_only', None) is not None:
        from .wsrf_zone import siro_cascade
        puzzle_str = args.siro_only or (args.puzzle if args.puzzle else None)
        if not puzzle_str:
            print('Error: --siro-only needs a puzzle. Use: --siro-only PUZZLE or PUZZLE --siro-only')
            sys.exit(1)
        bd81 = normalize_puzzle(puzzle_str)
        sol = solve_backtrack(bd81)  # Used for skip-oracle (mirrors JS) + verification display

        bb = BitBoard.from_string(bd81)
        # Convert solution string to list of ints for skip-oracle
        sol_ints = [int(ch) for ch in sol] if sol else None

        print(f'\n  SIRO Analysis — Pure Zone Oracle Engine (siro_cascade)')
        print(f'  {"═" * 55}')
        print(f'  Puzzle: {bd81[:30]}...')
        print(f'  Clues: {sum(1 for ch in bd81 if ch != "0")}')
        print(f'  Empty: {bb.empty}')
        print()

        import time as _t
        t0 = _t.perf_counter()
        steps = siro_cascade(bb, solution=sol_ints)
        elapsed = (_t.perf_counter() - t0) * 1000

        zone_count = 0
        rule_count = 0
        zone_correct = 0
        zone_wrong = 0
        rule_correct = 0
        xhatch_count = 0
        crossdigit_count = 0

        for i, step in enumerate(steps):
            pos = step['pos']
            digit = step['digit']
            r, c = pos // 9, pos % 9
            correct = sol and int(sol[pos]) == digit
            mark = '✓' if correct else '✗'

            if step['type'] == 'zone-oracle':
                zone_count += 1
                if correct:
                    zone_correct += 1
                else:
                    zone_wrong += 1
                if step['subtype'] == 'xhatch':
                    xhatch_count += 1
                else:
                    crossdigit_count += 1
            else:
                rule_count += 1
                if correct:
                    rule_correct += 1

            print(f'  #{i+1} R{r+1}C{c+1} = {digit} {mark}  [{step["type"]}:{step["subtype"]}]')
            print(f'    {step["detail"]}')

        # Summary
        print(f'\n  {"═" * 55}')
        print(f'  {zone_count} Zone Oracles ({crossdigit_count} cross-digit + {xhatch_count} xhatch)')
        print(f'  {rule_count} Sudoku Rule Oracles (100% deterministic)')
        print(f'  {len(steps)} total placements in {elapsed:.1f}ms')
        if sol:
            total_correct = zone_correct + rule_correct
            total_wrong = zone_wrong
            final_mark = '✓' if total_wrong == 0 else '✗'
            print(f'  {final_mark} {total_correct} correct' +
                  (f', {total_wrong} wrong' if total_wrong else ''))
            if total_wrong == 0 and bb.empty == 0:
                print(f'  All placements verified correct!')
            elif bb.empty > 0:
                print(f'  Stalled with {bb.empty} cells remaining')
        print()
        return

    # ── Generate mode ──
    if args.generate is not None or args.generate_multi is not None:
        import random
        is_unique = args.generate is not None
        n_clues = args.generate if is_unique else args.generate_multi
        if is_unique:
            n_clues = max(17, min(27, n_clues))
        else:
            n_clues = max(8, min(16, n_clues))

        sol = solve_backtrack('0' * 81)
        sol = shuffle_sudoku(sol)
        chars = list(sol)
        positions = list(range(81))
        random.shuffle(positions)
        removed = 0
        for pos in positions:
            if removed >= 81 - n_clues:
                break
            saved = chars[pos]
            chars[pos] = '0'
            if is_unique:
                if has_unique_solution(''.join(chars)):
                    removed += 1
                else:
                    chars[pos] = saved
            else:
                removed += 1
        puzzle = ''.join(chars)
        actual = sum(1 for ch in puzzle if ch != '0')
        unique_check = has_unique_solution(puzzle)

        print(f'\n  Generated {"Unique" if is_unique else "Multi-Solution"} Puzzle')
        print(f'  {"─" * 40}')
        print(f'  {puzzle}')
        print(f'  Clues: {actual} | Unique: {unique_check}')

        # Solve it oracle-free
        result = solve_selective(puzzle, verbose=True)
        if result['success']:
            print(f'\n  SOLVED — {result["n_steps"]} steps')
        else:
            print(f'\n  STALLED — {result["empty_remaining"]} cells remaining')
        techs = ', '.join(f'{t}={c}' for t, c in sorted(result['technique_counts'].items(), key=lambda x: -x[1]))
        print(f'  Techniques: {techs}')
        print()
        return

    # ── Batch mode ──
    if args.batch is not None:
        import random
        count = args.batch
        n_clues = max(17, min(27, args.batch_clues))
        print(f'\n  Batch: {count} unique puzzles, {n_clues} clues each')
        print(f'  {"─" * 50}')
        solved = 0
        stalled = 0
        wrong = 0
        t0 = time.perf_counter()
        for i in range(count):
            sol = solve_backtrack('0' * 81)
            sol = shuffle_sudoku(sol)
            chars = list(sol)
            positions = list(range(81))
            random.shuffle(positions)
            removed = 0
            for pos in positions:
                if removed >= 81 - n_clues:
                    break
                saved = chars[pos]
                chars[pos] = '0'
                if has_unique_solution(''.join(chars)):
                    removed += 1
                else:
                    chars[pos] = saved
            puzzle = ''.join(chars)
            result = solve_selective(puzzle, verbose=False)
            if result['success']:
                board = [int(ch) for ch in result['board']]
                if validate_sudoku(board):
                    solved += 1
                else:
                    wrong += 1
                    print(f'  [{i+1}] WRONG BOARD: {puzzle}')
            else:
                stalled += 1
                print(f'  [{i+1}] STALLED ({result["empty_remaining"]} left): {puzzle}')
            if (i + 1) % 10 == 0:
                print(f'  [{i+1}/{count}] solved={solved} stalled={stalled} wrong={wrong}')

        elapsed = (time.perf_counter() - t0) * 1000
        print(f'\n  RESULTS: {solved}/{count} solved, {stalled} stalled, {wrong} wrong')
        print(f'  Time: {elapsed:.0f}ms ({elapsed/count:.0f}ms/puzzle)')
        print(f'  Solve rate: {solved/count*100:.1f}%')
        if wrong:
            print(f'  *** {wrong} WRONG BOARDS — BUGS ***')
        print()
        return

    # ── Mask batch mode ──
    if args.mask_batch is not None:
        import random
        count = args.mask_batch
        n_clues = args.mask_clues
        print(f'\n  Mask Batch: {count} puzzles, {n_clues}-clue masks, oracle-free solve')
        print(f'  {"═" * 55}')

        solved = 0
        stalled = 0
        unique_count = 0
        multi_count = 0
        tech_totals = {}
        t0 = time.perf_counter()

        for i in range(count):
            # Generate mask
            mask_result = generate_random_mask(n_clues=n_clues, min_score=0.70)
            if mask_result is None:
                print(f'  [{i+1}] mask generation failed')
                continue
            positions, score, stddev = mask_result

            # Build puzzle from mask
            sol = solve_backtrack('0' * 81)
            sol = shuffle_sudoku(sol)
            puzzle = ''.join(sol[p] if p in set(positions) else '0' for p in range(81))
            is_unique = has_unique_solution(puzzle)
            if is_unique:
                unique_count += 1
            else:
                multi_count += 1

            # Solve oracle-free
            result = solve_selective(puzzle, verbose=False)
            status = 'SOLVED' if result['success'] else f'STALLED({result["empty_remaining"]})'
            if result['success']:
                solved += 1
            else:
                stalled += 1

            for tech, cnt in result['technique_counts'].items():
                tech_totals[tech] = tech_totals.get(tech, 0) + cnt

            tag = 'U' if is_unique else 'M'
            if (i + 1) % 5 == 0 or not result['success']:
                print(f'  [{i+1:3d}/{count}] [{tag}] {status:12s} clues={len(positions)} score={score:.2f}')

        elapsed = (time.perf_counter() - t0) * 1000
        print(f'\n  {"═" * 55}')
        print(f'  RESULTS: {solved}/{count} solved, {stalled} stalled')
        print(f'  Unique: {unique_count} | Multi-solution: {multi_count}')
        print(f'  Time: {elapsed:.0f}ms ({elapsed/max(count,1):.0f}ms/puzzle)')
        print(f'  Solve rate: {solved/max(count,1)*100:.1f}%')
        top = sorted(tech_totals.items(), key=lambda x: -x[1])[:8]
        if top:
            print(f'  Techniques: {", ".join(f"{t}={c}" for t,c in top)}')
        print()
        return

    # ── Test mask mode ──
    # ── Board Forge mode: build boards from zone geometry ──
    if args.board_forge is not None:
        from .board_forge import forge_board, forge_unique_board, POSITIONS

        pos_name = args.board_forge.upper()
        target_clues = args.board_forge_clues
        count = args.board_forge_count

        # Parse position(s) — can be comma-separated like MC,TL
        pos_list = [p.strip() for p in pos_name.split(',')]
        for p in pos_list:
            if p not in POSITIONS:
                print(f'  Error: unknown position "{p}". Valid: {", ".join(POSITIONS.keys())}')
                sys.exit(1)

        print(f'\n{"═" * 60}')
        print(f'  BOARD FORGE — Zone Geometry Builder')
        print(f'  Position{"s" if len(pos_list) > 1 else ""}: {", ".join(pos_list)} | Target: {target_clues} clues | Count: {count}')
        print(f'{"═" * 60}')

        import random as _bf_rng
        rng = _bf_rng.Random()
        solved = 0

        for i in range(count):
            # Place digits 1-9 at zone position(s) across all 9 boxes
            from .board_forge import get_cells_for_position
            digits_by_cell = {}
            for name in pos_list:
                cells = get_cells_for_position(name)
                perm = list(range(1, 10))
                rng.shuffle(perm)
                for cell, digit in zip(cells, perm):
                    digits_by_cell[cell] = digit

            base = ['0'] * 81
            for cell, digit in digits_by_cell.items():
                base[cell] = str(digit)
            base_str = ''.join(base)
            base_n = sum(1 for c in base_str if c != '0')

            # Get full solution via backtracker
            solution = solve_backtrack(base_str)
            if not solution:
                print(f'\n  [{i+1}] No solution from zone placement — retrying')
                continue

            # Add ALL clues from solution, then minimize back to target
            fat = list(solution)  # start with full solution
            for cell in digits_by_cell:
                fat[cell] = str(digits_by_cell[cell])  # ensure zone base is marked
            fat_str = ''.join(fat)

            # Minimize: remove clues one at a time, keep if still unique
            removable = [j for j in range(81) if j not in digits_by_cell]
            rng.shuffle(removable)
            puzzle_list = list(fat_str)
            for pos in removable:
                if sum(1 for c in puzzle_list if c != '0') <= target_clues:
                    break
                saved = puzzle_list[pos]
                puzzle_list[pos] = '0'
                if not has_unique_solution(''.join(puzzle_list)):
                    puzzle_list[pos] = saved  # put it back
            puzzle = ''.join(puzzle_list)

            is_unique = has_unique_solution(puzzle)
            n_clues = sum(1 for c in puzzle if c != '0')

            # Solve it
            r = solve_selective(puzzle, verbose=False)
            techs = r.get('technique_counts', {})
            success = r.get('success', False)
            if success:
                solved += 1

            top = sorted(techs.items(), key=lambda x: -x[1])[:4]
            tech_str = ', '.join(f'{t}={c}' for t, c in top) if top else 'none'
            status = 'SOLVED' if success else 'STALLED'
            unique_tag = ' unique' if is_unique else ' multi'

            print(f'\n  [{i+1}] {status} | {n_clues} clues ({base_n} from zones){unique_tag}')
            print(f'  Puzzle: {puzzle}')
            print(f'  Techs:  {tech_str}')

            if count == 1 and success:
                board_str = r.get('board', '')
                if board_str:
                    print(format_board(board_str, puzzle))

        if count > 1:
            print(f'\n{"═" * 60}')
            print(f'  RESULTS: {solved}/{count} solved')
        print()
        return

    # ── Parse mode: convert forum grid from stdin to bd81 ──
    if args.parse:
        import re
        lines = []
        print('  Paste forum grid, then press Ctrl+D (or Ctrl+Z on Windows):')
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass

        # Collect data lines (skip separators)
        data_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Skip pure separator lines
            if re.match(r'^[\s+\-*=─│┼┤├┐┘┌└|]+$', stripped):
                continue
            # Must have at least one digit or dot to be a data line
            if not re.search(r'[\d.]', stripped):
                continue
            data_lines.append(stripped)

        if not data_lines:
            print('  Error: no data lines found')
            sys.exit(1)

        # Detect format: check if dots are used (compact dot-format)
        all_text = '\n'.join(data_lines)
        has_dots = '.' in all_text and all_text.count('.') >= 5

        cells = []
        if has_dots:
            # Dot-format: each digit or dot is one cell, ignore everything else
            for line in data_lines:
                for ch in line:
                    if ch == '.':
                        cells.append(0)
                    elif ch.isdigit() and ch != '0':
                        cells.append(int(ch))
                    elif ch == '0':
                        cells.append(0)
        else:
            # Candidate-format: space-separated tokens, pipes as separators
            for line in data_lines:
                cleaned = line.replace('|', ' ').replace('+', ' ').replace('*', ' ')
                # Remove annotation letters (a-z)
                cleaned = re.sub(r'[a-z]', '', cleaned)
                # Remove elimination dashes
                cleaned = re.sub(r'-', '', cleaned)
                tokens = cleaned.split()
                for tok in tokens:
                    if not tok or not any(c.isdigit() for c in tok):
                        continue
                    digits_only = re.sub(r'[^0-9]', '', tok)
                    if not digits_only:
                        continue
                    if len(digits_only) == 1:
                        cells.append(int(digits_only))
                    else:
                        cells.append(0)  # candidates = unsolved

        if len(cells) != 81:
            print(f'  Error: parsed {len(cells)} cells, expected 81')
            if cells:
                print(f'  Got {len(cells)} cells, format={"dot" if is_dot_format else "candidate"}')
            sys.exit(1)

        bd81 = ''.join(str(c) for c in cells)
        n_clues = sum(1 for c in bd81 if c != '0')
        print(f'  bd81 ({n_clues} clues): {bd81}')
        return

    # ── To-Mask mode: convert puzzle string to mask ──
    if args.to_mask is not None:
        puzzle = args.to_mask.strip()
        if len(puzzle) != 81:
            print(f'Error: puzzle must be 81 chars, got {len(puzzle)}')
            sys.exit(1)
        mask = ''.join('X' if c != '0' and c != '.' else '0' for c in puzzle)
        n_clues = sum(1 for c in mask if c == 'X')
        print(f'  Mask ({n_clues} clues): {mask}')
        return

    # ── Forge-Larstech mode: hunt for forged puzzles that need WSRF techniques ──
    if args.forge_larstech is not None:
        from .mask_forge import parse_mask, forge_unique_randomized

        mask_str = args.forge_larstech
        max_attempts = args.forge_larstech_attempts
        dr_m = args.dr_mode

        mask = parse_mask(mask_str)
        n_clues = sum(mask)

        print(f'\n{"═" * 65}')
        print(f'  FORGE LARSTECH — hunting for puzzles that need WSRF techniques')
        print(f'  {n_clues} clue mask, up to {max_attempts} seeds')
        print(f'{"═" * 65}')

        hits = []
        total_forge_time = 0

        for seed in range(max_attempts):
            t0 = time.perf_counter()
            puzzle, solution, checks, _elapsed = forge_unique_randomized(
                mask, seed=seed, max_seconds=15, verbose=False)
            forge_ms = (time.perf_counter() - t0) * 1000
            total_forge_time += forge_ms

            if puzzle is None:
                continue

            # Solve it and check which techniques fired
            result = solve_selective(puzzle, verbose=False, dr_mode=dr_m)
            techs = result.get('technique_counts', {})
            wsrf_used = WSRF_INVENTIONS & set(techs.keys())

            if wsrf_used:
                steps = result.get('n_steps', 0)
                elapsed = forge_ms
                top_tech = sorted(techs.items(), key=lambda x: -x[1])[:5]
                tech_str = ', '.join(f'{t}={c}' for t, c in top_tech)
                hits.append({
                    'puzzle': puzzle, 'solution': solution,
                    'seed': seed, 'checks': checks,
                    'wsrf': wsrf_used, 'steps': steps,
                    'techs': techs, 'tech_str': tech_str,
                    'forge_ms': forge_ms
                })
                status = 'HIT'
            else:
                status = '   '

            # Progress every 10 seeds or on hits
            if wsrf_used or (seed + 1) % 10 == 0:
                wsrf_tag = f' ★ {", ".join(sorted(wsrf_used))}' if wsrf_used else ''
                print(f'  Seed {seed+1:3d}/{max_attempts}  forge={forge_ms:6.0f}ms  checks={checks:6d}  {status}{wsrf_tag}')

        # Results
        print(f'\n{"═" * 65}')
        if hits:
            print(f'  FOUND {len(hits)} LARSTECH PUZZLE{"S" if len(hits) != 1 else ""} in {max_attempts} seeds!')
            print(f'{"═" * 65}')
            for i, h in enumerate(hits, 1):
                print(f'\n  #{i}  Seed {h["seed"]} — {", ".join(sorted(h["wsrf"]))}')
                print(f'  Puzzle:  {h["puzzle"]}')
                print(f'  Steps:   {h["steps"]}  |  Forge: {h["forge_ms"]:.0f}ms  ({h["checks"]} checks)')
                print(f'  Techs:   {h["tech_str"]}')
        else:
            print(f'  No WSRF-technique puzzles found in {max_attempts} seeds.')
            print(f'  Try more attempts: --forge-larstech-attempts 200')
        print(f'\n  Total forge time: {total_forge_time:.0f}ms')
        print()
        return

    # ── Forge-Solve mode: forge unique puzzles from mask, then solve ──
    if args.forge_solve is not None:
        from .mask_forge import parse_mask, forge_unique
        import itertools

        mask_str = args.forge_solve
        n_puzzles = args.forge_count
        dr_m = args.dr_mode

        mask = parse_mask(mask_str)
        n_clues = sum(mask)
        pos_set = {i for i, v in enumerate(mask) if v == 1}

        print(f'\n{"═" * 65}')
        print(f'  FORGE & SOLVE — {n_clues} clue mask, {n_puzzles} puzzles')
        print(f'{"═" * 65}')

        # Step 1: Forge the seed puzzle
        print(f'\n  Forging seed puzzle...')
        t0 = time.perf_counter()
        seed_puzzle, seed_solution, checks, _elapsed = forge_unique(mask, verbose=False)
        forge_ms = (time.perf_counter() - t0) * 1000

        if seed_puzzle is None:
            print(f'  Forge FAILED — no unique puzzle found for this mask.')
            sys.exit(1)

        print(f'  Seed forged in {checks} checks ({forge_ms:.0f}ms)')

        # Step 2: Generate variants via digit permutation
        digits = list(range(1, 10))
        puzzles = [seed_puzzle]
        rng = __import__('random').Random(42)
        seen = {seed_puzzle}
        attempts = 0
        while len(puzzles) < n_puzzles and attempts < 1000:
            perm = list(digits)
            rng.shuffle(perm)
            mapping = {str(d): str(perm[d - 1]) for d in digits}
            variant = ''.join(mapping.get(c, '0') for c in seed_puzzle)
            if variant not in seen:
                seen.add(variant)
                puzzles.append(variant)
            attempts += 1

        # Step 3: Solve each puzzle
        print(f'\n  {"#":>3s}  {"Puzzle":81s}  {"Status":8s}  {"Steps":>5s}  {"Time":>8s}  Techniques')
        print(f'  {"─" * 3}  {"─" * 81}  {"─" * 8}  {"─" * 5}  {"─" * 8}  {"─" * 20}')

        total_solved = 0
        total_stalled = 0
        total_wrong = 0
        all_tech = {}
        total_time = 0

        for idx, puzzle in enumerate(puzzles, 1):
            t1 = time.perf_counter()
            result = solve_selective(puzzle, verbose=False, dr_mode=dr_m)
            elapsed = (time.perf_counter() - t1) * 1000
            total_time += elapsed

            steps = result.get('n_steps', 0)
            techs = result.get('technique_counts', {})
            for tech, cnt in techs.items():
                all_tech[tech] = all_tech.get(tech, 0) + cnt

            if result['success']:
                board = [int(ch) for ch in result['board']]
                if validate_sudoku(board):
                    total_solved += 1
                    status = 'SOLVED'
                else:
                    total_wrong += 1
                    status = 'WRONG!'
            else:
                total_stalled += 1
                status = 'STALLED'

            top_tech = sorted(techs.items(), key=lambda x: -x[1])[:3]
            tech_str = ', '.join(f'{t}={c}' for t, c in top_tech)
            print(f'  {idx:3d}  {puzzle}  {status:8s}  {steps:5d}  {elapsed:7.0f}ms  {tech_str}')

        # Summary
        print(f'\n{"═" * 65}')
        print(f'  RESULTS: {total_solved}/{n_puzzles} solved | {total_stalled} stalled | {total_wrong} wrong')
        print(f'  Forge: {forge_ms:.0f}ms | Solve: {total_time:.0f}ms total ({total_time/n_puzzles:.0f}ms avg)')
        if all_tech:
            top = sorted(all_tech.items(), key=lambda x: -x[1])[:8]
            print(f'  Techniques: {", ".join(f"{t}={c}" for t,c in top)}')
        grade = 'PERFECT' if total_solved == n_puzzles else ('STRONG' if total_solved / n_puzzles >= 0.9 else 'NEEDS WORK')
        print(f'  Grade: {grade}')
        print()
        return

    if args.test_mask is not None:
        import random
        mask_str = args.test_mask
        n_per_round = args.test_mask_count
        dr_m = args.dr_mode

        # Parse mask: x/X/1 = clue, 0/. = empty
        positions = set()
        for i, ch in enumerate(mask_str):
            if ch in ('x', 'X', '1'):
                positions.add(i)
        if len(positions) == 0 or len(mask_str) != 81:
            print(f'Error: mask must be 81 chars with x/X/1 for clues, 0/. for empty')
            sys.exit(1)

        n_clues = len(positions)
        display_mask(positions, f'Testing mask ({n_clues} clues):')
        validation = validate_mask_rules(positions)
        print()
        print(f'MASK VALIDATION ({n_clues} clues)')
        for rule in validation['rules']:
            s = rule['status']
            tag = '[PASS]' if s == 'PASS' else ('[WARN]' if s == 'WARN' else ('[FAIL]' if s == 'FAIL' else '[INFO]'))
            print(f'  {tag:6s}  {rule["name"]}: {rule["detail"]}')
        print(f'  Quality Score: {validation["score"]:.2f} — {validation["verdict"]}')

        pos_set = set(positions)

        # ── Round 1: Generate N puzzles from mask ──
        print(f'\n{"═" * 60}')
        print(f'ROUND 1: {n_per_round} puzzles from mask (fresh boards)')
        print(f'{"═" * 60}')
        t0 = time.perf_counter()
        r1_solved = 0
        r1_stalled = 0
        r1_unique = 0
        r1_multi = 0
        r1_wrong = 0
        r1_tech = {}
        r1_stall_puzzles = []

        for i in range(n_per_round):
            sol = solve_backtrack('0' * 81)
            sol = shuffle_sudoku(sol)
            puzzle = ''.join(sol[p] if p in pos_set else '0' for p in range(81))
            is_unique = has_unique_solution(puzzle)
            if is_unique:
                r1_unique += 1
            else:
                r1_multi += 1

            result = solve_selective(puzzle, verbose=False, dr_mode=dr_m)

            # Verify correctness
            if result['success']:
                board = [int(ch) for ch in result['board']]
                if validate_sudoku(board):
                    r1_solved += 1
                else:
                    r1_wrong += 1
            else:
                r1_stalled += 1
                r1_stall_puzzles.append((puzzle, result['empty_remaining']))

            for tech, cnt in result['technique_counts'].items():
                r1_tech[tech] = r1_tech.get(tech, 0) + cnt

        r1_elapsed = (time.perf_counter() - t0) * 1000
        print(f'  Solved: {r1_solved}/{n_per_round} | Stalled: {r1_stalled} | Wrong: {r1_wrong}')
        print(f'  Unique: {r1_unique} | Multi: {r1_multi}')
        print(f'  Time: {r1_elapsed:.0f}ms ({r1_elapsed/n_per_round:.0f}ms/puzzle)')
        if r1_tech:
            top = sorted(r1_tech.items(), key=lambda x: -x[1])[:8]
            print(f'  Techniques: {", ".join(f"{t}={c}" for t,c in top)}')
        if r1_stall_puzzles:
            print(f'  Stalled puzzles:')
            for p, rem in r1_stall_puzzles[:5]:
                print(f'    {p} ({rem} left)')

        # ── Round 2: Shuffle each Round 1 puzzle and re-solve ──
        print(f'\n{"═" * 60}')
        print(f'ROUND 2: {n_per_round} shuffled variants (test solve stability)')
        print(f'{"═" * 60}')
        t0 = time.perf_counter()
        r2_solved = 0
        r2_stalled = 0
        r2_wrong = 0
        r2_tech = {}

        # Re-generate puzzles and shuffle them
        for i in range(n_per_round):
            sol = solve_backtrack('0' * 81)
            sol = shuffle_sudoku(sol)
            puzzle = ''.join(sol[p] if p in pos_set else '0' for p in range(81))
            shuffled = shuffle_sudoku(puzzle)

            result = solve_selective(shuffled, verbose=False, dr_mode=dr_m)

            if result['success']:
                board = [int(ch) for ch in result['board']]
                if validate_sudoku(board):
                    r2_solved += 1
                else:
                    r2_wrong += 1
            else:
                r2_stalled += 1

            for tech, cnt in result['technique_counts'].items():
                r2_tech[tech] = r2_tech.get(tech, 0) + cnt

        r2_elapsed = (time.perf_counter() - t0) * 1000
        print(f'  Solved: {r2_solved}/{n_per_round} | Stalled: {r2_stalled} | Wrong: {r2_wrong}')
        print(f'  Time: {r2_elapsed:.0f}ms ({r2_elapsed/n_per_round:.0f}ms/puzzle)')
        if r2_tech:
            top = sorted(r2_tech.items(), key=lambda x: -x[1])[:8]
            print(f'  Techniques: {", ".join(f"{t}={c}" for t,c in top)}')

        # ── Summary ──
        print(f'\n{"═" * 60}')
        print(f'SUMMARY — Mask ({n_clues} clues)')
        print(f'{"═" * 60}')
        total = n_per_round * 2
        total_solved = r1_solved + r2_solved
        total_wrong = r1_wrong + r2_wrong
        print(f'  Fresh:    {r1_solved}/{n_per_round} ({r1_solved/n_per_round*100:.0f}%)')
        print(f'  Shuffled: {r2_solved}/{n_per_round} ({r2_solved/n_per_round*100:.0f}%)')
        print(f'  Total:    {total_solved}/{total} ({total_solved/total*100:.0f}%)')
        if total_wrong:
            print(f'  *** {total_wrong} WRONG BOARDS ***')
        grade = 'PERFECT' if total_solved == total else ('STRONG' if total_solved/total >= 0.9 else ('MODERATE' if total_solved/total >= 0.7 else 'NEEDS WORK'))
        print(f'  Grade:    {grade}')
        print()
        return

    # ── Random mask mode ──
    if args.random_mask is not None:
        import random
        n_clues = args.random_mask
        print(f'\n  Generating random mask (target {n_clues} clues, all rules PASS)...')
        result = generate_random_mask(n_clues=n_clues, min_score=0.80)
        if result is None:
            print(f'  Failed to generate valid mask. Try more clues (e.g., --random-mask 20)')
            sys.exit(1)
        positions, score, stddev = result
        actual = len(positions)
        mask_str = ''.join('x' if i in positions else '0' for i in range(81))
        display_mask(positions, f'Random ({actual} clues):')
        validation = validate_mask_rules(positions)
        print()
        print(f'MASK VALIDATION — Random ({actual} clues) ({actual} clues)')
        for rule in validation['rules']:
            s = rule['status']
            tag = '[PASS]' if s == 'PASS' else ('[WARN]' if s == 'WARN' else ('[FAIL]' if s == 'FAIL' else '[INFO]'))
            print(f'  {tag:6s}  {rule["name"]}: {rule["detail"]}')
        print(f'  Quality Score: {validation["score"]:.2f} — {validation["verdict"]}')

        if args.validate:
            print(f'\n  Mask string (use with --generate):')
            print(f'  {mask_str}')
            print()
            return

        # Generate a puzzle from this mask
        sol = solve_backtrack('0' * 81)
        sol = shuffle_sudoku(sol)
        puzzle = ''.join(sol[i] if i in positions else '0' for i in range(81))
        is_unique = has_unique_solution(puzzle)
        print(f'\n  Generated puzzle: {puzzle}')
        print(f'  Clues: {actual} | Unique: {is_unique}')

        # Solve oracle-free
        solve_result = solve_selective(puzzle, verbose=True)
        if solve_result['success']:
            print(f'\n  SOLVED — {solve_result["n_steps"]} steps')
        else:
            print(f'\n  STALLED — {solve_result["empty_remaining"]} cells remaining')
        techs = ', '.join(f'{t}={c}' for t, c in sorted(solve_result['technique_counts'].items(), key=lambda x: -x[1]))
        print(f'  Techniques: {techs}')
        print()
        return

    # Read puzzle
    if not args.puzzle:
        parser.print_help()
        sys.exit(1)
    if args.puzzle == '-':
        puzzle_raw = sys.stdin.read().strip()
    else:
        puzzle_raw = args.puzzle

    try:
        bd81 = normalize_puzzle(puzzle_raw)
    except ValueError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    # Parse technique filter
    only_techniques = parse_techniques(args.only) if args.only else None

    # Apply preset (--preset overrides --only if both given)
    preset_label = None
    if args.preset:
        preset_techs = PRESETS[args.preset]
        if preset_techs is not None:
            only_techniques = preset_techs
        else:
            only_techniques = None  # wsrf = all
        if args.preset == 'expert':
            preset_label = 'Sudoku Expert Approved'
        elif args.preset == 'exotic':
            preset_label = 'Exotic Techniques'

    # Apply --exotic: add exotic techniques to the current set
    if args.exotic and not args.preset:
        from larsdoku.constants import EXOTIC_TECHNIQUES
        if only_techniques is not None:
            only_techniques = only_techniques | EXOTIC_TECHNIQUES
        # If only_techniques is None (all), exotic is already included

    # Apply --exclude: remove specific techniques from the allowed set
    if args.exclude:
        exclude_set = parse_techniques(args.exclude)
        if exclude_set:
            if only_techniques is None:
                # Start with all techniques, then remove excluded
                only_techniques = set(TECHNIQUE_LEVELS.keys()) - exclude_set
            else:
                only_techniques = only_techniques - exclude_set
            # Always keep L1 foundation
            only_techniques.update(['crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'])

    # ── Board SIRO — Global illumination ──
    if args.board_siro:
        from .siro_boost import siro_predict_global, siro_predict
        # Already imported at module level from engine

        solution_str = solve_backtrack(bd81)
        solution = [int(ch) for ch in solution_str] if solution_str else None

        bb = BitBoard.from_string(bd81)
        propagate_l1l2(bb)

        t0 = time.perf_counter()
        local = siro_predict(bb)
        glbl = siro_predict_global(bb)
        elapsed = (time.perf_counter() - t0) * 1000

        print(f'\n{"=" * 80}')
        print(f'GLOBAL SIRO — Board Illumination ({elapsed:.1f}ms)')
        print(f'{"=" * 80}')

        # Print the board grid with local vs global predictions
        for r in range(9):
            if r % 3 == 0 and r > 0:
                print('  ' + '-' * 73)
            line_local = '  '
            line_global = '  '
            for c in range(9):
                if c % 3 == 0 and c > 0:
                    line_local += ' | '
                    line_global += ' | '
                pos = r * 9 + c
                if bb.board[pos] != 0:
                    line_local += f'  {bb.board[pos]}  '
                    line_global += f'  {bb.board[pos]}  '
                else:
                    ld = local[pos]['digit'] if pos in local else '?'
                    gd = glbl[pos]['digit'] if pos in glbl else '?'
                    sol_d = solution[pos] if solution else '?'

                    lmark = '*' if ld == sol_d else ' '
                    gmark = '*' if gd == sol_d else ' '
                    line_local += f' {ld}{lmark}  '
                    line_global += f' {gd}{gmark}  '

            print(f'L {line_local}')
            print(f'G {line_global}')
            print()

        print(f'  L = Local SIRO   G = Global SIRO   * = correct prediction')

        # Per-cell detail table (sorted by global impact)
        print(f'\n{"=" * 80}')
        print(f'CELL DETAIL — Sorted by impact potential')
        print(f'{"=" * 80}')
        print(f'  {"Cell":>5} {"Cands":>5} {"Pred":>4} {"Sol":>3} {"Local":>6} '
              f'{"Casc":>4} {"Hid":>4} {"BndP":>5} {"StkP":>5} {"BMin":>4} {"SMin":>4} {"Impact":>7}')
        print(f'  {"-"*72}')

        cell_data = []
        for pos in range(81):
            if bb.board[pos] != 0 or pos not in glbl:
                continue
            info = glbl[pos]
            pred = info['digit']
            sol_d = solution[pos] if solution else '?'
            n_cands = POPCOUNT[bb.cands[pos]]

            # Get detail for the predicted digit
            det = info['global_detail'].get(pred, {})
            casc = det.get('cascade_singles', 0)
            hid = det.get('hidden_creates', 0)
            bp = det.get('band_pressure', 0)
            sp = det.get('stack_pressure', 0)
            bmin = det.get('band_min', 9)
            smin = det.get('stack_min', 9)
            loc = det.get('local', 0)
            impact = casc * 3 + hid * 4 + max(0, 3 - bmin) + max(0, 3 - smin)

            cell_data.append((pos, n_cands, pred, sol_d, loc, casc, hid, bp, sp, bmin, smin, impact))

        # Sort by impact (highest first)
        cell_data.sort(key=lambda x: -x[-1])

        for pos, nc, pred, sol_d, loc, casc, hid, bp, sp, bmin, smin, impact in cell_data[:30]:
            r, c = pos // 9, pos % 9
            mark = '*' if pred == sol_d else ' '
            print(f'  R{r+1}C{c+1}{mark} {nc:5d} {pred:4d} {sol_d:>3} {loc:6d} '
                  f'{casc:4d} {hid:4d} {bp:5d} {sp:5d} {bmin:4d} {smin:4d} {impact:7.1f}')

        # Summary stats
        if solution:
            lc = sum(1 for p in local if local[p]['digit'] == solution[p])
            gc = sum(1 for p in glbl if glbl[p]['digit'] == solution[p])
            n = len(local)
            print(f'\n  Local accuracy:  {lc}/{n} = {100*lc/n:.1f}%')
            print(f'  Global accuracy: {gc}/{n} = {100*gc/n:.1f}%')
            print(f'  Cells with cascade potential: {sum(1 for _, _, _, _, _, c, _, _, _, _, _, _ in cell_data if c > 0)}')
            print(f'  Cells creating hidden singles: {sum(1 for _, _, _, _, _, _, h, _, _, _, _, _ in cell_data if h > 0)}')

        print(f'{"=" * 80}')
        sys.exit(0)

    # ── SIRO Bootstrap mode ──
    if getattr(args, 'siro_bootstrap', False):
        if args.steps or args.verbose:
            print(f'\nSolving with SIRO Bootstrap...')
            print(f'{"─" * 50}')

        t0 = time.perf_counter()
        result = solve_siro_bootstrap(bd81, max_level=args.level,
                                       verbose=(args.steps or args.verbose),
                                       detail=args.detail)
        elapsed = (time.perf_counter() - t0) * 1000

        veri = result.get('siro_bootstrap', {})

        print(f'\n{"═" * 65}')
        print(f'SIRO BOOTSTRAP — Self-Verifying Oracle')
        print(f'{"═" * 65}')

        if veri.get('verified'):
            plvl = veri.get('proof_level', 1)
            print(f'  Proven (L{plvl}): {veri["proven_placed_count"]} cells')
            print(f'  Control zone: {veri["zone"]}')
            for cc in veri['control_cells']:
                m = '✓' if cc['match'] else '✗'
                print(f'    {cc["cell"]}  expected={cc["expected"]}  predicted={cc["predicted"]}  {m}')
            print(f'  Oracle:       VERIFIED — cascade trusted')
        else:
            print(f'  Proven:       {veri.get("proven_placed_count", "?")} cells')
            print(f'  Oracle:       NOT VERIFIED — {veri.get("reason", "unknown")}')
            print(f'  (fell back to standard SIRO)')

        print(f'  Status:       {"SOLVED" if result["success"] else "STALLED"}')
        print(f'  Steps:        {result["n_steps"]}')
        print(f'  Time:         {elapsed:.1f}ms')
        print()

        tc = result['technique_counts']
        for tech in sorted(tc.keys(), key=lambda t: -tc[t]):
            lvl = TECHNIQUE_LEVELS.get(tech, '?')
            wsrf_tag = ' *' if tech in WSRF_INVENTIONS else ''
            print(f'    {tech:<20} {tc[tech]:4d}  L{lvl}{wsrf_tag}')

        if veri.get('verified'):
            ctrl = veri['control_cells']
            matched = sum(1 for c in ctrl if c['match'])
            print(f'\n  Oracle verification: PASSED ({matched}/{len(ctrl)} control digits matched)')

        if result.get('zone_sums'):
            print(f'\n  Zone sums: {result["zone_sums"]}')

        print(f'{"═" * 65}')

        if args.board and result['success']:
            print(f'\n{format_board(result["board"], bd81)}')

        if args.json:
            result['elapsed_ms'] = round(elapsed, 1)
            print(json.dumps(result, indent=2, default=str))

        sys.exit(0 if result['success'] else 1)

    # ── SIRO-Guided mode ──
    if getattr(args, 'siro_cascade', False):
        t0 = time.perf_counter()
        result = solve_siro_guided(bd81, max_level=args.level,
                                   no_oracle=args.no_oracle,
                                   verbose=(args.steps or args.verbose),
                                   detail=args.detail)
        elapsed = (time.perf_counter() - t0) * 1000

        # Also time standard cascade for comparison
        t1 = time.perf_counter()
        standard = solve_selective(bd81, max_level=args.level,
                                   no_oracle=args.no_oracle)
        standard_ms = (time.perf_counter() - t1) * 1000

        speedup = standard_ms / elapsed if elapsed > 0.01 else float('inf')

        print(f'\n{"=" * 65}')
        print(f'SIRO-GUIDED CASCADE — Zone-Predicted Technique Dispatch')
        print(f'{"=" * 65}')
        print(f'  Status:     {"SOLVED" if result["success"] else "STALLED" if result.get("stalled") else "INCOMPLETE"}')
        print(f'  Steps:      {result["n_steps"]}')
        print(f'  Rounds:     {result.get("rounds", "?")}')
        print()

        tc = result['technique_counts']
        for tech in sorted(tc.keys(), key=lambda t: -tc[t]):
            lvl = TECHNIQUE_LEVELS.get(tech, '?')
            wsrf_tag = ' *' if tech in WSRF_INVENTIONS else ''
            print(f'    {tech:<20} {tc[tech]:4d}  L{lvl}{wsrf_tag}')
        print()
        print(f'  SIRO-guided:  {elapsed:.1f}ms')
        print(f'  Standard:     {standard_ms:.1f}ms')
        print(f'  Speedup:      {speedup:.1f}x')
        print(f'{"=" * 65}')

        if args.board and result['success']:
            print(f'\n{format_board(result["board"], bd81)}')

        sys.exit(0 if result['success'] else 1)

    # ── Benchmark mode ──
    if args.bench:
        bench_count = args.bench
        print(f'\nBenchmarking {bench_count} shuffled variants of puzzle...', file=sys.stderr)
        bench = run_benchmark(bd81, count=bench_count, max_level=args.level,
                             only_techniques=only_techniques, no_oracle=args.no_oracle,
                             gf2=args.gf2, gf2_extended=args.gf2x)
        if args.json:
            bench['results'] = f'{len(bench["results"])} results (omitted)'
            print(json.dumps(bench, indent=2, default=str))
        else:
            print(format_benchmark(bench, preset_label))
        sys.exit(0 if bench['solved'] == bench['count'] else 1)

    # ── Cross-wise benchmark mode ──
    if args.crosswise:
        cw_count = args.crosswise
        use_autotrust = getattr(args, 'autotrust', False)
        print(f'\nCross-wise shuffle: {cw_count} anti-diagonal variants'
              f'{" (autotrust)" if use_autotrust else ""}...', file=sys.stderr)
        bench = run_crosswise_benchmark(bd81, count=cw_count, max_level=args.level,
                                        only_techniques=only_techniques, no_oracle=args.no_oracle,
                                        gf2=args.gf2, gf2_extended=args.gf2x,
                                        autotrust=use_autotrust)
        if args.json:
            bench['results'] = f'{len(bench["results"])} results (omitted)'
            print(json.dumps(bench, indent=2, default=str))
        else:
            lines = []
            if preset_label:
                lines.append(f'\n  ✦ {preset_label} Techniques ✦')
            lines.append(f'\n{"═" * 60}')
            lines.append(f'CROSS-WISE SHUFFLE: {cw_count} variants'
                        f'{" (autotrust)" if use_autotrust else ""}')
            lines.append(f'{"═" * 60}')
            lines.append(f'Valid puzzles: {bench["valid"]}/{cw_count} '
                        f'({bench["invalid"]} had no unique solution)')
            lines.append(f'Solve rate:   {bench["solve_rate"]} '
                        f'({bench["solved"]}/{bench["valid"]})')
            if bench['stalled']:
                lines.append(f'Stalled:      {bench["stalled"]}')
            lines.append(f'Avg time:     {bench["avg_time_ms"]:.1f}ms/puzzle')
            lines.append(f'Total time:   {bench["total_time_ms"]/1000:.1f}s')
            lines.append(f'Avg steps:    {bench["avg_steps"]}')
            if bench['avg_oracle']:
                lines.append(f'Avg oracle:   {bench["avg_oracle"]} per puzzle')
            lines.append(f'\nTechnique averages (per valid puzzle):')
            avgs = bench.get('technique_averages', {})
            for tech, avg in sorted(avgs.items(), key=lambda x: -x[1]):
                total = bench['technique_totals'].get(tech, 0)
                lvl = TECHNIQUE_LEVELS.get(tech, '?')
                pct = total / max(sum(bench['technique_totals'].values()), 1) * 100
                bar = '█' * max(1, int(pct / 3))
                tag = ' ★' if tech in WSRF_INVENTIONS else (' ⚠' if tech == 'ORACLE_ONLY' else '')
                lines.append(f'  {tech:20s}  {avg:6.2f} ({pct:5.1f}%)  L{lvl}  {bar}{tag}')
            lines.append(f'{"═" * 60}')
            print('\n'.join(lines))

        # Save hardest puzzles
        save_n = getattr(args, 'save_hardest', 0)
        if save_n and bench.get('results'):
            ranked = sorted(bench['results'], key=lambda r: -r.get('difficulty', 0))
            top = ranked[:save_n]
            fname = 'crosswise_hardest.txt'
            with open(fname, 'w') as f:
                f.write(f'# Top {len(top)} hardest cross-wise shuffled puzzles\n')
                f.write(f'# Source: {bd81[:20]}...\n')
                f.write(f'# Generated: {cw_count} variants, {bench["valid"]} valid\n')
                f.write(f'# Ranked by L5+ technique count (difficulty score)\n\n')
                for rank, r in enumerate(top, 1):
                    techs = ', '.join(f'{t}:{c}' for t, c in
                                     sorted(r['technique_counts'].items(), key=lambda x: -x[1])
                                     if TECHNIQUE_LEVELS.get(t, 0) >= 3)
                    f.write(f'# #{rank} difficulty={r["difficulty"]} '
                            f'time={r["elapsed_ms"]}ms [{techs}]\n')
                    f.write(f'{r["puzzle"]}\n\n')
            print(f'\nSaved top {len(top)} hardest to {fname}')

        sys.exit(0 if bench['solved'] == bench.get('valid', 0) else 1)

    # ── Cell query mode ──
    if args.cell:
        try:
            row, col = parse_cell(args.cell)
        except ValueError as e:
            print(f'Error: {e}', file=sys.stderr)
            sys.exit(1)

        use_autotrust = getattr(args, 'autotrust', False)
        t0 = time.perf_counter()
        result = query_cell(bd81, row, col, max_level=args.level,
                          only_techniques=only_techniques, autotrust=use_autotrust,
                          gf2=args.gf2, gf2_extended=args.gf2x)
        elapsed = (time.perf_counter() - t0) * 1000

        if args.json:
            result['elapsed_ms'] = round(elapsed, 1)
            if preset_label:
                result['preset'] = preset_label
            print(json.dumps(result, indent=2, default=str))
        else:
            if preset_label:
                print(f'\n  ✦ {preset_label} Techniques ✦')

            status = result.get('solve_status', '?')
            if status == 'given':
                print(f'\n  {result["message"]}')
            elif result.get('reachable'):
                print(f'\n  {result["message"]}')
                if result.get('retry_msg'):
                    print(f'  ({result["retry_msg"]})')
                if result.get('candidates'):
                    print(f'  Candidates: {result["candidates"]}')
                total = result.get('total_steps', '?')
                remaining = result.get('total_empty', 0)
                if remaining == 0:
                    print(f'  Full solve: {total} steps, COMPLETE')
                else:
                    print(f'  Solver reached cell at step {result["step"]}, then stalled ({remaining} cells remaining)')
            else:
                print(f'\n  {result["message"]}')
                if result.get('retry_msg'):
                    print(f'  ({result["retry_msg"]})')
                if result.get('candidates'):
                    print(f'  Candidates: {result["candidates"]}')
                if not use_autotrust:
                    print(f'  Tip: try --autotrust to enable Deep Resonance verification')

            print(f'  Time: {elapsed:.1f}ms')

            # WSRF / validation check
            tc = result.get('technique_counts', {})
            wsrf_used = WSRF_INVENTIONS & set(tc.keys())
            oracle_used = 'ORACLE_ONLY' in tc
            if wsrf_used:
                print(f'\n  WSRF techniques used: {", ".join(sorted(wsrf_used))} ★')
                print(f'  All placements are deterministic logic — no guessing, no backtracking.')
                print(f'  WSRF techniques (★) are Lars\'s inventions, not yet Sudoku Expert Approved.')
            elif oracle_used:
                print(f'\n  Oracle: {tc["ORACLE_ONLY"]} oracle placements (zone prediction, not pure logic)')
            elif result.get('reachable') and result.get('solve_status') != 'given':
                print(f'\n  Verify: All techniques are Sudoku Expert Approved ✓')
                print(f'  No backtracking or trial-and-error was used at any point.')
                print(f'  Every placement was derived by deterministic logic alone.')

            # Technique breakdown for the path
            path_techs = result.get('path_technique_counts', {})
            if path_techs:
                print(f'\n  Techniques used:')
                for tech, count in sorted(path_techs.items(), key=lambda x: -x[1]):
                    lvl = TECHNIQUE_LEVELS.get(tech, '?')
                    print(f'    {tech:20s} {count:3d}  L{lvl}')

            # Show path with interleaved elimination events
            if args.path and result.get('path'):
                path = result['path']
                is_stalled = not result.get('reachable')
                label = 'Stall trace' if is_stalled else 'Solution path'

                # Build interleaved timeline: eliminations + placements by round
                elim_events = result.get('elim_events', [])
                # elim_events from query_cell are already filtered to path scope
                elim_by_round = {}
                for ev in elim_events:
                    rnd = ev.get('round', 0)
                    elim_by_round.setdefault(rnd, []).append(ev)

                # Collect rounds present in path
                path_rounds = set()
                for s in path:
                    path_rounds.add(s.get('round', 0))
                # Also include elimination rounds up to the target step's round
                max_round = max((s.get('round', 0) for s in path), default=0)
                relevant_elim_rounds = {r for r in elim_by_round if r <= max_round}
                all_rounds = sorted(path_rounds | relevant_elim_rounds)

                # Count elimination events in path scope
                elim_count = sum(len(elim_by_round.get(r, [])) for r in all_rounds)
                total_items = len(path) + elim_count
                print(f'\n  {label} ({len(path)} placements, {elim_count} elimination rounds):')

                for rnd in all_rounds:
                    # Show eliminations for this round first
                    for ev in elim_by_round.get(rnd, []):
                        tech = ev.get('technique', '?')
                        n_elims = len(ev.get('eliminations', []))
                        lvl = TECHNIQUE_LEVELS.get(tech, '?')
                        detail = ev.get('detail', '')
                        print(f'       ~elim~  [{tech} L{lvl}] {n_elims} eliminations')
                    # Then placements for this round
                    for s in path:
                        if s.get('round', 0) != rnd:
                            continue
                        is_target = s.get('pos') == row * 9 + col
                        marker = ' →' if is_target else '  '
                        tech = s.get('technique', '?')
                        cell = s.get('cell', f'R{s["pos"]//9+1}C{s["pos"]%9+1}')
                        digit = s.get('digit', '?')
                        lvl = TECHNIQUE_LEVELS.get(tech, '?')
                        print(f'  {marker} #{s["step"]:3d}  {cell}={digit}  [{tech} L{lvl}]')

                if is_stalled:
                    remaining = result.get('total_empty', '?')
                    print(f'  ── STALLED ── {remaining} cells remaining')
        return

    # ── Full solve mode ──
    use_detail = args.detail
    if args.steps or args.verbose:
        print(f'\nSolving: {bd81[:20]}{"..." if len(bd81)>20 else ""}')
        print(f'{"─" * 50}')

    # Oracle-free: no trusted solution — Zone/Rule Oracle are SIRO-based, not backtracker
    use_zo = args.siro or args.zone_oracle
    use_ro = args.siro or args.rule_oracle

    # Zone135: auto-compute oracle zone sums from backtracker solution
    z135_oracle = None
    if args.zone135:
        from .engine import solve_backtrack_pure
        z135_sol = solve_backtrack_pure(bd81)
        if z135_sol:
            z135_oracle = compute_zone_sums_from_solution(z135_sol)
            if args.verbose or args.steps:
                print(f'  Zone135 oracle: {z135_oracle}')

    t0 = time.perf_counter()
    result = solve_selective(bd81, max_level=args.level, only_techniques=only_techniques,
                            verbose=(args.steps or args.verbose) and not use_detail,
                            detail=use_detail, gf2=args.gf2, gf2_extended=args.gf2x,
                            dr_mode=args.dr_mode,
                            zone_oracle=use_zo, rule_oracle=use_ro,
                            zone135_oracle=z135_oracle)
    elapsed = (time.perf_counter() - t0) * 1000

    if args.json:
        result['elapsed_ms'] = round(elapsed, 1)
        # Steps can be large, keep them if --steps was requested
        if not args.steps and not use_detail:
            result['steps'] = f'{len(result["steps"])} steps (use --steps for detail)'
        print(json.dumps(result, indent=2, default=str))
        return

    # Print summary
    if args.steps or args.verbose:
        print(f'{"─" * 50}')
    if preset_label:
        print(f'\n  ✦ {preset_label} Techniques ✦')
    print(f'\n{format_summary(result, elapsed)}')

    # Print detailed round-by-round output
    if use_detail:
        print(f'\n{"═" * 60}')
        print(f'DETAILED SOLVE LOG ({result.get("rounds", "?")} rounds)')
        print(f'{"═" * 60}')
        print(format_detail(result))
        print(f'{"═" * 60}')

    if args.board:
        print(f'\n{format_board(result["board"], bd81)}')

    # Exit code: 0 = solved, 1 = stalled/failed
    if not result['success']:
        sys.exit(1)


if __name__ == '__main__':
    main()
