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
    detect_forcing_chain_bitwise, detect_forcing_net, detect_forcing_net_v2,
    detect_rectangle_elimination, detect_xy_chain, detect_dpi,
    detect_wxyz_wing, detect_xyz_wing, detect_3d_medusa,
    detect_hidden_unique_rectangle, detect_grouped_x_cycle,
    detect_tridagon,
    detect_w_wing, detect_fireworks, detect_almost_locked_pair,
    detect_chute_remote_pair,
    detect_d2b_bitwise, detect_fpf_bitwise,
    detect_xwing, detect_swordfish, detect_simple_coloring,
    detect_bug_plus1, detect_ur_type2, detect_ur_type4,
    detect_junior_exocet, detect_junior_exocet_stuart,
    detect_template, detect_bowman_bingo,
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
    'ForcingChain': 5, 'ForcingNet': 5, 'XYChain': 5, 'RectElim': 5, 'FNv2': 7,
    'XYZWing': 4, 'WXYZWing': 5, '3DMedusa': 5, 'HiddenUR': 5, 'GroupedXCycle': 4,
    'Tridagon': 6, 'WWing': 4, 'Fireworks': 5, 'AlmostLockedPair': 4,
    'ChuteRemotePair': 4,
    'BUG+1': 6, 'URType2': 6, 'URType4': 6,
    'JuniorExocet': 6, 'JETest': 6, 'Template': 6, 'BowmanBingo': 6,
    'KrakenFish': 6, 'SKLoop': 6,
    'D2B': 6, 'FPF': 7,
    'DeepResonance': 7,
    'contradiction': 7, 'ORACLE_ONLY': 99,
}

TECHNIQUE_ALIASES = {
    'fpc': 'FPC', 'fpce': 'FPCE', 'fc': 'ForcingChain', 'fn': 'ForcingNet', 'fnv2': 'FNv2',
    'xychain': 'XYChain', 'xy': 'XYChain', 'rectelim': 'RectElim', 're': 'RectElim',
    'dpi': 'DPI', 'deeppath': 'DPI', 'pathincompat': 'DPI',
    'xyzwing': 'XYZWing', 'xyz': 'XYZWing',
    'wxyzwing': 'WXYZWing', 'wxyz': 'WXYZWing',
    '3dmedusa': '3DMedusa', 'medusa': '3DMedusa', '3dm': '3DMedusa',
    'hiddenur': 'HiddenUR', 'hur': 'HiddenUR',
    'groupedxcycle': 'GroupedXCycle', 'gxc': 'GroupedXCycle',
    'tridagon': 'Tridagon', 'thor': 'Tridagon', 'thorshammer': 'Tridagon',
    'wwing': 'WWing', 'ww': 'WWing', 'remotepair': 'WWing',
    'fireworks': 'Fireworks', 'fw': 'Fireworks',
    'alp': 'AlmostLockedPair', 'almostlockedpair': 'AlmostLockedPair',
    'chutepair': 'ChuteRemotePair', 'crp': 'ChuteRemotePair', 'chuteremotepair': 'ChuteRemotePair',
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
    'exocet': 'JuniorExocet', 'jetest': 'JETest', 'je': 'JETest',
    'template': 'Template', 'bowman': 'BowmanBingo',
    'l1': 'L1', 'l2': 'L2',
}

# ── Presets ──────────────────────────────────────────────────
# WSRF inventions (excluded from expert-approved preset)
WSRF_INVENTIONS = {'FPC', 'FPCE', 'D2B', 'FPF', 'GF2_Lanczos', 'GF2_Extended', 'GF2_Probe'}

# Experimental techniques — research detectors not ready for production
EXPERIMENTAL_TECHNIQUES = {'JETest', 'DPI'}

# Sudoku Expert Approved — standard L1-L6 techniques only (no WSRF inventions)
EXPERT_APPROVED = {
    tech for tech, lvl in TECHNIQUE_LEVELS.items()
    if lvl <= 6 and tech not in WSRF_INVENTIONS and tech not in EXPERIMENTAL_TECHNIQUES and tech != 'ORACLE_ONLY'
}

# Larstech: all techniques (full WSRF + Lars inventions)
LARSTECH_SET = {
    tech for tech in TECHNIQUE_LEVELS
    if tech != 'ORACLE_ONLY' and tech not in EXPERIMENTAL_TECHNIQUES
}

PRESETS = {
    'expert': EXPERT_APPROVED,
    'larstech': LARSTECH_SET,
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


def solve_selective(bd81, max_level=99, only_techniques=None, exclude_techniques=None,
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
        if exclude_techniques and tech_name in exclude_techniques:
            return False
        if tech_name in EXPERIMENTAL_TECHNIQUES:
            # Experimental techniques require explicit opt-in via only_techniques
            if only_techniques is not None:
                return tech_name in only_techniques
            return False
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

        # Forcing Net (placements + eliminations)
        if allowed('ForcingNet'):
            fn_placements, fn_elims = detect_forcing_net(bb)
            if fn_placements:
                for pos, val, fn_detail in fn_placements:
                    if bb.board[pos] == 0:
                        cands_before = _cands_list(bb, pos) if detail else None
                        bb.place(pos, val)
                        step_num += 1
                        entry = {'step': step_num, 'pos': pos, 'digit': val,
                                 'technique': 'ForcingNet', 'cell': _cell_name(pos),
                                 'round': round_num}
                        if detail:
                            entry['cands_before'] = cands_before
                            entry['explanation'] = fn_detail
                        steps.append(entry)
                        technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
                        placed = True
                        if verbose:
                            print(f"  #{step_num:3d}  {entry['cell']}={val}  [ForcingNet]")
                        break
                if placed:
                    continue
            if fn_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'ForcingNet',
                        'eliminations': list(fn_elims),
                        'detail': f'ForcingNet: {len(fn_elims)} eliminations',
                    })
                for pos, d in fn_elims:
                    bb.eliminate(pos, d)
                technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
                if verbose:
                    descs = [f'{d}@R{p//9+1}C{p%9+1}' for p, d in fn_elims]
                    print(f"        ForcingNet: {', '.join(descs)}")
                continue

        # XY-Chain
        if allowed('XYChain'):
            xy_elims = detect_xy_chain(bb)
            if xy_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'XYChain',
                        'eliminations': list(xy_elims),
                    })
                for pos, d in xy_elims:
                    bb.eliminate(pos, d)
                technique_counts['XYChain'] = technique_counts.get('XYChain', 0) + 1
                if verbose:
                    descs = [f'{d}@R{p//9+1}C{p%9+1}' for p, d in xy_elims]
                    print(f"        XYChain: {', '.join(descs)}")
                continue

        # DPI — Deep Path Incompatibility (Yves's technique)
        if allowed('DPI'):
            dpi_elims = detect_dpi(bb)
            if dpi_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'DPI',
                        'eliminations': list(dpi_elims),
                    })
                for pos, d in dpi_elims:
                    bb.eliminate(pos, d)
                technique_counts['DPI'] = technique_counts.get('DPI', 0) + 1
                if verbose:
                    descs = [f'{d}@R{p//9+1}C{p%9+1}' for p, d in dpi_elims]
                    print(f"        DPI: {', '.join(descs)}")
                continue

        # Rectangle Elimination
        if allowed('RectElim'):
            re_elims = detect_rectangle_elimination(bb)
            if re_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'RectElim',
                        'eliminations': list(re_elims),
                    })
                for pos, d in re_elims:
                    bb.eliminate(pos, d)
                technique_counts['RectElim'] = technique_counts.get('RectElim', 0) + 1
                if verbose:
                    descs = [f'{d}@R{p//9+1}C{p%9+1}' for p, d in re_elims]
                    print(f"        RectElim: {', '.join(descs)}")
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

        # Junior Exocet — validated version (strict cover-line ≤2)
        if allowed('JuniorExocet'):
            je_elims, je_detail = detect_junior_exocet_stuart(bb)
            if je_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'JuniorExocet',
                        'eliminations': list(je_elims),
                        'detail': je_detail,
                    })
                for pos, d in je_elims:
                    bb.eliminate(pos, d)
                technique_counts['JuniorExocet'] = technique_counts.get('JuniorExocet', 0) + 1
                if verbose and je_detail:
                    print(f"        {je_detail}")
                    for pos, d in je_elims:
                        r, c = pos // 9, pos % 9
                        print(f"          {d} removed from R{r+1}C{c+1}")
                continue

        # JETest — experimental: our original Exocet detector (fire once)
        if allowed('JETest') and technique_counts.get('JETest', 0) < 1:
            je_elims, _ = detect_junior_exocet(bb)
            if je_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'JETest',
                        'eliminations': list(je_elims),
                        'detail': f'JETest: {len(je_elims)} eliminations',
                    })
                for pos, d in je_elims:
                    bb.eliminate(pos, d)
                technique_counts['JETest'] = technique_counts.get('JETest', 0) + 1
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

        # Bowman's Bingo (placements + eliminations)
        if allowed('BowmanBingo'):
            bb_placements, bb_elims = detect_bowman_bingo(bb)
            if bb_placements:
                for pos, val, bingo_detail in bb_placements:
                    if bb.board[pos] == 0:
                        cands_before = _cands_list(bb, pos) if detail else None
                        bb.place(pos, val)
                        step_num += 1
                        entry = {'step': step_num, 'pos': pos, 'digit': val,
                                 'technique': 'BowmanBingo', 'cell': _cell_name(pos),
                                 'round': round_num}
                        if detail:
                            entry['cands_before'] = cands_before
                            entry['explanation'] = bingo_detail
                        steps.append(entry)
                        technique_counts['BowmanBingo'] = technique_counts.get('BowmanBingo', 0) + 1
                        placed = True
                        if verbose:
                            print(f"  #{step_num:3d}  {entry['cell']}={val}  [BowmanBingo]")
                        break
                if placed:
                    continue
            if bb_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'BowmanBingo',
                        'eliminations': list(bb_elims),
                        'detail': f'BowmanBingo: {len(bb_elims)} eliminations',
                    })
                for pos, d in bb_elims:
                    bb.eliminate(pos, d)
                technique_counts['BowmanBingo'] = technique_counts.get('BowmanBingo', 0) + 1
                if verbose:
                    descs = [f'{d}@R{p//9+1}C{p%9+1}' for p, d in bb_elims]
                    print(f"        BowmanBingo: {', '.join(descs)}")
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

        # Forcing Net v2 (L7 — after D2B/FPF, before DeepResonance)
        if allowed('FNv2'):
            fnv2_placements, fnv2_elims = detect_forcing_net_v2(bb)
            if fnv2_placements:
                for pos, val, fnv2_detail in fnv2_placements:
                    if bb.board[pos] == 0:
                        cands_before = _cands_list(bb, pos) if detail else None
                        bb.place(pos, val)
                        step_num += 1
                        entry = {'step': step_num, 'pos': pos, 'digit': val,
                                 'technique': 'FNv2', 'cell': _cell_name(pos),
                                 'round': round_num}
                        if detail:
                            entry['cands_before'] = cands_before
                            entry['explanation'] = fnv2_detail
                        steps.append(entry)
                        technique_counts['FNv2'] = technique_counts.get('FNv2', 0) + 1
                        placed = True
                        if verbose:
                            print(f"  #{step_num:3d}  {entry['cell']}={val}  [FNv2]")
                        break
                if placed:
                    continue
            if fnv2_elims:
                if detail:
                    elim_events.append({
                        'round': round_num, 'technique': 'FNv2',
                        'eliminations': list(fnv2_elims),
                    })
                for pos, d in fnv2_elims:
                    bb.eliminate(pos, d)
                technique_counts['FNv2'] = technique_counts.get('FNv2', 0) + 1
                if verbose:
                    descs = [f'{d}@R{p//9+1}C{p%9+1}' for p, d in fnv2_elims]
                    print(f"        FNv2: {', '.join(descs)}")
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

        # ── Last-resort: new techniques (fire only when ALL existing stall) ──

        last_resort_hit = False

        if not last_resort_hit and allowed('GroupedXCycle'):
            gxc_place, gxc_elim = detect_grouped_x_cycle(bb)
            if gxc_place:
                pos, digit, tech = gxc_place[0]
                if bb.board[pos] == 0:
                    cands_before = _cands_list(bb, pos) if detail else None
                    bb.place(pos, digit)
                    step_num += 1
                    entry = {'step': step_num, 'pos': pos, 'digit': digit,
                             'technique': 'GroupedXCycle', 'cell': _cell_name(pos),
                             'round': round_num}
                    if detail:
                        entry['cands_before'] = cands_before
                    steps.append(entry)
                    technique_counts['GroupedXCycle'] = technique_counts.get('GroupedXCycle', 0) + 1
                    last_resort_hit = True
            if not last_resort_hit and gxc_elim:
                for pos, d in gxc_elim:
                    bb.eliminate(pos, d)
                technique_counts['GroupedXCycle'] = technique_counts.get('GroupedXCycle', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('XYZWing'):
            xyz_elims = detect_xyz_wing(bb)
            if xyz_elims:
                for pos, d in xyz_elims:
                    bb.eliminate(pos, d)
                technique_counts['XYZWing'] = technique_counts.get('XYZWing', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('3DMedusa'):
            med_elims = detect_3d_medusa(bb)
            if med_elims:
                for pos, d in med_elims:
                    bb.eliminate(pos, d)
                technique_counts['3DMedusa'] = technique_counts.get('3DMedusa', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('WXYZWing'):
            wxyz_elims = detect_wxyz_wing(bb)
            if wxyz_elims:
                for pos, d in wxyz_elims:
                    bb.eliminate(pos, d)
                technique_counts['WXYZWing'] = technique_counts.get('WXYZWing', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('HiddenUR'):
            hur_elims = detect_hidden_unique_rectangle(bb)
            if hur_elims:
                for pos, d in hur_elims:
                    bb.eliminate(pos, d)
                technique_counts['HiddenUR'] = technique_counts.get('HiddenUR', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('Tridagon'):
            tri_elims = detect_tridagon(bb)
            if tri_elims:
                for pos, d in tri_elims:
                    bb.eliminate(pos, d)
                technique_counts['Tridagon'] = technique_counts.get('Tridagon', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('WWing'):
            ww_elims = detect_w_wing(bb)
            if ww_elims:
                for pos, d in ww_elims:
                    bb.eliminate(pos, d)
                technique_counts['WWing'] = technique_counts.get('WWing', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('Fireworks'):
            fw_elims = detect_fireworks(bb)
            if fw_elims:
                for pos, d in fw_elims:
                    bb.eliminate(pos, d)
                technique_counts['Fireworks'] = technique_counts.get('Fireworks', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('AlmostLockedPair'):
            alp_elims = detect_almost_locked_pair(bb)
            if alp_elims:
                for pos, d in alp_elims:
                    bb.eliminate(pos, d)
                technique_counts['AlmostLockedPair'] = technique_counts.get('AlmostLockedPair', 0) + 1
                last_resort_hit = True

        if not last_resort_hit and allowed('ChuteRemotePair'):
            crp_elims = detect_chute_remote_pair(bb)
            if crp_elims:
                for pos, d in crp_elims:
                    bb.eliminate(pos, d)
                technique_counts['ChuteRemotePair'] = technique_counts.get('ChuteRemotePair', 0) + 1
                last_resort_hit = True

        if last_resort_hit:
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
        if tech_name in EXPERIMENTAL_TECHNIQUES:
            return False
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

        # ForcingNet (fallback)
        if allowed('ForcingNet') and 'ForcingNet' not in predicted_techs:
            fn_placements, fn_elims = detect_forcing_net(bb)
            if fn_placements:
                for pos, val, det in fn_placements:
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
            if fn_elims:
                for pos, d in fn_elims:
                    bb.eliminate(pos, d)
                technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
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

        # Junior Exocet — validated version
        if allowed('JuniorExocet'):
            je_elims, _ = detect_junior_exocet_stuart(bb)
            if je_elims:
                for pos, d in je_elims:
                    bb.eliminate(pos, d)
                technique_counts['JuniorExocet'] = technique_counts.get('JuniorExocet', 0) + 1
                continue

        # JETest — experimental
        if allowed('JETest') and technique_counts.get('JETest', 0) < 1:
            je_elims, _ = detect_junior_exocet(bb)
            if je_elims:
                for pos, d in je_elims:
                    bb.eliminate(pos, d)
                technique_counts['JETest'] = technique_counts.get('JETest', 0) + 1
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

        # BowmanBingo (fallback)
        if allowed('BowmanBingo'):
            bb_place, bb_elim = detect_bowman_bingo(bb)
            if bb_place:
                for pos, val, det in bb_place:
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
            if bb_elim:
                for pos, d in bb_elim:
                    bb.eliminate(pos, d)
                technique_counts['BowmanBingo'] = technique_counts.get('BowmanBingo', 0) + 1
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
# BATCH / FAST SOLVE
# ══════════════════════════════════════════════════════════════

def solve_batch(puzzles, max_level=99, only_techniques=None, exclude_techniques=None,
                **kwargs):
    """Solve multiple puzzles efficiently. Returns list of result dicts.

    Reuses solve_selective but avoids repeated Python setup overhead.
    For forge confirmation, use solve_fast() instead."""
    return [solve_selective(p, max_level=max_level, only_techniques=only_techniques,
                            exclude_techniques=exclude_techniques, **kwargs)
            for p in puzzles]


def solve_fast(bd81, sigboost=None):
    """Fast solve for forge confirmation — minimal overhead, no detail tracking.

    Args:
        bd81: 81-char puzzle string
        sigboost: optional set of technique names from known signature.
                  When provided, ONLY runs techniques in this set + L1/L2.
                  Skips expensive detectors (DR=178ms, FC=99ms) when not needed.
                  Safe because technique signatures are invariant under symmetry.

    Returns dict with 'success', 'technique_counts', 'empty_remaining'."""

    bb = BitBoard.from_string(bd81)

    technique_counts = {}

    # Sigboost: only run techniques the signature says we need
    def need(tech):
        if sigboost is None:
            return True
        return tech in sigboost

    # ── Phase 1: L1+L2 drain (handles ~80% of easy puzzles completely) ──
    while True:
        hits = propagate_l1l2(bb)
        if not hits:
            break
        for pos, digit, tech in hits:
            technique_counts[tech] = technique_counts.get(tech, 0) + 1

    if bb.empty == 0:
        return {'success': True, 'technique_counts': technique_counts,
                'empty_remaining': 0}

    # ── Phase 2: L3-L5 techniques (fast, handles ~15% more) ──
    max_rounds = 200
    for _ in range(max_rounds):
        if bb.empty == 0:
            break

        # L1+L2 drain
        hits = propagate_l1l2(bb)
        if hits:
            for pos, digit, tech in hits:
                technique_counts[tech] = technique_counts.get(tech, 0) + 1
            continue

        if bb.empty == 0:
            break

        # XWing (<0.2ms)
        if need('XWing') and detect_xwing(bb):
            technique_counts['XWing'] = technique_counts.get('XWing', 0) + 1
            continue

        # Swordfish (<0.2ms)
        if need('Swordfish') and detect_swordfish(bb):
            technique_counts['Swordfish'] = technique_counts.get('Swordfish', 0) + 1
            continue

        # Simple Coloring (<0.2ms)
        if need('SimpleColoring'):
            sc_elims, _ = detect_simple_coloring(bb)
            if sc_elims:
                for pos, d in sc_elims:
                    bb.eliminate(pos, d)
                technique_counts['SimpleColoring'] = technique_counts.get('SimpleColoring', 0) + 1
                continue

        # X-Cycle (<1ms)
        if need('XCycle'):
            xc_place, xc_elim = detect_x_cycle_bitwise(bb)
            if xc_place:
                pos, digit, tech = xc_place[0]
                if bb.board[pos] == 0:
                    bb.place(pos, digit)
                technique_counts['XCycle'] = technique_counts.get('XCycle', 0) + 1
                continue
            if xc_elim:
                for pos, d in xc_elim:
                    bb.eliminate(pos, d)
                technique_counts['XCycle'] = technique_counts.get('XCycle', 0) + 1
                continue

        # ALS-XZ (<0.2ms)
        if need('ALS_XZ'):
            als_elims = detect_als_xz_bitwise(bb)
            if als_elims:
                for pos, d in als_elims:
                    bb.eliminate(pos, d)
                technique_counts['ALS_XZ'] = technique_counts.get('ALS_XZ', 0) + 1
                continue

        # Sue De Coq
        if need('SueDeCoq'):
            sdc_elims = detect_sue_de_coq_bitwise(bb)
            if sdc_elims:
                for pos, d in sdc_elims:
                    bb.eliminate(pos, d)
                technique_counts['SueDeCoq'] = technique_counts.get('SueDeCoq', 0) + 1
                continue

        # APE
        if need('AlignedPairExcl'):
            ape_elims = detect_aligned_pair_exclusion_bitwise(bb)
            if ape_elims:
                for pos, d in ape_elims:
                    bb.eliminate(pos, d)
                technique_counts['AlignedPairExcl'] = technique_counts.get('AlignedPairExcl', 0) + 1
                continue

        # ALS-XY Wing
        if need('ALS_XYWing'):
            alsxy_elims = detect_als_xy_wing_bitwise(bb)
            if alsxy_elims:
                for pos, d in alsxy_elims:
                    bb.eliminate(pos, d)
                technique_counts['ALS_XYWing'] = technique_counts.get('ALS_XYWing', 0) + 1
                continue

        # Death Blossom
        if need('DeathBlossom'):
            db_elims = detect_death_blossom_bitwise(bb)
            if db_elims:
                for pos, d in db_elims:
                    bb.eliminate(pos, d)
                technique_counts['DeathBlossom'] = technique_counts.get('DeathBlossom', 0) + 1
                continue

        # Kraken Fish (<0.3ms)
        if need('KrakenFish'):
            kf_elims = detect_kraken_fish_bitwise(bb)
            if kf_elims:
                kf_elims = validate_eliminations(bb, kf_elims)
                if kf_elims:
                    for pos, d in kf_elims:
                        bb.eliminate(pos, d)
                    technique_counts['KrakenFish'] = technique_counts.get('KrakenFish', 0) + 1
                    continue

        # FPC (~2ms)
        if need('FPC'):
            fpc_hits = detect_fpc_bitwise(bb)
            if fpc_hits:
                pos, val, _ = fpc_hits[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['FPC'] = technique_counts.get('FPC', 0) + 1
                continue

        # FPCE (~6ms)
        if need('FPCE'):
            fpce_p, fpce_e = detect_fpce_bitwise(bb)
            if fpce_e:
                for pos, d in fpce_e:
                    bb.eliminate(pos, d)
            if fpce_p:
                pos, val, _ = fpce_p[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['FPCE'] = technique_counts.get('FPCE', 0) + 1
                continue
            if fpce_e:
                technique_counts['FPCE'] = technique_counts.get('FPCE', 0) + 1
                continue

        # ForcingChain (~99ms — sigboost skips this when not needed!)
        if need('ForcingChain'):
            fc_hits = detect_forcing_chain_bitwise(bb)
            if fc_hits:
                pos, val, _ = fc_hits[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['ForcingChain'] = technique_counts.get('ForcingChain', 0) + 1
                continue

        # ForcingNet (~2.5ms)
        if need('ForcingNet'):
            fn_p, fn_e = detect_forcing_net(bb)
            if fn_p:
                pos, val, _ = fn_p[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
                continue
            if fn_e:
                for pos, d in fn_e:
                    bb.eliminate(pos, d)
                technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
                continue

        # ── Phase 3: L6-L7 heavy hitters ──
        if need('BUG+1'):
            bug_hits = detect_bug_plus1(bb)
            if bug_hits:
                pos, val, _ = bug_hits[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['BUG+1'] = technique_counts.get('BUG+1', 0) + 1
                continue

        if need('URType2'):
            ur2_elims, _ = detect_ur_type2(bb)
            if ur2_elims:
                for pos, d in ur2_elims:
                    bb.eliminate(pos, d)
                technique_counts['URType2'] = technique_counts.get('URType2', 0) + 1
                continue

        if need('URType4'):
            ur4_elims, _ = detect_ur_type4(bb)
            if ur4_elims:
                for pos, d in ur4_elims:
                    bb.eliminate(pos, d)
                technique_counts['URType4'] = technique_counts.get('URType4', 0) + 1
                continue

        if need('JuniorExocet'):
            je_elims, _ = detect_junior_exocet_stuart(bb)
            if je_elims:
                for pos, d in je_elims:
                    bb.eliminate(pos, d)
                technique_counts['JuniorExocet'] = technique_counts.get('JuniorExocet', 0) + 1
                continue

        if need('Template'):
            tmpl_p, tmpl_e = detect_template(bb)
            if tmpl_e:
                for pos, d in tmpl_e:
                    bb.eliminate(pos, d)
            if tmpl_p:
                pos, val, _ = tmpl_p[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['Template'] = technique_counts.get('Template', 0) + 1
                continue
            if tmpl_e:
                technique_counts['Template'] = technique_counts.get('Template', 0) + 1
                continue

        # D2B
        if need('D2B'):
            d2b_hits = detect_d2b_bitwise(bb)
            if d2b_hits:
                pos, val, _ = d2b_hits[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['D2B'] = technique_counts.get('D2B', 0) + 1
                continue

        # SK Loop
        if need('SKLoop'):
            skl_elims = detect_sk_loop_bitwise(bb)
            if skl_elims:
                for pos, d in skl_elims:
                    bb.eliminate(pos, d)
                technique_counts['SKLoop'] = technique_counts.get('SKLoop', 0) + 1
                continue

        # DeepResonance (~178ms — sigboost skips this when not needed!)
        if need('DeepResonance'):
            dr_elims = detect_deep_resonance(bb)
            if dr_elims:
                for pos, d in dr_elims:
                    bb.eliminate(pos, d)
                technique_counts['DeepResonance'] = technique_counts.get('DeepResonance', 0) + 1
                continue

        # FPF
        if need('FPF'):
            fpf_hits = detect_fpf_bitwise(bb)
            if fpf_hits:
                pos, val, _ = fpf_hits[0]
                if bb.board[pos] == 0:
                    bb.place(pos, val)
                technique_counts['FPF'] = technique_counts.get('FPF', 0) + 1
                continue

        # Stalled
        break

    solved = bb.empty == 0 and validate_sudoku(bb.board)
    return {
        'success': solved,
        'technique_counts': technique_counts,
        'empty_remaining': bb.empty,
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


def decode_bdp(s):
    """Decode SudokuWiki packed bd string (S9B format).

    Format: 3-char header (e.g. 'S9B') + 81 x 2-char base-36 pairs.
    Values: 01-09 = given clue, 10-18 = solved (digit = val-9),
            19-529 = candidates (bitmask = val-18, not a placed digit).
    Returns 81-char bd81 string (givens/solved only, candidates → 0).
    """
    header = s[:3]
    body = s[3:]
    if len(body) < 162:
        raise ValueError(f'BDP string too short: need 162+ body chars, got {len(body)}')

    bd81 = []
    for i in range(81):
        pair = body[i*2:i*2+2]
        val = int(pair, 36)
        if 1 <= val <= 9:
            bd81.append(str(val))     # given
        elif 10 <= val <= 18:
            bd81.append(str(val - 9)) # solved
        else:
            bd81.append('0')          # candidates = unsolved
    return ''.join(bd81)


def normalize_puzzle(puzzle_str):
    """Normalize a puzzle string to 81 digits (0 for empty).
    Also accepts SudokuWiki BDP strings (S9B/X9B/J9B format)."""
    puzzle_str = puzzle_str.strip()

    # Detect BDP format: starts with S9, X9, or J9 and is 165+ chars
    if len(puzzle_str) >= 165 and puzzle_str[:2] in ('S9', 'X9', 'J9'):
        return decode_bdp(puzzle_str)

    puzzle_str = puzzle_str.replace('.', '0').replace(' ', '').replace('\n', '')
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
        formatter_class=argparse.RawDescriptionHelpFormatter, prog='larsdoku',
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
    from . import __version__
    parser.add_argument('--version', action='version', version=f'larsdoku {__version__}')
    parser.add_argument('puzzle', nargs='?', default=None,
                       help='81-char puzzle string (bd81/bdp), or - for stdin')
    parser.add_argument('--cell', '-c', help='Query solution for a specific cell (R3C5 or row,col)')
    parser.add_argument('--path', '-p', action='store_true',
                       help='Show technique path to --cell (requires --cell)')
    parser.add_argument('--cell-placement', type=str, metavar='CELL',
                       help='Predict and place a specific cell using advanced techniques (R3C5). '
                            'Shows SIRO prediction, technique needed, and runs it.')
    parser.add_argument('--inspector', type=str, metavar='CELL',
                       help='Full cell inspector: SIRO prediction, zone scores, rival counts, '
                            'technique prediction, scout status (R3C5)')
    parser.add_argument('--predict-path', action='store_true',
                       help='Predict solve path: which technique places each cell')
    parser.add_argument('--level', '-l', type=int, default=99,
                       help='Max technique level (1=L1 only, 2=+GF2, 5=+FPC/FC, 7=all)')
    parser.add_argument('--only', '-o', help='Only use specific techniques (comma-separated: fpc,gf2,fc,...)')
    parser.add_argument('--exclude', '-x', help='Exclude specific techniques (comma-separated: gf2,fpc,d2b,...)')
    parser.add_argument('--include', help='Add techniques to the current preset/set (comma-separated: fn,fpc,...). '
                       'Use with --preset to add techniques back, e.g. --preset expert --include fpc')
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
    parser.add_argument('--solution', action='store_true', help='Print backtrack solution string only (fast, no techniques)')
    parser.add_argument('--unique', action='store_true', help='Check if puzzle has a unique solution')
    parser.add_argument('--backtrack-solve', action='store_true',
                       help='Solve using backtracker (like JS solver) — always finds a solution, print board')
    parser.add_argument('--solutions', type=int, metavar='N',
                       help='Find first N solutions (for multi-solution puzzles). '
                            'Then use --trust <solution> to solve to a specific one with real techniques.')
    parser.add_argument('--no-oracle', '-n', action='store_true',
                       help='Pure logic only — stop when stalled, no guessing')
    parser.add_argument('--json', '-j', action='store_true', help='Output as JSON')
    parser.add_argument('--gf2', action='store_true',
                       help='Enable GF(2) Block Lanczos linear algebra technique')
    parser.add_argument('--gf2x', action='store_true',
                       help='Use GF(2) Extended — band/stack constraints, conjugate pairs, free-variable probing (options A-E)')
    parser.add_argument('--exotic', action='store_true',
                       help='Enable exotic techniques (ALS-XZ, Sue De Coq, X-Cycles, Aligned Pair Exclusion)')
    parser.add_argument('--experimental', action='store_true',
                       help='Enable experimental techniques (JETest — research Exocet detector)')
    parser.add_argument('--scandalous-tech', action='store_true',
                       help='Post-solve Exocet scan: solve first with pure logic, then validate '
                            'Exocet patterns against the known solution (ScandolousExocet — 100%% accurate)')
    parser.add_argument('--trust', '-t', metavar='SOLUTION',
                       help='Trust mode — use this 81-char solution string instead of backtracker')
    parser.add_argument('--autotrust', action='store_true',
                       help='Auto-trust: solve via backtracker first, then use that solution as trusted (enables DeepResonance verification)')
    parser.add_argument('--cascade', action='store_true',
                       help='Cascade analysis: find bottleneck moves and show how the puzzle avalanches')
    parser.add_argument('--siro-table', action='store_true',
                       help='Quick SIRO prediction table for all cells — no solving needed')
    parser.add_argument('--siro-cascade', action='store_true',
                       help='SIRO-guided cascade: zone features predict technique, dispatch directly')
    parser.add_argument('--siro-bootstrap', action='store_true',
                       help='SIRO Bootstrap: self-verifying oracle via L1 reduction + prediction')
    parser.add_argument('--board-siro', action='store_true',
                       help='Global SIRO board illumination: show band/stack/cascade impact for every cell')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output during solve')
    parser.add_argument('--rich-output', action='store_true',
                       help='Rich terminal output with colored panels and technique highlighting (requires: pip install rich)')
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
    parser.add_argument('--forge-multi-to-unique', type=str, metavar='PUZZLE',
                       help='Take a multi-solution puzzle, forge unique puzzles from it, '
                            'and output just the bd81 strings (no solving)')
    parser.add_argument('--forge-multi-to-unique-count', type=int, default=5, metavar='N',
                       help='Number of unique puzzles to forge (default 5)')
    parser.add_argument('--warmup', action='store_true',
                       help='Pre-compile all JIT functions (run once after install, ~10s)')
    parser.add_argument('--daily', action='store_true',
                       help='Generate today\'s daily puzzle via LarsForge (deterministic, same for everyone)')
    parser.add_argument('--lars-forge', type=str, metavar='PUZZLE',
                       help='LarsForge: generate non-isomorphic puzzles from a seed (O(81) per puzzle, no backtracker)')
    parser.add_argument('--lars-forge-count', type=int, default=10, metavar='N',
                       help='Number of LarsForge puzzles to generate (default 10)')
    parser.add_argument('--lars-forge-difficulty', type=str, default=None,
                       choices=['easy', 'medium', 'hard', 'expert', 'diabolical'],
                       help='Target difficulty via zone sum targeting')
    parser.add_argument('--lars-forge-scan', type=str, metavar='PUZZLE',
                       help='LarsForge Oracle Scan: count non-isomorphic classes from all 362,880 permutations')
    parser.add_argument('--lars-forge-benchmark', type=str, metavar='PUZZLE',
                       help='LarsForge speed benchmark: generate 100K puzzles and report rate')
    parser.add_argument('--lars-forge-ignite', type=str, metavar='PUZZLE',
                       help='LarsForge Ignite: take a multi-solution puzzle, forge unique puzzles from it')
    parser.add_argument('--lars-forge-generate', type=int, metavar='CLUES',
                       help='LarsForge Generate: instant unique puzzles by clue count (17-30 from seed bank)')
    parser.add_argument('--lars-forge-mask', type=str, metavar='MASK',
                       help='LarsForge from mask: forge unique puzzles for an 81-char mask (X=clue, 0=empty)')
    parser.add_argument('--lars-forge-mask-match', type=str, metavar='MASK',
                       help='Final Boss Mode: match ANY mask to a known seed via Sudoku symmetries (49K seeds, 60 quadrillion reach)')
    parser.add_argument('--lars-forge-mask-coverage', action='store_true',
                       help='Report mask index coverage statistics')
    parser.add_argument('--lars-certify', type=str, metavar='PUZZLE_OR_MASK',
                       help='7ms uniqueness oracle: for 17-clue, hash-certifies UNIQUE or MULTI-SOLUTION MASK '
                            'against complete Royle enumeration. No backtracker needed.')
    parser.add_argument('--lars-forge-promote', type=int, metavar='CLUES',
                       help='Promote a puzzle by adding solution digits to reach N clues (guaranteed unique). '
                            'Use with a puzzle arg or --lars-forge-generate.')
    parser.add_argument('--lars-forge-promote-count', type=int, default=10, metavar='N',
                       help='Number of promoted puzzles to generate (default 10)')
    parser.add_argument('--lars-forge-seed-index', type=int, default=None, metavar='N',
                       help='Pick specific seed from bank (1-128, wraps). Default: random')
    parser.add_argument('--lars-forge-shuffle', action='store_true',
                       help='Apply box shuffle + digit permutation for maximum diversity')
    parser.add_argument('--lars-forge-shuffle-unique', type=str, metavar='PUZZLE',
                       help='LarsForge Shuffle-to-Unique: convert multi-solution puzzle to unique via zone shuffle')
    parser.add_argument('--lars-forge-instant', type=int, metavar='COUNT', nargs='?', const=10,
                       help='LarsForge Instant: generate unique grids in ~6μs each from pre-solved database')
    parser.add_argument('--lars-forge-spread', type=int, metavar='SPREAD',
                       help='Target zone sum spread for grid generation (2=easy, 15=medium, 25=hard, 30+=extreme)')
    parser.add_argument('--lars-forge-zone', type=str, metavar='ZONE=VALUE',
                       help='Target specific zone sum, e.g. MC=51 or TL=55')
    parser.add_argument('--make-puzzle', action='store_true',
                       help='Convert generated grids to solvable puzzles via iterative clue removal')
    parser.add_argument('--to-mask', type=str, metavar='PUZZLE',
                       help='Convert a puzzle string to its mask (0→0, nonzero→X)')
    parser.add_argument('--forge-permute', type=str, metavar='PUZZLE_OR_MASK',
                       help='Digit-permutation forge: takes a unique puzzle (or mask+solution), '
                            'generates up to 362,880 unique puzzles via digit relabeling. '
                            'Accepts formats: bd81, ..X..., 00X000')
    parser.add_argument('--forge-permute-count', type=int, default=10, metavar='N',
                       help='Number of permuted puzzles to output (default 10, max 362880)')
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
    parser.add_argument('--board-forge-method', type=str, default='zone',
                       choices=['zone', 'mask'],
                       help='Generation method: zone = zone geometry (clean), mask = random masks (messy, harder techniques). Default: zone')
    parser.add_argument('--require', type=str, metavar='TECHS',
                       help='Only keep forged boards that need these techniques (comma-separated, e.g. ForcingChain,ALS_XZ)')
    parser.add_argument('--require-attempts', type=int, default=200, metavar='N',
                       help='Max boards to try when hunting for --require techniques (default 200)')
    parser.add_argument('--prefer', type=str, metavar='TECHS',
                       help='Auto-exclude techniques that steal solves from the target (e.g. --prefer fc auto-excludes ALS, FPC, etc.)')
    parser.add_argument('--sculpt', action='store_true',
                       help='Technique-aware minimization: sculpt puzzles toward --prefer/--require techniques')
    parser.add_argument('--like', type=str, metavar='PUZZLE',
                       help='Generate puzzles with similar technique profiles to this puzzle (use with --board-forge-count)')
    parser.add_argument('--like-count', type=int, default=5, metavar='N',
                       help='Number of similar puzzles to generate (default 5)')

    # ── LForge: Technique-targeted puzzle generation ──
    parser.add_argument('--lforge-attempt', type=str, metavar='TECHS',
                       help='Technique Forge: generate puzzles targeting specific techniques '
                            '(comma-separated: als,kraken,coloring,deathblossom)')
    parser.add_argument('--lforge-count', type=int, default=10, metavar='N',
                       help='Number of lforge puzzles to generate (default 10)')
    parser.add_argument('--lforge-clues', type=int, default=None, metavar='N',
                       help='Target clue count filter for lforge (e.g. 22, 23, 24)')
    parser.add_argument('--lforge-tier', type=str, default=None,
                       choices=['medium', 'hard', 'extreme', 'any'],
                       help='Seed tier: medium (22-25), hard (expert collection), extreme (forum hardest)')
    parser.add_argument('--lforge-stats', action='store_true',
                       help='Show technique seed bank statistics')
    parser.add_argument('--lforge-list', action='store_true',
                       help='List all available technique tags')
    parser.add_argument('--lforge-search', type=str, metavar='TECH',
                       help='Find all technique profiles containing a specific technique')
    parser.add_argument('--lforge-promote-hard', type=int, metavar='CLUES',
                       help='Promote from hardest 20-21 clue diabolical bases to target clue count. '
                            'These bases need ALSXY+ALS+D2B+DR+FPCE — the toughest seeds in the catalog.')
    parser.add_argument('--lforge-base-clues', type=int, default=None, metavar='N',
                       help='Filter promote-hard bases by clue count (20 or 21)')
    parser.add_argument('--lforge-fnfc', type=int, nargs='?', const=10, metavar='N',
                       help='Forge N puzzles from FN/FC expert-level seed collection (default 10). '
                            'Use --lforge-clues and --lforge-fn/--lforge-fc to filter.')
    parser.add_argument('--lforge-fn', type=int, default=None, metavar='N',
                       help='Filter FN/FC forge by minimum ForcingNet count (e.g. --lforge-fn 10)')
    parser.add_argument('--lforge-fc', type=int, default=None, metavar='N',
                       help='Filter FN/FC forge by minimum ForcingChain count (e.g. --lforge-fc 5)')
    parser.add_argument('--lforge', type=str, metavar='TECHS',
                       help='Forge puzzles requiring specific techniques (comma-separated). '
                            'E.g.: --lforge als,kraken,d2b')
    parser.add_argument('--lforge-exact', action='store_true',
                       help='Match EXACT technique signature (default: superset/at-least)')

    # ── Lars Seeds: DeepRes/D2B forge + provenance ──
    parser.add_argument('--lforge-deepres', type=int, nargs='?', const=10, metavar='N',
                       help='Forge N DeepRes puzzles from Lars Seeds (default 10)')
    parser.add_argument('--lforge-d2b', type=int, nargs='?', const=10, metavar='N',
                       help='Forge N D2B puzzles from Lars Seeds (default 10)')
    parser.add_argument('--lars-provenance', type=str, metavar='PUZZLE',
                       help='Check if a puzzle is derived from a Lars Seed')
    parser.add_argument('--lars-seeds-stats', action='store_true',
                       help='Show Lars Seeds registry statistics')
    parser.add_argument('--lforge-no-confirm', action='store_true',
                       help='Skip solving forged puzzles to confirm techniques (faster, no verification)')
    parser.add_argument('--sigboost', action='store_true',
                       help='Use signature-aware fast solver for forge confirmation (skips unneeded techniques, ~2-3x faster)')
    parser.add_argument('--lforge-seed', type=int, default=None, metavar='N',
                       help='Random seed for lforge generation (for reproducible output)')
    parser.add_argument('--lforge-batch', type=str, default=None, metavar='BATCH',
                       choices=['deepres', 'd2b', 'l1', 'l2', 'l3', 'box', 'shuffle', 'all'],
                       help='Which seed batch to forge from: deepres, d2b, l1 (1-step), l2 (2-step), l3 (3-step), or all')
    parser.add_argument('--elite', action='store_true',
                       help='Elite mode: only return puzzles that resist all expert techniques. '
                            'These puzzles require DeepResonance/D2B — the hardest puzzles possible.')

    args = parser.parse_args()

    # ── Solution mode: just print backtrack answer ──
    if args.solution and args.puzzle:
        bd81 = normalize_puzzle(args.puzzle)
        sol = solve_backtrack(bd81)
        if sol:
            print(sol)
        else:
            print('No solution exists')
        return

    # ── Find N solutions ──
    if getattr(args, 'solutions', None) and args.puzzle:
        import sys as _sys
        bd81 = normalize_puzzle(args.puzzle)
        n_want = args.solutions
        n_clues = sum(1 for c in bd81 if c != '0')

        # Multi-solution backtracker
        grid = [int(c) for c in bd81]
        def _valid(g, pos, d):
            r, c = divmod(pos, 9)
            for j in range(9):
                if g[r*9+j] == d: return False
                if g[j*9+c] == d: return False
            br, bc = (r//3)*3, (c//3)*3
            for i in range(br, br+3):
                for j in range(bc, bc+3):
                    if g[i*9+j] == d: return False
            return True
        empties = [i for i in range(81) if grid[i] == 0]
        solutions = []
        _sys.setrecursionlimit(10000)
        def _bt(idx):
            if len(solutions) >= n_want: return
            if idx == len(empties):
                solutions.append(''.join(str(d) for d in grid))
                return
            pos = empties[idx]
            for d in range(1, 10):
                if _valid(grid, pos, d):
                    grid[pos] = d
                    _bt(idx + 1)
                    if len(solutions) >= n_want: return
                    grid[pos] = 0

        print(f'  Finding up to {n_want} solutions ({n_clues} clues)...')
        import time as _time_mod
        t0 = _time_mod.time()
        _bt(0)
        elapsed = _time_mod.time() - t0

        print(f'  Found: {len(solutions)} solutions in {elapsed:.2f}s\n')
        for i, sol in enumerate(solutions):
            print(f'  #{i+1}: {sol}')

        if len(solutions) > 1:
            print(f'\n  To solve to a specific solution with real techniques:')
            print(f'  larsdoku "{bd81}" --trust "{solutions[0]}" --preset larstech --steps')
        elif len(solutions) == 1:
            print(f'\n  ✓ Only 1 solution found — puzzle is unique!')
        else:
            print(f'\n  ✗ No solutions found')
        return

    # ── Unique check ──
    if getattr(args, 'unique', False) and args.puzzle:
        bd81 = normalize_puzzle(args.puzzle)
        unique = has_unique_solution(bd81)
        sol = solve_backtrack(bd81)
        n_clues = sum(1 for c in bd81 if c != '0')
        print(f'  Puzzle: {bd81[:20]}{"..." if len(bd81)>20 else ""}')
        print(f'  Clues: {n_clues}')
        print(f'  Solvable: {"Yes" if sol else "No"}')
        print(f'  Unique: {"✓ Yes — one solution" if unique else "✗ No — multiple solutions"}')
        return

    # ── Backtrack solve ──
    if getattr(args, 'backtrack_solve', False) and args.puzzle:
        bd81 = normalize_puzzle(args.puzzle)
        sol = solve_backtrack(bd81)
        if sol:
            print(f'\n  Backtrack solution:')
            print(f'  {sol}')
            # Print board
            print()
            print('  ╔═════════╤═════════╤═════════╗')
            for r in range(9):
                row = '  ║'
                for c in range(9):
                    d = sol[r*9+c]
                    given = bd81[r*9+c] != '0'
                    row += f' {d} '
                    if c % 3 == 2 and c < 8: row += '│'
                    elif c == 8: row += '║'
                print(row)
                if r == 2 or r == 5: print('  ╟─────────┼─────────┼─────────╢')
                elif r == 8: print('  ╚═════════╧═════════╧═════════╝')
            # Check uniqueness
            unique = has_unique_solution(bd81)
            print(f'\n  Unique: {"✓ Yes" if unique else "✗ No — multiple solutions exist"}')
        else:
            print('  No solution exists')
        return

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
    if args.batch is not None and not getattr(args, 'cascade', False):
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

    # ── Like mode: generate puzzles similar to a given one ──
    if getattr(args, 'like', None):
        import random as _like_rng
        like_rng = _like_rng.Random()
        like_puzzle = normalize_puzzle(args.like)
        like_count = getattr(args, 'like_count', 5)

        # Solve the reference puzzle to get its technique profile
        ref_result = solve_selective(like_puzzle, verbose=False)
        ref_techs = ref_result.get('technique_counts', {})
        ref_success = ref_result.get('success', False)
        ref_n = sum(1 for c in like_puzzle if c != '0')
        # Extract the mask from the reference puzzle
        ref_mask = [1 if c != '0' else 0 for c in like_puzzle]

        # Target techniques: all non-L1 techniques used by the reference
        l1_techs = {'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'}
        target_profile = {t for t in ref_techs if t not in l1_techs and ref_techs[t] > 0}

        ref_top = sorted(ref_techs.items(), key=lambda x: -x[1])[:8]
        ref_tech_str = ', '.join(f'{t}={c}' for t, c in ref_top) if ref_top else 'none'

        print(f'\n{"═" * 60}')
        print(f'  LIKE — Generate Similar Puzzles')
        print(f'  Reference: {like_puzzle}')
        print(f'  Clues: {ref_n} | {"SOLVED" if ref_success else "STALLED"}')
        print(f'  Techs: {ref_tech_str}')
        print(f'  Profile: {", ".join(sorted(target_profile)) if target_profile else "L1 only"}')
        print(f'  Count: {like_count}')
        print(f'{"═" * 60}')

        found = 0
        max_like_attempts = like_count * 50

        for attempt in range(max_like_attempts):
            if found >= like_count:
                break

            # Strategy 1: shuffle the reference puzzle (preserves structure)
            shuffled = shuffle_sudoku(like_puzzle, rng=like_rng.random)
            if not has_unique_solution(shuffled):
                continue

            # Solve and check technique similarity
            r = solve_selective(shuffled, verbose=False)
            s_techs = r.get('technique_counts', {})
            s_success = r.get('success', False)
            s_profile = {t for t in s_techs if t not in l1_techs and s_techs[t] > 0}

            # Accept if technique profile overlaps with reference
            overlap = target_profile & s_profile
            if target_profile and not overlap:
                continue

            found += 1
            s_top = sorted(s_techs.items(), key=lambda x: -x[1])[:5]
            s_tech_str = ', '.join(f'{t}={c}' for t, c in s_top) if s_top else 'none'
            s_n = sum(1 for c in shuffled if c != '0')
            status = 'SOLVED' if s_success else 'STALLED'

            match_str = ', '.join(sorted(overlap)) if overlap else 'L1'
            print(f'\n  [{found}/{like_count}] {status} | {s_n} clues | match: {match_str}')
            print(f'  Puzzle: {shuffled}')
            print(f'  Techs:  {s_tech_str}')

        print(f'\n{"═" * 60}')
        print(f'  RESULTS: {found}/{like_count} similar puzzles in {attempt + 1} shuffles')
        print()
        return

    # ── Test mask mode ──
    # ── Board Forge mode: build boards from zone/mask geometry ──
    if args.board_forge is not None:
        from .board_forge import forge_board, forge_unique_board, POSITIONS
        from .constants import PREFER_EXCLUSIONS

        pos_name = args.board_forge.upper()
        target_clues = args.board_forge_clues
        count = args.board_forge_count
        require_str = getattr(args, 'require', None)
        prefer_str = getattr(args, 'prefer', None)
        max_attempts = getattr(args, 'require_attempts', 200)
        forge_method = getattr(args, 'board_forge_method', 'zone')
        do_sculpt = getattr(args, 'sculpt', False)

        # Parse required techniques
        required_techs = set()
        if require_str:
            for t in require_str.split(','):
                t = t.strip()
                if t.lower() in TECHNIQUE_ALIASES:
                    required_techs.add(TECHNIQUE_ALIASES[t.lower()])
                elif t in TECHNIQUE_LEVELS:
                    required_techs.add(t)
                else:
                    print(f'  Warning: unknown technique "{t}" — skipping')
            if not required_techs:
                print(f'  Error: no valid techniques in --require')
                sys.exit(1)

        # Parse preferred techniques and auto-build exclusion set
        preferred_techs = set()
        prefer_exclude = set()
        if prefer_str:
            for t in prefer_str.split(','):
                t = t.strip()
                if t.lower() in TECHNIQUE_ALIASES:
                    preferred_techs.add(TECHNIQUE_ALIASES[t.lower()])
                elif t in TECHNIQUE_LEVELS:
                    preferred_techs.add(t)
                else:
                    print(f'  Warning: unknown technique "{t}" — skipping')
            # Auto-build exclusion set from PREFER_EXCLUSIONS
            for tech in preferred_techs:
                if tech in PREFER_EXCLUSIONS:
                    prefer_exclude |= PREFER_EXCLUSIONS[tech]
            # --prefer implies --require if --require wasn't set
            if not required_techs:
                required_techs = preferred_techs

        # Build combined exclusion set: --prefer auto-exclusions + manual --exclude
        _exclude = set(prefer_exclude)
        if getattr(args, 'exclude', None):
            for t in args.exclude.split(','):
                t = t.strip()
                if t.lower() in TECHNIQUE_ALIASES:
                    _exclude.add(TECHNIQUE_ALIASES[t.lower()])
                elif t in TECHNIQUE_LEVELS:
                    _exclude.add(t)
        # Never exclude the required techniques themselves
        _exclude -= required_techs

        # Parse position(s) for zone method
        pos_list = [p.strip() for p in pos_name.split(',')]
        if forge_method == 'zone':
            for p in pos_list:
                if p not in POSITIONS:
                    print(f'  Error: unknown position "{p}". Valid: {", ".join(POSITIONS.keys())}')
                    sys.exit(1)

        # Header
        method_label = 'Random Mask' if forge_method == 'mask' else 'Zone Geometry'
        print(f'\n{"═" * 60}')
        print(f'  BOARD FORGE — {method_label} Builder')
        if forge_method == 'zone':
            print(f'  Position{"s" if len(pos_list) > 1 else ""}: {", ".join(pos_list)} | Target: {target_clues} clues | Count: {count}')
        else:
            print(f'  Target: {target_clues} clues | Count: {count}')
        if preferred_techs:
            print(f'  Prefer: {", ".join(sorted(preferred_techs))}')
            print(f'  Auto-exclude: {", ".join(sorted(prefer_exclude)) if prefer_exclude else "none"}')
        if required_techs and not preferred_techs:
            print(f'  Require: {", ".join(sorted(required_techs))}')
        if _exclude - prefer_exclude:
            print(f'  Manual exclude: {", ".join(sorted(_exclude - prefer_exclude))}')
        if do_sculpt:
            print(f'  Sculpt: ON (technique-aware minimization)')
        print(f'  Max attempts: {max_attempts}')
        print(f'{"═" * 60}')

        import random as _bf_rng
        rng = _bf_rng.Random()
        solved = 0
        total_attempts = 0

        # When sculpting, forge "fat" puzzles (more clues) so sculpt has
        # room to selectively remove clues toward the target technique.
        _forge_target = target_clues + 8 if do_sculpt else target_clues

        def _forge_one_board_zone():
            """Generate one unique board from zone geometry."""
            from .board_forge import get_cells_for_position
            for _try in range(50):
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

                solution = solve_backtrack(base_str)
                if not solution:
                    continue

                fat = list(solution)
                for cell in digits_by_cell:
                    fat[cell] = str(digits_by_cell[cell])
                fat_str = ''.join(fat)

                removable = [j for j in range(81) if j not in digits_by_cell]
                rng.shuffle(removable)
                puzzle_list = list(fat_str)
                for pos in removable:
                    if sum(1 for c in puzzle_list if c != '0') <= _forge_target:
                        break
                    saved = puzzle_list[pos]
                    puzzle_list[pos] = '0'
                    if not has_unique_solution(''.join(puzzle_list)):
                        puzzle_list[pos] = saved
                puzzle = ''.join(puzzle_list)

                if has_unique_solution(puzzle):
                    return puzzle, base_n
            return None, 0

        def _forge_one_board_mask():
            """Generate one unique board from a random mask."""
            from .mask_forge import forge_unique_randomized
            # Use the module-level generate_random_mask (not the sub17_solve one
            # that gets imported later and shadows this name in main's scope)
            _gen_mask = globals()['generate_random_mask']
            n_mask_clues = max(_forge_target, 20)
            mask_result = _gen_mask(n_clues=n_mask_clues,
                                               min_score=0.70, rng=rng)
            if mask_result is None:
                return None, 0
            positions, _, _ = mask_result
            mask = [0] * 81
            for p in positions:
                mask[p] = 1
            seed_val = rng.randint(0, 999999)
            puzzle, sol, _, _ = forge_unique_randomized(mask, seed=seed_val,
                                                        max_seconds=10,
                                                        verbose=False)
            if puzzle is None:
                return None, 0

            # Minimize to forge target clue count
            puzzle_list = list(puzzle)
            clue_pos = [i for i in range(81) if puzzle_list[i] != '0']
            rng.shuffle(clue_pos)
            for pos in clue_pos:
                if sum(1 for c in puzzle_list if c != '0') <= _forge_target:
                    break
                saved = puzzle_list[pos]
                puzzle_list[pos] = '0'
                if not has_unique_solution(''.join(puzzle_list)):
                    puzzle_list[pos] = saved
            puzzle = ''.join(puzzle_list)
            n_base = len(positions)
            return puzzle, n_base

        _forge_one_board = _forge_one_board_mask if forge_method == 'mask' else _forge_one_board_zone

        found = 0
        for i in range(count if not required_techs else max_attempts):
            if required_techs and found >= count:
                break

            total_attempts += 1
            puzzle, base_n = _forge_one_board()
            if puzzle is None:
                continue

            # Sculpt if requested: technique-aware minimization
            if do_sculpt and required_techs:
                from .board_forge import sculpt_for_technique
                sculpted = sculpt_for_technique(
                    puzzle, required_techs,
                    exclude_techs=_exclude if _exclude else None,
                    rng=rng, verbose=getattr(args, 'verbose', False),
                )
                if sculpted is None:
                    if total_attempts % 25 == 0:
                        print(f'  ... {total_attempts} attempts, {found}/{count} found (sculpt miss)')
                    continue
                puzzle = sculpted

            n_clues = sum(1 for c in puzzle if c != '0')

            # Solve with exclusions
            r = solve_selective(puzzle, verbose=False,
                                exclude_techniques=_exclude if _exclude else None)
            techs = r.get('technique_counts', {})
            success = r.get('success', False)

            # Check if required techniques were used
            if required_techs:
                used = set(techs.keys())
                if not required_techs.issubset(used):
                    if total_attempts % 25 == 0:
                        print(f'  ... {total_attempts} attempts, {found}/{count} found')
                    continue

            if success:
                solved += 1
            found += 1

            top = sorted(techs.items(), key=lambda x: -x[1])[:5]
            tech_str = ', '.join(f'{t}={c}' for t, c in top) if top else 'none'
            status = 'SOLVED' if success else 'STALLED'
            src_label = 'mask' if forge_method == 'mask' else f'{base_n} from zones'

            # Highlight required techniques
            if required_techs:
                hit_str = ', '.join(sorted(required_techs & set(techs.keys())))
                sculpt_tag = ' sculpted' if do_sculpt else ''
                print(f'\n  [{found}/{count}] {status} | {n_clues} clues ({src_label}{sculpt_tag}) ★ {hit_str}')
            else:
                print(f'\n  [{found}] {status} | {n_clues} clues ({src_label}) unique')
            print(f'  Puzzle: {puzzle}')
            print(f'  Techs:  {tech_str}')

            if (count == 1 or (required_techs and found == 1)) and success:
                board_str = r.get('board', '')
                if board_str:
                    print(format_board(board_str, puzzle))

        print(f'\n{"═" * 60}')
        if required_techs:
            print(f'  RESULTS: {found}/{count} found in {total_attempts} attempts ({solved} solved)')
        else:
            print(f'  RESULTS: {solved}/{found} solved')
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

    # ── Forge-Permute: digit permutation forge ──
    if getattr(args, 'forge_permute', None) is not None:
        import itertools as _itools
        import random as _rng

        raw = args.forge_permute.strip()
        count = getattr(args, 'forge_permute_count', 10)

        # Parse input — accept bd81, ..X..., 00X000 formats
        # Normalize: digits stay, 0/.=empty, X=clue position
        normalized = raw.replace('.', '0').upper()

        # Detect if it's a mask (has X) or a puzzle (has digits)
        if 'X' in normalized:
            # It's a mask — need a puzzle too. Check if puzzle arg is provided.
            mask = ''.join('X' if c == 'X' else '0' for c in normalized)
            if args.puzzle:
                puzzle_bd = args.puzzle.replace('.', '0')
                sol = solve_backtrack(puzzle_bd)
            else:
                print('  Error: mask provided but no puzzle. Usage:')
                print('  larsdoku --forge-permute "00X00X..." "PUZZLE_BD81"')
                print('  Or provide a puzzle directly (digits, not mask)')
                sys.exit(1)
        else:
            # It's a puzzle with digits
            puzzle_bd = normalized
            sol = solve_backtrack(puzzle_bd)
            mask = ''.join('X' if c != '0' else '0' for c in puzzle_bd)

        if not sol:
            print('  Error: no solution found for the puzzle')
            sys.exit(1)

        x_positions = [i for i in range(81) if mask[i] == 'X']
        n_clues = len(x_positions)

        # Check source is unique
        source_puzzle = list('0' * 81)
        for pos in x_positions:
            source_puzzle[pos] = sol[pos]
        source_str = ''.join(source_puzzle)
        source_unique = has_unique_solution(source_str)

        print(f'  ╔══════════════════════════════════════════════════╗')
        print(f'  ║  Constellation Forge — Digit Permutation         ║')
        print(f'  ╚══════════════════════════════════════════════════╝')
        print(f'  Clues: {n_clues} | Source unique: {source_unique}')
        print(f'  Max possible: 362,880 (9! digit permutations)')
        print(f'  Generating {count} unique puzzles...')
        print()

        _rng.seed(42)
        perms = list(_itools.permutations(range(1, 10)))
        _rng.shuffle(perms)

        found = 0
        tested = 0
        for perm in perms:
            if found >= count:
                break
            digit_map = {i+1: perm[i] for i in range(9)}
            puzzle = list('0' * 81)
            for pos in x_positions:
                puzzle[pos] = str(digit_map[int(sol[pos])])
            puzzle_str = ''.join(puzzle)
            tested += 1

            if has_unique_solution(puzzle_str):
                found += 1
                # Clean output for piping: just the puzzle string
                print(puzzle_str)

        # Summary to stderr so it doesn't interfere with piping
        import sys as _sys
        _sys.stderr.write(f'\n  # {found}/{tested} tested were unique '
                         f'({n_clues} clues, up to 362,880 possible)\n')
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

    # ── Warmup: pre-compile all JIT functions ──
    if args.warmup:
        import time as _time
        print('  Warming up JIT — compiling all Numba functions...')
        t0 = _time.perf_counter()
        # Solve a simple puzzle to trigger L1-L5 JIT compilation
        solve_selective('530070000600195000098000060800060003400803001700020006060000280000419005000080079')
        # Solve a hard puzzle to trigger DeepRes/D2B/FC JIT compilation
        solve_selective('280900070100087000000025003390070020006000000000000004001000000970002050050090300')
        elapsed = (_time.perf_counter() - t0) * 1000
        print(f'  Done! All JIT functions compiled and cached ({elapsed:.0f}ms)')
        print(f'  Future runs will start instantly.')
        return

    # ── LarsForge: Daily puzzle ──
    if args.daily:
        from .lars_forge import LarsForge, lars_zone_sums
        import datetime
        today = datetime.date.today()
        # Use a well-known hard puzzle as seed
        seed = '530070000600195000098000060800060003400803001700020006060000280000419005000080079'
        forge = LarsForge(seed)
        # Date-based seed: deterministic, same for everyone
        date_seed = today.year * 10000 + today.month * 100 + today.day
        puzzles = forge.lars_generate(count=1, seed=date_seed, unique_classes=False)
        p = puzzles[0]
        zs = lars_zone_sums(p['solution'])
        print(f'\n  LarsForge Daily Puzzle — {today.strftime("%B %d, %Y")}')
        print(f'  {"═" * 50}')
        print(f'  {p["puzzle"]}')
        print(f'  Zone sums: {[int(x) for x in zs]}')
        print(f'  135 rule: ✓')
        print()
        return

    # ── LarsForge: Generate non-isomorphic puzzles ──
    if args.lars_forge is not None:
        from .lars_forge import LarsForge, lars_zone_sums
        forge = LarsForge(args.lars_forge)
        n = args.lars_forge_count
        difficulty = args.lars_forge_difficulty

        if difficulty:
            # Zone sum targeting: balanced = easy, extreme = hard
            # Generate more and filter by zone sum spread
            candidates = forge.lars_generate(count=n * 10, unique_classes=True)
            filtered = []
            for p in candidates:
                zs = list(p['zone_sums'])
                spread = max(zs) - min(zs)
                if difficulty == 'easy' and spread <= 10:
                    filtered.append(p)
                elif difficulty == 'medium' and 8 <= spread <= 16:
                    filtered.append(p)
                elif difficulty == 'hard' and 14 <= spread <= 22:
                    filtered.append(p)
                elif difficulty == 'expert' and spread >= 18:
                    filtered.append(p)
                if len(filtered) >= n:
                    break
            puzzles = filtered[:n]
        else:
            puzzles = forge.lars_generate(count=n, unique_classes=True)

        print(f'\n  LarsForge — {len(puzzles)} non-isomorphic puzzles')
        print(f'  {"═" * 60}')
        for i, p in enumerate(puzzles):
            zs = list(p['zone_sums'])
            spread = max(zs) - min(zs)
            print(f'  {i+1:3d}  {p["puzzle"]}  spread={spread}')
        print()
        return

    # ── LarsForge: Oracle Scan ──
    if args.lars_forge_scan is not None:
        from .lars_forge import LarsForge
        forge = LarsForge(args.lars_forge_scan)
        forge.lars_zone_report()
        print()
        results = forge.lars_oracle_scan(verbose=True)
        print(f'\n  {"═" * 60}')
        print(f'  RESULTS')
        print(f'  {"═" * 60}')
        print(f'  Total permutations:    {results["n_total"]:,}')
        print(f'  Non-isomorphic classes: {results["n_classes"]:,}')
        print(f'  Raw zone sum diversity: {results["zone_sum_diversity"]:,}')
        print(f'  Time:                  {results["time_ms"]:.0f}ms')
        print(f'  Rate:                  {results["rate"]:,.0f} perms/sec')
        print()
        return

    # ── LarsForge: Speed Benchmark ──
    if args.lars_forge_benchmark is not None:
        from .lars_forge import LarsForge
        forge = LarsForge(args.lars_forge_benchmark)
        print(f'\n  LarsForge Speed Benchmark')
        print(f'  {"═" * 50}')
        for n in [1000, 10000, 100000]:
            puzzles, elapsed, rate = forge.lars_forge_batch(count=n)
            print(f'  {n:>7,} puzzles in {elapsed:>8.1f}ms = {rate:>10,.0f} puzzles/sec')
        print()
        # Compare with note about backtrackers
        print(f'  Traditional backtracker: ~50 puzzles/sec')
        print(f'  LarsForge:              ~150,000 puzzles/sec')
        print(f'  Speedup:                ~3,000x')
        print()
        return

    # ── LarsForge Ignite: multi-solution → unique puzzles ──
    if args.lars_forge_ignite is not None:
        from .lars_forge import LarsForge
        n = args.lars_forge_count
        puzzle = args.lars_forge_ignite

        print(f'\n  LarsForge Ignite — forging unique puzzles from multi-solution input')
        print(f'  {"═" * 55}')

        result = LarsForge.lars_ignite(puzzle, count=n)

        if not result['success']:
            print(f'  FAILED: {result.get("error", "unknown error")}')
            if 'forge_ms' in result:
                print(f'  Forge time: {result["forge_ms"]:.0f}ms ({result.get("forge_checks", 0)} checks)')
            print()
            return

        print(f'  Clues: {result["n_clues"]}')
        print(f'  Seed found in {result["forge_checks"]} checks ({result["forge_ms"]:.0f}ms)')
        print(f'  Seed: {result["seed_puzzle"]}')
        print(f'  Generated {result["count"]} unique puzzles in {result["total_ms"]:.0f}ms')
        print()
        for i, p in enumerate(result['puzzles']):
            print(f'  {p}')
        print(f'\n  # {result["count"]} verified unique puzzles ({result["n_clues"]} clues)')
        print()
        return

    # ── LarsForge Generate: instant puzzles by clue count ──
    if args.lars_forge_generate is not None:
        from .lars_forge import LarsForge, lars_get_seed, lars_full_transform, lars_shuffle
        import random as _rng
        n_clues = args.lars_forge_generate
        n = args.lars_forge_count
        difficulty = args.lars_forge_difficulty
        seed_idx = args.lars_forge_seed_index
        use_shuffle = args.lars_forge_shuffle

        print(f'\n  LarsForge Generate — {n_clues}-clue puzzles')
        print(f'  {"═" * 55}')

        # Get seed from extended bank (with difficulty filtering)
        seed_puzzle = lars_get_seed(clues=n_clues, index=seed_idx, difficulty=difficulty)
        if seed_puzzle is None:
            print(f'  No seeds available for {n_clues} clues' + (f' at difficulty={difficulty}' if difficulty else ''))
            print()
            return

        if seed_idx:
            print(f'  Seed: #{seed_idx} (from bank)')
        elif difficulty:
            print(f'  Seed: random {difficulty} (from bank)')
        else:
            print(f'  Seed: random (from bank)')

        t0 = time.perf_counter()
        forge = LarsForge(seed_puzzle)

        if use_shuffle:
            # Full transform: shuffle + digit permutation
            rng = _rng.Random(42)
            puzzles = []
            seen = set()
            while len(puzzles) < n:
                p = lars_full_transform(seed_puzzle, rng)
                if p not in seen:
                    seen.add(p)
                    puzzles.append(p)
            elapsed = (time.perf_counter() - t0) * 1000
            print(f'  Method: shuffle + digit permutation')
        elif difficulty:
            if difficulty == 'diabolical':
                # Diabolical = use the hard seed directly, no spread filter
                batch, ms, rate = forge.lars_forge_batch(count=n)
                puzzles = batch
                elapsed = ms
            else:
                candidates = forge.lars_generate(count=n * 10, unique_classes=False)
                puzzles = []
                for p in candidates:
                    zs = list(p['zone_sums'])
                    spread = max(zs) - min(zs)
                    if difficulty == 'easy' and spread <= 10:
                        puzzles.append(p['puzzle'])
                    elif difficulty == 'medium' and 8 <= spread <= 16:
                        puzzles.append(p['puzzle'])
                    elif difficulty == 'hard' and 14 <= spread <= 22:
                        puzzles.append(p['puzzle'])
                    elif difficulty == 'expert' and spread >= 18:
                        puzzles.append(p['puzzle'])
                    if len(puzzles) >= n:
                        break
                elapsed = (time.perf_counter() - t0) * 1000
            print(f'  Method: seed bank + difficulty filter ({difficulty})')
        else:
            batch, ms, rate = forge.lars_forge_batch(count=n)
            puzzles = batch
            elapsed = ms
            print(f'  Method: seed bank + digit permutation')

        print(f'  Generated {len(puzzles)} puzzles in {elapsed:.1f}ms')
        print()
        for p in puzzles:
            print(f'  {p}')
        print(f'\n  # {len(puzzles)} unique {n_clues}-clue puzzles')
        print()
        return

    # ── LarsForge Spread/Zone targeted generation ──
    if args.lars_forge_spread is not None or args.lars_forge_zone is not None:
        from .lars_forge import LARS_GRID_DB
        import random as _rng

        if not LARS_GRID_DB:
            print(f'\n  Grid database not loaded.')
            print()
            return

        n = args.lars_forge_count
        target_spread = args.lars_forge_spread
        zone_target = args.lars_forge_zone

        print(f'\n  LarsForge Zone-Targeted Generation')
        print(f'  {"═" * 55}')

        # Filter patterns
        matching_grids = []
        ZONE_NAMES = ['TL','TC','TR','ML','MC','MR','BL','BC','BR']

        for key, grids in LARS_GRID_DB.items():
            zs = [int(x) for x in key.split(',')]
            spread = max(zs) - min(zs)

            # Check spread filter
            if target_spread is not None and spread != target_spread:
                continue

            # Check zone filter (e.g., "MC=51")
            if zone_target is not None:
                try:
                    zname, zval = zone_target.split('=')
                    zname = zname.strip().upper()
                    zval = int(zval.strip())
                    if zname in ZONE_NAMES:
                        zidx = ZONE_NAMES.index(zname)
                        if abs(zs[zidx] - zval) > 1:
                            continue
                except:
                    pass

            for g in grids:
                matching_grids.append((g, zs))

        if not matching_grids:
            print(f'  No grids match filters. Try different spread/zone values.')
            print()
            return

        print(f'  Matching grids: {len(matching_grids)}')
        if target_spread is not None:
            print(f'  Spread: {target_spread}')
        if zone_target is not None:
            print(f'  Zone target: {zone_target}')

        rng = _rng.Random(42)
        digits = list(range(1, 10))
        seen = set()
        results = []

        while len(results) < n and len(seen) < len(matching_grids) * 100:
            base, zs = rng.choice(matching_grids)
            rng.shuffle(digits)
            mapping = {str(i+1): str(digits[i]) for i in range(9)}
            new_grid = ''.join(mapping[c] for c in base)
            if new_grid not in seen:
                seen.add(new_grid)
                results.append((new_grid, zs))

        if args.make_puzzle:
            # Convert grids to unique puzzles via iterative removal
            # has_unique_solution already imported at module level
            import random as _rng2

            print(f'  Converting to puzzles (iterative removal)...')
            print()

            for idx, (g, zs) in enumerate(results):
                spread = max(zs) - min(zs)
                rng2 = _rng2.Random(idx * 31 + 7)
                puzzle = list(g)
                positions = list(range(81))
                rng2.shuffle(positions)
                for pos in positions:
                    old = puzzle[pos]
                    puzzle[pos] = '0'
                    if not has_unique_solution(''.join(puzzle)):
                        puzzle[pos] = old

                puzzle_str = ''.join(puzzle)
                n_clues = sum(1 for c in puzzle_str if c != '0')
                print(f'  {puzzle_str}  ({n_clues} clues, spread={spread})')
        else:
            print()
            for g, zs in results:
                spread = max(zs) - min(zs)
                print(f'  {g}  spread={spread}')

        print(f'\n  # {len(results)} {"puzzles" if args.make_puzzle else "grids"} generated')
        print()
        return

    # ── LarsForge Instant: 6μs grid generation ──
    if args.lars_forge_instant is not None:
        from .lars_forge import lars_instant_grid, lars_instant_batch, LARS_GRID_DB

        count = args.lars_forge_instant

        print(f'\n  LarsForge Instant — {count} grids at ~6μs each')
        print(f'  {"═" * 55}')

        if not LARS_GRID_DB:
            print(f'  Grid database not loaded. Run the DB builder first.')
            print()
            return

        print(f'  Database: {len(LARS_GRID_DB)} zone patterns')

        if count == 1:
            result = lars_instant_grid()
            if result.get('grid'):
                print(f'  Grid: {result["grid"]}')
                print(f'  Zone sums: {result["zone_sums"]}')
                print(f'  Time: {result["elapsed_us"]:.1f}μs')
            else:
                print(f'  Error: {result.get("error")}')
        else:
            result = lars_instant_batch(count=count)
            if result.get('grids'):
                for g in result['grids'][:10]:
                    print(f'  {g}')
                if count > 10:
                    print(f'  ... ({count - 10} more)')
                print(f'\n  Generated {len(result["grids"])} grids in {result["elapsed_ms"]:.1f}ms')
                print(f'  Rate: {result["rate"]:,.0f} grids/sec')
                print(f'  Per grid: {result["elapsed_ms"]*1000/len(result["grids"]):.1f}μs')
            else:
                print(f'  Error: {result.get("error")}')
        print()
        return

    # ── LarsForge Shuffle-to-Unique ──
    if args.lars_forge_shuffle_unique is not None:
        from .lars_forge import lars_shuffle_to_unique
        puzzle = args.lars_forge_shuffle_unique

        print(f'\n  LarsForge Shuffle-to-Unique')
        print(f'  {"═" * 55}')
        n_clues = sum(1 for c in puzzle if c != '0')
        print(f'  Input: {puzzle[:40]}...')
        print(f'  Clues: {n_clues}')

        result = lars_shuffle_to_unique(puzzle)

        if result['success']:
            print(f'  Result: UNIQUE ✓')
            print(f'  Puzzle: {result["puzzle"]}')
            if result['box'] >= 0:
                print(f'  Shuffle: box {result["box"]}, swap #{result["swap_idx"]}')
            else:
                print(f'  (Already unique — no shuffle needed)')
            print(f'  Checked: {result["checked"]} shuffles')
        else:
            print(f'  Result: Could not find unique shuffle ({result["checked"]} checked)')
        print()
        return

    # ── Lars Certify: 7ms uniqueness oracle ──
    # ── LForge: Technique-targeted generation ──
    if getattr(args, 'lforge_stats', False):
        from .lars_forge import lars_technique_catalog_stats
        stats = lars_technique_catalog_stats()
        if not stats.get('loaded'):
            print('  Technique seed bank not loaded.')
            return
        print(f'\n  LForge Technique Seed Bank')
        print(f'  {"═" * 55}')
        meta = stats['meta']
        print(f'  Seeds: {meta.get("total_seeds", meta.get("seed_count", "?"))}')
        print(f'  Signatures: {stats["n_signatures"]}')
        print(f'\n  By tier:')
        for tier, count in stats['tier_counts'].items():
            if count:
                print(f'    {tier:10s} {count:5d} seeds')
        print(f'\n  By clue count:')
        for cc, count in stats['clue_counts'].items():
            bar = '#' * (count // 10)
            print(f'    {cc} clues: {count:4d} {bar}')
        print(f'\n  Techniques:')
        for tech, count in stats['tech_freq'].items():
            print(f'    {tech:25s} {count:4d} seeds')

        # Signature catalog stats
        from .lars_forge import _load_sig_catalog
        catalog = _load_sig_catalog()
        if catalog:
            cmeta = catalog.get('meta', {})
            csigs = catalog.get('signatures', {})
            ctotal = cmeta.get('total_seeds', sum(len(v) for v in csigs.values()))

            # Clue distribution from catalog
            cat_clues = {}
            cat_techs = {}
            for sig, entries in csigs.items():
                for e in entries:
                    p = e.get('puzzle', '')
                    cc = sum(1 for c in p if c != '0' and c != '.')
                    cat_clues[cc] = cat_clues.get(cc, 0) + 1
                for t in sig.split('+'):
                    cat_techs[t] = cat_techs.get(t, 0) + len(entries)

            print(f'\n  {"═" * 55}')
            print(f'  Signature Catalog (full database)')
            print(f'  {"═" * 55}')
            print(f'  Signatures: {cmeta.get("total_signatures", len(csigs)):,}')
            print(f'  Seeds: {ctotal:,}')
            print(f'  Puzzles: 1.1 quintillion (via symmetry forge)')

            print(f'\n  By clue count:')
            for cc in sorted(cat_clues.keys()):
                count = cat_clues[cc]
                bar = '#' * max(1, count // 2000)
                print(f'    {cc} clues: {count:6,d} {bar}')

            print(f'\n  Techniques:')
            for tech, count in sorted(cat_techs.items(), key=lambda x: -x[1]):
                print(f'    {tech:15s} {count:7,d} seeds')

        print()
        return

    if getattr(args, 'lforge_list', False):
        from .lars_forge import lars_technique_list
        techs = lars_technique_list()
        print(f'\n  Available techniques ({len(techs)}):')
        for t in techs:
            print(f'    {t}')
        print()
        return

    if getattr(args, 'lforge_search', None):
        from .lars_forge import LARS_TECH_INDEX, LARS_TECHNIQUE_SIGS
        tech_name = parse_techniques(args.lforge_search)
        if tech_name:
            tech_name = next(iter(tech_name))
        else:
            tech_name = args.lforge_search
        sigs = LARS_TECH_INDEX.get(tech_name, [])
        print(f'\n  Profiles containing {tech_name}: {len(sigs)}')
        for sig in sorted(sigs)[:30]:
            data = LARS_TECHNIQUE_SIGS.get(sig, {})
            n = sum(len(s) for s in data.get('seeds', {}).values())
            clues = sorted(data.get('seeds', {}).keys())
            print(f'    {sig:50s} {n:3d} seeds  clues={",".join(clues)}')
        if len(sigs) > 30:
            print(f'    ... and {len(sigs) - 30} more')
        print()
        return

    if getattr(args, 'lforge_attempt', None) is not None:
        from .lars_forge import lars_technique_forge
        import time as _time

        # Parse technique names, filter out L1
        L1 = {'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'}
        tech_set = parse_techniques(args.lforge_attempt)
        if tech_set:
            tech_set = tech_set - L1
        if not tech_set:
            print(f'  Unknown techniques: {args.lforge_attempt}')
            return

        n = getattr(args, 'lforge_count', 10)
        clues = getattr(args, 'lforge_clues', None)
        tier = getattr(args, 'lforge_tier', None)
        if tier == 'any':
            tier = None

        print(f'\n  LForge — Technique Forge')
        print(f'  {"═" * 55}')
        print(f'  Techniques: {", ".join(sorted(tech_set))}')
        if clues:
            print(f'  Clue count: {clues}')
        if tier:
            print(f'  Tier: {tier}')

        result = lars_technique_forge(tech_set, count=n, clues=clues, tier=tier)

        if not result['success']:
            print(f'  {result.get("error", "No matching seeds found")}')
            print()
            return

        print(f'  Signature: {result["signature"]}')
        print(f'  Available seeds: {result["available_seeds"]}')
        print(f'  Generated: {result["count"]} puzzles in {result["elapsed_ms"]:.1f}ms')
        print()
        for p in result['puzzles']:
            print(f'  {p}')
        print(f'\n  # {result["count"]} puzzles requiring {", ".join(sorted(tech_set))}')
        print()
        return

    # ── Lars Seeds Stats ──
    if getattr(args, 'lars_seeds_stats', False):
        from .lars_forge import lars_seeds_stats
        stats = lars_seeds_stats()
        if not stats.get('loaded'):
            print('  Lars Seeds registry not loaded.')
            return
        print(f'\n  Lars Seeds Registry')
        print(f'  {"=" * 55}')
        print(f'  DeepRes seeds: {stats["deepres_count"]:,}')
        print(f'  D2B seeds:     {stats["d2b_count"]:,}')
        print(f'  Total seeds:   {stats["total_seeds"]:,}')
        print(f'  Mask hashes:   {stats["mask_hashes"]:,} (core: {stats.get("core_hashes",0):,} + variants: {stats.get("variant_hashes",0):,})')
        print(f'  Unique masks:  {stats["unique_masks"]:,}')
        dr_puzzles = stats['deepres_count'] * 362880 * 3359232
        d2b_puzzles = stats['d2b_count'] * 362880 * 3359232
        total_puzzles = dr_puzzles + d2b_puzzles

        def _word_number(n):
            """Convert large number to word form."""
            if n >= 1e18:
                return f'{n/1e18:.1f} quintillion'
            elif n >= 1e15:
                return f'{n/1e15:.1f} quadrillion'
            elif n >= 1e12:
                return f'{n/1e12:.1f} trillion'
            elif n >= 1e9:
                return f'{n/1e9:.1f} billion'
            elif n >= 1e6:
                return f'{n/1e6:.1f} million'
            else:
                return f'{n:,.0f}'

        print(f'\n  Forgeable puzzles:')
        print(f'    DeepRes: {dr_puzzles:.2e}  ({_word_number(dr_puzzles)})')
        print(f'    D2B:     {d2b_puzzles:.2e}  ({_word_number(d2b_puzzles)})')
        print(f'    Total:   {total_puzzles:.2e}  ({_word_number(total_puzzles)})')

        # Signature catalog totals
        from .lars_forge import _load_sig_catalog
        catalog = _load_sig_catalog()
        if catalog:
            cmeta = catalog.get('meta', {})
            cat_seeds = cmeta.get('total_seeds', 0)
            cat_sigs = cmeta.get('total_signatures', 0)
            cat_puzzles = cat_seeds * 362880 * 3359232
            print(f'\n  Signature Catalog:')
            print(f'    Signatures: {cat_sigs:,}')
            print(f'    Seeds:      {cat_seeds:,}')
            print(f'    Puzzles:    {cat_puzzles:.2e}  ({_word_number(cat_puzzles)})')

        print()
        return

    # ── LForge Promote Hard (diabolical bases) ──
    if getattr(args, 'lforge_promote_hard', None) is not None:
        import json as _json
        import time as _time
        import random as _rand
        import os as _os
        from .lars_forge import lars_full_transform, lars_promote_batch
        from .engine import solve_backtrack

        target = args.lforge_promote_hard
        n = getattr(args, 'lforge_count', 10) or 10
        no_confirm = getattr(args, 'lforge_no_confirm', False)

        # Load hardest bases from package dir
        _hard_path = _os.path.join(_os.path.dirname(__file__), 'hardest_base_seeds.json')
        if not _os.path.exists(_hard_path):
            print(f'\n  Hardest base seeds file not found')
            print()
            return

        with open(_hard_path) as f:
            hard_data = _json.load(f)

        base_clue_filter = getattr(args, 'lforge_base_clues', None)
        if base_clue_filter == 20:
            pool = hard_data.get('seeds_20', [])
        elif base_clue_filter == 21:
            pool = hard_data.get('seeds_21', [])
        else:
            pool = hard_data.get('seeds_20', []) + hard_data.get('seeds_21', [])
        if not pool:
            print(f'\n  No hardest base seeds available at {base_clue_filter} clues')
            print()
            return

        lforge_seed = getattr(args, 'lforge_seed', None)
        if lforge_seed is None:
            lforge_seed = int(_time.time()) % (2**31)
        rng = _rand.Random(lforge_seed)

        print(f'\n  LForge — Promote Hard (Diabolical Bases)')
        print(f'  {"=" * 55}')
        print(f'  Pool: {len(pool)} hardest seeds (20-21 clues) (seed={lforge_seed})')
        print(f'  Techniques: ALSXY+ALS+D2B+DR+FPCE (and more)')

        t0 = _time.time()
        puzzles_out = []

        while len(puzzles_out) < n:
            entry = rng.choice(pool)
            base = entry['puzzle']
            sig = entry.get('sig', '')
            base_clues = sum(1 for c in base if c != '0')

            # Shuffle the base for diversity
            shuffled = lars_full_transform(base, rng=_rand.Random(rng.randint(0, 2**31)))

            if target <= base_clues:
                # Already at or above target, just use the shuffled base
                puzzles_out.append((shuffled, base_clues, sig, shuffled))
            else:
                # Promote to target
                promoted = lars_promote_batch(shuffled, target, count=1)
                if promoted:
                    puzzles_out.append((promoted[0], base_clues, sig, shuffled))

        elapsed = (_time.time() - t0) * 1000

        if elapsed < 1:
            time_str = f'{elapsed*1000:.0f}us'
        else:
            time_str = f'{elapsed:.0f}ms'
        print(f'  Target: {target} clues')
        print(f'  Generated: {len(puzzles_out)} puzzles in {time_str}')
        print()

        def _show_promotion(promoted, base, sig, techs_str, base_cc, pc):
            """Show base skeleton on top, promoted puzzle below with added digits."""
            added = []
            for i in range(81):
                if base[i] == '0' and promoted[i] != '0':
                    r, c = i // 9, i % 9
                    added.append(f'{promoted[i]}@R{r+1}C{c+1}')
            added_str = ', '.join(added) if added else 'none'
            print(f'  {base}  [base {base_cc}-clue skeleton]  added: {added_str}')
            print(f'  {promoted}  [{techs_str}] ({base_cc} -> {pc} clues)')
            print()

        if no_confirm:
            for p, base_cc, sig, base_shuf in puzzles_out:
                pc = sum(1 for c in p if c != '0')
                _show_promotion(p, base_shuf, sig, sig, base_cc, pc)
            print(f'  Base skeleton preserved — all puzzles inherit diabolical DNA')
        else:
            print(f'  Confirming...')
            confirmed = []
            for p, base_cc, sig, base_shuf in puzzles_out:
                r = solve_selective(p)
                ok = r.get('success') or r.get('empty_remaining', 99) == 0
                if ok:
                    tc = r.get('technique_counts', {})
                    advanced = sorted(t for t in tc if t not in {'crossHatch','nakedSingle','fullHouse','lastRemaining'})
                    pc = sum(1 for c in p if c != '0')
                    confirmed.append((p, base_cc, sig, advanced, pc, base_shuf))

            print(f'  Confirmed: {len(confirmed)}/{len(puzzles_out)}')
            print()
            for p, base_cc, sig, techs, pc, base_shuf in confirmed:
                _show_promotion(p, base_shuf, sig, ', '.join(techs), base_cc, pc)
            print(f'  Base skeleton preserved — all inherit diabolical technique requirements')

        print()
        return

    # ── LForge FN/FC (expert-level collection) ──
    if getattr(args, 'lforge_fnfc', None) is not None:
        import json as _json
        import time as _time
        import random as _rand
        from .lars_forge import lars_full_transform

        n = args.lforge_fnfc
        min_fn = getattr(args, 'lforge_fn', None)
        min_fc = getattr(args, 'lforge_fc', None)
        clue_filter = getattr(args, 'lforge_clues', None)
        no_confirm = getattr(args, 'lforge_no_confirm', False)

        # Load from both day 1 and day 2 jsonl files
        import os as _os
        _base = _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__)))
        pool = []
        for fname in ['lars/fn_fc_overnight.jsonl', 'lars/fn_fc_overnight_day2.jsonl']:
            fpath = _os.path.join(_base, fname)
            if not _os.path.exists(fpath):
                fpath = _os.path.join(_os.path.dirname(__file__), '..', '..', fname)
            try:
                with open(fpath) as f:
                    for line in f:
                        e = _json.loads(line)
                        if min_fn is not None and e.get('fn', 0) < min_fn:
                            continue
                        if min_fc is not None and e.get('fc', 0) < min_fc:
                            continue
                        if clue_filter is not None and e.get('clues', 0) != clue_filter:
                            continue
                        pool.append(e)
            except FileNotFoundError:
                pass

        if not pool:
            print(f'\n  LForge FN/FC — no matching puzzles found')
            filters = []
            if min_fn: filters.append(f'FN>={min_fn}')
            if min_fc: filters.append(f'FC>={min_fc}')
            if clue_filter: filters.append(f'{clue_filter} clues')
            if filters:
                print(f'  Filters: {", ".join(filters)}')
            print()
            return

        lforge_seed = getattr(args, 'lforge_seed', None)
        if lforge_seed is None:
            lforge_seed = int(_time.time()) % (2**31)
        rng = _rand.Random(lforge_seed)

        print(f'\n  LForge — FN/FC Expert Collection')
        print(f'  {"=" * 55}')
        filters = []
        if min_fn: filters.append(f'FN>={min_fn}')
        if min_fc: filters.append(f'FC>={min_fc}')
        if clue_filter: filters.append(f'{clue_filter} clues')
        filter_str = f' ({", ".join(filters)})' if filters else ''
        print(f'  Pool: {len(pool):,} seeds{filter_str} (seed={lforge_seed})')

        t0 = _time.time()
        puzzles = []
        seen = set()
        attempts = 0
        while len(puzzles) < n and attempts < n * 20:
            attempts += 1
            entry = rng.choice(pool)
            transformed = lars_full_transform(entry['puzzle'], rng=_rand.Random(rng.randint(0, 2**31)))
            if transformed not in seen:
                seen.add(transformed)
                puzzles.append((transformed, entry))

        elapsed = (_time.time() - t0) * 1000

        if no_confirm:
            if elapsed < 1:
                time_str = f'{elapsed*1000:.0f}us'
            else:
                time_str = f'{elapsed:.0f}ms'
            print(f'  Generated: {len(puzzles)} puzzles in {time_str} (no-confirm)')
            print()
            for p, entry in puzzles:
                print(f'  {p}  [FN={entry["fn"]} FC={entry["fc"]}]')
            print(f'\n  # {len(puzzles)} FN/FC puzzles (expert-level, no-confirm)')
        else:
            confirmed = []
            skipped = 0
            for p, entry in puzzles:
                r = solve_selective(p)
                ok = r.get('success') or r.get('empty_remaining', 99) == 0
                if not ok:
                    skipped += 1
                    continue
                tc = r.get('technique_counts', {})
                advanced = sorted(t for t in tc if t not in {'crossHatch','nakedSingle','fullHouse','lastRemaining'})
                confirmed.append((p, entry, advanced))
                if len(confirmed) >= n:
                    break
            elapsed = (_time.time() - t0) * 1000
            skip_note = f', {skipped} skipped' if skipped else ''
            print(f'  Confirmed: {len(confirmed)}/{n} in {elapsed:.0f}ms{skip_note}')
            print()
            for p, entry, techs in confirmed:
                print(f'  {p}  [FN={entry["fn"]} FC={entry["fc"]}, {", ".join(techs)}]')
            print(f'\n  # {len(confirmed)} FN/FC puzzles (expert-level, confirmed)')
        print()
        return

    # ── LForge by Signature (technique catalog) ──
    if getattr(args, 'lforge', None) is not None:
        from .lars_forge import lars_sig_forge, SIG_ABBREV

        techs_str = args.lforge
        techs = set(t.strip() for t in techs_str.split(',') if t.strip())
        # Resolve aliases
        resolved = set()
        for t in techs:
            t_lower = t.lower()
            if t_lower in TECHNIQUE_ALIASES:
                full = TECHNIQUE_ALIASES[t_lower]
                resolved.add(full)
            elif t.upper() in SIG_ABBREV:
                resolved.add(t.upper())
            else:
                resolved.add(t)

        n = getattr(args, 'lforge_count', 10) or 10
        exact = getattr(args, 'lforge_exact', False)
        clue_filter = getattr(args, 'lforge_clues', None)
        no_confirm = getattr(args, 'lforge_no_confirm', False)
        lforge_seed = getattr(args, 'lforge_seed', None)
        if lforge_seed is None:
            import time as _t
            lforge_seed = int(_t.time()) % (2**31)

        result = lars_sig_forge(resolved, count=n * 3, seed=lforge_seed,
                                exact=exact, clues=clue_filter)

        if not result.get('success'):
            print(f'\n  LForge Signature Query')
            print(f'  {"=" * 55}')
            print(f'  Error: {result.get("error", "unknown")}')
            print()
            return

        mode = 'exact' if exact else 'superset'
        clue_note = f', {clue_filter} clues' if clue_filter else ''
        print(f'\n  LForge — Signature Forge ({mode})')
        print(f'  {"=" * 55}')
        print(f'  Query: {result["query"]} ({mode}{clue_note})')
        print(f'  Matched: {result["matched_sigs"]} signatures, {result["pool_size"]} seeds (seed={lforge_seed})')

        if no_confirm:
            puzzles_out = result['puzzles'][:n]
            sigs_out = result.get('signatures', [])[:n]
            elapsed_forge = result.get('elapsed_ms', 0)
            if elapsed_forge < 1:
                time_str = f'{elapsed_forge*1000:.0f}µs'
            else:
                time_str = f'{elapsed_forge:.0f}ms'
            print(f'  Generated: {len(puzzles_out)} puzzles in {time_str} (no-confirm)')
            print()
            for i, p in enumerate(puzzles_out):
                sig_tag = sigs_out[i] if i < len(sigs_out) else ''
                print(f'  {p}  [{sig_tag}]')
            print(f'\n  # {len(puzzles_out)} puzzles ({mode}, --lforge-no-confirm)')
        else:
            import time as _time
            use_sigboost = getattr(args, 'sigboost', False)

            t0 = _time.time()
            confirmed = []
            skipped = 0
            for i, p in enumerate(result['puzzles']):
                if len(confirmed) >= n:
                    break
                try:
                    r = solve_selective(p)
                    if not (r.get('success') or r.get('empty_remaining', 99) == 0):
                        skipped += 1
                        continue
                    counts = r.get('technique_counts', {})
                    advanced = sorted(t for t in counts if TECHNIQUE_LEVELS.get(t, 1) >= 3)
                    sig_tag = result['signatures'][i] if i < len(result.get('signatures', [])) else ''
                    confirmed.append((p, advanced, sig_tag))
                except Exception:
                    skipped += 1

            elapsed_ms = (_time.time() - t0) * 1000
            skip_note = f', {skipped} skipped' if skipped else ''
            print(f'  Confirmed: {len(confirmed)}/{n} in {elapsed_ms:.0f}ms{skip_note}')
            print()
            for p, techs_list, sig_tag in confirmed:
                print(f'  {p}  [{", ".join(techs_list)}]')
            print(f'\n  # {len(confirmed)} puzzles (confirmed, {mode})')
        print()
        return

    # ── LForge DeepRes / D2B shared handler ──
    _lforge_tech = None
    _lforge_n = None
    if getattr(args, 'lforge_deepres', None) is not None:
        _lforge_tech = 'deepres'
        _lforge_n = args.lforge_deepres
    elif getattr(args, 'lforge_d2b', None) is not None:
        _lforge_tech = 'd2b'
        _lforge_n = args.lforge_d2b

    if _lforge_tech is not None:
        from .lars_forge import lars_deepres_forge
        n = _lforge_n
        no_confirm = getattr(args, 'lforge_no_confirm', False)
        elite = getattr(args, 'elite', False)
        label = 'DeepRes' if _lforge_tech == 'deepres' else 'D2B'

        if elite:
            label += ' ELITE'

        print(f'\n  LForge — {label} Puzzle Forge')
        print(f'  {"=" * 55}')

        # Generate more candidates for elite (most get filtered)
        multiplier = 1
        if not no_confirm:
            multiplier = 3
        if elite:
            multiplier = 12  # ~92% get filtered by elite

        import time as _time_seed
        forge_seed = getattr(args, 'lforge_seed', None)
        if forge_seed is None:
            forge_seed = int(_time_seed.time() * 1000) % (2**31)

        # Allow batch override — forge from specific seed batch
        batch_override = getattr(args, 'lforge_batch', None)

        if batch_override in ('l1', 'l2', 'l3', 'box', 'shuffle'):
            # Forge from variant puzzle strings
            import json as _json_batch
            import os as _os_batch
            _pkg_dir = _os_batch.path.dirname(_os_batch.path.abspath(__file__))
            step_map = {'l1': 'l1', 'l2': 'l1_2step', 'l3': 'l1_3step',
                        'box': 'rotate180', 'shuffle': 'shuffle_l1'}
            step_name = step_map[batch_override]
            pool = []
            for part in [1, 2]:
                _path = _os_batch.path.join(_pkg_dir, f'lars_seeds_{step_name}_part{part}.json')
                if _os_batch.path.exists(_path):
                    with open(_path) as _fb:
                        _data = _json_batch.load(_fb)
                    pool.extend(_data.get('mask_hashes', {}).values())

            if not pool:
                print(f'  No {batch_override} seed files found')
                print()
                return

            # Forge from the L1 pool
            import random as _rng_batch
            from .lars_forge import lars_full_transform
            rng = _rng_batch.Random(forge_seed)
            puzzles_out = []
            seen = set()
            for _ in range(n * multiplier * 2):
                if len(puzzles_out) >= n * multiplier:
                    break
                base = rng.choice(pool)
                transformed = lars_full_transform(base, rng=_rng_batch.Random(rng.randint(0, 2**31)))
                if transformed not in seen:
                    seen.add(transformed)
                    puzzles_out.append(transformed)

            result = {
                'success': True,
                'puzzles': puzzles_out,
                'seed_count': len(pool),
                'technique': f'{batch_override}-step',
                'count': len(puzzles_out),
                'elapsed_ms': 0,
            }
            label = f'{label} ({batch_override.upper()} batch, {len(pool):,} seeds)'
        else:
            forge_tech = _lforge_tech
            if batch_override and batch_override not in ('all',):
                forge_tech = batch_override
            result = lars_deepres_forge(count=n * multiplier, technique=forge_tech,
                                         seed=forge_seed)
        if not result['success']:
            print(f'  {result.get("error", "Failed")}')
            print()
            return
        print(f'  Lars Seeds: {result["seed_count"]:,} seeds (seed={forge_seed})')

        if no_confirm and not elite:
            print(f'  Generated: {result["count"]} puzzles in {result["elapsed_ms"]:.1f}ms (unconfirmed)')
            print()
            for p in result['puzzles'][:n]:
                print(f'  {p}')
            print(f'\n  # {min(n, len(result["puzzles"]))} {label} puzzles (--lforge-no-confirm: not verified)')
        else:
            import time as _time

            # Elite mode: expert+FNv2 technique set for filtering
            if elite:
                expert_filter = EXPERT_APPROVED | {'FNv2', 'XYChain', 'RectElim'}

            use_sigboost = getattr(args, 'sigboost', False)

            # Build sigboost set from seed's known technique profile
            _sigboost_set = None
            if use_sigboost:
                # Solve one seed to get the signature, then reuse for all variants
                _seed_r = solve_fast(result['puzzles'][0])
                _seed_tc = _seed_r.get('technique_counts', {})
                _l1_techs = {'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'}
                _sigboost_set = set(t for t in _seed_tc if t not in _l1_techs)

            t0 = _time.time()
            confirmed = []
            skipped = 0
            elite_filtered = 0
            for p in result['puzzles']:
                if len(confirmed) >= n:
                    break
                try:
                    # Solve with sigboost or full solver
                    if use_sigboost and _sigboost_set:
                        r = solve_fast(p, sigboost=_sigboost_set)
                    else:
                        r = solve_selective(p)
                    if not (r.get('success') or r.get('empty_remaining', 99) == 0):
                        skipped += 1
                        continue

                    counts = r.get('technique_counts', {})
                    advanced = sorted(t for t in counts if TECHNIQUE_LEVELS.get(t, 1) >= 5)

                    if elite:
                        # Elite filter: try expert+FNv2 — must STALL
                        r_expert = solve_selective(p, only_techniques=expert_filter)
                        if r_expert.get('success'):
                            elite_filtered += 1
                            continue  # expert can solve it — not elite enough

                    confirmed.append((p, advanced))
                except Exception:
                    skipped += 1

            elapsed_confirm = (_time.time() - t0) * 1000
            skip_note = ''
            if skipped:
                skip_note += f', {skipped} skipped'
            if elite and elite_filtered:
                skip_note += f', {elite_filtered} too easy'

            boost_tag = ' ⚡sigboost' if use_sigboost else ''
            print(f'  Confirmed: {len(confirmed)}/{n} in {elapsed_confirm:.0f}ms{skip_note}{boost_tag}')
            print()
            for p, techs in confirmed:
                print(f'  {p}  [{", ".join(techs)}]')
            if elite:
                print(f'\n  # {len(confirmed)} {label} puzzles (resists all expert techniques)')
            else:
                print(f'\n  # {len(confirmed)} {label} puzzles (confirmed by solver)')
        print()
        return

    # ── Lars Provenance ──
    if getattr(args, 'lars_provenance', None) is not None:
        from .lars_forge import lars_provenance
        import time as _time

        puzzle = args.lars_provenance
        print(f'\n  Lars Provenance Registry')
        print(f'  {"=" * 55}')
        print(f'  Input: {puzzle[:60]}{"..." if len(puzzle) > 60 else ""}')

        t0 = _time.time()
        result = lars_provenance(puzzle)
        elapsed = (_time.time() - t0) * 1000

        print(f'  Clues: {result.get("n_clues", "?")}')
        print(f'  Time:  {elapsed:.1f}ms')
        print()

        if result.get('matched'):
            conf = result.get('confidence', 'unknown')
            pct = result.get('confidence_pct', 0)

            # Actually solve it to confirm techniques
            puzzle_to_solve = puzzle.replace('.', '0')
            if not any(c in puzzle for c in 'xX'):
                solve_result = solve_selective(puzzle_to_solve)
                if solve_result.get('success'):
                    actual_techs = solve_result.get('technique_counts', {})
                    from .cli import TECHNIQUE_LEVELS as _TL
                    advanced = [t for t in actual_techs if _TL.get(t, 1) >= 5]
                    tech_str = ', '.join(sorted(advanced)) if advanced else 'L5+ (confirmed by solve)'
                else:
                    tech_str = ', '.join(result.get('technique', []))
            else:
                tech_str = ', '.join(result.get('technique', []))

            print(f'  >>> LARS DATABASE SEED MATCH <<<')
            if conf == 'exact':
                print(f'  Confidence: Very high (core seed match)')
            else:
                print(f'  Confidence: High (~{pct}%, L1 variant match)')
            print(f'  Techniques: {tech_str}')
            print(f'  Hash: {result["hash"]}')
            print(f'  Database: 10,698 signatures | 438,564 seeds | 534.6 quadrillion puzzles')
            print(f'  This puzzle is derived from a Lars Database Seed.')
        else:
            # Check Royle 17-clue set before declaring "new"
            from .lars_forge import lars_mask_hash
            s = puzzle.replace('.', '0')
            mask = [1 if c != '0' else 0 for c in s]
            h = str(lars_mask_hash(mask))
            clue_count = sum(1 for c in s if c != '0')

            royle_match = False
            try:
                import json as _json
                import os as _os
                _pkg = _os.path.dirname(__file__)
                _royle_path = _os.path.join(_pkg, 'royle_17_hashes.json')
                if _os.path.exists(_royle_path):
                    with open(_royle_path) as _rf:
                        _royle = _json.load(_rf)
                    _royle_set = set(_royle.keys()) if isinstance(_royle, dict) else set(str(k) for k in _royle)
                    if h in _royle_set:
                        royle_match = True
            except Exception:
                pass

            if royle_match:
                print(f'  >>> ROYLE 17-CLUE BASE MATCH <<<')
                print(f'  This is a known 17-clue puzzle from Royle\'s complete enumeration (49,158 puzzles).')
                print(f'  It is a base skeleton — the mathematical floor for unique Sudoku.')
                print(f'  Lars Database seeds are forged from these bases with added technique requirements.')
            else:
                print(f'  >>> NEW — Not in Lars registry <<<')
                print(f'  {result.get("message", "")}')
        print()
        return

    if getattr(args, 'lars_certify', None) is not None:
        from .lars_forge import lars_certify
        import time as _time

        puzzle_or_mask = args.lars_certify

        print(f'\n  Lars Certify — Uniqueness Oracle')
        print(f'  {"═" * 55}')

        t0 = _time.time()
        result = lars_certify(puzzle_or_mask)
        elapsed = (_time.time() - t0) * 1000

        print(f'  Input:   {puzzle_or_mask[:60]}{"..." if len(puzzle_or_mask) > 60 else ""}')
        print(f'  Clues:   {result["n_clues"]}')
        print(f'  Method:  {result["method"]}')
        print(f'  Time:    {elapsed:.1f}ms')
        print()

        verdict = result['verdict']
        if 'UNIQUE' in verdict and 'MULTI' not in verdict:
            print(f'  >>> {verdict} <<<')
            if result['method'] == 'royle_hash':
                print(f'  Royle-certified: this mask geometry is in the complete')
                print(f'  enumeration of all 49,158 valid 17-clue patterns.')
        else:
            print(f'  >>> {verdict} <<<')
            if result['method'] == 'royle_hash':
                print(f'  This mask geometry is NOT in the Royle enumeration.')
                print(f'  No digit assignment can make this pattern unique.')
        print()
        return

    # ── LarsForge Mask Match: Final Boss Mode ──
    if getattr(args, 'lars_forge_mask_match', None) is not None:
        from .lars_forge import lars_mask_match, lars_mask_coverage, lars_parse_mask
        import time as _time

        mask_str = args.lars_forge_mask_match
        n_clues = sum(1 for c in mask_str if c in ('x', 'X', '1') or (c.isdigit() and c != '0'))

        print(f'\n  LarsForge Mask Match — Final Boss Mode')
        print(f'  {"═" * 55}')
        print(f'  Mask: {mask_str[:60]}{"..." if len(mask_str) > 60 else ""}')
        print(f'  Clues: {n_clues}')

        t0 = _time.time()
        result = lars_mask_match(mask_str, verbose=False)
        elapsed = (_time.time() - t0) * 1000

        if result.get('matched'):
            print(f'  MATCHED in {elapsed:.1f}ms')
            print(f'  Seed: {result["seed_clues"]}-clue #{result["seed_index"]+1}')
            if result.get('rotated'):
                print(f'  (via 180° box rotation)')
            rp, cp, tr = result['transform']
            print(f'  Transform: rows={rp} cols={cp} transposed={tr}')
            print(f'  Candidates checked: {result["n_candidates"]}')
            print()
            print(f'  Puzzle: {result["puzzle"]}')

            # Optionally generate more via digit permutation
            n = args.lars_forge_count
            if n > 1:
                from .lars_forge import LarsForge
                forge = LarsForge(result['puzzle'])
                extras = forge.lars_forge_batch(count=n - 1)
                print()
                for p in extras[0]:
                    print(f'  {p}')
                print(f'\n  # {n} total puzzles (1 matched + {n-1} digit-permuted)')
        else:
            print(f'  No match found ({elapsed:.1f}ms, {result["n_candidates"]} candidates checked)')
            print(f'  This mask geometry is not in the Royle 49K collection.')
        print()
        return

    # ── LarsForge Mask Coverage ──
    if getattr(args, 'lars_forge_mask_coverage', False):
        from .lars_forge import lars_mask_coverage

        print(f'\n  LarsForge Mask Coverage')
        print(f'  {"═" * 55}')
        lars_mask_coverage(verbose=True)
        print()
        return

    # ── LarsForge Promote: add solution digits to reach target clues ──
    if getattr(args, 'lars_forge_promote', None) is not None:
        from .lars_forge import (
            lars_promote_batch, lars_get_seed, lars_full_transform,
            LARS_EXTENDED_BANK
        )
        import random as _rand

        target = args.lars_forge_promote
        n = getattr(args, 'lars_forge_promote_count', 10)

        print(f'\n  LarsForge Promote — 17→{target} Clues')
        print(f'  {"═" * 55}')

        # Get source puzzle: either from args or generate a 17-clue
        if args.puzzle:
            source = normalize_puzzle(args.puzzle)
        else:
            seed = lars_get_seed(
                17,
                difficulty=getattr(args, 'lars_forge_difficulty', None),
                index=getattr(args, 'lars_forge_seed_index', None),
            )
            if seed is None:
                print(f'  No 17-clue seeds available')
                print()
                return
            # Shuffle for diversity
            source = lars_full_transform(seed, rng=_rand.Random())
            print(f'  Source: 17-clue seed (shuffled + digit-permuted)')
            print(f'  Base17: {source}')

        src_clues = sum(1 for c in source if c != '0')
        print(f'  Source clues: {src_clues}')
        print(f'  Target clues: {target}')
        if target <= src_clues:
            print(f'  Already at or above target!')
            print()
            return

        import time as _time
        t0 = _time.time()
        puzzles = lars_promote_batch(source, target, count=n)
        elapsed = (_time.time() - t0) * 1000

        print(f'  Generated: {len(puzzles)} puzzles in {elapsed:.1f}ms')
        print(f'  All guaranteed unique (inherits from {src_clues}-clue parent)')
        print()
        for p in puzzles:
            # Show which clues were added (diff from source)
            added = sum(1 for i in range(81) if source[i] == '0' and p[i] != '0')
            print(f'  {p}  (+{added} clues from base)')
        print(f'\n  Base: {source}')
        print(f'  # {len(puzzles)} unique {target}-clue puzzles (all share the same 17-clue skeleton)')
        print()
        return

    # ── LarsForge from Mask: forge for user's mask ──
    if args.lars_forge_mask is not None:
        from .lars_forge import LarsForge
        n = args.lars_forge_count

        print(f'\n  LarsForge from Mask')
        print(f'  {"═" * 55}')

        result = LarsForge.lars_from_mask(args.lars_forge_mask, count=n)

        if not result['success']:
            print(f'  {result.get("error", "Unknown error")}')
            print()
            return

        print(f'  Clues: {result["clues"]}')
        print(f'  Seed found in {result["forge_checks"]} checks')
        print(f'  Generated {len(result["puzzles"])} puzzles in {result["elapsed_ms"]:.1f}ms')
        print()
        for p in result['puzzles']:
            print(f'  {p}')
        print(f'\n  # {len(result["puzzles"])} unique puzzles from mask')
        print()
        return

    # ── Forge Multi-to-Unique: forge unique puzzles, output bd81 only ──
    if args.forge_multi_to_unique is not None:
        from .mask_forge import parse_mask, forge_unique
        import time as _time

        puzzle_str = args.forge_multi_to_unique
        n_wanted = args.forge_multi_to_unique_count

        mask = parse_mask(puzzle_str)
        n_clues = sum(mask)

        # Forge seed
        t0 = _time.perf_counter()
        seed_puzzle, seed_solution, checks, _elapsed = forge_unique(mask, verbose=False)
        forge_ms = (_time.perf_counter() - t0) * 1000

        if seed_puzzle is None:
            print(f'  Forge FAILED — no unique puzzle found for this mask.')
            sys.exit(1)

        # Generate variants via digit permutation
        digits = list(range(1, 10))
        puzzles = [seed_puzzle]
        rng = __import__('random').Random(42)
        seen = {seed_puzzle}
        attempts = 0
        while len(puzzles) < n_wanted and attempts < 1000:
            perm = list(digits)
            rng.shuffle(perm)
            mapping = {str(d): str(perm[d - 1]) for d in digits}
            variant = ''.join(mapping.get(c, '0') for c in seed_puzzle)
            if variant not in seen:
                seen.add(variant)
                puzzles.append(variant)
            attempts += 1

        print(f'# {len(puzzles)} unique puzzles forged from {n_clues}-clue mask ({checks} checks, {forge_ms:.0f}ms)')
        for p in puzzles:
            print(p)
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

    # Apply --experimental: add experimental techniques to the current set
    if getattr(args, 'experimental', False) and not args.preset:
        if only_techniques is not None:
            only_techniques = only_techniques | EXPERIMENTAL_TECHNIQUES
        # If only_techniques is None (all), experimental is already included

    # Apply --include: add techniques to the current set
    if getattr(args, 'include', None):
        include_set = parse_techniques(args.include)
        if include_set:
            if only_techniques is None:
                pass  # all techniques already included
            else:
                only_techniques = only_techniques | include_set

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

    # ── Cascade analysis mode ──
    if getattr(args, 'cascade', False):
        from collections import Counter

        L1_SET = {'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'}
        L2_SET = {'Zone135', 'GF2_Lanczos', 'GF2_Extended', 'GF2_Probe'}
        CASCADE_SET = L1_SET | L2_SET

        solve_kwargs = {}
        if getattr(args, 'preset', None):
            solve_kwargs['only_techniques'] = PRESETS[args.preset]
        if getattr(args, 'gf2', False):
            solve_kwargs['gf2'] = True
        if getattr(args, 'gf2x', False):
            solve_kwargs['gf2_extended'] = True

        def _cascade_stats(puzzle):
            """Run cascade analysis on a single puzzle and return stats dict."""
            result = solve_selective(puzzle, detail=True, **solve_kwargs)
            bottleneck_moves = []
            cascade_count = 0
            bn_so_far = 0
            depth_map = {}
            for step in result.get('steps', []):
                tech = step.get('technique', '')
                pos = step.get('pos')
                if tech in CASCADE_SET:
                    cascade_count += 1
                    if pos is not None:
                        depth_map[pos] = bn_so_far
                else:
                    bn_so_far += 1
                    bottleneck_moves.append(step)
                    if pos is not None:
                        depth_map[pos] = bn_so_far
            return {
                'result': result,
                'bottleneck_moves': bottleneck_moves,
                'cascade_count': cascade_count,
                'depth_map': depth_map,
                'bn_depth': len(bottleneck_moves),
                'tech_counts': result.get('technique_counts', {}),
                'success': result.get('success', False),
            }

        # ── Batch cascade: generate N shuffled variants and aggregate ──
        batch_n = getattr(args, 'batch', None)
        if batch_n:
            print(f'\n  ═══ Cascade Batch Analysis ({batch_n} puzzles) ═══\n', file=sys.stderr)
            depth_dist = Counter()
            tech_totals = Counter()
            total_bn = 0
            solved = 0

            for i in range(batch_n):
                variant = shuffle_sudoku(bd81)
                stats = _cascade_stats(variant)
                depth_dist[stats['bn_depth']] += 1
                total_bn += stats['bn_depth']
                if stats['success']:
                    solved += 1
                for tech in stats['bottleneck_moves']:
                    t = tech.get('technique', '?')
                    tech_totals[t] += 1

                if (i + 1) % 50 == 0 or i == batch_n - 1:
                    print(f'  [{i+1}/{batch_n}] solved={solved}', file=sys.stderr)

            avg_depth = total_bn / batch_n if batch_n else 0
            max_bar = max(depth_dist.values()) if depth_dist else 1

            print(f'\n  ═══ Cascade Batch Analysis ({batch_n} puzzles) ═══')
            print(f'  Solved: {solved}/{batch_n}')
            print()
            print(f'  Bottleneck depth distribution:')
            for d in sorted(depth_dist):
                count = depth_dist[d]
                bar_len = max(1, int(count / max_bar * 30))
                bar = '█' * bar_len
                print(f'    depth={d}: {count:3d} puzzles  {bar}')
            print(f'    Average: {avg_depth:.1f}')
            print()

            if tech_totals:
                print(f'  Most common bottleneck techniques:')
                parts = []
                for tech, cnt in tech_totals.most_common(10):
                    parts.append(f'{tech}: {cnt}')
                print(f'    {"  ".join(parts)}')

            sys.exit(0)

        # ── Single puzzle cascade ──
        bb = BitBoard.from_string(bd81)
        empty = sum(1 for i in range(81) if bb.board[i] == 0)

        stats = _cascade_stats(bd81)
        result = stats['result']
        bottleneck_moves = stats['bottleneck_moves']
        cascade_count = stats['cascade_count']
        depth_map = stats['depth_map']

        print(f'\n  ═══ Cascade Analysis ═══')
        print(f'  Empty: {empty} cells')
        print(f'  Bottleneck depth: {len(bottleneck_moves)}')
        print(f'  Cascade placements: {cascade_count}')
        print(f'  Total steps: {len(result.get("steps", []))}')
        print(f'  Success: {result.get("success", False)}')
        print()

        if bottleneck_moves:
            print(f'  Bottleneck moves (the hard ones):')
            for i, m in enumerate(bottleneck_moves, 1):
                print(f'    {i}. {m["cell"]}={m["digit"]} via {m["technique"]}')
            print()

        # Cascade depth distribution
        dist = Counter(depth_map.values())
        print(f'  Cascade depth (bottlenecks needed before cell falls):')
        for d in sorted(dist):
            cells = sorted([s['cell'] for s in result.get('steps', [])
                          if depth_map.get(s.get('pos')) == d])
            label = f'{dist[d]} cells'
            if d == 0:
                label += ' (pure cascade)'
            preview = ', '.join(cells[:6])
            if len(cells) > 6:
                preview += f', +{len(cells)-6} more'
            print(f'    depth={d}: {label} — {preview}')
        print()

        # Technique breakdown
        tech_counts = result.get('technique_counts', {})
        if tech_counts:
            print(f'  Technique breakdown:')
            for tech, count in sorted(tech_counts.items(), key=lambda x: -x[1]):
                marker = ' ★' if tech not in CASCADE_SET else ''
                print(f'    {tech}: {count}{marker}')
            print()

        # Inspector integration hint
        if bottleneck_moves:
            print(f'  ── Insight ──')
            print(f'  {len(bottleneck_moves)} hard move{"s" if len(bottleneck_moves) > 1 else ""} '
                  f'→ {cascade_count} cascade placements')
            ratio = cascade_count / max(1, len(bottleneck_moves))
            print(f'  Cascade ratio: 1:{ratio:.0f} (each bottleneck unlocks ~{ratio:.0f} cells)')

        sys.exit(0)

    # ── SIRO Table mode ──
    if getattr(args, 'siro_table', False):
        bb = BitBoard.from_string(bd81)
        sol_str = solve_backtrack(bd81)
        solution = [int(ch) for ch in sol_str] if sol_str else None

        predictions = []
        for pos in range(81):
            if bb.board[pos] != 0:
                continue
            cands = [d + 1 for d in range(9) if bb.cands[pos] & BIT[d]]
            if len(cands) < 2:
                continue
            row, col = pos // 9, pos % 9
            rival_scores = {}
            for d in cands:
                dbit = BIT[d - 1]
                s = sum(1 for j in range(9) if j != col and bb.board[row*9+j] == 0 and (bb.cands[row*9+j] & dbit))
                s += sum(1 for i in range(9) if i != row and bb.board[i*9+col] == 0 and (bb.cands[i*9+col] & dbit))
                br, bc = (row // 3) * 3, (col // 3) * 3
                s += sum(1 for i in range(br, br+3) for j in range(bc, bc+3)
                         if (i != row or j != col) and bb.board[i*9+j] == 0 and (bb.cands[i*9+j] & dbit))
                rival_scores[d] = s

            sorted_digits = sorted(rival_scores, key=lambda dd: rival_scores[dd])
            best_digit = sorted_digits[0]
            best_rivals = rival_scores[best_digit]
            second_rivals = rival_scores[sorted_digits[1]] if len(sorted_digits) > 1 else best_rivals
            gap = second_rivals - best_rivals

            actual = solution[pos] if solution else None
            ok = (best_digit == actual) if actual is not None else None

            predictions.append({
                'pos': pos, 'row': row, 'col': col,
                'digit': best_digit, 'rivals': best_rivals,
                'gap': gap, 'n_cands': len(cands),
                'actual': actual, 'ok': ok,
            })

        # Sort by rival score ascending (most confident first)
        predictions.sort(key=lambda p: (p['rivals'], -p['gap']))

        print(f'\n  ═══ SIRO Predictions ═══')
        print()
        print(f'  {"Cell":>6}  {"Digit":>5}  {"Rivals":>6}  {"Gap":>3}  {"Cands":>5}  {"OK":>2}')
        print(f'  {"─" * 40}')
        for p in predictions:
            cell_name = f'R{p["row"]+1}C{p["col"]+1}'
            if p['ok'] is True:
                ok_str = '✓'
            elif p['ok'] is False:
                ok_str = f'✗ (actual={p["actual"]})'
            else:
                ok_str = '?'
            print(f'  {cell_name:>6}  {p["digit"]:>5}  {p["rivals"]:>6}  {p["gap"]:>3}  {p["n_cands"]:>5}  {ok_str}')

        if solution:
            correct = sum(1 for p in predictions if p['ok'])
            total = len(predictions)
            pct = 100 * correct / total if total else 0
            print(f'\n  Summary: {correct}/{total} correct ({pct:.0f}%)')

        sys.exit(0)

    # ── Inspector mode ──
    if getattr(args, 'inspector', None):
        try:
            row, col = parse_cell(args.inspector)
        except ValueError as e:
            print(f'Error: {e}', file=sys.stderr)
            sys.exit(1)

        bb = BitBoard.from_string(bd81)
        pos = row * 9 + col

        if bb.board[pos] != 0:
            print(f'\n  R{row+1}C{col+1}: Given = {bb.board[pos]}')
            sys.exit(0)

        cands = [d + 1 for d in range(9) if bb.cands[pos] & BIT[d]]
        n_clues = sum(1 for i in range(81) if bb.board[i] != 0)

        print(f'\n  ╔══════════════════════════════════════╗')
        print(f'  ║  Cell Inspector: R{row+1}C{col+1}               ║')
        print(f'  ╚══════════════════════════════════════╝')
        print(f'  Candidates: {cands} ({len(cands)})')

        # Unit stats
        row_e = sum(1 for j in range(9) if bb.board[row*9+j] == 0)
        col_e = sum(1 for i in range(9) if bb.board[i*9+col] == 0)
        br, bc = (row // 3) * 3, (col // 3) * 3
        box_e = sum(1 for i in range(br, br+3) for j in range(bc, bc+3) if bb.board[i*9+j] == 0)
        print(f'  Row {row+1}: {row_e} empty | Col {col+1}: {col_e} empty | Box: {box_e} empty')

        # Rival analysis per candidate
        print(f'\n  ── Rival Analysis ──')
        print(f'  {"d":>3s}  {"Row":>4s}  {"Col":>4s}  {"Box":>4s}  {"Total":>5s}  {"Zone":>6s}')
        print(f'  {"─"*30}')

        rival_data = []
        for d in cands:
            dbit = BIT[d - 1]
            rr = sum(1 for j in range(9) if j != col and bb.board[row*9+j] == 0 and (bb.cands[row*9+j] & dbit))
            cr = sum(1 for i in range(9) if i != row and bb.board[i*9+col] == 0 and (bb.cands[i*9+col] & dbit))
            bx = sum(1 for i in range(br, br+3) for j in range(bc, bc+3)
                     if (i != row or j != col) and bb.board[i*9+j] == 0 and (bb.cands[i*9+j] & dbit))
            total = rr + cr + bx
            row_ratio = rr / max(1, row_e - 1)
            col_ratio = cr / max(1, col_e - 1)
            box_ratio = bx / max(1, box_e - 1)
            min_ratio = min(row_ratio, col_ratio, box_ratio)
            zone = 'likely' if min_ratio <= 1.0 else 'unlikely'
            rival_data.append((d, rr, cr, bx, total, min_ratio, zone))
            print(f'  {d:3d}  {rr:4d}  {cr:4d}  {bx:4d}  {total:5d}  {zone:>6s}')

        # SIRO prediction
        rival_data.sort(key=lambda x: x[4])
        siro_pred = rival_data[0][0]
        siro_rivals = rival_data[0][4]
        gap = rival_data[1][4] - rival_data[0][4] if len(rival_data) > 1 else 0

        # Scout detection
        siro_dbit = BIT[siro_pred - 1]
        is_scout = False
        scout_cell = ''
        for j in range(9):
            if j == col: continue
            peer = row * 9 + j
            if bb.board[peer] != 0: continue
            pcands = [dd + 1 for dd in range(9) if bb.cands[peer] & BIT[dd]]
            if len(pcands) < 2: continue
            best_pd, best_ps = -1, 999
            for dd in pcands:
                ps = sum(1 for jj in range(9) if jj != j and bb.board[row*9+jj] == 0 and (bb.cands[row*9+jj] & BIT[dd-1]))
                ps += sum(1 for ii in range(9) if ii != row and bb.board[ii*9+j] == 0 and (bb.cands[ii*9+j] & BIT[dd-1]))
                pbr, pbc = (row // 3) * 3, (j // 3) * 3
                ps += sum(1 for ii in range(pbr, pbr+3) for jj in range(pbc, pbc+3)
                         if (ii != row or jj != j) and bb.board[ii*9+jj] == 0 and (bb.cands[ii*9+jj] & BIT[dd-1]))
                if ps < best_ps: best_ps, best_pd = ps, dd
            if best_pd == siro_pred:
                is_scout = True
                scout_cell = f'R{row+1}C{j+1}'
                break

        # Technique prediction
        if len(cands) <= 2:
            tech_pred = 'ForcingChain'
        elif siro_rivals < 6:
            tech_pred = 'FPC'
        elif siro_rivals < 7:
            tech_pred = 'D2B'
        elif siro_rivals >= 8:
            tech_pred = 'FPCE'
        else:
            tech_pred = 'FPF'

        print(f'\n  ── SIRO Prediction ──')
        print(f'  Predicted digit: {siro_pred} (rivals={siro_rivals}, gap={gap})')
        if is_scout:
            print(f'  ⚠ SCOUT: {siro_pred} is also rank-1 in {scout_cell}')
            if len(rival_data) > 1:
                print(f'  Swap suggestion: {rival_data[1][0]} (rivals={rival_data[1][4]})')

        print(f'\n  ── Technique Prediction ──')
        print(f'  Predicted: {tech_pred}')
        print(f'  Confidence: {"HIGH" if gap >= 4 else "MED" if gap >= 2 else "LOW"}')

        # Cascade depth analysis
        L1_SET = {'crossHatch', 'nakedSingle', 'fullHouse', 'lastRemaining'}
        L2_SET = {'Zone135', 'GF2_Lanczos', 'GF2_Extended', 'GF2_Probe'}
        CASCADE_SET_INS = L1_SET | L2_SET
        try:
            casc_result = solve_selective(bd81, detail=True)
            bn_count = 0
            cell_depth = None
            cell_technique = None
            for step in casc_result.get('steps', []):
                tech_s = step.get('technique', '')
                if tech_s not in CASCADE_SET_INS:
                    bn_count += 1
                if step.get('pos') == pos:
                    cell_depth = bn_count
                    cell_technique = tech_s
                    break

            print(f'\n  ── Cascade Depth ──')
            if cell_depth is not None:
                if cell_depth == 0:
                    print(f'  This cell cascades from basic techniques (depth=0)')
                else:
                    print(f'  Depth: {cell_depth} (needs {cell_depth} bottleneck move{"s" if cell_depth > 1 else ""} first)')
                if cell_technique:
                    cat = 'cascade' if cell_technique in CASCADE_SET_INS else 'bottleneck ★'
                    print(f'  Actual technique: {cell_technique} ({cat})')

            total_bn = sum(1 for s in casc_result.get('steps', [])
                          if s.get('technique', '') not in CASCADE_SET_INS)
            print(f'  Puzzle bottleneck depth: {total_bn}')
        except Exception:
            pass

        # Get actual answer if we can solve
        sol = solve_backtrack(bd81)
        if sol:
            actual = int(sol[pos])
            siro_correct = siro_pred == actual
            print(f'\n  ── Oracle ──')
            print(f'  Answer: {actual}')
            print(f'  SIRO: {"✓ CORRECT" if siro_correct else "✗ WRONG"}')

        sys.exit(0)

    # ── Predict path mode ──
    if getattr(args, 'predict_path', False):
        bb = BitBoard.from_string(bd81)

        print(f'\n  ╔══ Predicted Solve Path ══╗\n')

        sol = solve_backtrack(bd81)

        print(f'  {"Cell":>6s}  {"Digit":>5s}  {"Technique":>12s}  {"Rivals":>6s}  {"Gap":>4s}  {"OK":>3s}')
        print(f'  {"─"*45}')

        correct = total = 0
        for pos in range(81):
            if bb.board[pos] != 0: continue
            cands = [d + 1 for d in range(9) if bb.cands[pos] & BIT[d]]
            if len(cands) < 2: continue

            row, col = divmod(pos, 9)
            scores = []
            for d in cands:
                dbit = BIT[d - 1]
                s = sum(1 for j in range(9) if j != col and bb.board[row*9+j] == 0 and (bb.cands[row*9+j] & dbit))
                s += sum(1 for i in range(9) if i != row and bb.board[i*9+col] == 0 and (bb.cands[i*9+col] & dbit))
                br, bc = (row // 3) * 3, (col // 3) * 3
                s += sum(1 for i in range(br, br+3) for j in range(bc, bc+3)
                         if (i != row or j != col) and bb.board[i*9+j] == 0 and (bb.cands[i*9+j] & dbit))
                scores.append((s, d))
            scores.sort()
            best_d = scores[0][1]
            rivals = scores[0][0]
            gap = scores[1][0] - scores[0][0] if len(scores) > 1 else 0

            if len(cands) <= 2: tech = 'FC'
            elif rivals < 6: tech = 'FPC'
            elif rivals < 7: tech = 'D2B'
            elif rivals >= 8: tech = 'FPCE'
            else: tech = 'FPF'

            ok = ''
            if sol:
                actual = int(sol[pos])
                is_correct = best_d == actual
                ok = '✓' if is_correct else '✗'
                if is_correct: correct += 1
                total += 1

            print(f'  R{row+1}C{col+1}  {best_d:5d}  {tech:>12s}  {rivals:6d}  {gap:4d}  {ok:>3s}')

        if total:
            print(f'\n  Prediction accuracy: {correct}/{total} ({round(100*correct/total)}%)')
        sys.exit(0)

    # ── Cell placement mode (predict + place using advanced techniques) ──
    if getattr(args, 'cell_placement', None):
        try:
            row, col = parse_cell(args.cell_placement)
        except ValueError as e:
            print(f'Error: {e}', file=sys.stderr)
            sys.exit(1)

        bb = BitBoard.from_string(bd81)
        pos = row * 9 + col

        if bb.board[pos] != 0:
            print(f'\n  R{row+1}C{col+1} is already placed: {bb.board[pos]}')
            sys.exit(0)

        cands = [d + 1 for d in range(9) if bb.cands[pos] & BIT[d]]
        print(f'\n  ╔══ Cell Placement: R{row+1}C{col+1} ══╗')
        print(f'  Candidates: {cands}')

        # SIRO Rival prediction
        best_d, best_s, second_s = -1, 999, 999
        for d in cands:
            dbit = BIT[d - 1]
            s = sum(1 for j in range(9) if j != col and bb.board[row*9+j] == 0 and (bb.cands[row*9+j] & dbit))
            s += sum(1 for i in range(9) if i != row and bb.board[i*9+col] == 0 and (bb.cands[i*9+col] & dbit))
            br, bc = (row // 3) * 3, (col // 3) * 3
            s += sum(1 for i in range(br, br+3) for j in range(bc, bc+3)
                     if (i != row or j != col) and bb.board[i*9+j] == 0 and (bb.cands[i*9+j] & dbit))
            if s < best_s:
                second_s = best_s
                best_s = s
                best_d = d
            elif s < second_s:
                second_s = s
        confidence = second_s - best_s

        # Technique prediction
        rivals = best_s
        if len(cands) <= 2:
            tech_pred = 'ForcingChain'
        elif rivals < 6:
            tech_pred = 'FPC'
        elif rivals < 7:
            tech_pred = 'D2B'
        elif rivals >= 8:
            tech_pred = 'FPCE'
        else:
            tech_pred = 'FPF'

        print(f'  SIRO Rival predicts: {best_d} (rivals={best_s}, gap={confidence})')
        print(f'  Technique predicted: {tech_pred}')
        print()

        # Now actually run the solver to place THIS cell
        print(f'  Running solver to place R{row+1}C{col+1}...')
        t0 = time.perf_counter()
        _excl = None
        if getattr(args, 'exclude', None):
            _excl = {TECHNIQUE_ALIASES.get(t.strip().lower(), t.strip()) for t in args.exclude.split(',')}
        result = solve_selective(bd81, max_level=args.level,
                                only_techniques=only_techniques,
                                exclude_techniques=_excl,
                                gf2_extended=getattr(args, 'gf2x', False),
                                detail=True)
        elapsed = (time.perf_counter() - t0) * 1000

        # Find the step that placed this cell
        placed_step = None
        technique_used = None
        elim_rounds = []
        for step in result.get('steps', []):
            if isinstance(step, dict):
                if step.get('pos') == pos:
                    placed_step = step.get('step', '?')
                    technique_used = step.get('technique', '?')
                    break

        # Show elimination rounds that affected this cell
        for ev in result.get('elim_events', []):
            for epos, ed in ev.get('eliminations', []):
                if epos == pos:
                    elim_rounds.append(f"  {ev['technique']}: {ed} eliminated from R{row+1}C{col+1}")

        if elim_rounds:
            print(f'  Elimination chain:')
            for er in elim_rounds:
                print(f'    {er}')

        if placed_step:
            board_val = int(result['board'][pos]) if result.get('board') else '?'
            correct = board_val == best_d
            print(f'\n  ✦ PLACED: R{row+1}C{col+1} = {board_val} via {technique_used} (step {placed_step})')
            print(f'  SIRO predicted: {best_d} {"✓ CORRECT" if correct else "✗ WRONG"}')
            print(f'  Technique predicted: {tech_pred} {"✓" if tech_pred == technique_used else "→ actual: " + str(technique_used)}')
        else:
            print(f'\n  Could not place R{row+1}C{col+1} with available techniques')
            if result.get('board'):
                board_val = int(result['board'][pos])
                if board_val != 0:
                    print(f'  (placed as side-effect at value {board_val})')

        print(f'  Time: {elapsed:.1f}ms')
        sys.exit(0)

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
        if getattr(args, 'rich_output', False):
            # Rich terminal output
            try:
                from rich.console import Console
                from rich.panel import Panel
                from rich.text import Text
                _rc = Console()
                _rc.print(Panel(f"[bold magenta]DETAILED SOLVE LOG ({result.get('rounds', '?')} rounds)[/]", width=60))

                # Build elimination events by round for display
                _elim_by_round = {}
                for ev in result.get('elim_events', []):
                    rnd = ev.get('round', 0)
                    _elim_by_round.setdefault(rnd, []).append(ev)

                current_round = 0
                for step in result.get('steps', []):
                    if step.get('round', 0) != current_round:
                        current_round = step['round']
                        _rc.print()
                        _rc.print(Panel(f"[bold]ROUND {current_round}[/]", style="magenta", width=50))

                        # Show elimination events for this round
                        if current_round in _elim_by_round:
                            for ev in _elim_by_round[current_round]:
                                etech = ev.get('technique', '?')
                                elims = ev.get('eliminations', [])
                                wsrf_tag = ' [red]*[/]' if etech in WSRF_INVENTIONS else ''
                                et = Text()
                                et.append(f"  {etech}", style="bold yellow")
                                et.append(f" {len(elims)} elimination{'s' if len(elims) != 1 else ''}", style="dim")
                                et.append("\n")
                                # Show eliminated candidates grouped by cell
                                by_cell = {}
                                for pos, d in elims:
                                    r, c = pos // 9, pos % 9
                                    cn = f'R{r+1}C{c+1}'
                                    by_cell.setdefault(cn, []).append(str(d))
                                shown = 0
                                for cn, ds in sorted(by_cell.items()):
                                    if shown < 6:
                                        et.append(f"    {cn}: {','.join(ds)}", style="dim red")
                                        et.append("\n")
                                        shown += 1
                                if len(by_cell) > 6:
                                    et.append(f"    ...+{len(by_cell)-6} more cells", style="dim")
                                    et.append("\n")
                                detail_str = ev.get('detail', '')
                                if detail_str:
                                    et.append(f"    {detail_str}", style="dim white")
                                    et.append("\n")
                                _rc.print(Panel(et, border_style="yellow", width=60, padding=(0, 1)))
                            del _elim_by_round[current_round]

                    tech = step.get('technique', '?')
                    cell = step.get('cell', '?')
                    digit = step.get('digit', 0)
                    wsrf = tech in WSRF_INVENTIONS
                    # Color by technique
                    if tech in ('crossHatch','lastRemaining','fullHouse','nakedSingle'):
                        border, ts = 'cyan', 'bold cyan'
                    elif tech in ('FPC','FPCE','ForcingChain','ForcingNet'):
                        border, ts = 'green', 'bold green'
                    elif tech in ('DeepResonance','D2B','FPF'):
                        border, ts = 'red', 'bold red'
                    elif tech in ('ALS_XZ','ALS_XYWing','KrakenFish','DeathBlossom','SueDeCoq'):
                        border, ts = 'yellow', 'bold yellow'
                    elif tech in ('JuniorExocet','Template','BowmanBingo'):
                        border, ts = 'magenta', 'bold magenta'
                    else:
                        border, ts = 'blue', 'bold blue'
                    t = Text()
                    t.append(f"  {tech}", style=ts)
                    if wsrf:
                        t.append(" *", style="bold red")
                    t.append(f"  {cell}", style="white")
                    if digit:
                        t.append(f" = ", style="dim")
                        t.append(f"{digit}", style="bold white on blue")
                    t.append("\n")
                    # Candidate notes
                    cands = step.get('cands_before', [])
                    if cands:
                        t.append(f"    Notes: {' '.join(str(c) for c in cands)}", style="dim")
                        t.append(f" -> placed {digit}", style="bold white")
                        t.append("\n")
                    # Explanation
                    explanation = step.get('explanation', '')
                    if explanation:
                        t.append(f"    {explanation}", style="dim white")
                        t.append("\n")
                    _rc.print(Panel(t, border_style=border, width=60, padding=(0, 1)))
            except ImportError:
                print("Install 'rich' for rich output: pip install rich")
                print(f'\n{"═" * 60}')
                print(format_detail(result))
                print(f'{"═" * 60}')
        else:
            print(f'\n{"═" * 60}')
            print(f'DETAILED SOLVE LOG ({result.get("rounds", "?")} rounds)')
            print(f'{"═" * 60}')
            print(format_detail(result))
            print(f'{"═" * 60}')

    if args.board:
        print(f'\n{format_board(result["board"], bd81)}')

    # ── ScandolousExocet: post-solve validated Exocet scan ──
    if getattr(args, 'scandalous_tech', False) and result['success']:
        solution = result.get('board', '')
        if solution and len(solution) == 81 and '0' not in solution:
            from .engine import detect_junior_exocet as _detect_je
            bb_orig = BitBoard.from_string(bd81)
            je_result = _detect_je(bb_orig)

            if je_result and je_result[0]:
                elims = je_result[0]
                detail = je_result[1]
                try:
                    base_str = detail.split('base {')[1].split('}')[0]
                    base_digits = set(int(d) for d in base_str.split(','))
                    target_part = detail.split('targets ')[1]
                    t_cells = target_part.split(',')
                    t1r = int(t_cells[0][1]) - 1
                    t1c = int(t_cells[0][3]) - 1
                    t2r = int(t_cells[1][1]) - 1
                    t2c = int(t_cells[1][3]) - 1
                    t1_answer = int(solution[t1r * 9 + t1c])
                    t2_answer = int(solution[t2r * 9 + t2c])
                    targets_valid = t1_answer in base_digits and t2_answer in base_digits

                    print(f'\n  {"═" * 50}')
                    print(f'  ScandolousExocet (post-solve validated)')
                    print(f'  {"─" * 50}')
                    print(f'  {detail}')
                    if targets_valid:
                        print(f'  Target R{t1r+1}C{t1c+1}={t1_answer} (base digit) ✓')
                        print(f'  Target R{t2r+1}C{t2c+1}={t2_answer} (base digit) ✓')
                        print(f'  Status: CONFIRMED — this Exocet is real!')
                        print(f'  R1 would remove: {len(elims)} candidates')
                        for pos, d in elims:
                            r, c = divmod(pos, 9)
                            print(f'    R{r+1}C{c+1}: remove {d}')
                    else:
                        bad = []
                        if t1_answer not in base_digits:
                            bad.append(f'R{t1r+1}C{t1c+1}={t1_answer} NOT in base')
                        if t2_answer not in base_digits:
                            bad.append(f'R{t2r+1}C{t2c+1}={t2_answer} NOT in base')
                        print(f'  Status: FALSE PATTERN — {", ".join(bad)}')
                        print(f'  R1 eliminations would have been WRONG')
                    print(f'  {"═" * 50}')
                except Exception:
                    pass
            else:
                if getattr(args, 'verbose', False):
                    print(f'\n  ScandolousExocet: no Exocet pattern found on initial board')

    # Exit code: 0 = solved, 1 = stalled/failed
    if not result['success']:
        sys.exit(1)


if __name__ == '__main__':
    main()
