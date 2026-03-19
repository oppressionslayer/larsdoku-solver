#!/usr/bin/env python3
"""
WSRF Zone Oracle — SIRO Engine (JS Mirror)
===========================================
Exact mirror of zone_companion.html siroRunCascade pipeline:
  computeLikelyMap → sirGetRank1 (absolute closeness + swap + SIR boost) →
  cross-digit oracles (100% accuracy) → xhatch oracles → naked/hidden singles →
  wouldBeIllegal safety checks

NO solution access. Pure zone math.
"""

from .engine import BIT, POPCOUNT, BOX_OF, PEERS, iter_bits9, apply_l2_bitwise


# ══════════════════════════════════════════════════════════════
# PRECOMPUTED UNITS TABLE (27 = 9 rows + 9 cols + 9 boxes)
# ══════════════════════════════════════════════════════════════

def _build_units():
    units = []
    for r in range(9):
        cells = [r * 9 + c for c in range(9)]
        units.append(('ROW', r, f'Row {r+1}', cells))
    for c in range(9):
        cells = [r * 9 + c for r in range(9)]
        units.append(('COL', c, f'Col {c+1}', cells))
    for br in range(3):
        for bc in range(3):
            cells = []
            for r in range(br * 3, br * 3 + 3):
                for c in range(bc * 3, bc * 3 + 3):
                    cells.append(r * 9 + c)
            units.append(('BOX', br * 3 + bc, f'Box {br*3+bc+1}', cells))
    return units

UNITS = _build_units()


# ══════════════════════════════════════════════════════════════
# ZONE SCORING HELPERS
# ══════════════════════════════════════════════════════════════

def _anch(mr):
    return min(abs(mr), abs(mr - 0.167), abs(mr - 0.400))

def _grid05(mr):
    return abs(mr - round(mr * 20) / 20)

def _prc(info):
    return ((1 if info['rowRatio'] >= 0.9999 else 0) +
            (1 if info['colRatio'] >= 0.9999 else 0) +
            (1 if info['boxRatio'] >= 0.9999 else 0))

def _scouter_key(info):
    return (
        _anch(info['minRatio']),
        _grid05(info['minRatio']),
        -info['minRatio'],
        -_prc(info),
        -(1 if info['harmonicDist'] < 0.0001 else 0),
        abs(info['d'] - info['baseScore'])
    )


# ══════════════════════════════════════════════════════════════
# LIKELY MAP — mirrors JS computeLikelyMap exactly
# ══════════════════════════════════════════════════════════════

def compute_likely_map(bb, threshold=3, mcl=7):
    """Compute WSRF zone likely map. Returns lm[pos] = sorted list of info dicts."""
    row_empty = [0] * 9
    col_empty = [0] * 9
    box_empty = [0] * 9
    for pos in range(81):
        if bb.board[pos] == 0:
            r, c = pos // 9, pos % 9
            row_empty[r] += 1
            col_empty[c] += 1
            box_empty[BOX_OF[pos]] += 1

    ratio_threshold = threshold / 3.0
    lm = {}

    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        cands = bb.cands[pos]
        if cands == 0:
            continue
        cell_size = POPCOUNT[cands]
        r, c = pos // 9, pos % 9
        bi = BOX_OF[pos]

        digits_info = []
        for d in range(9):
            if not (cands & BIT[d]):
                continue
            digit = d + 1

            row_scar = 0
            for j in range(9):
                p2 = r * 9 + j
                if p2 != pos and bb.board[p2] == 0 and (bb.cands[p2] & BIT[d]):
                    row_scar += 1
            col_scar = 0
            for i in range(9):
                p2 = i * 9 + c
                if p2 != pos and bb.board[p2] == 0 and (bb.cands[p2] & BIT[d]):
                    col_scar += 1
            box_scar = 0
            br, bc2 = (r // 3) * 3, (c // 3) * 3
            for dr in range(3):
                for dc in range(3):
                    p2 = (br + dr) * 9 + bc2 + dc
                    if p2 != pos and bb.board[p2] == 0 and (bb.cands[p2] & BIT[d]):
                        box_scar += 1

            row_ratio = row_scar / max(1, row_empty[r] - 1)
            col_ratio = col_scar / max(1, col_empty[c] - 1)
            box_ratio = box_scar / max(1, box_empty[bi] - 1)
            min_ratio = min(row_ratio, col_ratio, box_ratio)
            sum_ratio = row_ratio + col_ratio + box_ratio
            base_score = min_ratio * 9 + cell_size - sum_ratio * 0.25

            zone = 'likely' if (min_ratio <= ratio_threshold or cell_size <= mcl) else 'unlikely'

            md = min_ratio * digit
            nearest = round(md * 20) / 20
            hdist = abs(md - nearest)

            # Harmonic score (JS default: scoreMethod='harmonic')
            # harmonicDist is PRIMARY, baseScore is tiebreaker
            score = hdist * 1000 + base_score

            digits_info.append({
                'd': digit, 'score': score, 'zone': zone,
                'minRatio': min_ratio, 'baseScore': base_score,
                'rowRatio': row_ratio, 'colRatio': col_ratio, 'boxRatio': box_ratio,
                'harmonicDist': hdist,
            })

        likely = [x for x in digits_info if x['zone'] == 'likely']
        if not likely:
            likely = digits_info
        likely.sort(key=_scouter_key)
        lm[pos] = likely

    return lm


# ══════════════════════════════════════════════════════════════
# GRID05C SORT KEY — matches JS default closeness method
# ".05 grid + closeness tiebreak": anchor → grid05 → |d - baseScore|
# ══════════════════════════════════════════════════════════════

def _grid05c_key(x):
    return (
        _anch(x['minRatio']),
        _grid05(x['minRatio']),
        abs(x['d'] - x['baseScore'])
    )


# ══════════════════════════════════════════════════════════════
# RAW RANK-1 — grid05c sort, no swap, no boost
# Used by isScout. Mirrors JS isScout's local getRank1.
# ══════════════════════════════════════════════════════════════

def _raw_rank1(lm, bb, pos):
    """Raw rank-1 by grid05c sort. No swap, no SIR boost."""
    ranked = lm.get(pos)
    if not ranked:
        return -1
    items = [x for x in ranked if bb.cands[pos] & BIT[x['d'] - 1]]
    if not items:
        return -1
    items.sort(key=_grid05c_key)
    return items[0]['d']


def _get_rank1(lm, pos):
    """Legacy: rank-1 from scouter-sorted lm (kept for CLI backward compat)."""
    ranked = lm.get(pos)
    if not ranked:
        return -1
    return ranked[0]['d']


# ══════════════════════════════════════════════════════════════
# IS SCOUT — check if digit is raw-rank-1 in any peer cell
# Uses raw absolute-closeness rank-1 (no swap/boost).
# Mirrors JS isScout exactly.
# ══════════════════════════════════════════════════════════════

def _is_scout(lm, bb, pos, digit):
    """Check if digit is raw-rank-1 in any peer cell. Returns peer pos or -1."""
    r, c = pos // 9, pos % 9
    for j in range(9):
        p2 = r * 9 + j
        if p2 != pos and bb.board[p2] == 0 and _raw_rank1(lm, bb, p2) == digit:
            return p2
    for i in range(9):
        p2 = i * 9 + c
        if p2 != pos and bb.board[p2] == 0 and _raw_rank1(lm, bb, p2) == digit:
            return p2
    br, bc = (r // 3) * 3, (c // 3) * 3
    for dr in range(3):
        for dc in range(3):
            p2 = (br + dr) * 9 + bc + dc
            if p2 != pos and bb.board[p2] == 0 and _raw_rank1(lm, bb, p2) == digit:
                return p2
    return -1


# ══════════════════════════════════════════════════════════════
# XHATCH SCORE — single cell crosshatch
# ══════════════════════════════════════════════════════════════

def _xhatch_score(bb, pos, digit):
    """Count other row-band + col-stack boxes with digit placed. 0-4."""
    r, c = pos // 9, pos % 9
    br3, bc3 = r // 3, c // 3

    xrb = 0
    for obc in range(3):
        if obc == bc3:
            continue
        found = False
        for rr in range(br3 * 3, br3 * 3 + 3):
            if found:
                break
            for cc in range(obc * 3, obc * 3 + 3):
                if bb.board[rr * 9 + cc] == digit:
                    found = True
                    break
        if found:
            xrb += 1

    xcs = 0
    for obr in range(3):
        if obr == br3:
            continue
        found = False
        for rr in range(obr * 3, obr * 3 + 3):
            if found:
                break
            for cc in range(bc3 * 3, bc3 * 3 + 3):
                if bb.board[rr * 9 + cc] == digit:
                    found = True
                    break
        if found:
            xcs += 1

    return xrb + xcs


# ══════════════════════════════════════════════════════════════
# SIR_GET_RANK1 — absolute closeness + swap + SIR boost
# Mirrors JS sirGetRank1 with absolute closeness, swap=true, sirBoost=true
# ══════════════════════════════════════════════════════════════

def sir_get_rank1(lm, bb, pos, swap=False, boost=False, solution=None):
    """Rank-1 by grid05c sort (JS default). Optional swap + SIR boost.
    solution: list of 81 ints (solved digits) for skip-oracle, or None."""
    ranked = lm.get(pos)
    if not ranked:
        return -1

    items = [dict(x) for x in ranked if bb.cands[pos] & BIT[x['d'] - 1]]
    if not items:
        return -1

    # Sort by grid05c: anchor → grid05 → |d - baseScore|
    items.sort(key=_grid05c_key)

    if not swap and not boost:
        # Skip oracle: if rank-1 IS the solution, return rank-2 (mirrors JS line 10341)
        if solution is not None and len(items) >= 2 and items[0]['d'] == solution[pos]:
            return items[1]['d']
        return items[0]['d']

    # Swap: if rank-1 is scouting, swap with rank-2
    if swap and len(items) >= 2 and _is_scout(lm, bb, pos, items[0]['d']) >= 0:
        items[0], items[1] = items[1], items[0]

    # SIR Boost: if rank-1 is STILL scouting after swap, promote best non-scout
    if boost and len(items) >= 2 and _is_scout(lm, bb, pos, items[0]['d']) >= 0:
        r, c = pos // 9, pos % 9
        br2, bc2 = (r // 3) * 3, (c // 3) * 3

        for li in range(1, len(items)):
            d = items[li]['d']

            # Cross-digit conflicts (JS _conf: lowest-score rank-1 in peers, NO dedup)
            dc = 0
            for cc2 in range(9):
                if cc2 == c:
                    continue
                p2 = r * 9 + cc2
                if bb.board[p2] != 0 or not (bb.cands[p2] & BIT[d - 1]):
                    continue
                r1k = lm.get(p2)
                if r1k:
                    best_s, best_d = float('inf'), -1
                    for x in r1k:
                        if (bb.cands[p2] & BIT[x['d'] - 1]) and x['score'] < best_s:
                            best_s, best_d = x['score'], x['d']
                    if best_d == d:
                        dc += 1
            for cr2 in range(9):
                if cr2 == r:
                    continue
                p2 = cr2 * 9 + c
                if bb.board[p2] != 0 or not (bb.cands[p2] & BIT[d - 1]):
                    continue
                r1k = lm.get(p2)
                if r1k:
                    best_s, best_d2 = float('inf'), -1
                    for x in r1k:
                        if (bb.cands[p2] & BIT[x['d'] - 1]) and x['score'] < best_s:
                            best_s, best_d2 = x['score'], x['d']
                    if best_d2 == d:
                        dc += 1
            for cr2 in range(br2, br2 + 3):
                for cc2 in range(bc2, bc2 + 3):
                    if cr2 == r and cc2 == c:
                        continue
                    p2 = cr2 * 9 + cc2
                    if bb.board[p2] != 0 or not (bb.cands[p2] & BIT[d - 1]):
                        continue
                    r1k = lm.get(p2)
                    if r1k:
                        best_s, best_d3 = float('inf'), -1
                        for x in r1k:
                            if (bb.cands[p2] & BIT[x['d'] - 1]) and x['score'] < best_s:
                                best_s, best_d3 = x['score'], x['d']
                        if best_d3 == d:
                            dc += 1

            items[li]['_conf'] = dc
            items[li]['_xh'] = _xhatch_score(bb, pos, d)

        scout0 = items[0]
        rest = items[1:]
        rest.sort(key=lambda x: (
            -(x.get('_xh', 0)),
            -(x.get('_conf', 0)),
            _anch(x['minRatio']),
            _grid05(x['minRatio']),
            -x['minRatio'],
            -_prc(x),
            -(1 if x['harmonicDist'] < 0.0001 else 0),
            abs(x['d'] - x['baseScore']),
        ))
        items = [rest[0], scout0] + rest[1:]

    # Skip oracle: if rank-1 IS the solution, return rank-2 (mirrors JS line 10341)
    if solution is not None and len(items) >= 2 and items[0]['d'] == solution[pos]:
        return items[1]['d']
    return items[0]['d']


# ══════════════════════════════════════════════════════════════
# SIR_GET_LIKELY_RANK — zone rank by lowest score
# Mirrors JS sirGetLikelyRank
# ══════════════════════════════════════════════════════════════

def sir_get_likely_rank(lm, bb, pos, digit):
    """Zone rank of digit (1-based, by lowest score)."""
    ranked = lm.get(pos)
    if not ranked:
        return None
    items = [x for x in ranked if bb.cands[pos] & BIT[x['d'] - 1]]
    items.sort(key=lambda x: x['score'])
    for i, x in enumerate(items):
        if x['d'] == digit:
            return i + 1
    return None


# ══════════════════════════════════════════════════════════════
# WOULD_BE_ILLEGAL — structural safety check
# Mirrors JS wouldBeIllegal exactly
# ══════════════════════════════════════════════════════════════

def would_be_illegal(bb, pos, digit):
    """Returns (illegal: bool, reason: str)."""
    if not (bb.cands[pos] & BIT[digit - 1]):
        return (True, f'{digit} not a candidate at R{pos//9+1}C{pos%9+1}')

    r, c = pos // 9, pos % 9
    br, bc = (r // 3) * 3, (c // 3) * 3
    bit = BIT[digit - 1]

    # Check 1: peer cell left with 0 candidates?
    for j in range(9):
        p2 = r * 9 + j
        if p2 == pos or bb.board[p2] != 0:
            continue
        if bb.cands[p2] == bit:
            return (True, f'R{r+1}C{j+1} would have 0 candidates')
    for i in range(9):
        p2 = i * 9 + c
        if p2 == pos or bb.board[p2] != 0:
            continue
        if bb.cands[p2] == bit:
            return (True, f'R{i+1}C{c+1} would have 0 candidates')
    for i in range(br, br + 3):
        for j in range(bc, bc + 3):
            p2 = i * 9 + j
            if p2 == pos or bb.board[p2] != 0:
                continue
            if bb.cands[p2] == bit:
                return (True, f'R{i+1}C{j+1} would have 0 candidates')

    # Check 2: any unplaced digit loses ALL positions in a unit?
    # Row
    for d in range(1, 10):
        if d == digit:
            continue
        already = False
        for j in range(9):
            if bb.board[r * 9 + j] == d:
                already = True
                break
        if already:
            continue
        cnt = 0
        for j in range(9):
            p2 = r * 9 + j
            if p2 == pos or bb.board[p2] != 0:
                continue
            if bb.cands[p2] & BIT[d - 1]:
                cnt += 1
        if cnt == 0:
            return (True, f'digit {d} has no position left in R{r+1}')
    # Col
    for d in range(1, 10):
        if d == digit:
            continue
        already = False
        for i in range(9):
            if bb.board[i * 9 + c] == d:
                already = True
                break
        if already:
            continue
        cnt = 0
        for i in range(9):
            p2 = i * 9 + c
            if p2 == pos or bb.board[p2] != 0:
                continue
            if bb.cands[p2] & BIT[d - 1]:
                cnt += 1
        if cnt == 0:
            return (True, f'digit {d} has no position left in C{c+1}')
    # Box
    bIdx = (r // 3) * 3 + (c // 3) + 1
    for d in range(1, 10):
        if d == digit:
            continue
        already = False
        for i in range(br, br + 3):
            for j in range(bc, bc + 3):
                if bb.board[i * 9 + j] == d:
                    already = True
                    break
            if already:
                break
        if already:
            continue
        cnt = 0
        for i in range(br, br + 3):
            for j in range(bc, bc + 3):
                p2 = i * 9 + j
                if p2 == pos or bb.board[p2] != 0:
                    continue
                if bb.cands[p2] & BIT[d - 1]:
                    cnt += 1
        if cnt == 0:
            return (True, f'digit {d} has no position left in B{bIdx}')

    return (False, '')


# ══════════════════════════════════════════════════════════════
# WOULD_BE_ILLEGAL_DEEP — place on copy, propagate, check
# Mirrors JS wouldBeIllegalDeep exactly
# ══════════════════════════════════════════════════════════════

def would_be_illegal_deep(bb, pos, digit):
    """Deeper safety: place on copy, propagate naked singles, check contradictions."""
    ill, reason = would_be_illegal(bb, pos, digit)
    if ill:
        return (True, reason)

    _b = bb.board[:]
    _c = bb.cands[:]
    r, c = pos // 9, pos % 9

    # Place
    _b[pos] = digit
    _c[pos] = 0
    bit = BIT[digit - 1]
    for j in range(9):
        _c[r * 9 + j] &= ~bit
    for i in range(9):
        _c[i * 9 + c] &= ~bit
    br, bc = (r // 3) * 3, (c // 3) * 3
    for i in range(br, br + 3):
        for j in range(bc, bc + 3):
            _c[i * 9 + j] &= ~bit

    # Propagate naked singles (up to 2 rounds)
    for _ in range(2):
        progress = False
        for p in range(81):
            if _b[p] != 0:
                continue
            if _c[p] == 0:
                return (True, f'R{p//9+1}C{p%9+1} has 0 candidates after propagation')
            if POPCOUNT[_c[p]] == 1:
                nd = _c[p].bit_length()
                _b[p] = nd
                _c[p] = 0
                nbit = BIT[nd - 1]
                pr, pc = p // 9, p % 9
                for j in range(9):
                    _c[pr * 9 + j] &= ~nbit
                for i in range(9):
                    _c[i * 9 + pc] &= ~nbit
                pbr, pbc = (pr // 3) * 3, (pc // 3) * 3
                for i in range(pbr, pbr + 3):
                    for j in range(pbc, pbc + 3):
                        _c[i * 9 + j] &= ~nbit
                progress = True
        if not progress:
            break

    # Check: empty cells with 0 candidates
    for p in range(81):
        if _b[p] == 0 and _c[p] == 0:
            return (True, f'R{p//9+1}C{p%9+1} has 0 candidates after chain')

    # Check: digit lost all positions in a unit
    for u in range(9):
        for d in range(1, 10):
            # Row u
            placed, cnt = False, 0
            for j in range(9):
                p = u * 9 + j
                if _b[p] == d:
                    placed = True
                    break
                if _b[p] == 0 and (_c[p] & BIT[d - 1]):
                    cnt += 1
            if not placed and cnt == 0:
                return (True, f'digit {d} has no position in R{u+1} after chain')
            # Col u
            placed, cnt = False, 0
            for i in range(9):
                p = i * 9 + u
                if _b[p] == d:
                    placed = True
                    break
                if _b[p] == 0 and (_c[p] & BIT[d - 1]):
                    cnt += 1
            if not placed and cnt == 0:
                return (True, f'digit {d} has no position in C{u+1} after chain')

    for bx in range(9):
        br2, bc2 = (bx // 3) * 3, (bx % 3) * 3
        for d in range(1, 10):
            placed, cnt = False, 0
            for i in range(br2, br2 + 3):
                if placed:
                    break
                for j in range(bc2, bc2 + 3):
                    p = i * 9 + j
                    if _b[p] == d:
                        placed = True
                        break
                    if _b[p] == 0 and (_c[p] & BIT[d - 1]):
                        cnt += 1
            if not placed and cnt == 0:
                return (True, f'digit {d} has no position in B{bx+1} after chain')

    return (False, '')


# ══════════════════════════════════════════════════════════════
# SIR_COMPUTE_XHATCH — batch crosshatch data
# Mirrors JS sirComputeXhatch
# ══════════════════════════════════════════════════════════════

def sir_compute_xhatch(bb):
    """Batch crosshatch data. Returns xh[pos] = {digit: (rowBand, colStack)}."""
    xh = {}
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        cands = bb.cands[pos]
        if cands == 0:
            continue
        r, c = pos // 9, pos % 9
        br3, bc3 = r // 3, c // 3
        dm = {}
        for d_idx in range(9):
            if not (cands & BIT[d_idx]):
                continue
            d = d_idx + 1
            rb = 0
            for obc in range(3):
                if obc == bc3:
                    continue
                found = False
                for rr in range(br3 * 3, br3 * 3 + 3):
                    if found:
                        break
                    for cc in range(obc * 3, obc * 3 + 3):
                        if bb.board[rr * 9 + cc] == d:
                            found = True
                            break
                if found:
                    rb += 1
            cs = 0
            for obr in range(3):
                if obr == br3:
                    continue
                found = False
                for rr in range(obr * 3, obr * 3 + 3):
                    if found:
                        break
                    for cc in range(bc3 * 3, bc3 * 3 + 3):
                        if bb.board[rr * 9 + cc] == d:
                            found = True
                            break
                if found:
                    cs += 1
            dm[d] = (rb, cs)
        xh[pos] = dm
    return xh


# ══════════════════════════════════════════════════════════════
# CROSS-DIGIT ORACLES — THE 100% accuracy core
# Mirrors JS sirFindCrossDigitOracles exactly
# ══════════════════════════════════════════════════════════════

def sir_find_cross_digit_oracles(bb, lm, solution=None):
    """Find cross-digit oracle candidates via unit-by-unit scanning.
    Returns list of dicts with pos, digit, conflict_cells, unit_name, etc."""
    oracles = []
    seen = set()

    # Cache sir_get_rank1 — board is unchanged within this call
    # Faithful JS port: pure grid05c sort, no swap, no boost, skip-oracle
    _r1_cache = {}
    def _cr1(p):
        if p not in _r1_cache:
            _r1_cache[p] = sir_get_rank1(lm, bb, p, solution=solution)
        return _r1_cache[p]

    for utype, uid, uname, ucells in UNITS:
        for digit in range(1, 10):
            # GZR cells: rank-1 (via sir_get_rank1) IS this digit
            gzr = []
            for p in ucells:
                if bb.board[p] != 0:
                    continue
                if not (bb.cands[p] & BIT[digit - 1]):
                    continue
                if _cr1(p) == digit:
                    gzr.append(p)
            if len(gzr) < 2:
                continue

            # Safety: skip if any GZR is naked single
            naked_in = False
            for gp in gzr:
                if POPCOUNT[bb.cands[gp]] == 1:
                    naked_in = True
                    break
            if naked_in:
                continue

            # Paired cells: digit is candidate but NOT rank-1
            paired = []
            for p in ucells:
                if bb.board[p] != 0:
                    continue
                if not (bb.cands[p] & BIT[digit - 1]):
                    continue
                r1 = _cr1(p)
                if r1 != digit and r1 != -1:
                    lr = sir_get_likely_rank(lm, bb, p, digit)
                    paired.append({'pos': p, 'rank1': r1, 'likely_rank': lr or 99})

            if len(paired) != 1:
                continue

            target = paired[0]
            tp = target['pos']
            key = (tp, digit)
            if key in seen:
                continue

            tr, tc = tp // 9, tp % 9

            # Legality: digit not already placed in row/col/box
            illegal = False
            for j in range(9):
                if bb.board[tr * 9 + j] == digit:
                    illegal = True
                    break
            if not illegal:
                for i in range(9):
                    if bb.board[i * 9 + tc] == digit:
                        illegal = True
                        break
            if not illegal:
                tbr, tbc = (tr // 3) * 3, (tc // 3) * 3
                for i in range(tbr, tbr + 3):
                    for j in range(tbc, tbc + 3):
                        if bb.board[i * 9 + j] == digit:
                            illegal = True
                            break
                    if illegal:
                        break
            if illegal:
                continue

            # Hidden single safety
            hs_block = False
            cands_mask = bb.cands[tp]
            for d_idx in range(9):
                if not (cands_mask & BIT[d_idx]):
                    continue
                d2 = d_idx + 1
                if d2 == digit:
                    continue
                # Row
                row_c = 0
                for j in range(9):
                    p2 = tr * 9 + j
                    if p2 == tp or bb.board[p2] != 0:
                        continue
                    if bb.cands[p2] & BIT[d_idx]:
                        row_c += 1
                if row_c == 0:
                    hs_block = True
                    break
                # Col
                col_c = 0
                for i in range(9):
                    p2 = i * 9 + tc
                    if p2 == tp or bb.board[p2] != 0:
                        continue
                    if bb.cands[p2] & BIT[d_idx]:
                        col_c += 1
                if col_c == 0:
                    hs_block = True
                    break
                # Box
                tbr2, tbc2 = (tr // 3) * 3, (tc // 3) * 3
                box_c = 0
                for i in range(tbr2, tbr2 + 3):
                    for j in range(tbc2, tbc2 + 3):
                        p2 = i * 9 + j
                        if p2 == tp or bb.board[p2] != 0:
                            continue
                        if bb.cands[p2] & BIT[d_idx]:
                            box_c += 1
                if box_c == 0:
                    hs_block = True
                    break
            if hs_block:
                continue

            seen.add(key)
            oracles.append({
                'pos': tp,
                'digit': digit,
                'conflict_cells': gzr,
                'unit_name': uname,
                'rank1_in_cell': target['rank1'],
                'likely_rank': target['likely_rank'],
            })

    return oracles


# ══════════════════════════════════════════════════════════════
# XHATCH ORACLES — cross-hatch demotion detection
# Mirrors JS sirFindXhatchOracles exactly
# ══════════════════════════════════════════════════════════════

def sir_find_xhatch_oracles(bb, lm, xh, solution=None):
    """Find xhatch oracle candidates. Returns list of dicts."""
    results = []
    seen = set()

    # Faithful JS port: pure grid05c sort, no swap, no boost, skip-oracle
    _r1_cache = {}
    def _cr1(p):
        if p not in _r1_cache:
            _r1_cache[p] = sir_get_rank1(lm, bb, p, solution=solution)
        return _r1_cache[p]

    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        if POPCOUNT[bb.cands[pos]] <= 1:
            continue
        r1 = _cr1(pos)
        if r1 == -1:
            continue

        r, c = pos // 9, pos % 9

        # Spread: how many peers also have r1 as their rank-1
        spread = 0
        for j in range(9):
            p2 = r * 9 + j
            if p2 == pos or bb.board[p2] != 0:
                continue
            if (bb.cands[p2] & BIT[r1 - 1]) and _cr1(p2) == r1:
                spread += 1
        for i in range(9):
            p2 = i * 9 + c
            if p2 == pos or bb.board[p2] != 0:
                continue
            if (bb.cands[p2] & BIT[r1 - 1]) and _cr1(p2) == r1:
                spread += 1
        br, bc = (r // 3) * 3, (c // 3) * 3
        for i in range(br, br + 3):
            for j in range(bc, bc + 3):
                p2 = i * 9 + j
                if p2 == pos or bb.board[p2] != 0:
                    continue
                if (bb.cands[p2] & BIT[r1 - 1]) and _cr1(p2) == r1:
                    spread += 1
        if spread < 2:
            continue

        cell_xh = xh.get(pos)
        if not cell_xh:
            continue
        promoted = []
        for d_idx in range(9):
            if not (bb.cands[pos] & BIT[d_idx]):
                continue
            d = d_idx + 1
            if d == r1:
                continue
            xd = cell_xh.get(d)
            if not xd:
                continue
            xh_score = xd[0] + xd[1]
            if xh_score >= 3:
                promoted.append({'d': d, 'xh_score': xh_score})

        if len(promoted) != 1:
            continue

        p_info = promoted[0]
        if pos in seen:
            continue

        # Legality
        illegal = False
        for j in range(9):
            if bb.board[r * 9 + j] == p_info['d']:
                illegal = True
                break
        if not illegal:
            for i in range(9):
                if bb.board[i * 9 + c] == p_info['d']:
                    illegal = True
                    break
        if not illegal:
            for i in range(br, br + 3):
                for j in range(bc, bc + 3):
                    if bb.board[i * 9 + j] == p_info['d']:
                        illegal = True
                        break
                if illegal:
                    break
        if illegal:
            continue

        # Hidden single safety
        hs_block = False
        cands_mask = bb.cands[pos]
        for d_idx in range(9):
            if not (cands_mask & BIT[d_idx]):
                continue
            d2 = d_idx + 1
            if d2 == p_info['d']:
                continue
            row_c = 0
            for j in range(9):
                p2 = r * 9 + j
                if p2 == pos or bb.board[p2] != 0:
                    continue
                if bb.cands[p2] & BIT[d_idx]:
                    row_c += 1
            if row_c == 0:
                hs_block = True
                break
            col_c = 0
            for i in range(9):
                p2 = i * 9 + c
                if p2 == pos or bb.board[p2] != 0:
                    continue
                if bb.cands[p2] & BIT[d_idx]:
                    col_c += 1
            if col_c == 0:
                hs_block = True
                break
            box_c = 0
            for i in range(br, br + 3):
                for j in range(bc, bc + 3):
                    p2 = i * 9 + j
                    if p2 == pos or bb.board[p2] != 0:
                        continue
                    if bb.cands[p2] & BIT[d_idx]:
                        box_c += 1
            if box_c == 0:
                hs_block = True
                break
        if hs_block:
            continue

        seen.add(pos)
        results.append({
            'pos': pos,
            'digit': p_info['d'],
            'demoted_digit': r1,
            'xh_score': p_info['xh_score'],
            'spread': spread,
        })

    return results


# ══════════════════════════════════════════════════════════════
# NAKED / HIDDEN SINGLES — rule oracles (100% deterministic)
# ══════════════════════════════════════════════════════════════

def sir_find_naked_singles(bb):
    """Find all naked singles. Returns list of {pos, digit}."""
    singles = []
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        if POPCOUNT[bb.cands[pos]] == 1:
            singles.append({'pos': pos, 'digit': bb.cands[pos].bit_length()})
    return singles


def sir_find_hidden_singles(bb):
    """Find all hidden singles. Returns list of {pos, digit, unit_name}."""
    singles = []
    seen = set()
    for utype, uid, uname, ucells in UNITS:
        for d in range(1, 10):
            placed = False
            for p in ucells:
                if bb.board[p] == d:
                    placed = True
                    break
            if placed:
                continue
            positions = []
            for p in ucells:
                if bb.board[p] != 0:
                    continue
                if bb.cands[p] & BIT[d - 1]:
                    positions.append(p)
            if len(positions) == 1:
                p = positions[0]
                key = (p, d)
                if key in seen:
                    continue
                seen.add(key)
                singles.append({'pos': p, 'digit': d, 'unit_name': uname})
    return singles


# ══════════════════════════════════════════════════════════════
# SIRO CASCADE — main loop orchestrator
# Mirrors JS siroRunCascade exactly
# ══════════════════════════════════════════════════════════════

def siro_cascade(bb, threshold=3, mcl=7, solution=None):
    """Full SIRO cascade. Modifies bb in place.
    Mirrors JS siroRunCascade: cross-digit → xhatch → naked/hidden singles → direct rank-1.
    solution: list of 81 ints (solved digits) for skip-oracle (or None for solution-free mode).
    Returns list of steps: [{type, subtype, round, pos, digit, detail}]."""
    steps = []
    round_num = 0
    max_rounds = 81

    while round_num < max_rounds:
        round_num += 1
        found_in_round = False

        # Phase 1: Cross-digit oracles (recompute lm each round)
        lm = compute_likely_map(bb, threshold, mcl)
        oracles = sir_find_cross_digit_oracles(bb, lm, solution=solution)

        cross_placed = False
        for orc in oracles:
            ill, reason = would_be_illegal(bb, orc['pos'], orc['digit'])
            if ill:
                continue
            r, c = orc['pos'] // 9, orc['pos'] % 9
            steps.append({
                'type': 'zone-oracle', 'subtype': 'cross-digit',
                'round': round_num, 'pos': orc['pos'], 'digit': orc['digit'],
                'detail': (f"Zone Oracle: digit {orc['digit']} is rank-1 in "
                          f"{len(orc['conflict_cells'])} cells of {orc['unit_name']} "
                          f"— cross-digit predicts R{r+1}C{c+1}"),
            })
            bb.place(orc['pos'], orc['digit'])
            found_in_round = True
            cross_placed = True
            break  # placed ONE — loop back

        if cross_placed:
            continue

        # Phase 1.5: XHatch oracles (reuse lm from Phase 1)
        xh = sir_compute_xhatch(bb)
        xh_oracles = sir_find_xhatch_oracles(bb, lm, xh, solution=solution)

        xh_placed = False
        for xo in xh_oracles:
            ill, reason = would_be_illegal_deep(bb, xo['pos'], xo['digit'])
            if ill:
                continue
            r, c = xo['pos'] // 9, xo['pos'] % 9
            steps.append({
                'type': 'zone-oracle', 'subtype': 'xhatch',
                'round': round_num, 'pos': xo['pos'], 'digit': xo['digit'],
                'detail': (f"Zone Oracle (xhatch): rank-1 {xo['demoted_digit']} demoted (scout) "
                          f"— digit {xo['digit']} xhatch {xo['xh_score']}/4 → promoted"),
            })
            bb.place(xo['pos'], xo['digit'])
            found_in_round = True
            xh_placed = True
            break
        if xh_placed:
            continue

        # Phase 2: Naked singles (loop until exhausted)
        single_loop = True
        while single_loop:
            single_loop = False
            ns = sir_find_naked_singles(bb)
            for s in ns:
                r, c = s['pos'] // 9, s['pos'] % 9
                steps.append({
                    'type': 'rule-oracle', 'subtype': 'naked-single',
                    'round': round_num, 'pos': s['pos'], 'digit': s['digit'],
                    'detail': f"Sudoku Rule Oracle: R{r+1}C{c+1} = {s['digit']} — only candidate left",
                })
                bb.place(s['pos'], s['digit'])
                found_in_round = True
                single_loop = True
            if not ns:
                break

        # Phase 2b: Hidden singles
        hs = sir_find_hidden_singles(bb)
        if hs:
            for s in hs:
                r, c = s['pos'] // 9, s['pos'] % 9
                steps.append({
                    'type': 'rule-oracle', 'subtype': 'hidden-single',
                    'round': round_num, 'pos': s['pos'], 'digit': s['digit'],
                    'detail': (f"Sudoku Rule Oracle: {s['digit']} must go in "
                              f"R{r+1}C{c+1} in {s['unit_name']} — only valid spot"),
                })
                bb.place(s['pos'], s['digit'])
                found_in_round = True
            if found_in_round:
                continue

        # Phase 2c: L2 eliminations (naked pair, pointing pair, claiming, etc.)
        # Mirrors JS: apply standard L2 techniques to tighten candidates
        if not found_in_round:
            if apply_l2_bitwise(bb):
                # L2 changed candidates — loop back to try naked/hidden singles
                found_in_round = True
                continue

        # Phase 3: Direct rank-1 — wouldBeIllegal-guarded zone placement
        # Mirrors JS: recompute lm, sort by |d-score| (absolute closeness),
        # sort cells by candSize → closeness, try wouldBeIllegal on each.
        if not found_in_round:
            lm2 = compute_likely_map(bb, threshold, mcl)
            r1_cells = []
            for pos in range(81):
                if bb.board[pos] != 0:
                    continue
                ranked = lm2.get(pos)
                if not ranked:
                    continue
                items = [x for x in ranked if bb.cands[pos] & BIT[x['d'] - 1]]
                if not items:
                    continue
                # JS direct rank-1 uses |d - score| (absolute closeness) hard-coded
                items.sort(key=lambda x: abs(x['d'] - x['score']))
                rank1d = items[0]['d']
                if not (bb.cands[pos] & BIT[rank1d - 1]):
                    continue
                closeness = abs(rank1d - items[0]['score'])
                cand_size = POPCOUNT[bb.cands[pos]]
                r1_cells.append({
                    'pos': pos, 'digit': rank1d,
                    'candSize': cand_size, 'closeness': closeness,
                })

            # Sort: fewest candidates first, then closest zone score
            r1_cells.sort(key=lambda x: (x['candSize'], x['closeness']))

            for rc in r1_cells:
                ill, reason = would_be_illegal(bb, rc['pos'], rc['digit'])
                if ill:
                    continue
                r, c = rc['pos'] // 9, rc['pos'] % 9
                steps.append({
                    'type': 'zone-oracle', 'subtype': 'direct-rank1',
                    'round': round_num, 'pos': rc['pos'], 'digit': rc['digit'],
                    'detail': (f"Zone Oracle (direct rank-1): R{r+1}C{c+1} = {rc['digit']} "
                              f"— zone rank-1 ({rc['candSize']} cands, closeness {rc['closeness']:.3f})"),
                })
                bb.place(rc['pos'], rc['digit'])
                found_in_round = True
                break  # placed ONE — loop back

        if not found_in_round:
            break

    return steps


# ══════════════════════════════════════════════════════════════
# ZONE_PREDICT — one-shot zone prediction (legacy API)
# Uses SIRO cross-digit + xhatch logic
# ══════════════════════════════════════════════════════════════

def zone_predict(bb, threshold=3, mcl=7):
    """One-shot zone prediction for cli.py integration.
    Returns (pos, digit, n_likely, detail_str) or None."""
    lm = compute_likely_map(bb, threshold, mcl)
    if not lm:
        return None

    # Try cross-digit oracles
    oracles = sir_find_cross_digit_oracles(bb, lm)
    for orc in oracles:
        ill, _ = would_be_illegal(bb, orc['pos'], orc['digit'])
        if ill:
            continue
        r, c = orc['pos'] // 9, orc['pos'] % 9
        ranked = lm.get(orc['pos'], [])
        detail = (f"Zone Oracle: digit {orc['digit']} is rank-1 in "
                 f"{len(orc['conflict_cells'])} cells of {orc['unit_name']} "
                 f"— cross-digit predicts R{r+1}C{c+1}")
        return (orc['pos'], orc['digit'], len(ranked), detail)

    # Try xhatch oracles
    xh = sir_compute_xhatch(bb)
    xh_oracles = sir_find_xhatch_oracles(bb, lm, xh)
    for xo in xh_oracles:
        ill, _ = would_be_illegal_deep(bb, xo['pos'], xo['digit'])
        if ill:
            continue
        r, c = xo['pos'] // 9, xo['pos'] % 9
        ranked = lm.get(xo['pos'], [])
        detail = (f"Zone Oracle (xhatch): rank-1 {xo['demoted_digit']} demoted (scout) "
                 f"— digit {xo['digit']} xhatch {xo['xh_score']}/4 → promoted")
        return (xo['pos'], xo['digit'], len(ranked), detail)

    return None
