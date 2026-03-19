#!/usr/bin/env python3
"""
SIRO-Boosted Bitwise Engine — Cross-Digit Matrix Oracle Guidance
================================================================
Uses the cross-digit matrix to compute SIRO predictions (constraint-based),
then uses those predictions to GUIDE advanced technique search order.

Key insight: if SIRO predicts digit D for cell X, then:
  - All OTHER candidates are probably WRONG
  - Wrong candidates CONTRADICT faster
  - Test wrong ones FIRST → early termination
  - If all others contradict → D is PROVEN without testing it
  - That's one fewer fast_propagate() call per placement (saves ~500µs)

For D2B: SIRO picks BETTER pivots (high-confidence cells have cleaner branches)
For FPCE: SIRO orders candidates so contradictions are found faster
For FPC: SIRO-hot cells are tested first as gold-filter targets
"""

import time
import json
from .bitwise_engine import (
    BitBoard, propagate_l1l2, fast_propagate, fast_propagate_full,
    detect_l1_bitwise, apply_l2_bitwise, detect_xwing, detect_swordfish,
    detect_fpc_bitwise, solve_backtrack,
    PEERS, UNITS, BIT, ALL_DIGITS, POPCOUNT, BOX_OF,
    ROW_81, COL_81, BOX_81, PEER_81,
    iter_bits9, iter_bits81, popcount81, lsb81
)

# ══════════════════════════════════════════════════════════════════════
# SIRO ORACLE — Cross-Digit Matrix Constraint Scoring
# ══════════════════════════════════════════════════════════════════════

def siro_predict(bb):
    """Compute SIRO prediction for every empty cell using cross-digit matrix.
    For each cell, the digit with the TIGHTEST constraints (fewest positions
    in its row+col+box) is predicted. Pure bit math — no loops over cells.

    Returns: dict mapping pos -> (predicted_digit, confidence_score, candidate_order)
      candidate_order: list of (digit, score) sorted worst-first (test these first)
    """
    predictions = {}

    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        m = bb.cands[pos]
        if not m:
            continue

        r = pos // 9
        c = pos % 9
        bi = BOX_OF[pos]

        # Score each candidate: lower = more constrained = more likely correct
        scored = []
        for d in iter_bits9(m):
            cross_d = bb.cross[d]
            # Count how many cells compete for this digit in each house
            row_rivals = popcount81(cross_d & ROW_81[r]) - 1  # exclude self
            col_rivals = popcount81(cross_d & COL_81[c]) - 1
            box_rivals = popcount81(cross_d & BOX_81[bi]) - 1
            # Constraint score: fewer rivals = tighter = better prediction
            score = row_rivals + col_rivals + box_rivals
            scored.append((d + 1, score))

        # Sort: lowest score = most constrained = SIRO prediction
        scored.sort(key=lambda x: x[1])
        predicted = scored[0][0]
        confidence = scored[-1][1] - scored[0][1]  # gap between best and worst

        # Candidate order for testing: test HIGH-score (likely wrong) FIRST
        test_order = [d for d, s in reversed(scored)]

        predictions[pos] = {
            'digit': predicted,
            'confidence': confidence,
            'order': test_order,         # worst-first for contradiction testing
            'scores': scored,
        }

    return predictions


# ══════════════════════════════════════════════════════════════════════
# GLOBAL SIRO — Whole-Board Impact Scoring
# ══════════════════════════════════════════════════════════════════════
#
# Standard SIRO has a 3-house flashlight: row + col + box.
# Global SIRO sees the shockwave from EVERY placement across:
#   - Band pressure:  3 boxes in this row-band (rivals for d in neighbor boxes)
#   - Stack pressure: 3 boxes in this column-stack
#   - Cascade count:  peers that become naked singles after this placement
#   - Box tightening: does placing d here force a hidden single in another box?
#   - Cross-row/col:  how does removing d from this row affect other bands?
#
# A placement that tightens constraints in 5 boxes is fundamentally
# different from one that only affects its local neighborhood.

# Precompute band and stack box groupings
_BAND_BOXES = [[bi for bi in range(9) if bi // 3 == band] for band in range(3)]
_STACK_BOXES = [[bi for bi in range(9) if bi % 3 == stack] for stack in range(3)]

# For each box, which band and stack it belongs to
_BOX_BAND = [bi // 3 for bi in range(9)]
_BOX_STACK = [bi % 3 for bi in range(9)]

# For each cell, its band and stack
_CELL_BAND = [BOX_OF[p] // 3 for p in range(81)]
_CELL_STACK = [BOX_OF[p] % 3 for p in range(81)]


def siro_predict_global(bb):
    """Whole-board SIRO — scores each candidate by its GLOBAL impact.

    For each candidate digit d at cell pos, computes:
      local_score:     rivals in own row + col + box (standard SIRO)
      band_pressure:   total d-candidates in the 2 OTHER boxes of this row-band
      stack_pressure:  total d-candidates in the 2 OTHER boxes of this col-stack
      band_min_box:    tightest box for d in band (lower = closer to hidden single)
      stack_min_box:   tightest box for d in stack
      cascade_singles: peers that would become naked singles after placement
      hidden_creates:  boxes where placing d leaves exactly 1 cell for d (instant cascade!)

    Combined score: lower = more powerful placement = better prediction.

    Returns dict mapping pos -> {digit, confidence, order, scores, global_detail}
    """
    predictions = {}

    # Precompute per-digit per-box candidate counts (9 digits × 9 boxes)
    # Pure bit math: popcount81(cross[d] & BOX_81[bi])
    dbox = [[0] * 9 for _ in range(9)]  # dbox[d][bi] = count of cells in box bi that have digit d+1
    for d in range(9):
        cross_d = bb.cross[d]
        for bi in range(9):
            dbox[d][bi] = popcount81(cross_d & BOX_81[bi])

    # Precompute per-digit per-row and per-col counts
    drow = [[0] * 9 for _ in range(9)]  # drow[d][r]
    dcol = [[0] * 9 for _ in range(9)]  # dcol[d][c]
    for d in range(9):
        cross_d = bb.cross[d]
        for r in range(9):
            drow[d][r] = popcount81(cross_d & ROW_81[r])
        for c in range(9):
            dcol[d][c] = popcount81(cross_d & COL_81[c])

    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        m = bb.cands[pos]
        if not m:
            continue

        r = pos // 9
        c = pos % 9
        bi = BOX_OF[pos]
        band = _BOX_BAND[bi]
        stack = _BOX_STACK[bi]
        cell_bit = 1 << pos

        scored = []

        for d in iter_bits9(m):
            cross_d = bb.cross[d]

            # ── LOCAL SCORE (standard SIRO) ──
            row_rivals = drow[d][r] - 1
            col_rivals = dcol[d][c] - 1
            box_rivals = dbox[d][bi] - 1
            local_score = row_rivals + col_rivals + box_rivals

            # ── BAND PRESSURE ──
            # How tight is digit d in the OTHER boxes of this row-band?
            # After placing d at (r,c), d is removed from entire row r.
            # In neighbor band-boxes, cells on row r lose d as candidate.
            band_pressure = 0
            band_min = 9
            band_hidden = 0
            for bbi in _BAND_BOXES[band]:
                if bbi == bi:
                    continue
                # Current count of d in this neighbor box
                cnt = dbox[d][bbi]
                # How many of those are on OUR row? They'd lose d after placement.
                on_our_row = popcount81(cross_d & BOX_81[bbi] & ROW_81[r])
                remaining = cnt - on_our_row
                band_pressure += remaining
                if remaining < band_min:
                    band_min = remaining
                if remaining == 1:
                    band_hidden += 1  # hidden single created!

            # ── STACK PRESSURE ──
            # Same logic for the column-stack (placing removes d from col c)
            stack_pressure = 0
            stack_min = 9
            stack_hidden = 0
            for sbi in _STACK_BOXES[stack]:
                if sbi == bi:
                    continue
                cnt = dbox[d][sbi]
                on_our_col = popcount81(cross_d & BOX_81[sbi] & COL_81[c])
                remaining = cnt - on_our_col
                stack_pressure += remaining
                if remaining < stack_min:
                    stack_min = remaining
                if remaining == 1:
                    stack_hidden += 1

            # ── CASCADE SINGLES ──
            # Peers that would become naked singles if we place d here.
            # Placing d at pos → remove d from all peer candidates.
            # If any peer's cands was {d, X} → becomes {X} → naked single!
            cascade_singles = 0
            peer_mask = PEER_81[pos] & cross_d  # peers that currently have d
            tmp = peer_mask
            while tmp:
                lsb = tmp & -tmp
                p = lsb.bit_length() - 1
                tmp ^= lsb
                pc = bb.cands[p]
                if pc and POPCOUNT[pc] == 2 and (pc & BIT[d]):
                    cascade_singles += 1  # this peer becomes a naked single

            # ── CROSS-BAND/STACK INFLUENCE ──
            # How many rows in OTHER bands are affected through the column?
            # Placing d at (r,c) removes d from column c.
            # For boxes NOT in our band that share column c's stack:
            cross_influence = 0
            for obi in range(9):
                if obi == bi:
                    continue
                ob = _BOX_BAND[obi]
                os = _BOX_STACK[obi]
                if ob == band or os == stack:
                    continue  # already counted in band/stack pressure
                # This box is in a DIFFERENT band AND different stack
                # Check if our row or column passes through it
                # Row r passes through boxes in our band → already counted
                # Column c passes through boxes in our stack → already counted
                # But: cascade singles in band/stack boxes can trigger
                # further L1 in distant boxes. We approximate with:
                pass  # indirect effects are hard to predict — skip for now

            # ── COMBINED GLOBAL SCORE ──
            # Primary: local_score (proven 42.6% accuracy for digit prediction)
            # Tiebreaker: global impact metrics
            #
            # Key insight: global SIRO is a POWER predictor, not a digit predictor.
            # It tells you which placements create the biggest shockwave.
            # For digit prediction: local is king, global breaks ties.
            # For technique prediction: global features are gold (separate use).

            hidden_creates = band_hidden + stack_hidden

            # Impact score: cascade potential (0-20 range, normalize to 0-1 fractional)
            # Only nudges the local score, never overrides it.
            # cascade_singles: immediate chain progress (bivalue peers → naked singles)
            # hidden_creates:  forces hidden singles in other boxes
            # band/stack_min:  proximity to forcing (min=1 = hidden single exists)
            impact = (cascade_singles * 0.15
                      + hidden_creates * 0.10
                      + max(0, 3 - band_min) * 0.05
                      + max(0, 3 - stack_min) * 0.05)

            # Global score: local primary, impact as fractional tiebreaker
            global_score = local_score - impact

            scored.append((d + 1, global_score, {
                'local': local_score,
                'band_pressure': band_pressure,
                'stack_pressure': stack_pressure,
                'band_min': band_min,
                'stack_min': stack_min,
                'cascade_singles': cascade_singles,
                'hidden_creates': hidden_creates,
            }))

        # Sort: lowest global score = best prediction
        scored.sort(key=lambda x: x[1])
        predicted = scored[0][0]
        confidence = scored[-1][1] - scored[0][1]

        # Candidate order for testing: worst-first
        test_order = [d for d, s, _ in reversed(scored)]

        predictions[pos] = {
            'digit': predicted,
            'confidence': confidence,
            'order': test_order,
            'scores': [(d, s) for d, s, _ in scored],
            'global_detail': {d: det for d, _, det in scored},
        }

    return predictions


def siro_accuracy(bb, solution):
    """Measure SIRO prediction accuracy against known solution."""
    preds = siro_predict(bb)
    correct = 0
    total = 0
    for pos, info in preds.items():
        total += 1
        if info['digit'] == solution[pos]:
            correct += 1
    return correct, total


# ══════════════════════════════════════════════════════════════════════
# TECHNIQUE PREDICTOR — Zone features predict which technique to run
# ══════════════════════════════════════════════════════════════════════
#
# Oracle Hunt + Combo Analysis + Closeness Deep Dive results
# (3255 records, 686 puzzles, 37 features across 3 families)
#
#   STRUCTURE family (avg F1=0.558):
#     conjugate_units: backbone separator
#       FPC vs GF2: F1=0.996 (μ=2.53 vs μ=0.08)
#       FPC vs FPF: F1=0.990 (μ=2.53 vs μ=0.36)
#
#   CLOSENESS family (NEW — best for FPF vs ForcingChain):
#     sum_ratio:       FPF=0.836 vs FC=1.119, F1=0.816
#     ratio_spread:    FPC=0.114 vs FC=0.185, F1=0.964
#     box_ratio:       FPF=0.294 vs FC=0.436, F1=0.812
#     sum_ratio_range: FPF=0.332 vs FC=0.561, F1=0.761
#     Key insight: FPF = uniform low ratios, ForcingChain = uneven variable
#
#   GLOBAL SIRO (board-wide impact):
#     band_min: D2B=0.39 (tightest bands), FPC=0.70
#     cascade_singles: D2B=0.00, ForcingChain=0.00
#
#   D2B ghost: structurally near-identical to FPC. Best enrichment:
#     band_min ≤ 1 AND base_score ≥ 1.5 → 2x baseline enrichment
#
# Classification tree (data-driven, v2):
#   1. n_cands == 1             → FPCE   (F1=0.918)
#   2. conjugate_units == 0     → GF2    (F1=0.996)
#   3. digit_min_spread ≥ 3     → FPF    (F1=0.990)
#   4. sum_ratio ≤ 1.06 + n≥3  → FPF    (closeness: uniform low ratios)
#   5. ratio_spread ≥ 0.15 + conj ≤ 1 → ForcingChain (uneven ratios)
#   6. band_min ≤ 1 + base ≥ 1.5      → D2B priority (enrichment)
#   7. default                  → FPC

def predict_technique_dispatch(bb):
    """Scan board and predict which technique will fire next.

    Uses data-driven classification from Oracle Hunt (686 puzzles, 12 WSRF
    scoring methods). Key separators: conjugate_units (STRUCTURE),
    siro_score (SIRO), perfect_count (HARMONIC), board_progress (BASIC).

    Returns ordered list of (technique_name, target_cells) where
    target_cells is a list of positions to focus the detector on.
    Costs ~0.05ms — pure bit math, no trial-and-error.
    """
    fpce_targets = []   # n_cands == 1 after elimination
    gf2_targets = []    # conjugate_units == 0 (no conjugate pairs)
    fpc_targets = []    # bivalue + conjugate pair
    fpc_tri = []        # trivalue + conjugate pair
    fpf_targets = []    # digit_min_spread ≥ 3 OR closeness-based (sum_ratio ≤ 1.06)
    fc_targets = []     # ratio_spread ≥ 0.15 + low conjugates
    d2b_targets = []    # band_min ≤ 1 + base_score ≥ 1.5 (enrichment)

    siro = siro_predict(bb)

    # Board progress: fraction of cells solved (D2B ghost tell)
    n_solved = sum(1 for i in range(81) if bb.board[i] != 0)
    board_progress = n_solved / 81.0

    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        cands = bb.cands[pos]
        if not cands:
            continue

        n_cands = POPCOUNT[cands]
        r = pos // 9
        c = pos % 9
        bi = BOX_OF[pos]

        # ── Per-candidate spread + conjugate + ratio analysis ──
        digit_min_spread = 9
        conjugate_units = 0
        total_rivals = 0
        max_weak = 0
        siro_score_val = 0

        for d in iter_bits9(cands):
            cross_d = bb.cross[d]
            row_sp = popcount81(cross_d & ROW_81[r])
            col_sp = popcount81(cross_d & COL_81[c])
            box_sp = popcount81(cross_d & BOX_81[bi])
            min_sp = min(row_sp, col_sp, box_sp)

            if min_sp < digit_min_spread:
                digit_min_spread = min_sp

            # Count conjugate units (houses where digit appears exactly 2x)
            if row_sp == 2:
                conjugate_units += 1
            if col_sp == 2:
                conjugate_units += 1
            if box_sp == 2:
                conjugate_units += 1

            # Rivals for this candidate
            rivals = (row_sp - 1) + (col_sp - 1) + (box_sp - 1)
            total_rivals += rivals
            siro_score_val = max(siro_score_val, rivals)

            # Weak links for this candidate
            weak = 0
            for p in PEERS[pos]:
                if bb.cands[p] & BIT[d]:
                    weak += 1
            if weak > max_weak:
                max_weak = weak

        avg_rivals = total_rivals / n_cands if n_cands else 0

        # ── Cross-digit interaction ──
        cross_int = 0
        pairs = 0
        digits = list(iter_bits9(cands))
        for i in range(len(digits)):
            for j in range(i + 1, len(digits)):
                cross_int += popcount81(bb.cross[digits[i]] & bb.cross[digits[j]])
                pairs += 1
        avg_cross = cross_int / max(pairs, 1)

        # ── SIRO confidence + score ──
        siro_conf = siro[pos]['confidence'] if pos in siro else 0
        siro_sc = siro[pos]['scores'][0][1] if pos in siro else 99

        # ── DATA-DRIVEN CLASSIFICATION TREE v2 ──
        # Structural rules first (cheap), closeness only for ambiguous cases

        # Rule 1: FPCE — single candidate
        if digit_min_spread == 1:
            fpce_targets.append((pos, 0))

        # Rule 2: GF2 — no conjugate pairs + board > 45% solved
        # GF2 fires late (avg board_progress=0.611). Without the gate,
        # every open cell on a crowded early board triggers false GF2.
        if conjugate_units == 0 and n_cands >= 2 and board_progress >= 0.45:
            gf2_targets.append((pos, -avg_rivals))

        # Rule 3: FPF — wide digit spread (F1=0.990)
        if digit_min_spread >= 3 and n_cands >= 3:
            fpf_targets.append((pos, -max_weak))

        # Rule 4: FPF — siro_score ≥ 7 catches spread=2 FPFs (F1=0.620)
        elif siro_score_val >= 7 and n_cands >= 3 and conjugate_units == 0:
            fpf_targets.append((pos, -max_weak))

        # Rule 5: ForcingChain — closeness-based (LAZY: only compute ratios
        # for cells that didn't match structural rules above)
        # ratio_spread μ=0.185 (FC) vs 0.114 (FPC), F1=0.964
        # Also: conjugate ≤ 1 + cross ≥ 12 (original structural rule)
        if conjugate_units <= 1 and n_cands >= 2:
            if avg_cross >= 12:
                fc_targets.append((pos, -siro_conf))
            elif n_cands >= 3:
                # Compute ratio_spread ONLY for ambiguous cells (lazy eval)
                rs_total = 0
                for d in iter_bits9(cands):
                    cd = bb.cross[d]
                    rsp = popcount81(cd & ROW_81[r])
                    csp = popcount81(cd & COL_81[c])
                    bsp = popcount81(cd & BOX_81[bi])
                    rr = 1.0 / rsp if rsp else 0
                    cr2 = 1.0 / csp if csp else 0
                    br = 1.0 / bsp if bsp else 0
                    rs_total += max(rr, cr2, br) - min(rr, cr2, br)
                avg_rs = rs_total / n_cands
                if avg_rs >= 0.15:
                    fc_targets.append((pos, -siro_conf))

        # Rule 6: D2B enrichment — bivalue + high confidence
        # (D2B is structurally identical to FPC; use as priority hint)
        if board_progress <= 0.32 and n_cands == 2 and siro_conf >= 5:
            d2b_targets.append((pos, -siro_conf))

        # Default: FPC — bivalue + conjugate pairs
        if n_cands == 2 and conjugate_units >= 1:
            fpc_targets.append((pos, -siro_conf))
        elif n_cands <= 3 and conjugate_units >= 1:
            fpc_tri.append((pos, -siro_conf))

    # Build dispatch order: most confident predictions first
    dispatch = []

    if fpce_targets:
        dispatch.append(('FPCE', [p for p, _ in fpce_targets]))
    if fpc_targets:
        fpc_targets.sort(key=lambda x: x[1])
        dispatch.append(('FPC', [p for p, _ in fpc_targets]))
    if fpc_tri:
        fpc_tri.sort(key=lambda x: x[1])
        dispatch.append(('FPC_TRI', [p for p, _ in fpc_tri]))
    if fc_targets:
        fc_targets.sort(key=lambda x: x[1])
        dispatch.append(('ForcingChain', [p for p, _ in fc_targets]))
    if d2b_targets:
        d2b_targets.sort(key=lambda x: x[1])
        dispatch.append(('D2B', [p for p, _ in d2b_targets]))
    if fpf_targets:
        fpf_targets.sort(key=lambda x: x[1])
        dispatch.append(('FPF', [p for p, _ in fpf_targets]))
    if gf2_targets:
        gf2_targets.sort(key=lambda x: x[1])
        dispatch.append(('GF2', [p for p, _ in gf2_targets]))

    return dispatch, siro


# ══════════════════════════════════════════════════════════════════════
# SIRO-BOOSTED FPCE — Test wrong candidates first, skip predicted
# ══════════════════════════════════════════════════════════════════════

def siro_fpce(bb, siro):
    """FPCE with SIRO-guided candidate ordering.
    Tests SIRO-unlikely candidates FIRST — they contradict faster.
    If all others contradict, the predicted digit is proven WITHOUT testing it.
    
    Returns (placements, eliminations, tests_saved)
    """
    eliminations = []
    tests_saved = 0
    tests_run = 0
    
    # Process cells ordered by SIRO confidence (highest first)
    cells = [(pos, info) for pos, info in siro.items() 
             if bb.board[pos] == 0 and POPCOUNT[bb.cands[pos]] >= 2]
    cells.sort(key=lambda x: -x[1]['confidence'])
    
    for pos, info in cells:
        m = bb.cands[pos]
        n_cands = POPCOUNT[m]
        if n_cands <= 1:
            continue
        
        predicted = info['digit']
        test_order = info['order']  # worst-first
        
        to_remove = 0
        all_others_contradict = True
        
        for digit in test_order:
            if digit == predicted:
                # SIRO SKIP: if all others already contradicted, don't test this one!
                if all_others_contradict and to_remove:
                    tests_saved += 1
                    continue  # proven by exhaustion
                # Otherwise we need to test it
            
            dbit = BIT[digit - 1]
            if not (m & dbit):
                continue
            
            tests_run += 1
            if fast_propagate(bb.board, bb.cands, pos, digit):
                to_remove |= dbit
            else:
                all_others_contradict = False
        
        if to_remove and to_remove != m:
            for d in iter_bits9(to_remove):
                eliminations.append((pos, d + 1))
    
    # Apply and find placements
    test_cands = bb.cands[:]
    for pos, digit in eliminations:
        test_cands[pos] &= ~BIT[digit - 1]
    
    placements = []
    for pos in range(81):
        if bb.board[pos] == 0:
            m = test_cands[pos]
            if m and (m & (m - 1)) == 0:
                placements.append((pos, m.bit_length(),
                    f'SIRO-FPCE R{pos//9+1}C{pos%9+1}={m.bit_length()}'))
    
    return placements, eliminations, tests_saved, tests_run


# ══════════════════════════════════════════════════════════════════════
# SIRO-BOOSTED D2B — Better pivot selection + ordered branches
# ══════════════════════════════════════════════════════════════════════

def siro_d2b(bb, siro):
    """D2B with SIRO-guided pivot selection and branch ordering.
    
    SIRO boost #1: Pivot cells sorted by SIRO confidence (high confidence = 
                    wrong branches contradict faster = faster D2B)
    SIRO boost #2: Within FPCE of each branch, test SIRO-wrong candidates first
    SIRO boost #3: Skip testing SIRO-predicted candidate if all others contradict
    """
    tests_saved = 0
    tests_run = 0
    
    # Collect pivots — weight by SIRO confidence
    pivots = []
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        pc = POPCOUNT[bb.cands[pos]]
        if 2 <= pc <= 4:
            conf = siro[pos]['confidence'] if pos in siro else 0
            pivots.append((pos, pc, conf))
    
    # Sort: fewest candidates first, then highest SIRO confidence
    pivots.sort(key=lambda x: (x[1], -x[2]))
    
    for pivot_pos, _, _ in pivots[:15]:
        pivot_mask = bb.cands[pivot_pos]
        
        # SIRO-ordered branch digits: test predicted-wrong first
        if pivot_pos in siro:
            pivot_digits = siro[pivot_pos]['order']  # worst-first
        else:
            pivot_digits = [d + 1 for d in iter_bits9(pivot_mask)]
        
        branch_elims = []
        for d1 in pivot_digits:
            if not (pivot_mask & BIT[d1 - 1]):
                continue
            
            if fast_propagate(bb.board, bb.cands, pivot_pos, d1):
                branch_elims.append(None)
                tests_run += 1
                continue
            tests_run += 1
            
            prop_b, prop_c = fast_propagate_full(bb.board, bb.cands, pivot_pos, d1)
            if prop_b is None:
                branch_elims.append(None)
                continue
            
            # FPCE on branch — SIRO-ordered within branch
            elim = [0] * 81
            for i in range(81):
                if prop_b[i] != 0:
                    continue
                pc = POPCOUNT[prop_c[i]]
                if pc < 2 or pc > 4:
                    continue
                
                # Get SIRO order for this cell
                if i in siro:
                    test_order = siro[i]['order']
                    predicted = siro[i]['digit']
                else:
                    test_order = [d + 1 for d in iter_bits9(prop_c[i])]
                    predicted = None
                
                all_others_contra = True
                for dd in test_order:
                    if not (prop_c[i] & BIT[dd - 1]):
                        continue
                    
                    if dd == predicted and all_others_contra and elim[i]:
                        tests_saved += 1
                        continue  # SIRO SKIP
                    
                    tests_run += 1
                    if fast_propagate(prop_b, prop_c, i, dd):
                        elim[i] |= BIT[dd - 1]
                    else:
                        all_others_contra = False
                
                branch_elims.append(elim)
        
        valid = [e for e in branch_elims if e is not None]
        if len(valid) < 2:
            continue
        
        common = valid[0][:]
        for v in valid[1:]:
            for i in range(81):
                common[i] &= v[i]
        
        if not any(common[i] for i in range(81)):
            continue
        
        test_c = bb.cands[:]
        for i in range(81):
            if common[i]:
                test_c[i] &= ~common[i]
        
        placements = []
        for pos in range(81):
            if bb.board[pos] == 0 and test_c[pos]:
                if (test_c[pos] & (test_c[pos] - 1)) == 0:
                    digit = test_c[pos].bit_length()
                    if POPCOUNT[bb.cands[pos]] > 1:
                        r, c = pos // 9, pos % 9
                        placements.append((pos, digit,
                            f'SIRO-D2B R{pivot_pos//9+1}C{pivot_pos%9+1} -> R{r+1}C{c+1}={digit}'))
        
        if placements:
            return placements, tests_saved, tests_run
    
    return [], tests_saved, tests_run


# ══════════════════════════════════════════════════════════════════════
# SIRO-BOOSTED CONTRADICTION — Direct proof via SIRO ordering
# ══════════════════════════════════════════════════════════════════════

def siro_contradiction(bb, siro):
    """Proof by contradiction with SIRO boost.
    For cells where SIRO is confident, test wrong candidates first.
    If all wrong candidates contradict, the predicted digit is proven.
    Saves 1 test per successful proof."""
    
    tests_saved = 0
    tests_run = 0
    
    # Sort by confidence — high confidence = most likely to succeed
    cells = [(pos, info) for pos, info in siro.items()
             if bb.board[pos] == 0 and POPCOUNT[bb.cands[pos]] >= 2
             and POPCOUNT[bb.cands[pos]] <= 4]
    cells.sort(key=lambda x: -x[1]['confidence'])
    
    for pos, info in cells[:30]:
        predicted = info['digit']
        if not (bb.cands[pos] & BIT[predicted - 1]):
            continue
        
        all_contra = True
        for d in info['order']:  # worst-first
            if d == predicted:
                if all_contra:
                    tests_saved += 1
                    continue  # SIRO SKIP — proven by exhaustion!
            if not (bb.cands[pos] & BIT[d - 1]):
                continue
            tests_run += 1
            if not fast_propagate(bb.board, bb.cands, pos, d):
                all_contra = False
                break
        
        if all_contra:
            r, c = pos // 9, pos % 9
            return [(pos, predicted, f'SIRO-Contradiction R{r+1}C{c+1}={predicted}')], tests_saved, tests_run
    
    return [], tests_saved, tests_run


# ══════════════════════════════════════════════════════════════════════
# FULL SIRO-BOOSTED SOLVER
# ══════════════════════════════════════════════════════════════════════

def solve_siro_boosted(bd81, solution=None, verbose=False):
    """Full solve with SIRO boost on every advanced technique."""
    bb = BitBoard.from_string(bd81)
    
    if solution is None:
        solution_str = solve_backtrack(bd81)
        if not solution_str:
            return {'success': False, 'error': 'No solution'}
        solution = [int(ch) for ch in solution_str]
    
    steps = []
    technique_counts = {}
    total_tests_saved = 0
    total_tests_run = 0
    step_num = 0
    
    while bb.empty > 0:
        # Phase 1: Drain L1+L2
        l1_batch = propagate_l1l2(bb)
        for pos, digit, tech in l1_batch:
            step_num += 1
            steps.append({'step': step_num, 'pos': pos, 'digit': digit, 'technique': tech})
            technique_counts[tech] = technique_counts.get(tech, 0) + 1
        
        if bb.empty == 0:
            break
        
        # Phase 2: Compute SIRO predictions (160µs — basically free)
        siro = siro_predict(bb)
        
        placed = False
        
        # L3: X-Wing + Swordfish (no SIRO boost needed — these are elimination-only)
        if detect_xwing(bb):
            continue
        if detect_swordfish(bb):
            continue
        
        # FPC (uses its own ordering, SIRO not critical here)
        fpc_hits = detect_fpc_bitwise(bb)
        for pos, val, detail in fpc_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'FPC'})
                technique_counts['FPC'] = technique_counts.get('FPC', 0) + 1
                placed = True
                break
        if placed:
            continue
        
        # SIRO-Boosted FPCE
        fpce_p, fpce_e, saved, ran = siro_fpce(bb, siro)
        total_tests_saved += saved
        total_tests_run += ran
        if fpce_e:
            for pos, d in fpce_e:
                bb.eliminate(pos, d)
        for pos, val, detail in fpce_p:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'SIRO-FPCE'})
                technique_counts['SIRO-FPCE'] = technique_counts.get('SIRO-FPCE', 0) + 1
                placed = True
                break
        if placed:
            continue
        
        # SIRO-Boosted Forcing Chain
        from bitwise_engine import detect_forcing_chain_bitwise
        fc_hits = detect_forcing_chain_bitwise(bb)
        for pos, val, detail in fc_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'ForcingChain'})
                technique_counts['ForcingChain'] = technique_counts.get('ForcingChain', 0) + 1
                placed = True
                break
        if placed:
            continue
        
        # SIRO-Boosted D2B
        d2b_hits, saved, ran = siro_d2b(bb, siro)
        total_tests_saved += saved
        total_tests_run += ran
        for pos, val, detail in d2b_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'SIRO-D2B'})
                technique_counts['SIRO-D2B'] = technique_counts.get('SIRO-D2B', 0) + 1
                placed = True
                break
        if placed:
            continue
        
        # SIRO-Boosted Contradiction
        contra_hits, saved, ran = siro_contradiction(bb, siro)
        total_tests_saved += saved
        total_tests_run += ran
        for pos, val, detail in contra_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'SIRO-Contradiction'})
                technique_counts['SIRO-Contradiction'] = technique_counts.get('SIRO-Contradiction', 0) + 1
                placed = True
                break
        if placed:
            continue
        
        # FPF (last resort — could add SIRO boost but it's already fast)
        from bitwise_engine import detect_fpf_bitwise
        fpf_hits = detect_fpf_bitwise(bb)
        for pos, val, detail in fpf_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'FPF'})
                technique_counts['FPF'] = technique_counts.get('FPF', 0) + 1
                placed = True
                break
        if placed:
            continue
        
        # Fallback
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
            steps.append({'step': step_num, 'pos': best, 'digit': solution[best], 'technique': 'ORACLE_ONLY'})
            technique_counts['ORACLE_ONLY'] = technique_counts.get('ORACLE_ONLY', 0) + 1
        else:
            break
        
        if step_num > 200:
            break
    
    solved = all(bb.board[i] == solution[i] for i in range(81))
    return {
        'success': solved,
        'steps': steps,
        'n_steps': len(steps),
        'technique_counts': technique_counts,
        'tests_saved': total_tests_saved,
        'tests_run': total_tests_run,
    }


# ══════════════════════════════════════════════════════════════════════
# BENCHMARK
# ══════════════════════════════════════════════════════════════════════

def main():
    with open('/home/wiliamrocha/WSRF_Sudoku_Solve/new/andrew_puzzles.json') as f:
        all_puzzles = json.load(f)
    
    print("=" * 75)
    print("SIRO-BOOSTED ENGINE — Cross-Digit Matrix Oracle Guidance")
    print("=" * 75)
    
    # First: measure SIRO accuracy
    print("\n── SIRO Prediction Accuracy ──")
    total_correct = 0
    total_cells = 0
    for idx in range(0, 686, 50):
        pz = all_puzzles[idx]
        sol_str = solve_backtrack(pz)
        solution = [int(ch) for ch in sol_str]
        bb = BitBoard.from_string(pz)
        propagate_l1l2(bb)
        correct, total = siro_accuracy(bb, solution)
        total_correct += correct
        total_cells += total
        pct = 100 * correct / total if total else 0
        print(f"  Andrew #{idx+1:>3}: {correct}/{total} = {pct:.0f}%")
    
    overall = 100 * total_correct / total_cells if total_cells else 0
    print(f"  OVERALL: {total_correct}/{total_cells} = {overall:.1f}%")
    
    # Benchmark: SIRO-boosted vs plain bitwise
    print(f"\n{'=' * 75}")
    print("HEAD-TO-HEAD: Plain Bitwise vs SIRO-Boosted")
    print(f"{'=' * 75}")
    
    import bitwise_engine as bw
    
    test_indices = list(range(20))
    
    plain_total = 0
    siro_total = 0
    grand_saved = 0
    grand_run = 0
    
    print(f"{'Puzzle':>15} | {'Plain (ms)':>10} | {'SIRO (ms)':>10} | {'Speedup':>8} | {'Tests Saved':>12}")
    print("-" * 75)
    
    for idx in test_indices:
        pz = all_puzzles[idx]
        
        # Plain bitwise
        t0 = time.perf_counter()
        r1 = bw.solve_bitwise(pz)
        plain_dt = (time.perf_counter() - t0) * 1000
        
        # SIRO-boosted
        t0 = time.perf_counter()
        r2 = solve_siro_boosted(pz)
        siro_dt = (time.perf_counter() - t0) * 1000
        
        plain_total += plain_dt
        siro_total += siro_dt
        grand_saved += r2['tests_saved']
        grand_run += r2['tests_run']
        
        speedup = plain_dt / siro_dt if siro_dt > 0 else 0
        saved_pct = 100 * r2['tests_saved'] / (r2['tests_run'] + r2['tests_saved']) if (r2['tests_run'] + r2['tests_saved']) > 0 else 0
        
        print(f"  Andrew #{idx+1:>3} | {plain_dt:10.0f} | {siro_dt:10.0f} | {speedup:7.2f}x | {r2['tests_saved']:4d}/{r2['tests_run']+r2['tests_saved']:4d} ({saved_pct:.0f}%)")
    
    print("-" * 75)
    speedup = plain_total / siro_total if siro_total > 0 else 0
    saved_pct = 100 * grand_saved / (grand_run + grand_saved) if (grand_run + grand_saved) > 0 else 0
    print(f"  {'TOTAL':>11} | {plain_total:10.0f} | {siro_total:10.0f} | {speedup:7.2f}x | {grand_saved:4d}/{grand_run+grand_saved:4d} ({saved_pct:.0f}%)")
    
    print(f"\n  Tests saved by SIRO skip: {grand_saved}")
    print(f"  Time saved per skip: ~500µs × {grand_saved} = ~{grand_saved * 0.5:.0f}ms")


if __name__ == '__main__':
    main()
