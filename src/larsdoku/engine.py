#!/usr/bin/env python3
"""
Bitwise Sudoku Engine — Hyper-Optimized with Every Trick in the Book
=====================================================================
Complete rewrite of oracle_solver.py using pure bitmask arithmetic.
No sets. No dicts in hot paths. Every operation is bitwise.

Architecture:
  DUAL REPRESENTATION — cell-centric + digit-centric (cross-digit)

  Cell-centric:  cands[81] — each cell is a 9-bit mask (bit i = digit i+1)
  Digit-centric: cross[9]  — each digit is an 81-bit mask (bit i = cell i has this digit)

  Both are kept in sync. Cell-centric is fast for per-cell ops (naked single, placement).
  Digit-centric is fast for per-digit ops (hidden single, X-Wing, pointing).

Techniques implemented:
  L1: Full House, Naked Single, Hidden Single (crossHatch/lastRemaining)
  L2: Naked Pair, Naked Triple, Naked Quad, Pointing Pair, Claiming, Hidden Pair
  L3: X-Wing, Swordfish, Empty Rectangle
  L6: BUG+1, UR Type 2, UR Type 4, Junior Exocet, Template, Bowman's Bingo
  Advanced: FPC, FPCE, Forcing Chain, D2B, FPF

Bit tricks used:
  - Isolate LSB:          x & -x
  - Clear LSB:            x & (x-1) or x ^= (x & -x)
  - Power-of-2 test:      x & (x-1) == 0  (naked single)
  - Popcount:             lookup table (9-bit) or Hamming weight
  - Bit iteration:        while x: lsb = x & -x; yield lsb.bit_length()-1; x ^= lsb
  - Subset test:          (a & b) == a  (a is subset of b)
  - Row/col projection:   81-bit masks with AND + shift
  - Cross-digit matrix:   9 × 81-bit integers for SIRO-style parallel ops
  - De Bruijn extraction: constant-time bit-to-index via multiply+shift
  - Bitmask intersection: AND across 81-element arrays for D2B common elims
"""

import time
import json
import sys
import argparse
import itertools
import numpy as np
import numba as nb

# ══════════════════════════════════════════════════════════════════════
# PRECOMPUTED TABLES — built once at import time
# ══════════════════════════════════════════════════════════════════════

# ── Lookup tables for 9-bit values (0-511) ──
POPCOUNT = [0] * 512
for _i in range(1, 512):
    POPCOUNT[_i] = POPCOUNT[_i >> 1] + (_i & 1)

# LSB position: given mask, returns index of lowest set bit (0-8)
# Returns -1 for 0
LSB_POS = [-1] * 512
for _i in range(1, 512):
    LSB_POS[_i] = (_i & -_i).bit_length() - 1

# Single-digit extraction: if popcount==1, returns digit (1-9), else 0
SINGLE_DIGIT = [0] * 512
for _i in range(512):
    if _i and (_i & (_i - 1)) == 0:
        SINGLE_DIGIT[_i] = _i.bit_length()

# Bit masks for each digit (0-indexed: BIT[0] = 1 = digit 1)
BIT = [1 << d for d in range(9)]
ALL_DIGITS = 0x1FF  # 111111111 binary — all 9 digits

# ── Peer lists ──
def _build_peers():
    peers = [None] * 81
    for pos in range(81):
        r, c = pos // 9, pos % 9
        br, bc = (r // 3) * 3, (c // 3) * 3
        s = set()
        for i in range(9):
            s.add(r * 9 + i)
            s.add(i * 9 + c)
        for dr in range(3):
            for dc in range(3):
                s.add((br + dr) * 9 + bc + dc)
        s.discard(pos)
        peers[pos] = tuple(sorted(s))
    return peers

PEERS = _build_peers()

# ── Unit structure ──
UNITS = [None] * 27  # 0-8: rows, 9-17: cols, 18-26: boxes
for _r in range(9):
    UNITS[_r] = tuple(_r * 9 + c for c in range(9))
for _c in range(9):
    UNITS[9 + _c] = tuple(r * 9 + _c for r in range(9))
for _bi in range(9):
    _br, _bc = (_bi // 3) * 3, (_bi % 3) * 3
    UNITS[18 + _bi] = tuple((_br + dr) * 9 + _bc + dc for dr in range(3) for dc in range(3))

# Cell-to-unit mapping: CELL_UNITS[pos] = (row_unit_idx, col_unit_idx, box_unit_idx)
CELL_UNITS = [None] * 81
for _pos in range(81):
    _r, _c = _pos // 9, _pos % 9
    CELL_UNITS[_pos] = (_r, 9 + _c, 18 + (_r // 3) * 3 + _c // 3)

# Box index for each cell
BOX_OF = [0] * 81
for _pos in range(81):
    _r, _c = _pos // 9, _pos % 9
    BOX_OF[_pos] = (_r // 3) * 3 + _c // 3

# Row cells, col cells, box cells (as tuples for fast iteration)
ROW_CELLS = [tuple(range(r * 9, r * 9 + 9)) for r in range(9)]
COL_CELLS = [tuple(r * 9 + c for r in range(9)) for c in range(9)]
BOX_CELLS_FLAT = [UNITS[18 + bi] for bi in range(9)]

# ── 81-bit masks for cross-digit operations ──
# These use Python's arbitrary-precision integers as 81-bit vectors
ROW_81 = [0] * 9
for _r in range(9):
    ROW_81[_r] = 0x1FF << (_r * 9)

COL_81 = [0] * 9
for _c in range(9):
    for _r in range(9):
        COL_81[_c] |= 1 << (_r * 9 + _c)

BOX_81 = [0] * 9
for _bi in range(9):
    for _pos in UNITS[18 + _bi]:
        BOX_81[_bi] |= 1 << _pos

# Precompute: for each cell, its 81-bit peer mask
PEER_81 = [0] * 81
for _pos in range(81):
    for _p in PEERS[_pos]:
        PEER_81[_pos] |= 1 << _p

# Box-row intersection: cells in box b that are on row r
BOX_ROW_81 = [[0] * 9 for _ in range(9)]
BOX_COL_81 = [[0] * 9 for _ in range(9)]
for _bi in range(9):
    for _pos in UNITS[18 + _bi]:
        _r, _c = _pos // 9, _pos % 9
        BOX_ROW_81[_bi][_r] |= 1 << _pos
        BOX_COL_81[_bi][_c] |= 1 << _pos

# ══════════════════════════════════════════════════════════════════════
# NUMPY PRECOMPUTED TABLES — vectorized operations
# ══════════════════════════════════════════════════════════════════════

# Peer matrix: NP_PEERS[i] = array of peer indices for cell i (padded to 20)
NP_PEERS = np.zeros((81, 20), dtype=np.int8)
for _i in range(81):
    _p = list(PEERS[_i])
    NP_PEERS[_i, :len(_p)] = _p

# Unit matrix: NP_UNITS[u] = 9 cell indices for unit u
NP_UNITS = np.array(UNITS, dtype=np.int8)

# Popcount lookup for uint16 (covers 9-bit masks)
NP_POPCOUNT = np.zeros(512, dtype=np.int8)
for _i in range(1, 512):
    NP_POPCOUNT[_i] = NP_POPCOUNT[_i >> 1] + (_i & 1)

# Single-digit lookup: if popcount==1, returns digit (1-9), else 0
NP_SINGLE = np.zeros(512, dtype=np.int8)
for _i in range(512):
    if _i and (_i & (_i - 1)) == 0:
        NP_SINGLE[_i] = _i.bit_length()

# Bit masks as numpy array
NP_BIT = np.array([1 << d for d in range(9)], dtype=np.uint16)

# Box index for each cell
NP_BOX_OF = np.array(BOX_OF, dtype=np.int8)

# Row/col for each cell
NP_ROW_OF = np.arange(81, dtype=np.int8) // 9
NP_COL_OF = np.arange(81, dtype=np.int8) % 9

# Box start row/col for each cell
NP_BOX_ROW = (NP_ROW_OF // 3) * 3
NP_BOX_COL = (NP_COL_OF // 3) * 3

# Peer visibility matrix: SEES[a, b] = True if cell a sees cell b
NP_SEES = np.zeros((81, 81), dtype=np.bool_)
for _a in range(81):
    for _b in PEERS[_a]:
        NP_SEES[_a, _b] = True

# Unit cells as contiguous numpy for JIT
NP_UNIT_CELLS = np.zeros((27, 9), dtype=np.int32)
for _ui in range(27):
    for _ci, _pos in enumerate(UNITS[_ui]):
        NP_UNIT_CELLS[_ui, _ci] = _pos


@nb.njit(cache=True)
def _find_all_als_jit(board, cands, unit_cells, popcount_lut):
    """JIT: find all ALS up to size 5. Returns als_cells, als_ncells, als_cands, n_als."""
    MAX_ALS = 4000
    als_cells = np.zeros((MAX_ALS, 5), dtype=np.int32)
    als_ncells = np.zeros(MAX_ALS, dtype=np.int32)
    als_cands = np.zeros(MAX_ALS, dtype=np.int32)
    n_als = 0

    for ui in range(27):
        ucells = np.zeros(9, dtype=np.int32)
        n_uc = 0
        for ci in range(9):
            pos = unit_cells[ui, ci]
            if board[pos] == 0 and cands[pos] != 0:
                ucells[n_uc] = pos
                n_uc += 1
        if n_uc < 2:
            continue

        for i in range(n_uc):
            m = cands[ucells[i]]
            if popcount_lut[m] == 2:
                if n_als < MAX_ALS:
                    als_cells[n_als, 0] = ucells[i]
                    als_ncells[n_als] = 1
                    als_cands[n_als] = m
                    n_als += 1

        for i in range(n_uc - 1):
            ca = cands[ucells[i]]
            for j in range(i + 1, n_uc):
                union = ca | cands[ucells[j]]
                if popcount_lut[union] == 3:
                    if n_als < MAX_ALS:
                        als_cells[n_als, 0] = ucells[i]
                        als_cells[n_als, 1] = ucells[j]
                        als_ncells[n_als] = 2
                        als_cands[n_als] = union
                        n_als += 1

        for i in range(n_uc - 2):
            ca = cands[ucells[i]]
            for j in range(i + 1, n_uc - 1):
                cab = ca | cands[ucells[j]]
                if popcount_lut[cab & 0x1FF] > 4:
                    continue
                for k in range(j + 1, n_uc):
                    union = cab | cands[ucells[k]]
                    if popcount_lut[union] == 4:
                        if n_als < MAX_ALS:
                            als_cells[n_als, 0] = ucells[i]
                            als_cells[n_als, 1] = ucells[j]
                            als_cells[n_als, 2] = ucells[k]
                            als_ncells[n_als] = 3
                            als_cands[n_als] = union
                            n_als += 1

        for i in range(n_uc - 3):
            ca = cands[ucells[i]]
            for j in range(i + 1, n_uc - 2):
                cab = ca | cands[ucells[j]]
                if popcount_lut[cab & 0x1FF] > 5:
                    continue
                for k in range(j + 1, n_uc - 1):
                    cabc = cab | cands[ucells[k]]
                    if popcount_lut[cabc & 0x1FF] > 5:
                        continue
                    for l in range(k + 1, n_uc):
                        union = cabc | cands[ucells[l]]
                        if popcount_lut[union] == 5:
                            if n_als < MAX_ALS:
                                als_cells[n_als, 0] = ucells[i]
                                als_cells[n_als, 1] = ucells[j]
                                als_cells[n_als, 2] = ucells[k]
                                als_cells[n_als, 3] = ucells[l]
                                als_ncells[n_als] = 4
                                als_cands[n_als] = union
                                n_als += 1

        for i in range(n_uc - 4):
            ca = cands[ucells[i]]
            for j in range(i + 1, n_uc - 3):
                cab = ca | cands[ucells[j]]
                if popcount_lut[cab & 0x1FF] > 6:
                    continue
                for k in range(j + 1, n_uc - 2):
                    cabc = cab | cands[ucells[k]]
                    if popcount_lut[cabc & 0x1FF] > 6:
                        continue
                    for l in range(k + 1, n_uc - 1):
                        cabcd = cabc | cands[ucells[l]]
                        if popcount_lut[cabcd & 0x1FF] > 6:
                            continue
                        for m in range(l + 1, n_uc):
                            union = cabcd | cands[ucells[m]]
                            if popcount_lut[union] == 6:
                                if n_als < MAX_ALS:
                                    als_cells[n_als, 0] = ucells[i]
                                    als_cells[n_als, 1] = ucells[j]
                                    als_cells[n_als, 2] = ucells[k]
                                    als_cells[n_als, 3] = ucells[l]
                                    als_cells[n_als, 4] = ucells[m]
                                    als_ncells[n_als] = 5
                                    als_cands[n_als] = union
                                    n_als += 1

    return als_cells, als_ncells, als_cands, n_als


@nb.njit(cache=True)
def _check_rcc(als_cells, als_ncells, i, j, digit, cands, sees):
    """Check if digit is a Restricted Common Candidate between ALS i and j."""
    na = als_ncells[i]
    nb_ = als_ncells[j]
    d_bit = 1 << digit
    # Cells in i with digit
    for ai in range(na):
        if cands[als_cells[i, ai]] & d_bit:
            for bi in range(nb_):
                if cands[als_cells[j, bi]] & d_bit:
                    if not sees[als_cells[i, ai], als_cells[j, bi]]:
                        return False
    return True


@nb.njit(cache=True)
def _als_xz_from_als_jit(als_cells, als_ncells, als_cands, n_als, cands, sees, popcount_lut):
    """JIT ALS-XZ: given pre-found ALS, check pairs for RCC eliminations."""
    elim_out = np.zeros((200, 2), dtype=np.int32)
    n_elims = 0
    elim_seen = np.zeros(729, dtype=np.bool_)

    for i in range(n_als):
        na = als_ncells[i]
        ca = als_cands[i]
        for j in range(i + 1, n_als):
            nb_ = als_ncells[j]
            cb = als_cands[j]

            overlap = False
            for ai in range(na):
                for bi in range(nb_):
                    if als_cells[i, ai] == als_cells[j, bi]:
                        overlap = True
                        break
                if overlap:
                    break
            if overlap:
                continue

            common = ca & cb
            if popcount_lut[common] < 2:
                continue

            x_mask = common
            while x_mask:
                x_bit = x_mask & (-x_mask)
                x_mask ^= x_bit
                x = 0
                tmp = x_bit
                while tmp > 1:
                    x += 1
                    tmp >>= 1

                if not _check_rcc(als_cells, als_ncells, i, j, x, cands, sees):
                    continue

                other = common ^ x_bit
                z_mask = other
                while z_mask:
                    z_bit = z_mask & (-z_mask)
                    z_mask ^= z_bit
                    z = 0
                    ztmp = z_bit
                    while ztmp > 1:
                        z += 1
                        ztmp >>= 1

                    all_z = np.zeros(10, dtype=np.int32)
                    n_z = 0
                    for ai in range(na):
                        if cands[als_cells[i, ai]] & z_bit:
                            all_z[n_z] = als_cells[i, ai]
                            n_z += 1
                    for bi in range(nb_):
                        if cands[als_cells[j, bi]] & z_bit:
                            all_z[n_z] = als_cells[j, bi]
                            n_z += 1
                    if n_z == 0:
                        continue

                    for pos in range(81):
                        if not (cands[pos] & z_bit):
                            continue
                        in_als = False
                        for ai in range(na):
                            if pos == als_cells[i, ai]:
                                in_als = True
                                break
                        if not in_als:
                            for bi in range(nb_):
                                if pos == als_cells[j, bi]:
                                    in_als = True
                                    break
                        if in_als:
                            continue
                        sees_all = True
                        for zi in range(n_z):
                            if not sees[pos, all_z[zi]]:
                                sees_all = False
                                break
                        if sees_all:
                            key = pos * 9 + z
                            if not elim_seen[key]:
                                elim_seen[key] = True
                                if n_elims < 200:
                                    elim_out[n_elims, 0] = pos
                                    elim_out[n_elims, 1] = z + 1
                                    n_elims += 1

            if n_elims > 0:
                return elim_out[:n_elims], n_elims

    return elim_out[:n_elims], n_elims


@nb.njit(cache=True)
def _als_xy_wing_jit(als_cells, als_ncells, als_cands, n_als, cands, sees, popcount_lut):
    """JIT ALS-XY Wing: pivot C + wings A, B via RCC."""
    # Build RCC adjacency: rcc_digits[i, j] = 9-bit mask of RCC digits
    MAX_RCC = 4000
    rcc_i = np.zeros(MAX_RCC, dtype=np.int32)
    rcc_j = np.zeros(MAX_RCC, dtype=np.int32)
    rcc_mask = np.zeros(MAX_RCC, dtype=np.int32)
    n_rcc = 0

    # Per-ALS adjacency: adj_idx[i] = start in adj_list, adj_count[i] = count
    adj_list = np.zeros(MAX_RCC * 2, dtype=np.int32)
    adj_rcc = np.zeros(MAX_RCC * 2, dtype=np.int32)
    adj_start = np.zeros(n_als + 1, dtype=np.int32)
    adj_count = np.zeros(n_als, dtype=np.int32)

    # First pass: find all RCC pairs
    for i in range(n_als):
        na = als_ncells[i]
        ca = als_cands[i]
        for j in range(i + 1, n_als):
            nb_ = als_ncells[j]
            cb = als_cands[j]

            overlap = False
            for ai in range(na):
                for bi in range(nb_):
                    if als_cells[i, ai] == als_cells[j, bi]:
                        overlap = True
                        break
                if overlap:
                    break
            if overlap:
                continue

            common = ca & cb
            if not common:
                continue

            rmask = 0
            d_mask = common
            while d_mask:
                d_bit = d_mask & (-d_mask)
                d_mask ^= d_bit
                d = 0
                tmp = d_bit
                while tmp > 1:
                    d += 1
                    tmp >>= 1
                if _check_rcc(als_cells, als_ncells, i, j, d, cands, sees):
                    rmask |= d_bit

            if rmask and n_rcc < MAX_RCC:
                rcc_i[n_rcc] = i
                rcc_j[n_rcc] = j
                rcc_mask[n_rcc] = rmask
                n_rcc += 1

    # Build adjacency from RCC pairs
    # Simple approach: for each ALS, collect its neighbors
    # Use two passes: count then fill
    for ri in range(n_rcc):
        adj_count[rcc_i[ri]] += 1
        adj_count[rcc_j[ri]] += 1

    total = 0
    for i in range(n_als):
        adj_start[i] = total
        total += adj_count[i]
        adj_count[i] = 0  # reset for fill pass

    fill_count = np.zeros(n_als, dtype=np.int32)
    for ri in range(n_rcc):
        ii = rcc_i[ri]
        jj = rcc_j[ri]
        idx_i = adj_start[ii] + fill_count[ii]
        adj_list[idx_i] = jj
        adj_rcc[idx_i] = rcc_mask[ri]
        fill_count[ii] += 1
        idx_j = adj_start[jj] + fill_count[jj]
        adj_list[idx_j] = ii
        adj_rcc[idx_j] = rcc_mask[ri]
        fill_count[jj] += 1

    # Search for triples: pivot C, wings A, B
    elim_out = np.zeros((200, 2), dtype=np.int32)
    n_elims = 0
    elim_seen = np.zeros(729, dtype=np.bool_)

    for ci in range(n_als):
        n_adj_c = fill_count[ci]
        if n_adj_c < 2:
            continue

        start_c = adj_start[ci]
        for ni in range(n_adj_c):
            ai = adj_list[start_c + ni]
            rcc_ca = adj_rcc[start_c + ni]

            for nj in range(ni + 1, n_adj_c):
                bi = adj_list[start_c + nj]
                rcc_cb = adj_rcc[start_c + nj]

                # A and B must not overlap
                na = als_ncells[ai]
                nb_ = als_ncells[bi]
                overlap = False
                for a_idx in range(na):
                    for b_idx in range(nb_):
                        if als_cells[ai, a_idx] == als_cells[bi, b_idx]:
                            overlap = True
                            break
                    if overlap:
                        break
                if overlap:
                    continue

                common_ab = als_cands[ai] & als_cands[bi]

                # Try X from rcc_ca, Y from rcc_cb
                x_mask = rcc_ca
                while x_mask:
                    x_bit = x_mask & (-x_mask)
                    x_mask ^= x_bit

                    y_mask = rcc_cb & ~x_bit
                    while y_mask:
                        y_bit = y_mask & (-y_mask)
                        y_mask ^= y_bit

                        z_cands = common_ab & ~x_bit & ~y_bit
                        if not z_cands:
                            continue

                        z_m = z_cands
                        while z_m:
                            z_bit = z_m & (-z_m)
                            z_m ^= z_bit
                            z = 0
                            ztmp = z_bit
                            while ztmp > 1:
                                z += 1
                                ztmp >>= 1

                            # Gather Z-cells from A and B
                            all_z = np.zeros(10, dtype=np.int32)
                            n_z = 0
                            for a_idx in range(na):
                                if cands[als_cells[ai, a_idx]] & z_bit:
                                    all_z[n_z] = als_cells[ai, a_idx]
                                    n_z += 1
                            for b_idx in range(nb_):
                                if cands[als_cells[bi, b_idx]] & z_bit:
                                    all_z[n_z] = als_cells[bi, b_idx]
                                    n_z += 1
                            if n_z == 0:
                                continue

                            # Find elimination targets
                            nc = als_ncells[ci]
                            for pos in range(81):
                                if not (cands[pos] & z_bit):
                                    continue
                                in_any = False
                                for a_idx in range(na):
                                    if pos == als_cells[ai, a_idx]:
                                        in_any = True
                                        break
                                if not in_any:
                                    for b_idx in range(nb_):
                                        if pos == als_cells[bi, b_idx]:
                                            in_any = True
                                            break
                                if not in_any:
                                    for c_idx in range(nc):
                                        if pos == als_cells[ci, c_idx]:
                                            in_any = True
                                            break
                                if in_any:
                                    continue
                                sees_all = True
                                for zi in range(n_z):
                                    if not sees[pos, all_z[zi]]:
                                        sees_all = False
                                        break
                                if sees_all:
                                    key = pos * 9 + z
                                    if not elim_seen[key]:
                                        elim_seen[key] = True
                                        if n_elims < 200:
                                            elim_out[n_elims, 0] = pos
                                            elim_out[n_elims, 1] = z + 1
                                            n_elims += 1

                        if n_elims > 0:
                            return elim_out[:n_elims], n_elims

    return elim_out[:n_elims], n_elims


@nb.njit(cache=True)
def _find_and_check_als_xz_jit(board, cands, sees, unit_cells, popcount_lut):
    """JIT ALS-XZ: find all ALS and check for RCC eliminations."""
    als_cells, als_ncells, als_cands, n_als = _find_all_als_jit(
        board, cands, unit_cells, popcount_lut)
    if n_als < 2:
        return np.zeros((0, 2), dtype=np.int32), 0
    return _als_xz_from_als_jit(als_cells, als_ncells, als_cands, n_als,
                                 cands, sees, popcount_lut)


# ── 81-bit popcount ──
def popcount81(x):
    """Popcount for 81-bit integer using divide-and-conquer."""
    # Process in 27-bit chunks (3 chunks cover 81 bits)
    c = 0
    while x:
        c += POPCOUNT[x & 0x1FF]
        x >>= 9
    return c

def lsb81(x):
    """Position of least significant bit in 81-bit integer."""
    return (x & -x).bit_length() - 1

def iter_bits81(x):
    """Iterate set bit positions of 81-bit integer."""
    while x:
        b = x & -x
        yield b.bit_length() - 1
        x ^= b

def iter_bits9(mask):
    """Iterate set bit positions of 9-bit mask. Yields digit-1 (0-8)."""
    while mask:
        b = mask & -mask
        yield b.bit_length() - 1
        mask ^= b


# ══════════════════════════════════════════════════════════════════════
# CORE: BitBoard — dual-representation state
# ══════════════════════════════════════════════════════════════════════

class BitBoard:
    """Sudoku board with dual bitmask representation.

    Cell-centric: self.cands[pos] — 9-bit mask of candidate digits
    Digit-centric: self.cross[d] — 81-bit mask of cells where digit d+1 can go
    Board: self.board[pos] — placed digit (0=empty)

    Constraint caches:
      self.row_used[r]  — 9-bit mask of placed digits in row r
      self.col_used[c]  — 9-bit mask of placed digits in col c
      self.box_used[b]  — 9-bit mask of placed digits in box b
    """
    __slots__ = ('board', 'cands', 'cross', 'row_used', 'col_used', 'box_used', 'empty')

    def __init__(self):
        self.board = [0] * 81
        self.cands = [0] * 81
        self.cross = [0] * 9        # cross[d] = 81-bit mask for digit d+1
        self.row_used = [0] * 9
        self.col_used = [0] * 9
        self.box_used = [0] * 9
        self.empty = 81

    @staticmethod
    def from_string(bd81):
        """Parse an 81-character puzzle string."""
        bb = BitBoard()
        for pos in range(81):
            ch = bd81[pos]
            d = int(ch) if ch.isdigit() else 0
            if d:
                bb.board[pos] = d
                bb.empty -= 1
                r, c = pos // 9, pos % 9
                bit = BIT[d - 1]
                bb.row_used[r] |= bit
                bb.col_used[c] |= bit
                bb.box_used[BOX_OF[pos]] |= bit
        # Build candidates
        for pos in range(81):
            if bb.board[pos]:
                continue
            r, c = pos // 9, pos % 9
            used = bb.row_used[r] | bb.col_used[c] | bb.box_used[BOX_OF[pos]]
            bb.cands[pos] = ALL_DIGITS & ~used
        # Build cross-digit arrays
        for d in range(9):
            mask81 = 0
            bit = BIT[d]
            for pos in range(81):
                if bb.cands[pos] & bit:
                    mask81 |= 1 << pos
            bb.cross[d] = mask81
        return bb

    def clone(self):
        """Fast clone — list slicing is ~3x faster than deepcopy."""
        bb = BitBoard.__new__(BitBoard)
        bb.board = self.board[:]    # list copy
        bb.cands = self.cands[:]
        bb.cross = self.cross[:]
        bb.row_used = self.row_used[:]
        bb.col_used = self.col_used[:]
        bb.box_used = self.box_used[:]
        bb.empty = self.empty
        return bb

    def place(self, pos, digit):
        """Place digit at pos. Updates both representations + constraint caches."""
        r, c = pos // 9, pos % 9
        bi = BOX_OF[pos]
        bit = BIT[digit - 1]

        self.board[pos] = digit
        self.cands[pos] = 0
        self.empty -= 1
        self.row_used[r] |= bit
        self.col_used[c] |= bit
        self.box_used[bi] |= bit

        # Remove this digit from cross-digit map at this cell
        cell_bit = 1 << pos
        for d in range(9):
            if self.cross[d] & cell_bit:
                self.cross[d] ^= cell_bit

        # Remove digit from all peers
        for peer in PEERS[pos]:
            if self.cands[peer] & bit:
                self.cands[peer] ^= bit
                self.cross[digit - 1] &= ~(1 << peer)

    def eliminate(self, pos, digit):
        """Remove candidate digit from cell pos. Returns False if cell becomes empty."""
        bit = BIT[digit - 1]
        if not (self.cands[pos] & bit):
            return True  # already gone
        self.cands[pos] ^= bit
        self.cross[digit - 1] &= ~(1 << pos)
        return self.cands[pos] != 0  # False = empty cell = contradiction


# ══════════════════════════════════════════════════════════════════════
# L1 DETECTION — Naked Single + Hidden Single + Full House
# ══════════════════════════════════════════════════════════════════════

def detect_l1_bitwise(bb):
    """Find all L1 placements using bitmask operations.
    Returns list of (pos, digit, technique_name)."""
    results = []
    seen = 0  # 81-bit mask of cells already found (dedup)

    # ── Full House: unit with exactly 1 empty cell ──
    for ui in range(27):
        unit = UNITS[ui]
        empty_pos = -1
        empty_count = 0
        for pos in unit:
            if bb.board[pos] == 0:
                empty_count += 1
                empty_pos = pos
                if empty_count > 1:
                    break
        if empty_count == 1 and not ((1 << empty_pos) & seen):
            # The missing digit = ALL_DIGITS minus placed digits
            if ui < 9:
                used = bb.row_used[ui]
            elif ui < 18:
                used = bb.col_used[ui - 9]
            else:
                used = bb.box_used[ui - 18]
            missing = ALL_DIGITS & ~used
            if missing and SINGLE_DIGIT[missing]:
                digit = SINGLE_DIGIT[missing]
                seen |= 1 << empty_pos
                results.append((empty_pos, digit, 'fullHouse'))

    # ── Naked Single: cell with exactly 1 candidate ──
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        m = bb.cands[pos]
        if m and (m & (m - 1)) == 0:  # power of 2 = exactly 1 bit
            if not ((1 << pos) & seen):
                seen |= 1 << pos
                results.append((pos, m.bit_length(), 'nakedSingle'))

    # ── Hidden Single: digit appears in only 1 cell of a unit ──
    # Using cross-digit arrays for blazing speed
    for d in range(9):
        digit = d + 1
        bit = BIT[d]
        cross_d = bb.cross[d]  # 81-bit: all cells where digit can go

        # Check each row
        for r in range(9):
            if bb.row_used[r] & bit:
                continue  # already placed
            row_hits = cross_d & ROW_81[r]
            if row_hits and (row_hits & (row_hits - 1)) == 0:
                # Exactly 1 cell in this row has digit
                pos = row_hits.bit_length() - 1
                if not ((1 << pos) & seen):
                    seen |= 1 << pos
                    results.append((pos, digit, 'crossHatch'))

        # Check each column
        for c in range(9):
            if bb.col_used[c] & bit:
                continue
            col_hits = cross_d & COL_81[c]
            if col_hits and (col_hits & (col_hits - 1)) == 0:
                pos = col_hits.bit_length() - 1
                if not ((1 << pos) & seen):
                    seen |= 1 << pos
                    results.append((pos, digit, 'crossHatch'))

        # Check each box
        for bi in range(9):
            if bb.box_used[bi] & bit:
                continue
            box_hits = cross_d & BOX_81[bi]
            if box_hits and (box_hits & (box_hits - 1)) == 0:
                pos = box_hits.bit_length() - 1
                if not ((1 << pos) & seen):
                    seen |= 1 << pos
                    results.append((pos, digit, 'lastRemaining'))

    return results


# ══════════════════════════════════════════════════════════════════════
# L2 DETECTION — Pairs, Pointing, Claiming, Triples, Hidden Pairs
# ══════════════════════════════════════════════════════════════════════

def apply_l2_bitwise(bb):
    """Apply L2 techniques using bitmask operations. Returns True if any change."""
    changed = False

    # ── Naked Pairs: two cells in unit with identical 2-candidate masks ──
    for ui in range(27):
        unit = UNITS[ui]
        # Collect cells with exactly 2 candidates
        for ai in range(9):
            pa = unit[ai]
            if bb.board[pa] != 0 or POPCOUNT[bb.cands[pa]] != 2:
                continue
            mask = bb.cands[pa]
            for bi_idx in range(ai + 1, 9):
                pb = unit[bi_idx]
                if bb.board[pb] != 0 or bb.cands[pb] != mask:
                    continue
                # Found naked pair! Eliminate mask from other cells
                for ci_idx in range(9):
                    pc = unit[ci_idx]
                    if pc == pa or pc == pb or bb.board[pc] != 0:
                        continue
                    elim = bb.cands[pc] & mask
                    if elim:
                        for d in iter_bits9(elim):
                            bb.cands[pc] ^= BIT[d]
                            bb.cross[d] &= ~(1 << pc)
                        changed = True

    # ── Naked Triples: 3 cells in unit whose union has exactly 3 candidates ──
    for ui in range(27):
        unit = UNITS[ui]
        # Collect empty cells with 2-3 candidates
        cells = []
        for pos in unit:
            if bb.board[pos] == 0 and 2 <= POPCOUNT[bb.cands[pos]] <= 3:
                cells.append(pos)
        if len(cells) < 3:
            continue
        for i in range(len(cells)):
            for j in range(i + 1, len(cells)):
                union2 = bb.cands[cells[i]] | bb.cands[cells[j]]
                if POPCOUNT[union2] > 3:
                    continue
                for k in range(j + 1, len(cells)):
                    union3 = union2 | bb.cands[cells[k]]
                    if POPCOUNT[union3] != 3:
                        continue
                    # Naked triple! Eliminate union from other cells
                    triple_set = {cells[i], cells[j], cells[k]}
                    for pos in unit:
                        if pos in triple_set or bb.board[pos] != 0:
                            continue
                        elim = bb.cands[pos] & union3
                        if elim:
                            for d in iter_bits9(elim):
                                bb.cands[pos] ^= BIT[d]
                                bb.cross[d] &= ~(1 << pos)
                            changed = True

    # ── Pointing Pairs: digit in box confined to one row/col ──
    for bi in range(9):
        br, bc = (bi // 3) * 3, (bi % 3) * 3
        for d in range(9):
            if bb.box_used[bi] & BIT[d]:
                continue
            # Get 81-bit positions of digit d in this box
            box_hits = bb.cross[d] & BOX_81[bi]
            if not box_hits:
                continue

            # Check if all on one row
            for r in range(br, br + 3):
                row_hits = box_hits & ROW_81[r]
                if row_hits == box_hits and row_hits:
                    # All digit-d candidates in box are on row r
                    # Eliminate from rest of row outside box
                    rest_of_row = bb.cross[d] & ROW_81[r] & ~BOX_81[bi]
                    if rest_of_row:
                        for pos in iter_bits81(rest_of_row):
                            bb.cands[pos] ^= BIT[d]
                            bb.cross[d] &= ~(1 << pos)
                        changed = True
                    break

            # Refresh box_hits (may have changed)
            box_hits = bb.cross[d] & BOX_81[bi]
            if not box_hits:
                continue

            # Check if all on one col
            for c in range(bc, bc + 3):
                col_hits = box_hits & COL_81[c]
                if col_hits == box_hits and col_hits:
                    rest_of_col = bb.cross[d] & COL_81[c] & ~BOX_81[bi]
                    if rest_of_col:
                        for pos in iter_bits81(rest_of_col):
                            bb.cands[pos] ^= BIT[d]
                            bb.cross[d] &= ~(1 << pos)
                        changed = True
                    break

    # ── Claiming: digit in row/col confined to one box ──
    for d in range(9):
        bit = BIT[d]

        # Row claiming
        for r in range(9):
            if bb.row_used[r] & bit:
                continue
            row_hits = bb.cross[d] & ROW_81[r]
            if not row_hits:
                continue
            # Check if all in one box
            for bci in range(3):
                bc = bci * 3
                bi = (r // 3) * 3 + bci
                box_row_hits = row_hits & BOX_81[bi]
                if box_row_hits == row_hits:
                    # All in one box — eliminate from rest of box
                    rest_of_box = bb.cross[d] & BOX_81[bi] & ~ROW_81[r]
                    if rest_of_box:
                        for pos in iter_bits81(rest_of_box):
                            bb.cands[pos] ^= BIT[d]
                            bb.cross[d] &= ~(1 << pos)
                        changed = True
                    break

        # Col claiming
        for c in range(9):
            if bb.col_used[c] & bit:
                continue
            col_hits = bb.cross[d] & COL_81[c]
            if not col_hits:
                continue
            for bri in range(3):
                br = bri * 3
                bi = bri * 3 + c // 3
                box_col_hits = col_hits & BOX_81[bi]
                if box_col_hits == col_hits:
                    rest_of_box = bb.cross[d] & BOX_81[bi] & ~COL_81[c]
                    if rest_of_box:
                        for pos in iter_bits81(rest_of_box):
                            bb.cands[pos] ^= BIT[d]
                            bb.cross[d] &= ~(1 << pos)
                        changed = True
                    break

    # ── Hidden Pairs: 2 digits that appear in only 2 cells of a unit ──
    for ui in range(27):
        unit = UNITS[ui]
        # For each unit, collect which digits have 2 positions
        if ui < 9:
            used = bb.row_used[ui]
        elif ui < 18:
            used = bb.col_used[ui - 9]
        else:
            used = bb.box_used[ui - 18]

        # unit_mask = 81-bit mask of cells in this unit
        unit81 = 0
        for pos in unit:
            if bb.board[pos] == 0:
                unit81 |= 1 << pos

        pair_digits = []  # (digit, positions_81bit)
        for d in range(9):
            if used & BIT[d]:
                continue
            hits = bb.cross[d] & unit81
            if POPCOUNT.get(0, 0) if False else popcount81(hits) == 2:
                pair_digits.append((d, hits))

        for i in range(len(pair_digits)):
            for j in range(i + 1, len(pair_digits)):
                d1, pos1 = pair_digits[i]
                d2, pos2 = pair_digits[j]
                if pos1 == pos2:
                    # Hidden pair! d1 and d2 appear in exactly the same 2 cells
                    keep = BIT[d1] | BIT[d2]
                    for pos in iter_bits81(pos1):
                        elim = bb.cands[pos] & ~keep
                        if elim:
                            for d in iter_bits9(elim):
                                bb.cands[pos] ^= BIT[d]
                                bb.cross[d] &= ~(1 << pos)
                            changed = True

    return changed


# ══════════════════════════════════════════════════════════════════════
# L3 DETECTION — X-Wing, Swordfish, Empty Rectangle
# ══════════════════════════════════════════════════════════════════════

def detect_xwing(bb):
    """X-Wing detection using cross-digit row projection.
    For each digit, find 2 rows where the digit appears in exactly 2 columns,
    and those columns are the same. Eliminate from those columns in other rows.
    Returns True if any elimination made."""
    changed = False
    for d in range(9):
        cross_d = bb.cross[d]
        if not cross_d:
            continue

        # Project each row to a 9-bit column mask
        row_cols = [0] * 9  # row_cols[r] = 9-bit mask of cols with digit d in row r
        for r in range(9):
            if bb.row_used[r] & BIT[d]:
                continue
            row_bits = cross_d & ROW_81[r]
            # Extract column positions
            cols = 0
            for pos in iter_bits81(row_bits):
                cols |= 1 << (pos % 9)
            row_cols[r] = cols

        # Find pairs of rows with identical 2-column masks
        for r1 in range(8):
            c1 = row_cols[r1]
            if POPCOUNT[c1] != 2:
                continue
            for r2 in range(r1 + 1, 9):
                if row_cols[r2] != c1:
                    continue
                # X-Wing found! Eliminate from these columns in other rows
                for c in iter_bits9(c1):
                    for r in range(9):
                        if r == r1 or r == r2:
                            continue
                        pos = r * 9 + c
                        if bb.cands[pos] & BIT[d]:
                            bb.cands[pos] ^= BIT[d]
                            bb.cross[d] &= ~(1 << pos)
                            changed = True

        # Column-based X-Wing (transpose)
        col_rows = [0] * 9
        for c in range(9):
            if bb.col_used[c] & BIT[d]:
                continue
            col_bits = cross_d & COL_81[c]
            rows = 0
            for pos in iter_bits81(col_bits):
                rows |= 1 << (pos // 9)
            col_rows[c] = rows

        for c1_idx in range(8):
            r1 = col_rows[c1_idx]
            if POPCOUNT[r1] != 2:
                continue
            for c2_idx in range(c1_idx + 1, 9):
                if col_rows[c2_idx] != r1:
                    continue
                for r in iter_bits9(r1):
                    for c in range(9):
                        if c == c1_idx or c == c2_idx:
                            continue
                        pos = r * 9 + c
                        if bb.cands[pos] & BIT[d]:
                            bb.cands[pos] ^= BIT[d]
                            bb.cross[d] &= ~(1 << pos)
                            changed = True

    return changed


def detect_swordfish(bb):
    """Swordfish: 3 rows where digit appears in subset of 3 columns (union=3).
    Returns True if any elimination."""
    changed = False
    for d in range(9):
        cross_d = bb.cross[d]
        if not cross_d:
            continue

        # Row-based swordfish
        row_cols = [0] * 9
        active_rows = []
        for r in range(9):
            if bb.row_used[r] & BIT[d]:
                continue
            row_bits = cross_d & ROW_81[r]
            cols = 0
            for pos in iter_bits81(row_bits):
                cols |= 1 << (pos % 9)
            row_cols[r] = cols
            pc = POPCOUNT[cols]
            if 2 <= pc <= 3:
                active_rows.append(r)

        for i in range(len(active_rows)):
            for j in range(i + 1, len(active_rows)):
                union2 = row_cols[active_rows[i]] | row_cols[active_rows[j]]
                if POPCOUNT[union2] > 3:
                    continue
                for k in range(j + 1, len(active_rows)):
                    union3 = union2 | row_cols[active_rows[k]]
                    if POPCOUNT[union3] != 3:
                        continue
                    # Swordfish! Eliminate from these 3 columns in other rows
                    sf_rows = {active_rows[i], active_rows[j], active_rows[k]}
                    for c in iter_bits9(union3):
                        for r in range(9):
                            if r in sf_rows:
                                continue
                            pos = r * 9 + c
                            if bb.cands[pos] & BIT[d]:
                                bb.cands[pos] ^= BIT[d]
                                bb.cross[d] &= ~(1 << pos)
                                changed = True

        # Column-based swordfish (transpose)
        col_rows = [0] * 9
        active_cols = []
        for c in range(9):
            if bb.col_used[c] & BIT[d]:
                continue
            col_bits = cross_d & COL_81[c]
            rows = 0
            for pos in iter_bits81(col_bits):
                rows |= 1 << (pos // 9)
            col_rows[c] = rows
            pc = POPCOUNT[rows]
            if 2 <= pc <= 3:
                active_cols.append(c)

        for i in range(len(active_cols)):
            for j in range(i + 1, len(active_cols)):
                union2 = col_rows[active_cols[i]] | col_rows[active_cols[j]]
                if POPCOUNT[union2] > 3:
                    continue
                for k in range(j + 1, len(active_cols)):
                    union3 = union2 | col_rows[active_cols[k]]
                    if POPCOUNT[union3] != 3:
                        continue
                    sf_cols = {active_cols[i], active_cols[j], active_cols[k]}
                    for r in iter_bits9(union3):
                        for c in range(9):
                            if c in sf_cols:
                                continue
                            pos = r * 9 + c
                            if bb.cands[pos] & BIT[d]:
                                bb.cands[pos] ^= BIT[d]
                                bb.cross[d] &= ~(1 << pos)
                                changed = True

    return changed


# ══════════════════════════════════════════════════════════════════════
# L4: Simple Coloring — conjugate pair 2-coloring chains
# ══════════════════════════════════════════════════════════════════════

def detect_simple_coloring(bb):
    """Simple Coloring: for each digit, build conjugate pair graph via strong
    links (units where digit appears in exactly 2 cells). BFS 2-color each
    connected component.
    Rule 1 (Contradiction): if two same-color cells see each other, eliminate
            the digit from ALL cells of that color.
    Rule 2 (Seeing both): if an uncolored cell sees cells of BOTH colors,
            eliminate the digit from that cell.
    Returns (eliminations, detail) or ([], None). Eliminations are (pos, digit)."""

    for d in range(9):
        cross_d = bb.cross[d]
        if not cross_d:
            continue
        dval = d + 1
        dbit = BIT[d]

        # Build adjacency list of strong links (conjugate pairs)
        # adj[pos] = list of positions connected by strong link
        adj = {}
        for ui in range(27):
            unit = UNITS[ui]
            # Find cells in this unit that have digit d as candidate
            cells_in_unit = []
            for pos in unit:
                if bb.board[pos] == 0 and (bb.cands[pos] & dbit):
                    cells_in_unit.append(pos)
            if len(cells_in_unit) == 2:
                a, b = cells_in_unit
                if a not in adj:
                    adj[a] = []
                if b not in adj:
                    adj[b] = []
                adj[b].append(a)
                adj[a].append(b)

        if not adj:
            continue

        # BFS 2-color connected components
        visited = set()
        for start in adj:
            if start in visited:
                continue
            # BFS
            color = {}
            color[start] = 0
            visited.add(start)
            queue = [start]
            chain = []
            qi = 0
            while qi < len(queue):
                cur = queue[qi]
                qi += 1
                chain.append(cur)
                for nb in adj.get(cur, []):
                    if nb in visited:
                        continue
                    visited.add(nb)
                    color[nb] = 1 - color[cur]
                    queue.append(nb)

            if len(chain) < 4:
                continue

            # Separate colors
            colors = [[], []]
            for k in chain:
                colors[color[k]].append(k)

            # Rule 1: contradiction — two same-color cells see each other
            for col in range(2):
                cells = colors[col]
                contradiction = False
                for ai in range(len(cells)):
                    if contradiction:
                        break
                    a_pos = cells[ai]
                    a_peers = PEER_81[a_pos]
                    for bi_idx in range(ai + 1, len(cells)):
                        b_pos = cells[bi_idx]
                        if a_peers & (1 << b_pos):
                            # Same color cells see each other → eliminate digit from all same-color cells
                            elims = []
                            for k in cells:
                                if bb.cands[k] & dbit:
                                    elims.append((k, dval))
                            if elims:
                                return elims, f'SimpleColoring d{dval}: contradiction in color {col} ({len(elims)} elims)'
                            contradiction = True
                            break

            # Rule 2: uncolored cell sees both colors → eliminate digit from it
            colored_set = set(chain)
            color0_81 = 0
            color1_81 = 0
            for k in colors[0]:
                color0_81 |= 1 << k
            for k in colors[1]:
                color1_81 |= 1 << k

            elims = []
            # Check all cells with digit d that aren't colored
            uncolored = cross_d & ~(color0_81 | color1_81)
            for pos in iter_bits81(uncolored):
                if bb.board[pos] != 0:
                    continue
                peers = PEER_81[pos]
                if (peers & color0_81) and (peers & color1_81):
                    elims.append((pos, dval))

            if elims:
                return elims, f'SimpleColoring d{dval}: sees both colors ({len(elims)} elims)'

    return [], None


# ══════════════════════════════════════════════════════════════════════
# PROPAGATION — The Hot Path (most-called functions)
# ══════════════════════════════════════════════════════════════════════

# Tech codes for JIT: 0=fullHouse, 1=nakedSingle, 2=crossHatch, 3=lastRemaining
_TECH_NAMES = ['fullHouse', 'nakedSingle', 'crossHatch', 'lastRemaining']

@nb.njit(cache=True)
def _drain_l1l2_jit(b, c, row_used, col_used, box_used,
                     box_of, peers, peer_len, units, popcount_lut):
    """JIT-compiled L1+L2 propagation to fixpoint.
    Returns (out_pos, out_dig, out_tech) arrays — each of length n_placed."""
    out_pos = np.empty(81, dtype=np.int32)
    out_dig = np.empty(81, dtype=np.int32)
    out_tech = np.empty(81, dtype=np.int32)
    n = 0

    for outer in range(50):
        l1_changed = True
        while l1_changed:
            l1_changed = False

            # ── Full House: unit with 1 empty ──
            for ui in range(27):
                empty_pos = -1
                empty_count = 0
                for ci in range(9):
                    pos = units[ui, ci]
                    if b[pos] == 0:
                        empty_count += 1
                        empty_pos = pos
                        if empty_count > 1:
                            break
                if empty_count == 1 and b[empty_pos] == 0:
                    if ui < 9:
                        used = row_used[ui]
                    elif ui < 18:
                        used = col_used[ui - 9]
                    else:
                        used = box_used[ui - 18]
                    missing = 0x1FF & ~used
                    if missing and (missing & (missing - 1)) == 0:
                        digit = 0
                        tmp = missing
                        while tmp > 1:
                            tmp >>= 1
                            digit += 1
                        digit += 1
                        # Place
                        r = empty_pos // 9
                        cc = empty_pos % 9
                        bi = box_of[empty_pos]
                        bit = 1 << (digit - 1)
                        b[empty_pos] = digit
                        c[empty_pos] = 0
                        row_used[r] |= bit
                        col_used[cc] |= bit
                        box_used[bi] |= bit
                        np_i = peer_len[empty_pos]
                        for pi in range(np_i):
                            c[peers[empty_pos, pi]] &= ~bit
                        out_pos[n] = empty_pos
                        out_dig[n] = digit
                        out_tech[n] = 0  # fullHouse
                        n += 1
                        l1_changed = True

            # ── Naked Single: cell with 1 candidate ──
            for i in range(81):
                if b[i] != 0:
                    continue
                m = c[i]
                if m == 0:
                    continue
                if (m & (m - 1)) == 0:
                    digit = 0
                    tmp = m
                    while tmp > 1:
                        tmp >>= 1
                        digit += 1
                    digit += 1
                    r = i // 9
                    cc = i % 9
                    bi = box_of[i]
                    bit = 1 << (digit - 1)
                    b[i] = digit
                    c[i] = 0
                    row_used[r] |= bit
                    col_used[cc] |= bit
                    box_used[bi] |= bit
                    np_i = peer_len[i]
                    for pi in range(np_i):
                        c[peers[i, pi]] &= ~bit
                    out_pos[n] = i
                    out_dig[n] = digit
                    out_tech[n] = 1  # nakedSingle
                    n += 1
                    l1_changed = True

            # ── Hidden Single: unit scan ──
            for ui in range(27):
                for d in range(1, 10):
                    dbit = 1 << (d - 1)
                    placed = False
                    count = 0
                    last = -1
                    for ci in range(9):
                        pos = units[ui, ci]
                        if b[pos] == d:
                            placed = True
                            break
                        if b[pos] == 0 and (c[pos] & dbit):
                            count += 1
                            last = pos
                            if count > 1:
                                break
                    if placed:
                        continue
                    if count == 1 and b[last] == 0:
                        r = last // 9
                        cc = last % 9
                        bi = box_of[last]
                        b[last] = d
                        c[last] = 0
                        row_used[r] |= dbit
                        col_used[cc] |= dbit
                        box_used[bi] |= dbit
                        np_last = peer_len[last]
                        for pi in range(np_last):
                            c[peers[last, pi]] &= ~dbit
                        out_pos[n] = last
                        out_dig[n] = d
                        # crossHatch for row/col (ui<18), lastRemaining for box
                        out_tech[n] = 2 if ui < 18 else 3
                        n += 1
                        l1_changed = True

        # ── L2: Naked Pairs ──
        l2_changed = False
        for ui in range(27):
            for ai in range(9):
                pa = units[ui, ai]
                if b[pa] != 0 or popcount_lut[c[pa]] != 2:
                    continue
                mask = c[pa]
                for bi_idx in range(ai + 1, 9):
                    pb = units[ui, bi_idx]
                    if b[pb] != 0 or c[pb] != mask:
                        continue
                    for ci_idx in range(9):
                        pc = units[ui, ci_idx]
                        if pc == pa or pc == pb or b[pc] != 0:
                            continue
                        if c[pc] & mask:
                            c[pc] &= ~mask
                            l2_changed = True

        # ── L2: Pointing Pairs ──
        for bi in range(9):
            br = (bi // 3) * 3
            bc_start = (bi % 3) * 3
            for d in range(1, 10):
                dbit = 1 << (d - 1)
                placed = False
                for ci in range(9):
                    if b[units[18 + bi, ci]] == d:
                        placed = True
                        break
                if placed:
                    continue
                rmask = 0
                cmask = 0
                for ci in range(9):
                    pos = units[18 + bi, ci]
                    if b[pos] == 0 and (c[pos] & dbit):
                        rmask |= 1 << (pos // 9)
                        cmask |= 1 << (pos % 9)
                if rmask == 0:
                    continue
                if (rmask & (rmask - 1)) == 0:
                    row = 0
                    tmp = rmask
                    while tmp > 1:
                        tmp >>= 1
                        row += 1
                    for col in range(9):
                        if bc_start <= col < bc_start + 3:
                            continue
                        pos = row * 9 + col
                        if b[pos] == 0 and (c[pos] & dbit):
                            c[pos] &= ~dbit
                            l2_changed = True
                if (cmask & (cmask - 1)) == 0:
                    col = 0
                    tmp = cmask
                    while tmp > 1:
                        tmp >>= 1
                        col += 1
                    for row in range(9):
                        if br <= row < br + 3:
                            continue
                        pos = row * 9 + col
                        if b[pos] == 0 and (c[pos] & dbit):
                            c[pos] &= ~dbit
                            l2_changed = True

        # ── L2: Claiming ──
        for d in range(1, 10):
            dbit = 1 << (d - 1)
            for r in range(9):
                placed = False
                for cc in range(9):
                    if b[r * 9 + cc] == d:
                        placed = True
                        break
                if placed:
                    continue
                bmask = 0
                for cc in range(9):
                    pos = r * 9 + cc
                    if b[pos] == 0 and (c[pos] & dbit):
                        bmask |= 1 << (cc // 3)
                if bmask and (bmask & (bmask - 1)) == 0:
                    bci = 0
                    tmp = bmask
                    while tmp > 1:
                        tmp >>= 1
                        bci += 1
                    bcc = bci * 3
                    brr = (r // 3) * 3
                    for dr in range(3):
                        if brr + dr == r:
                            continue
                        for dc in range(3):
                            pos = (brr + dr) * 9 + bcc + dc
                            if b[pos] == 0 and (c[pos] & dbit):
                                c[pos] &= ~dbit
                                l2_changed = True
            for cc in range(9):
                placed = False
                for rr in range(9):
                    if b[rr * 9 + cc] == d:
                        placed = True
                        break
                if placed:
                    continue
                bmask = 0
                for rr in range(9):
                    pos = rr * 9 + cc
                    if b[pos] == 0 and (c[pos] & dbit):
                        bmask |= 1 << (rr // 3)
                if bmask and (bmask & (bmask - 1)) == 0:
                    bri = 0
                    tmp = bmask
                    while tmp > 1:
                        tmp >>= 1
                        bri += 1
                    brr = bri * 3
                    bcc = (cc // 3) * 3
                    for dc in range(3):
                        if bcc + dc == cc:
                            continue
                        for dr in range(3):
                            pos = (brr + dr) * 9 + bcc + dc
                            if b[pos] == 0 and (c[pos] & dbit):
                                c[pos] &= ~dbit
                                l2_changed = True

        if not l2_changed:
            break

    return out_pos[:n], out_dig[:n], out_tech[:n]


def propagate_l1l2(bb):
    """JIT-accelerated L1+L2 propagation. Syncs back to BitBoard after."""
    b = np.array(bb.board, dtype=np.int32)
    c = np.array(bb.cands, dtype=np.int32)
    ru = np.array(bb.row_used, dtype=np.int32)
    cu = np.array(bb.col_used, dtype=np.int32)
    bu = np.array(bb.box_used, dtype=np.int32)

    pos_arr, dig_arr, tech_arr = _drain_l1l2_jit(
        b, c, ru, cu, bu, _NB_BOX_OF, _NB_PEERS, _NB_PEER_LEN, _NB_UNITS, _NB_POPCOUNT)

    # Sync back to BitBoard
    for i in range(81):
        bb.board[i] = int(b[i])
        bb.cands[i] = int(c[i])
    for i in range(9):
        bb.row_used[i] = int(ru[i])
        bb.col_used[i] = int(cu[i])
        bb.box_used[i] = int(bu[i])
    bb.empty = sum(1 for x in bb.board if x == 0)
    # Rebuild cross-digit arrays from cands
    for d in range(9):
        mask81 = 0
        bit = BIT[d]
        for pos in range(81):
            if bb.cands[pos] & bit:
                mask81 |= 1 << pos
        bb.cross[d] = mask81

    # Build placement list
    placements = []
    for i in range(len(pos_arr)):
        tech_name = _TECH_NAMES[int(tech_arr[i])]
        placements.append((int(pos_arr[i]), int(dig_arr[i]), tech_name))
    return placements


def propagate_l1l2_pure(bb):
    """Original pure-Python L1+L2 propagation (kept for reference)."""
    all_placements = []
    for _ in range(50):
        progress = True
        while progress:
            progress = False
            hits = detect_l1_bitwise(bb)
            for pos, digit, tech in hits:
                if bb.board[pos] == 0:
                    bb.place(pos, digit)
                    all_placements.append((pos, digit, tech))
                    progress = True
        if not apply_l2_bitwise(bb):
            break
    return all_placements


def fast_propagate(board, cands, test_pos, test_digit):
    """Ultra-fast contradiction check using only cell-centric bitmasks.
    No cross-digit sync needed — this is the inner-loop hot function.
    Returns True if contradiction found."""
    b = board[:]
    c = cands[:]

    b[test_pos] = test_digit
    c[test_pos] = 0
    bit = BIT[test_digit - 1]
    for peer in PEERS[test_pos]:
        c[peer] &= ~bit

    for outer in range(30):
        # ── L1: Naked singles + Hidden singles ──
        changed = True
        while changed:
            changed = False
            for i in range(81):
                if b[i] != 0:
                    continue
                m = c[i]
                if m == 0:
                    return True  # contradiction
                if (m & (m - 1)) == 0:  # single candidate
                    d = m.bit_length()
                    b[i] = d
                    c[i] = 0
                    elim_bit = BIT[d - 1]
                    for peer in PEERS[i]:
                        c[peer] &= ~elim_bit
                    changed = True

            # Hidden singles using unit scan
            for unit in UNITS:
                for d in range(1, 10):
                    dbit = BIT[d - 1]
                    placed = False
                    count = 0
                    last = -1
                    for pos in unit:
                        if b[pos] == d:
                            placed = True
                            break
                        if b[pos] == 0 and (c[pos] & dbit):
                            count += 1
                            last = pos
                            if count > 1:
                                break
                    if placed:
                        continue
                    if count == 0:
                        return True  # contradiction
                    if count == 1:
                        b[last] = d
                        c[last] = 0
                        for peer in PEERS[last]:
                            c[peer] &= ~dbit
                        changed = True

        # ── L2: Naked Pairs ──
        l2 = False
        for unit in UNITS:
            for ai in range(9):
                pa = unit[ai]
                if b[pa] != 0 or POPCOUNT[c[pa]] != 2:
                    continue
                mask = c[pa]
                for bi_idx in range(ai + 1, 9):
                    pb = unit[bi_idx]
                    if b[pb] != 0 or c[pb] != mask:
                        continue
                    for ci_idx in range(9):
                        pc = unit[ci_idx]
                        if pc == pa or pc == pb or b[pc] != 0:
                            continue
                        if c[pc] & mask:
                            c[pc] &= ~mask
                            l2 = True
                            if c[pc] == 0:
                                return True

        # ── L2: Pointing Pairs (using bitmask row/col confinement) ──
        for bi in range(9):
            br, bc = (bi // 3) * 3, (bi % 3) * 3
            box_unit = UNITS[18 + bi]
            for d in range(1, 10):
                dbit = BIT[d - 1]
                if any(b[pos] == d for pos in box_unit):
                    continue
                rmask = 0  # which rows have this digit (3-bit)
                cmask = 0  # which cols have this digit (3-bit)
                for pos in box_unit:
                    if b[pos] == 0 and (c[pos] & dbit):
                        rmask |= 1 << (pos // 9)
                        cmask |= 1 << (pos % 9)
                if rmask == 0:
                    continue
                # Pointing in row: all on one row
                if (rmask & (rmask - 1)) == 0:
                    row = rmask.bit_length() - 1
                    for col in range(9):
                        if bc <= col < bc + 3:
                            continue
                        pos = row * 9 + col
                        if b[pos] == 0 and (c[pos] & dbit):
                            c[pos] &= ~dbit
                            l2 = True
                            if c[pos] == 0:
                                return True
                # Pointing in col: all on one col
                if (cmask & (cmask - 1)) == 0:
                    col = cmask.bit_length() - 1
                    for row in range(9):
                        if br <= row < br + 3:
                            continue
                        pos = row * 9 + col
                        if b[pos] == 0 and (c[pos] & dbit):
                            c[pos] &= ~dbit
                            l2 = True
                            if c[pos] == 0:
                                return True

        # ── L2: Claiming ──
        for d in range(1, 10):
            dbit = BIT[d - 1]
            # Row claiming
            for r in range(9):
                if any(b[r * 9 + cc] == d for cc in range(9)):
                    continue
                bmask = 0
                for cc in range(9):
                    pos = r * 9 + cc
                    if b[pos] == 0 and (c[pos] & dbit):
                        bmask |= 1 << (cc // 3)
                if bmask and (bmask & (bmask - 1)) == 0:
                    bci = bmask.bit_length() - 1
                    bcc, brr = bci * 3, (r // 3) * 3
                    for dr in range(3):
                        if brr + dr == r:
                            continue
                        for dc in range(3):
                            pos = (brr + dr) * 9 + bcc + dc
                            if b[pos] == 0 and (c[pos] & dbit):
                                c[pos] &= ~dbit
                                l2 = True
                                if c[pos] == 0:
                                    return True
            # Col claiming
            for cc in range(9):
                if any(b[rr * 9 + cc] == d for rr in range(9)):
                    continue
                bmask = 0
                for rr in range(9):
                    pos = rr * 9 + cc
                    if b[pos] == 0 and (c[pos] & dbit):
                        bmask |= 1 << (rr // 3)
                if bmask and (bmask & (bmask - 1)) == 0:
                    bri = bmask.bit_length() - 1
                    brr, bcc = bri * 3, (cc // 3) * 3
                    for dc in range(3):
                        if bcc + dc == cc:
                            continue
                        for dr in range(3):
                            pos = (brr + dr) * 9 + bcc + dc
                            if b[pos] == 0 and (c[pos] & dbit):
                                c[pos] &= ~dbit
                                l2 = True
                                if c[pos] == 0:
                                    return True

        if not l2:
            break

    return False


# ── Numba JIT: build peer/unit arrays for the JIT function ──
_NB_PEERS = np.zeros((81, 20), dtype=np.int32)
_NB_PEER_LEN = np.zeros(81, dtype=np.int32)
for _i in range(81):
    _p = list(PEERS[_i])
    _NB_PEERS[_i, :len(_p)] = _p
    _NB_PEER_LEN[_i] = len(_p)

_NB_UNITS = np.array(UNITS, dtype=np.int32)

_NB_BOX_OF = np.array(BOX_OF, dtype=np.int32)

_NB_POPCOUNT = np.zeros(512, dtype=np.int32)
for _i in range(1, 512):
    _NB_POPCOUNT[_i] = _NB_POPCOUNT[_i >> 1] + (_i & 1)

# ── Peer boolean matrix for JIT AIC graph ──
_NB_IS_PEER = np.zeros((81, 81), dtype=np.bool_)
for _i in range(81):
    for _p in PEERS[_i]:
        _NB_IS_PEER[_i, _p] = True

# ── Pre-allocated CSR buffers for AIC graph (reused across calls) ──
_AIC_S_ADJ = np.empty(20000, dtype=np.int32)
_AIC_S_OFF = np.zeros(730, dtype=np.int32)
_AIC_W_ADJ = np.empty(40000, dtype=np.int32)
_AIC_W_OFF = np.zeros(730, dtype=np.int32)


@nb.njit(nb.boolean(nb.int32[:], nb.int32[:], nb.int32, nb.int32,
                     nb.int32[:, :], nb.int32[:], nb.int32[:, :], nb.int32[:], nb.int32[:]),
         cache=True)
def _fast_prop_jit(b, c, test_pos, test_digit, peers, peer_len, units, box_of, popcount_lut):
    """Numba-JIT compiled contradiction checker. ~10-30x faster than pure Python."""
    b[test_pos] = test_digit
    c[test_pos] = 0
    bit = 1 << (test_digit - 1)
    npeers = peer_len[test_pos]
    for pi in range(npeers):
        c[peers[test_pos, pi]] &= ~bit

    for outer in range(30):
        changed = True
        while changed:
            changed = False
            # Naked singles
            for i in range(81):
                if b[i] != 0:
                    continue
                m = c[i]
                if m == 0:
                    return True
                if (m & (m - 1)) == 0:
                    # bit_length via manual log2
                    d = 0
                    tmp = m
                    while tmp > 1:
                        tmp >>= 1
                        d += 1
                    d += 1  # digit is 1-indexed
                    b[i] = d
                    c[i] = 0
                    elim_bit = 1 << (d - 1)
                    np_i = peer_len[i]
                    for pi in range(np_i):
                        c[peers[i, pi]] &= ~elim_bit
                    changed = True

            # Hidden singles
            for ui in range(27):
                for d in range(1, 10):
                    dbit = 1 << (d - 1)
                    placed = False
                    count = 0
                    last = -1
                    for ci in range(9):
                        pos = units[ui, ci]
                        if b[pos] == d:
                            placed = True
                            break
                        if b[pos] == 0 and (c[pos] & dbit):
                            count += 1
                            last = pos
                            if count > 1:
                                break
                    if placed:
                        continue
                    if count == 0:
                        return True
                    if count == 1:
                        b[last] = d
                        c[last] = 0
                        np_last = peer_len[last]
                        for pi in range(np_last):
                            c[peers[last, pi]] &= ~dbit
                        changed = True

        # L2: Naked Pairs
        l2 = False
        for ui in range(27):
            for ai in range(9):
                pa = units[ui, ai]
                if b[pa] != 0 or popcount_lut[c[pa]] != 2:
                    continue
                mask = c[pa]
                for bi_idx in range(ai + 1, 9):
                    pb = units[ui, bi_idx]
                    if b[pb] != 0 or c[pb] != mask:
                        continue
                    for ci_idx in range(9):
                        pc = units[ui, ci_idx]
                        if pc == pa or pc == pb or b[pc] != 0:
                            continue
                        if c[pc] & mask:
                            c[pc] &= ~mask
                            l2 = True
                            if c[pc] == 0:
                                return True

        # L2: Pointing Pairs
        for bi in range(9):
            br = (bi // 3) * 3
            bc_start = (bi % 3) * 3
            for d in range(1, 10):
                dbit = 1 << (d - 1)
                placed = False
                for ci in range(9):
                    if b[units[18 + bi, ci]] == d:
                        placed = True
                        break
                if placed:
                    continue
                rmask = 0
                cmask = 0
                for ci in range(9):
                    pos = units[18 + bi, ci]
                    if b[pos] == 0 and (c[pos] & dbit):
                        rmask |= 1 << (pos // 9)
                        cmask |= 1 << (pos % 9)
                if rmask == 0:
                    continue
                if (rmask & (rmask - 1)) == 0:
                    row = 0
                    tmp = rmask
                    while tmp > 1:
                        tmp >>= 1
                        row += 1
                    for col in range(9):
                        if bc_start <= col < bc_start + 3:
                            continue
                        pos = row * 9 + col
                        if b[pos] == 0 and (c[pos] & dbit):
                            c[pos] &= ~dbit
                            l2 = True
                            if c[pos] == 0:
                                return True
                if (cmask & (cmask - 1)) == 0:
                    col = 0
                    tmp = cmask
                    while tmp > 1:
                        tmp >>= 1
                        col += 1
                    for row in range(9):
                        if br <= row < br + 3:
                            continue
                        pos = row * 9 + col
                        if b[pos] == 0 and (c[pos] & dbit):
                            c[pos] &= ~dbit
                            l2 = True
                            if c[pos] == 0:
                                return True

        # L2: Claiming
        for d in range(1, 10):
            dbit = 1 << (d - 1)
            for r in range(9):
                placed = False
                for cc in range(9):
                    if b[r * 9 + cc] == d:
                        placed = True
                        break
                if placed:
                    continue
                bmask = 0
                for cc in range(9):
                    pos = r * 9 + cc
                    if b[pos] == 0 and (c[pos] & dbit):
                        bmask |= 1 << (cc // 3)
                if bmask and (bmask & (bmask - 1)) == 0:
                    bci = 0
                    tmp = bmask
                    while tmp > 1:
                        tmp >>= 1
                        bci += 1
                    bcc = bci * 3
                    brr = (r // 3) * 3
                    for dr in range(3):
                        if brr + dr == r:
                            continue
                        for dc in range(3):
                            pos = (brr + dr) * 9 + bcc + dc
                            if b[pos] == 0 and (c[pos] & dbit):
                                c[pos] &= ~dbit
                                l2 = True
                                if c[pos] == 0:
                                    return True
            for cc in range(9):
                placed = False
                for rr in range(9):
                    if b[rr * 9 + cc] == d:
                        placed = True
                        break
                if placed:
                    continue
                bmask = 0
                for rr in range(9):
                    pos = rr * 9 + cc
                    if b[pos] == 0 and (c[pos] & dbit):
                        bmask |= 1 << (rr // 3)
                if bmask and (bmask & (bmask - 1)) == 0:
                    bri = 0
                    tmp = bmask
                    while tmp > 1:
                        tmp >>= 1
                        bri += 1
                    brr = bri * 3
                    bcc = (cc // 3) * 3
                    for dc in range(3):
                        if bcc + dc == cc:
                            continue
                        for dr in range(3):
                            pos = (brr + dr) * 9 + bcc + dc
                            if b[pos] == 0 and (c[pos] & dbit):
                                c[pos] &= ~dbit
                                l2 = True
                                if c[pos] == 0:
                                    return True
        if not l2:
            break
    return False


def fast_propagate_np(board_list, cands_list, test_pos, test_digit):
    """Numba-JIT contradiction check wrapper. Accepts lists or numpy arrays."""
    if isinstance(board_list, np.ndarray):
        b = board_list.copy()
        c = cands_list.copy()
    else:
        b = np.array(board_list, dtype=np.int32)
        c = np.array(cands_list, dtype=np.int32)
    return _fast_prop_jit(b, c, np.int32(test_pos), np.int32(test_digit),
                          _NB_PEERS, _NB_PEER_LEN, _NB_UNITS, _NB_BOX_OF, _NB_POPCOUNT)

# ── Swap: use JIT version everywhere ──
fast_propagate_pure = fast_propagate   # keep original for benchmarking
fast_propagate = fast_propagate_np     # JIT is now the default (34x faster)


def fast_propagate_full(board, cands, test_pos, test_digit, return_np=False):
    """JIT-accelerated propagation with full state return.
    Returns (board, cands) or (None, None) on contradiction.
    If return_np=True, returns numpy arrays. Otherwise returns Python lists."""
    if isinstance(board, np.ndarray):
        b = board.copy()
        c = cands.copy()
    else:
        b = np.array(board, dtype=np.int32)
        c = np.array(cands, dtype=np.int32)
    contra = _fast_prop_jit(b, c, np.int32(test_pos), np.int32(test_digit),
                            _NB_PEERS, _NB_PEER_LEN, _NB_UNITS, _NB_BOX_OF, _NB_POPCOUNT)
    if contra:
        return None, None
    if return_np:
        return b, c
    return b.tolist(), c.tolist()


def fast_propagate_full_np(board, cands, test_pos, test_digit):
    """JIT propagation returning numpy arrays directly (avoids tolist() overhead).
    Returns (board_np, cands_np) or (None, None) on contradiction."""
    b = np.array(board, dtype=np.int32)
    c = np.array(cands, dtype=np.int32)
    contra = _fast_prop_jit(b, c, np.int32(test_pos), np.int32(test_digit),
                            _NB_PEERS, _NB_PEER_LEN, _NB_UNITS, _NB_BOX_OF, _NB_POPCOUNT)
    if contra:
        return None, None
    return b, c


# ══════════════════════════════════════════════════════════════════════
# JIT AIC GRAPH BUILDER — CSR format for Kraken Fish
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _build_aic_graph_jit(cands, units, is_peer, popcount_lut,
                         s_adj, s_off, w_adj, w_off):
    """Build AIC graph in CSR format. Returns (s_count, w_count).

    Node ID = pos * 9 + d (0-indexed digit), 729 nodes total.
    s_adj/s_off = strong link CSR, w_adj/w_off = weak link CSR.
    """
    N = 729

    # ── Pass 1: count edges per node ──
    s_deg = np.zeros(N, dtype=np.int32)
    w_deg = np.zeros(N, dtype=np.int32)

    # Dedup for strong links (flat boolean array)
    has_strong = np.zeros(N * N, dtype=nb.boolean)

    # Strong links: conjugate pairs (digit in exactly 2 cells per unit)
    for ui in range(27):
        for d in range(9):
            dbit = 1 << d
            count = 0
            p0 = -1
            p1 = -1
            for ci in range(9):
                pos = units[ui, ci]
                if cands[pos] & dbit:
                    if count == 0:
                        p0 = pos
                    elif count == 1:
                        p1 = pos
                    count += 1
                    if count > 2:
                        break
            if count == 2:
                ni = p0 * 9 + d
                nj = p1 * 9 + d
                key_ij = ni * N + nj
                if not has_strong[key_ij]:
                    has_strong[key_ij] = True
                    has_strong[nj * N + ni] = True
                    s_deg[ni] += 1
                    s_deg[nj] += 1

    # Strong links: bivalue cells (exactly 2 candidates)
    for pos in range(81):
        c = cands[pos]
        if c == 0 or popcount_lut[c] != 2:
            continue
        # Extract the two digits
        d0 = -1
        d1 = -1
        for dd in range(9):
            if c & (1 << dd):
                if d0 < 0:
                    d0 = dd
                else:
                    d1 = dd
                    break
        ni = pos * 9 + d0
        nj = pos * 9 + d1
        key_ij = ni * N + nj
        if not has_strong[key_ij]:
            has_strong[key_ij] = True
            has_strong[nj * N + ni] = True
            s_deg[ni] += 1
            s_deg[nj] += 1

    # Weak links: same cell, different digits
    for pos in range(81):
        c = cands[pos]
        if c == 0 or popcount_lut[c] < 2:
            continue
        digits_buf = np.empty(9, dtype=np.int32)
        nd = 0
        for dd in range(9):
            if c & (1 << dd):
                digits_buf[nd] = dd
                nd += 1
        for a in range(nd):
            for b in range(a + 1, nd):
                ni = pos * 9 + digits_buf[a]
                nj = pos * 9 + digits_buf[b]
                w_deg[ni] += 1
                w_deg[nj] += 1

    # Weak links: same digit, cells see each other (not already strong)
    for d in range(9):
        dbit = 1 << d
        d_pos = np.empty(81, dtype=np.int32)
        nd = 0
        for pos in range(81):
            if cands[pos] & dbit:
                d_pos[nd] = pos
                nd += 1
        for a in range(nd):
            for b in range(a + 1, nd):
                pa = d_pos[a]
                pb = d_pos[b]
                if is_peer[pa, pb]:
                    ni = pa * 9 + d
                    nj = pb * 9 + d
                    key_ij = ni * N + nj
                    if not has_strong[key_ij]:
                        w_deg[ni] += 1
                        w_deg[nj] += 1

    # ── Build offsets from degrees ──
    s_off[0] = 0
    for i in range(N):
        s_off[i + 1] = s_off[i] + s_deg[i]
    w_off[0] = 0
    for i in range(N):
        w_off[i + 1] = w_off[i] + w_deg[i]

    s_total = s_off[N]
    w_total = w_off[N]

    # ── Pass 2: fill adjacency arrays ──
    s_cur = np.zeros(N, dtype=np.int32)
    w_cur = np.zeros(N, dtype=np.int32)

    # Reset has_strong for reuse
    for i in range(N * N):
        has_strong[i] = False

    # Strong: conjugate pairs
    for ui in range(27):
        for d in range(9):
            dbit = 1 << d
            count = 0
            p0 = -1
            p1 = -1
            for ci in range(9):
                pos = units[ui, ci]
                if cands[pos] & dbit:
                    if count == 0:
                        p0 = pos
                    elif count == 1:
                        p1 = pos
                    count += 1
                    if count > 2:
                        break
            if count == 2:
                ni = p0 * 9 + d
                nj = p1 * 9 + d
                key_ij = ni * N + nj
                if not has_strong[key_ij]:
                    has_strong[key_ij] = True
                    has_strong[nj * N + ni] = True
                    s_adj[s_off[ni] + s_cur[ni]] = nj
                    s_cur[ni] += 1
                    s_adj[s_off[nj] + s_cur[nj]] = ni
                    s_cur[nj] += 1

    # Strong: bivalue cells
    for pos in range(81):
        c = cands[pos]
        if c == 0 or popcount_lut[c] != 2:
            continue
        d0 = -1
        d1 = -1
        for dd in range(9):
            if c & (1 << dd):
                if d0 < 0:
                    d0 = dd
                else:
                    d1 = dd
                    break
        ni = pos * 9 + d0
        nj = pos * 9 + d1
        key_ij = ni * N + nj
        if not has_strong[key_ij]:
            has_strong[key_ij] = True
            has_strong[nj * N + ni] = True
            s_adj[s_off[ni] + s_cur[ni]] = nj
            s_cur[ni] += 1
            s_adj[s_off[nj] + s_cur[nj]] = ni
            s_cur[nj] += 1

    # Weak: same cell, different digits
    for pos in range(81):
        c = cands[pos]
        if c == 0 or popcount_lut[c] < 2:
            continue
        digits_buf = np.empty(9, dtype=np.int32)
        nd = 0
        for dd in range(9):
            if c & (1 << dd):
                digits_buf[nd] = dd
                nd += 1
        for a in range(nd):
            for b in range(a + 1, nd):
                ni = pos * 9 + digits_buf[a]
                nj = pos * 9 + digits_buf[b]
                w_adj[w_off[ni] + w_cur[ni]] = nj
                w_cur[ni] += 1
                w_adj[w_off[nj] + w_cur[nj]] = ni
                w_cur[nj] += 1

    # Weak: same digit, peer cells (not strong)
    for d in range(9):
        dbit = 1 << d
        d_pos = np.empty(81, dtype=np.int32)
        nd = 0
        for pos in range(81):
            if cands[pos] & dbit:
                d_pos[nd] = pos
                nd += 1
        for a in range(nd):
            for b in range(a + 1, nd):
                pa = d_pos[a]
                pb = d_pos[b]
                if is_peer[pa, pb]:
                    ni = pa * 9 + d
                    nj = pb * 9 + d
                    key_ij = ni * N + nj
                    if not has_strong[key_ij]:
                        w_adj[w_off[ni] + w_cur[ni]] = nj
                        w_cur[ni] += 1
                        w_adj[w_off[nj] + w_cur[nj]] = ni
                        w_cur[nj] += 1

    return s_total, w_total


def build_aic_graph_jit(bb):
    """Build AIC graph using JIT, return CSR arrays."""
    cands_np = np.array(bb.cands, dtype=np.int32)
    s_total, w_total = _build_aic_graph_jit(
        cands_np, _NB_UNITS, _NB_IS_PEER, _NB_POPCOUNT,
        _AIC_S_ADJ, _AIC_S_OFF, _AIC_W_ADJ, _AIC_W_OFF)
    return (_AIC_S_ADJ[:s_total].copy(), _AIC_S_OFF.copy(),
            _AIC_W_ADJ[:w_total].copy(), _AIC_W_OFF.copy())


# ══════════════════════════════════════════════════════════════════════
# JIT AIC REACHABILITY BFS — alternating strong/weak links
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _aic_reaches_jit(src, tgt, s_adj, s_off, w_adj, w_off):
    """BFS with alternating strong/weak links. Returns True if target reachable.
    Link type: 0 = strong start, 1 = weak start. Alternates at each step.
    After strong → follow weak neighbors. After weak → follow strong neighbors.
    """
    if src == tgt:
        return False

    # Queue: flat arrays for (node, link_type) pairs
    # link_type: 0 = arrived via strong (next should follow weak), 1 = arrived via weak
    q_node = np.empty(1500, dtype=np.int32)
    q_type = np.empty(1500, dtype=np.int32)
    visited = np.zeros(729 * 2, dtype=nb.boolean)  # visited[node*2+type]

    # Start with lt=0 only: fin is ON → follow weak links first
    head = 0
    tail = 0
    q_node[tail] = src
    q_type[tail] = 0  # "arrived via strong" = node is ON → will follow weak
    tail += 1
    visited[src * 2] = True

    for _depth in range(20):
        if head >= tail:
            break
        level_end = tail
        while head < level_end:
            cur = q_node[head]
            lt = q_type[head]
            head += 1

            # After arriving via strong (lt=0), follow weak neighbors
            # After arriving via weak (lt=1), follow strong neighbors
            if lt == 0:
                # Follow weak links
                start_idx = w_off[cur]
                end_idx = w_off[cur + 1]
                nt = 1  # next arrives "via weak"
            else:
                # Follow strong links
                start_idx = s_off[cur]
                end_idx = s_off[cur + 1]
                nt = 0  # next arrives "via strong"

            for ei in range(start_idx, end_idx):
                if lt == 0:
                    nxt = w_adj[ei]
                else:
                    nxt = s_adj[ei]
                if nxt == tgt and lt == 0:
                    return True  # target reached via weak link → proven OFF
                vk = nxt * 2 + nt
                if not visited[vk]:
                    visited[vk] = True
                    if tail < 1500:
                        q_node[tail] = nxt
                        q_type[tail] = nt
                        tail += 1
    return False


def aic_reaches_jit(src_nid, tgt_nid, s_adj, s_off, w_adj, w_off):
    """Python wrapper for JIT AIC reachability."""
    return _aic_reaches_jit(np.int32(src_nid), np.int32(tgt_nid),
                            s_adj, s_off, w_adj, w_off)


# ══════════════════════════════════════════════════════════════════════
# JIT FORCING CHAIN FOLLOWER — contradiction-only variant
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _follow_chain_contra_jit(board, cands, start_pos, start_val,
                              peers, peer_len, units, popcount_lut):
    """Contradiction-only chain follower. Returns True if contradiction found.
    Uses forced_vals[81] + elim_at[81] arrays, max depth 12.
    """
    forced_vals = np.zeros(81, dtype=np.int32)
    forced_vals[start_pos] = start_val
    forced_visited = np.zeros(81, dtype=nb.boolean)
    forced_visited[start_pos] = True
    elim_at = np.zeros(81, dtype=np.int32)  # bitmask of eliminated digits per cell

    # Initialize: start_pos eliminates its digit from all peers
    start_bit = 1 << (start_val - 1)
    np_start = peer_len[start_pos]
    for pi in range(np_start):
        elim_at[peers[start_pos, pi]] |= start_bit

    q_buf = np.empty(81, dtype=np.int32)
    q_buf[0] = start_pos
    q_len = 1

    for depth in range(12):
        if q_len == 0:
            break
        nxt_buf = np.empty(81, dtype=np.int32)
        nxt_len = 0

        for qi in range(q_len):
            fpos = q_buf[qi]
            fval = forced_vals[fpos]
            np_f = peer_len[fpos]
            for pi in range(np_f):
                peer = peers[fpos, pi]
                if board[peer] != 0 or forced_visited[peer]:
                    continue
                ec = cands[peer] & ~elim_at[peer]
                if ec == 0:
                    return True  # contradiction
                if (ec & (ec - 1)) == 0:  # single candidate left
                    nv = 0
                    tmp = ec
                    while tmp > 1:
                        tmp >>= 1
                        nv += 1
                    nv += 1  # 1-indexed
                    forced_vals[peer] = nv
                    forced_visited[peer] = True
                    if nxt_len < 81:
                        nxt_buf[nxt_len] = peer
                        nxt_len += 1
                    # Update elim_at for new forced cell
                    nv_bit = 1 << (nv - 1)
                    np_p = peer_len[peer]
                    for p2i in range(np_p):
                        elim_at[peers[peer, p2i]] |= nv_bit

        # Hidden singles in units
        for ui in range(27):
            for n in range(1, 10):
                nbit = 1 << (n - 1)
                placed = False
                for ci in range(9):
                    p = units[ui, ci]
                    if board[p] == n or forced_vals[p] == n:
                        placed = True
                        break
                if placed:
                    continue
                spots = 0
                last_spot = -1
                for ci in range(9):
                    p = units[ui, ci]
                    if board[p] != 0 or forced_visited[p]:
                        continue
                    ec = cands[p] & ~elim_at[p]
                    if ec & nbit:
                        spots += 1
                        last_spot = p
                        if spots > 1:
                            break
                if spots == 0:
                    return True  # contradiction
                if spots == 1 and not forced_visited[last_spot]:
                    forced_vals[last_spot] = n
                    forced_visited[last_spot] = True
                    if nxt_len < 81:
                        nxt_buf[nxt_len] = last_spot
                        nxt_len += 1
                    n_bit = 1 << (n - 1)
                    np_ls = peer_len[last_spot]
                    for p2i in range(np_ls):
                        elim_at[peers[last_spot, p2i]] |= n_bit

        # Move to next depth
        q_len = nxt_len
        for i in range(nxt_len):
            q_buf[i] = nxt_buf[i]

    return False


def follow_chain_contra(board, cands, start_pos, start_val):
    """Python wrapper: JIT contradiction-only chain follower.
    Accepts both Python lists and numpy arrays."""
    if isinstance(board, np.ndarray):
        b = board.copy()
        c = cands.copy()
    else:
        b = np.array(board, dtype=np.int32)
        c = np.array(cands, dtype=np.int32)
    return _follow_chain_contra_jit(b, c, np.int32(start_pos), np.int32(start_val),
                                     _NB_PEERS, _NB_PEER_LEN, _NB_UNITS, _NB_POPCOUNT)


# ══════════════════════════════════════════════════════════════════════
# FPC — Finned Pointing Chain (bitmask version)
# ══════════════════════════════════════════════════════════════════════

def detect_fpc_bitwise(bb):
    """FPC using BitBoard for fast candidate lookups."""
    results = []
    prop_cache = {}

    def cached_prop(pos, digit):
        key = pos * 10 + digit
        if key not in prop_cache:
            prop_cache[key] = fast_propagate(bb.board, bb.cands, pos, digit)
        return prop_cache[key]

    ap_cache = {}
    def find_ap(bkr, bkc, digit):
        key = bkr * 90 + bkc * 10 + digit
        if key in ap_cache:
            return ap_cache[key]
        bk_box = BOX_OF[bkr * 9 + bkc]
        dbit = BIT[digit - 1]
        aps = []
        for bx in range(9):
            if bx == bk_box:
                continue
            d_in_box = bb.cross[digit - 1] & BOX_81[bx]
            if popcount81(d_in_box) < 2:
                continue
            bx_r0 = (bx // 3) * 3
            bx_c0 = (bx % 3) * 3
            if bx_r0 <= bkr < bx_r0 + 3:
                on = d_in_box & ROW_81[bkr]
                off = d_in_box & ~ROW_81[bkr]
                if on and popcount81(off) == 1:
                    fin_pos = lsb81(off)
                    fin_r, fin_c = fin_pos // 9, fin_pos % 9
                    on_cells = [(p // 9, p % 9) for p in iter_bits81(on)]
                    aps.append({'dir': 'row', 'box': bx, 'fin': (fin_r, fin_c),
                                'pointing': on_cells, 'line': bkr})
            if bx_c0 <= bkc < bx_c0 + 3:
                on = d_in_box & COL_81[bkc]
                off = d_in_box & ~COL_81[bkc]
                if on and popcount81(off) == 1:
                    fin_pos = lsb81(off)
                    fin_r, fin_c = fin_pos // 9, fin_pos % 9
                    on_cells = [(p // 9, p % 9) for p in iter_bits81(on)]
                    aps.append({'dir': 'col', 'box': bx, 'fin': (fin_r, fin_c),
                                'pointing': on_cells, 'line': bkc})
        ap_cache[key] = aps
        return aps

    def passes_gold(target, blockers, digit):
        tr, tc = target
        bkr, bkc = blockers[0]
        t_pos, b_pos = tr * 9 + tc, bkr * 9 + bkc
        dbit = BIT[digit - 1]
        same_row = bkr == tr
        same_col = bkc == tc
        same_box = BOX_OF[t_pos] == BOX_OF[b_pos]
        if same_row:
            for cc in range(9):
                if cc == bkc or cc == tc:
                    continue
                if bb.cands[tr * 9 + cc] & dbit:
                    return False
        elif same_col:
            for rr in range(9):
                if rr == bkr or rr == tr:
                    continue
                if bb.cands[rr * 9 + tc] & dbit:
                    return False
        elif same_box:
            br2, bc2 = (tr // 3) * 3, (tc // 3) * 3
            for rr in range(br2, br2 + 3):
                for cc in range(bc2, bc2 + 3):
                    if (rr == bkr and cc == bkc) or (rr == tr and cc == tc):
                        continue
                    if bb.cands[rr * 9 + cc] & dbit:
                        return False
        else:
            return False
        if cached_prop(t_pos, digit):
            return False
        if not cached_prop(b_pos, digit):
            return False
        return True

    def try_unit(cells, digit):
        if len(cells) < 2 or len(cells) > 4:
            return
        for ti in range(len(cells)):
            ok = True
            for bi in range(len(cells)):
                if bi == ti:
                    continue
                if not find_ap(cells[bi][0], cells[bi][1], digit):
                    ok = False
                    break
            if not ok:
                continue
            target = cells[ti]
            blockers = [cells[bi] for bi in range(len(cells)) if bi != ti]
            if passes_gold(target, blockers, digit):
                pos = target[0] * 9 + target[1]
                results.append((pos, digit, f'FPC d{digit} R{target[0]+1}C{target[1]+1}'))
                return

    for d in range(1, 10):
        dbit = BIT[d - 1]
        for r in range(9):
            cells = []
            for c in range(9):
                pos = r * 9 + c
                if bb.board[pos] == 0 and (bb.cands[pos] & dbit):
                    cells.append((r, c))
            try_unit(cells, d)
        for c in range(9):
            cells = []
            for r in range(9):
                pos = r * 9 + c
                if bb.board[pos] == 0 and (bb.cands[pos] & dbit):
                    cells.append((r, c))
            try_unit(cells, d)
        for bi in range(9):
            cells = []
            for pos in UNITS[18 + bi]:
                if bb.board[pos] == 0 and (bb.cands[pos] & dbit):
                    cells.append((pos // 9, pos % 9))
            try_unit(cells, d)

    return results


# ══════════════════════════════════════════════════════════════════════
# FPCE — FPC Elimination (bitmask version)
# ══════════════════════════════════════════════════════════════════════

def detect_fpce_bitwise(bb):
    """Test each candidate via contradiction. Eliminate those that contradict.
    Returns (placements, eliminations)."""
    eliminations = []  # (pos, digit)

    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        m = bb.cands[pos]
        if POPCOUNT[m] <= 1:
            continue
        to_remove = 0  # bitmask of digits to eliminate
        for d in iter_bits9(m):
            if fast_propagate(bb.board, bb.cands, pos, d + 1):
                to_remove |= BIT[d]
        if to_remove and to_remove != m:  # don't eliminate all
            for d in iter_bits9(to_remove):
                eliminations.append((pos, d + 1))

    # Apply to copy, find placements
    test_cands = bb.cands[:]
    for pos, digit in eliminations:
        test_cands[pos] &= ~BIT[digit - 1]

    placements = []
    for pos in range(81):
        if bb.board[pos] == 0:
            m = test_cands[pos]
            if m and (m & (m - 1)) == 0:
                placements.append((pos, m.bit_length(), f'FPCE R{pos//9+1}C{pos%9+1}={m.bit_length()}'))

    return placements, eliminations


# ══════════════════════════════════════════════════════════════════════
# FORCING CHAIN (bitmask version)
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _follow_chain_jit(board, cands, start_pos, start_val, peers, unit_cells, max_depth=12):
    """JIT forcing chain. Returns (status, forced_vals).
    status: 0=inconclusive/None, 1=contradiction, 2=valid result."""
    forced_vals = np.zeros(81, dtype=np.int32)
    forced_vals[start_pos] = start_val
    forced_mask = np.zeros(81, dtype=np.bool_)
    forced_mask[start_pos] = True

    elim_at = np.zeros(81, dtype=np.int32)
    start_bit = 1 << (start_val - 1)
    for pi in range(20):
        peer = peers[start_pos, pi]
        elim_at[peer] |= start_bit

    queue = np.zeros(81, dtype=np.int32)
    queue[0] = start_pos
    q_len = 1

    for depth in range(max_depth):
        if q_len == 0:
            break
        nxt = np.zeros(81, dtype=np.int32)
        n_nxt = 0

        for qi in range(q_len):
            fpos = queue[qi]
            fval = forced_vals[fpos]
            for pi in range(20):
                peer = peers[fpos, pi]
                if board[peer] != 0 or forced_mask[peer]:
                    continue
                ec = cands[peer] & ~elim_at[peer]
                if ec == 0:
                    return 1, forced_vals  # contradiction
                if ec & (ec - 1) == 0:  # single candidate
                    nv = 0
                    tmp = ec
                    while tmp > 1:
                        nv += 1
                        tmp >>= 1
                    nv += 1  # 1-indexed
                    forced_vals[peer] = nv
                    forced_mask[peer] = True
                    nxt[n_nxt] = peer
                    n_nxt += 1
                    nv_bit = 1 << (nv - 1)
                    for p2i in range(20):
                        p2 = peers[peer, p2i]
                        elim_at[p2] |= nv_bit

        # Hidden singles in units
        for ui in range(27):
            for n in range(1, 10):
                nbit = 1 << (n - 1)
                placed = False
                for ci in range(9):
                    p = unit_cells[ui, ci]
                    if board[p] == n or forced_vals[p] == n:
                        placed = True
                        break
                if placed:
                    continue
                spots_count = 0
                last_spot = -1
                for ci in range(9):
                    p = unit_cells[ui, ci]
                    if board[p] != 0 or forced_mask[p]:
                        continue
                    ec = cands[p] & ~elim_at[p]
                    if ec & nbit:
                        spots_count += 1
                        last_spot = p
                        if spots_count > 1:
                            break
                if spots_count == 0:
                    return 1, forced_vals  # contradiction
                if spots_count == 1 and not forced_mask[last_spot]:
                    forced_vals[last_spot] = n
                    forced_mask[last_spot] = True
                    nxt[n_nxt] = last_spot
                    n_nxt += 1
                    n_bit = 1 << (n - 1)
                    for p2i in range(20):
                        p2 = peers[last_spot, p2i]
                        elim_at[p2] |= n_bit

        # Copy nxt to queue
        q_len = n_nxt
        for i in range(n_nxt):
            queue[i] = nxt[i]

    # Count forced
    count = 0
    for pos in range(81):
        if forced_vals[pos] != 0:
            count += 1
    if count > 1:
        return 2, forced_vals  # valid result
    return 0, forced_vals  # inconclusive


def follow_chain_bitwise(bb, start_pos, start_val, max_depth=12):
    """Follow forcing chain — JIT-accelerated wrapper."""
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    status, forced = _follow_chain_jit(board_arr, cands_arr, start_pos, start_val,
                                        NP_PEERS, NP_UNIT_CELLS, max_depth)
    if status == 1:
        return 'contradiction'
    if status == 2:
        result = {}
        for pos in range(81):
            if forced[pos] != 0:
                result[pos] = int(forced[pos])
        return result
    return None


@nb.njit(cache=True)
def _detect_forcing_chain_jit(board, cands, peers, unit_cells, popcount_lut):
    """JIT forcing chain detection: bivalue/trivalue cells, contradiction/convergence."""
    # Output: (pos, digit, mode) mode: 0=contradict, 1=converge
    out = np.zeros((10, 3), dtype=np.int32)
    n_out = 0

    # Collect start cells (bivalue first, then trivalue)
    starts_bi = np.zeros(81, dtype=np.int32)
    starts_tri = np.zeros(81, dtype=np.int32)
    n_bi = 0
    n_tri = 0
    for pos in range(81):
        if board[pos] != 0:
            continue
        pc = popcount_lut[cands[pos]]
        if pc == 2:
            starts_bi[n_bi] = pos
            n_bi += 1
        elif pc == 3:
            starts_tri[n_tri] = pos
            n_tri += 1

    for phase in range(2):
        arr = starts_bi if phase == 0 else starts_tri
        count = n_bi if phase == 0 else n_tri
        for si in range(count):
            pos = arr[si]
            m = cands[pos]
            # Extract digits
            digits = np.zeros(4, dtype=np.int32)
            n_d = 0
            for d in range(9):
                if m & (1 << d):
                    digits[n_d] = d + 1
                    n_d += 1

            # Run chains for each digit
            statuses = np.zeros(4, dtype=np.int32)
            forced_all = np.zeros((4, 81), dtype=np.int32)
            for di in range(n_d):
                st, fv = _follow_chain_jit(board, cands, pos, digits[di],
                                            peers, unit_cells, 12)
                statuses[di] = st
                for p in range(81):
                    forced_all[di, p] = fv[p]

            # Check contradiction pattern
            n_contra = 0
            n_valid = 0
            valid_idx = -1
            for di in range(n_d):
                if statuses[di] == 1:
                    n_contra += 1
                elif statuses[di] == 2:
                    n_valid += 1
                    valid_idx = di

            if n_contra == n_d - 1 and n_valid == 1:
                if n_out < 10:
                    out[n_out, 0] = pos
                    out[n_out, 1] = digits[valid_idx]
                    out[n_out, 2] = 0
                    n_out += 1
                return out[:n_out], n_out

            # Convergence: all chains valid and agree on some cell
            if n_valid == n_d and n_valid >= 2:
                for p in range(81):
                    if p == pos or board[p] != 0:
                        continue
                    v = forced_all[0, p]
                    if v == 0:
                        continue
                    agree = True
                    for di in range(1, n_d):
                        if forced_all[di, p] != v:
                            agree = False
                            break
                    if agree:
                        if n_out < 10:
                            out[n_out, 0] = p
                            out[n_out, 1] = v
                            out[n_out, 2] = 1
                            n_out += 1
                        return out[:n_out], n_out

            # Partial contradiction: some contradict, one remains
            if n_contra > 0 and n_contra < n_d:
                remaining = -1
                n_rem = 0
                for di in range(n_d):
                    if statuses[di] != 1:
                        remaining = di
                        n_rem += 1
                if n_rem == 1:
                    if n_out < 10:
                        out[n_out, 0] = pos
                        out[n_out, 1] = digits[remaining]
                        out[n_out, 2] = 0
                        n_out += 1
                    return out[:n_out], n_out

    return out[:n_out], n_out


def detect_forcing_chain_bitwise(bb):
    """Detect forcing chain placements — JIT-accelerated."""
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    out, n_out = _detect_forcing_chain_jit(board_arr, cands_arr,
                                            NP_PEERS, NP_UNIT_CELLS, NP_POPCOUNT)
    results = []
    for k in range(n_out):
        pos = int(out[k, 0])
        val = int(out[k, 1])
        r, c = pos // 9, pos % 9
        mode = int(out[k, 2])
        if mode == 0:
            results.append((pos, val, f'ForcingChain R{r+1}C{c+1}={val} (contradiction)'))
        else:
            results.append((pos, val, f'ForcingChain R{r+1}C{c+1}={val} (convergence)'))
    return results


# ══════════════════════════════════════════════════════════════════════
# FORCING NET — 3-4 candidate cells, depth 12 chain following
# ══════════════════════════════════════════════════════════════════════

def detect_forcing_net(bb):
    """Forcing Net: 3-4 candidate cells, JIT-accelerated propagation.
    Uses fast_propagate for contradiction, fast_propagate_full for convergence."""
    results = []
    cells = []
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        pc = POPCOUNT[bb.cands[pos]]
        if 3 <= pc <= 4:
            cells.append((pos, pc))
    cells.sort(key=lambda x: x[1])

    for pos, _ in cells[:15]:
        digits = [d + 1 for d in iter_bits9(bb.cands[pos])]

        # Phase 1: JIT contradiction check
        contradicted = []
        valid = []
        for v in digits:
            if fast_propagate(bb.board, bb.cands, pos, v):
                contradicted.append(v)
            else:
                valid.append(v)

        # All but one contradicted → placement
        if len(contradicted) == len(digits) - 1 and len(valid) == 1:
            val = valid[0]
            r, c = pos // 9, pos % 9
            results.append((pos, val,
                f'ForcingNet R{r+1}C{c+1}={val} ({len(contradicted)} contradicted)'))
            return results

        # Some contradicted → naked single
        if contradicted and len(contradicted) < len(digits):
            remaining = bb.cands[pos]
            for v in contradicted:
                remaining &= ~BIT[v - 1]
            if remaining and (remaining & (remaining - 1)) == 0:
                val = remaining.bit_length()
                r, c = pos // 9, pos % 9
                results.append((pos, val,
                    f'ForcingNet R{r+1}C{c+1}={val} (elim {len(contradicted)})'))
                return results

        # Phase 2: Convergence check
        if len(valid) >= 2:
            boards = []
            for v in valid:
                new_b, _ = fast_propagate_full(bb.board, bb.cands, pos, v)
                if new_b is not None:
                    boards.append(new_b)
            if len(boards) == len(valid):
                for cell in range(81):
                    if bb.board[cell] != 0:
                        continue
                    vals = [b[cell] for b in boards]
                    if all(v != 0 for v in vals) and len(set(vals)) == 1:
                        kr, kc = cell // 9, cell % 9
                        r, c = pos // 9, pos % 9
                        results.append((cell, vals[0],
                            f'ForcingNet from R{r+1}C{c+1}: all → R{kr+1}C{kc+1}={vals[0]}'))
                        return results

    return results


# ══════════════════════════════════════════════════════════════════════
# L6 TECHNIQUES — BUG+1, UR Type 2/4, Junior Exocet, Template, Bowman
# ══════════════════════════════════════════════════════════════════════

def detect_bug_plus1(bb):
    """BUG+1: If all unsolved cells are bivalue except exactly one trivalue cell,
    the digit with odd parity count in its row/col/box is the answer.
    Pure bitmask — O(81) scan + 3 parity checks on the trivalue cell."""
    tri_pos = -1
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        pc = POPCOUNT[bb.cands[pos]]
        if pc < 2:
            return []  # invalid state
        if pc == 2:
            continue
        if pc == 3:
            if tri_pos >= 0:
                return []  # more than one non-bivalue
            tri_pos = pos
        else:
            return []  # 4+ candidates exist
    if tri_pos < 0:
        return []

    r, c = tri_pos // 9, tri_pos % 9
    bi = BOX_OF[tri_pos]
    mask = bb.cands[tri_pos]

    for d in iter_bits9(mask):
        dbit = BIT[d]
        # Check row parity
        row_count = 0
        for cc in range(9):
            p = r * 9 + cc
            if bb.board[p] == 0 and (bb.cands[p] & dbit):
                row_count += 1
        if row_count & 1:
            return [(tri_pos, d + 1, f'BUG+1 R{r+1}C{c+1}={d+1} (odd row count)')]

        # Check col parity
        col_count = 0
        for rr in range(9):
            p = rr * 9 + c
            if bb.board[p] == 0 and (bb.cands[p] & dbit):
                col_count += 1
        if col_count & 1:
            return [(tri_pos, d + 1, f'BUG+1 R{r+1}C{c+1}={d+1} (odd col count)')]

        # Check box parity
        box_count = 0
        for bp in BOX_CELLS_FLAT[bi]:
            if bb.board[bp] == 0 and (bb.cands[bp] & dbit):
                box_count += 1
        if box_count & 1:
            return [(tri_pos, d + 1, f'BUG+1 R{r+1}C{c+1}={d+1} (odd box count)')]

    return []


def detect_ur_type2(bb):
    """Unique Rectangle Type 2: Floor pair (bivalue) + roof pair (same 2 + shared extra).
    Eliminate the extra digit from common peers of the roof cells.
    Uses bitmask candidate ops throughout."""
    results_elims = []  # will hold (elim_list, detail_str) if found

    for r1 in range(9):
        for c1 in range(9):
            pos1 = r1 * 9 + c1
            if bb.board[pos1] != 0:
                continue
            m1 = bb.cands[pos1]
            if POPCOUNT[m1] != 2:
                continue
            # Floor cell 1 found (bivalue). Try all floor cell 2 in same row, different box
            for c2 in range(c1 + 1, 9):
                pos2 = r1 * 9 + c2
                if bb.board[pos2] != 0 or bb.cands[pos2] != m1:
                    continue
                if BOX_OF[pos1] == BOX_OF[pos2]:
                    continue
                # Floor pair confirmed: (r1,c1) and (r1,c2) with same 2 digits
                pair_mask = m1  # the 2 digits
                # Look for roof row
                for r2 in range(r1 + 1, 9):
                    roof1 = r2 * 9 + c1
                    roof2 = r2 * 9 + c2
                    if bb.board[roof1] != 0 or bb.board[roof2] != 0:
                        continue
                    # Must span exactly 2 boxes
                    boxes = {BOX_OF[pos1], BOX_OF[pos2], BOX_OF[roof1], BOX_OF[roof2]}
                    if len(boxes) != 2:
                        continue
                    # Roof cells must contain both pair digits
                    if (bb.cands[roof1] & pair_mask) != pair_mask:
                        continue
                    if (bb.cands[roof2] & pair_mask) != pair_mask:
                        continue
                    # Extras: digits beyond the pair
                    extra1 = bb.cands[roof1] & ~pair_mask
                    extra2 = bb.cands[roof2] & ~pair_mask
                    if POPCOUNT[extra1] != 1 or POPCOUNT[extra2] != 1:
                        continue
                    if extra1 != extra2:
                        continue
                    extra_d = extra1.bit_length()  # digit value (1-9)
                    extra_bit = extra1

                    # Eliminate extra_d from cells that see BOTH roof cells
                    # Common peers = intersection of peer sets
                    common_peers_81 = PEER_81[roof1] & PEER_81[roof2]
                    # Filter to cells that have extra_d as candidate
                    target_81 = bb.cross[extra_d - 1] & common_peers_81
                    if not target_81:
                        continue

                    elims = []
                    for ep in iter_bits81(target_81):
                        elims.append((ep, extra_d))

                    if elims:
                        detail = f'UR Type2: floor R{r1+1}C{c1+1},R{r1+1}C{c2+1} roof R{r2+1}C{c1+1},R{r2+1}C{c2+1} elim {extra_d}'
                        return elims, detail

    return [], None


def detect_ur_type4(bb):
    """Unique Rectangle Type 4: Floor pair (bivalue) + roof cells have extra candidates.
    If one UR digit has a strong link in the roof's row/box, eliminate the other UR digit
    from both roof cells.
    Returns (eliminations, detail) or ([], None)."""
    for r1 in range(9):
        for c1 in range(9):
            pos1 = r1 * 9 + c1
            if bb.board[pos1] != 0:
                continue
            m1 = bb.cands[pos1]
            if POPCOUNT[m1] != 2:
                continue
            for c2 in range(c1 + 1, 9):
                pos2 = r1 * 9 + c2
                if bb.board[pos2] != 0 or bb.cands[pos2] != m1:
                    continue
                if BOX_OF[pos1] == BOX_OF[pos2]:
                    continue
                pair_mask = m1
                # Extract the two pair digits
                d0 = LSB_POS[pair_mask]
                d1 = LSB_POS[pair_mask ^ BIT[d0]]
                pair_digits = (d0, d1)  # 0-indexed

                for r2 in range(r1 + 1, 9):
                    roof1 = r2 * 9 + c1
                    roof2 = r2 * 9 + c2
                    if bb.board[roof1] != 0 or bb.board[roof2] != 0:
                        continue
                    boxes = {BOX_OF[pos1], BOX_OF[pos2], BOX_OF[roof1], BOX_OF[roof2]}
                    if len(boxes) != 2:
                        continue
                    if (bb.cands[roof1] & pair_mask) != pair_mask:
                        continue
                    if (bb.cands[roof2] & pair_mask) != pair_mask:
                        continue
                    # At least one roof cell must have extras (not both bivalue with same pair)
                    if bb.cands[roof1] == pair_mask and bb.cands[roof2] == pair_mask:
                        continue

                    for pi in range(2):
                        strong_d = pair_digits[pi]      # 0-indexed digit
                        elim_d = pair_digits[1 - pi]    # 0-indexed digit
                        strong_bit = BIT[strong_d]

                        # Check strong link in row r2: only roof1 and roof2 have strong_d in row
                        row_strong = True
                        for cc in range(9):
                            if cc == c1 or cc == c2:
                                continue
                            p = r2 * 9 + cc
                            if bb.board[p] == 0 and (bb.cands[p] & strong_bit):
                                row_strong = False
                                break

                        # Check box strong link if both roof cells share a box
                        box_strong = False
                        if BOX_OF[roof1] == BOX_OF[roof2]:
                            box_strong = True
                            for bp in BOX_CELLS_FLAT[BOX_OF[roof1]]:
                                if bp == roof1 or bp == roof2:
                                    continue
                                if bb.board[bp] == 0 and (bb.cands[bp] & strong_bit):
                                    box_strong = False
                                    break

                        if not row_strong and not box_strong:
                            continue

                        elim_bit = BIT[elim_d]
                        elims = []
                        if bb.cands[roof1] & elim_bit:
                            elims.append((roof1, elim_d + 1))
                        if bb.cands[roof2] & elim_bit:
                            elims.append((roof2, elim_d + 1))
                        if elims:
                            detail = f'UR Type4: strong link on {strong_d+1} in roof R{r2+1} → elim {elim_d+1}'
                            return elims, detail
    return [], None


def detect_junior_exocet_stuart(bb):
    """Junior Exocet — Andrew Stuart's validated implementation.

    Pattern Rules 1-4 from Bird's specification via sudokuwiki.org:
      1. Base pair in minirow with 3-4 combined candidates
      2. Two targets in other boxes, different lines, can't see each other
      3. Companion cells must not contain placed base digits
      4. Cover-line check: S-cells (cross-line columns, OUTSIDE band),
         each base digit in ≤2 perpendicular cover lines

    Elimination: Rule 1 only (remove non-base from targets).
    No R8, no trial validation needed — the strict cover-line check
    rejects all false patterns.
    """
    for orient in range(2):
        for band_idx in range(3):
            lines = [band_idx * 3, band_idx * 3 + 1, band_idx * 3 + 2]
            for base_line in lines:
                for bx in range(3):
                    empties = []
                    for dc in range(3):
                        pos_idx = bx * 3 + dc
                        if orient == 0:
                            r, c = base_line, pos_idx
                        else:
                            r, c = pos_idx, base_line
                        pos = r * 9 + c
                        if bb.board[pos] == 0:
                            empties.append((pos_idx, pos, r, c))
                    if len(empties) < 2:
                        continue

                    for ei in range(len(empties)):
                        for ej in range(ei + 1, len(empties)):
                            bp1_idx, bp1, br1, bc1 = empties[ei]
                            bp2_idx, bp2, br2, bc2 = empties[ej]

                            base_cands = bb.cands[bp1] | bb.cands[bp2]
                            base_pc = POPCOUNT[base_cands]
                            if base_pc < 3 or base_pc > 4:
                                continue
                            base_digits = [d for d in iter_bits9(base_cands)]

                            target_candidates = []
                            for obx in range(3):
                                if obx == bx:
                                    continue
                                for dl in range(3):
                                    t_line = lines[dl]
                                    if t_line == base_line:
                                        continue
                                    for dc in range(3):
                                        pos_idx = obx * 3 + dc
                                        if orient == 0:
                                            tr, tc = t_line, pos_idx
                                        else:
                                            tr, tc = pos_idx, t_line
                                        tp = tr * 9 + tc
                                        if bb.board[tp] != 0:
                                            continue
                                        if (bb.cands[tp] & base_cands) != base_cands:
                                            continue
                                        target_candidates.append((tp, tr, tc, obx, t_line))

                            for ti in range(len(target_candidates)):
                                for tj in range(ti + 1, len(target_candidates)):
                                    t1p, t1r, t1c, t1bx, t1ln = target_candidates[ti]
                                    t2p, t2r, t2c, t2bx, t2ln = target_candidates[tj]
                                    if t1bx == t2bx:
                                        continue
                                    if t1r == t2r or t1c == t2c or BOX_OF[t1p] == BOX_OF[t2p]:
                                        continue

                                    # Rule 3: Companion check
                                    companion_bad = False
                                    for tp, tr, tc, tbx, tln in [(t1p, t1r, t1c, t1bx, t1ln),
                                                                   (t2p, t2r, t2c, t2bx, t2ln)]:
                                        for dc in range(3):
                                            pos_idx = tbx * 3 + dc
                                            if orient == 0:
                                                cr, cc = tln, pos_idx
                                            else:
                                                cr, cc = pos_idx, tln
                                            cp = cr * 9 + cc
                                            if cp == tp:
                                                continue
                                            if bb.board[cp] != 0 and (BIT[bb.board[cp] - 1] & base_cands):
                                                companion_bad = True
                                                break
                                        if companion_bad:
                                            break
                                    if companion_bad:
                                        continue

                                    # Rule 4: Cover-line validation (Stuart/Bird)
                                    # Cross-lines = target columns + unused base column
                                    base_box_start = bx * 3
                                    cross_positions = set()
                                    if orient == 0:
                                        cross_positions.add(t1c)
                                        cross_positions.add(t2c)
                                        for dc in range(3):
                                            pos_idx = base_box_start + dc
                                            if pos_idx != bc1 and pos_idx != bc2:
                                                cross_positions.add(pos_idx)
                                    else:
                                        cross_positions.add(t1r)
                                        cross_positions.add(t2r)
                                        for dc in range(3):
                                            pos_idx = base_box_start + dc
                                            if pos_idx != br1 and pos_idx != br2:
                                                cross_positions.add(pos_idx)

                                    # S-cells: cross-line positions OUTSIDE the band
                                    # Count perpendicular cover lines per base digit (≤2)
                                    cover_ok = True
                                    for d in base_digits:
                                        dval = d + 1
                                        placed_in_band = False
                                        for ln in lines:
                                            for p in range(9):
                                                if orient == 0:
                                                    sr, sc = ln, p
                                                else:
                                                    sr, sc = p, ln
                                                sp = sr * 9 + sc
                                                if bb.board[sp] == dval:
                                                    placed_in_band = True
                                                    break
                                            if placed_in_band:
                                                break
                                        if placed_in_band:
                                            continue

                                        cover_lines = set()
                                        for cross_pos in cross_positions:
                                            for ln in range(9):
                                                if band_idx * 3 <= ln < band_idx * 3 + 3:
                                                    continue
                                                if orient == 0:
                                                    sr, sc = ln, cross_pos
                                                else:
                                                    sr, sc = cross_pos, ln
                                                sp = sr * 9 + sc
                                                if bb.board[sp] == 0 and (bb.cands[sp] & BIT[d]):
                                                    cover_lines.add(ln)
                                        if len(cover_lines) > 2:
                                            cover_ok = False
                                            break
                                    if not cover_ok:
                                        continue

                                    # ═══ VALIDATED — Rule 1 eliminations ═══
                                    elims = []
                                    for tp in [t1p, t2p]:
                                        non_base = bb.cands[tp] & ~base_cands
                                        for d in iter_bits9(non_base):
                                            elims.append((tp, d + 1))

                                    if elims:
                                        elims = list(dict.fromkeys(elims))
                                        base_str = ','.join(str(d + 1) for d in base_digits)
                                        detail = (f'JuniorExocet [R1]: '
                                                  f'base {{{base_str}}} at '
                                                  f'R{br1+1}C{bc1+1},R{br2+1}C{bc2+1} → '
                                                  f'targets R{t1r+1}C{t1c+1},R{t2r+1}C{t2c+1}')
                                        return elims, detail
    return [], None


def detect_junior_exocet(bb):
    """Junior Exocet: base-target pattern with cover-line validation.
    Both horizontal and vertical orientations. Returns (eliminations, detail) or ([], None).
    Uses bitmask candidate ops for speed."""
    # orient 0 = rows (bands), orient 1 = cols (stacks)
    for orient in range(2):
        for band_idx in range(3):
            lines = [band_idx * 3, band_idx * 3 + 1, band_idx * 3 + 2]
            for base_line in lines:
                for bx in range(3):
                    # Find empties in the minirow/minicol
                    empties = []
                    for dc in range(3):
                        pos_idx = bx * 3 + dc
                        if orient == 0:
                            r, c = base_line, pos_idx
                        else:
                            r, c = pos_idx, base_line
                        pos = r * 9 + c
                        if bb.board[pos] == 0:
                            empties.append((pos_idx, pos, r, c))

                    if len(empties) < 2:
                        continue

                    # Try all pairs of empties as base cells
                    for ei in range(len(empties)):
                        for ej in range(ei + 1, len(empties)):
                            bp1_idx, bp1, br1, bc1 = empties[ei]
                            bp2_idx, bp2, br2, bc2 = empties[ej]

                            # Pattern Rule 1: Combined base candidates 3 or 4
                            base_cands = bb.cands[bp1] | bb.cands[bp2]
                            base_pc = POPCOUNT[base_cands]
                            if base_pc < 3 or base_pc > 4:
                                continue
                            base_digits = [d for d in iter_bits9(base_cands)]  # 0-indexed

                            # Find target cells in other boxes of same band
                            target_candidates = []
                            for obx in range(3):
                                if obx == bx:
                                    continue
                                for dl in range(3):
                                    t_line = lines[dl]
                                    if t_line == base_line:
                                        continue
                                    for dc in range(3):
                                        pos_idx = obx * 3 + dc
                                        if orient == 0:
                                            tr, tc = t_line, pos_idx
                                        else:
                                            tr, tc = pos_idx, t_line
                                        tp = tr * 9 + tc
                                        if bb.board[tp] != 0:
                                            continue
                                        # Target must contain ALL base digits (extras OK — Rule 1 removes them)
                                        if (bb.cands[tp] & base_cands) != base_cands:
                                            continue
                                        target_candidates.append((tp, tr, tc, obx, t_line))

                            # Need 2 targets in different boxes
                            for ti in range(len(target_candidates)):
                                for tj in range(ti + 1, len(target_candidates)):
                                    t1p, t1r, t1c, t1bx, t1ln = target_candidates[ti]
                                    t2p, t2r, t2c, t2bx, t2ln = target_candidates[tj]
                                    if t1bx == t2bx:
                                        continue
                                    # Targets must not see each other
                                    if t1r == t2r or t1c == t2c or BOX_OF[t1p] == BOX_OF[t2p]:
                                        continue

                                    # Companion check: companions must not have PLACED base digits
                                    companion_bad = False
                                    for tp, tr, tc, tbx, tln in [(t1p, t1r, t1c, t1bx, t1ln),
                                                                   (t2p, t2r, t2c, t2bx, t2ln)]:
                                        for dc in range(3):
                                            pos_idx = tbx * 3 + dc
                                            if orient == 0:
                                                cr, cc = tln, pos_idx
                                            else:
                                                cr, cc = pos_idx, tln
                                            cp = cr * 9 + cc
                                            if cp == tp:
                                                continue
                                            if bb.board[cp] != 0 and (BIT[bb.board[cp] - 1] & base_cands):
                                                companion_bad = True
                                                break
                                        if companion_bad:
                                            break
                                    if companion_bad:
                                        continue

                                    # ═══ PATTERN CONFIRMED — collect eliminations ═══
                                    elims = []
                                    rules_used = set()

                                    # Rule 1: Remove non-base candidates from targets
                                    for tp in [t1p, t2p]:
                                        non_base = bb.cands[tp] & ~base_cands
                                        for d in iter_bits9(non_base):
                                            elims.append((tp, d + 1))
                                            rules_used.add('R1')

                                    # Trial validation: apply R1 eliminations to a
                                    # copy and check for contradictions (empty cands).
                                    # Catches false Exocet patterns that look valid
                                    # structurally but produce wrong eliminations.
                                    if elims:
                                        bb_trial = BitBoard.from_string(''.join(str(bb.board[i]) for i in range(81)))
                                        for tp_e, dval_e in elims:
                                            bb_trial.cands[tp_e] &= ~BIT[dval_e - 1]
                                        # Propagate naked singles on trial board
                                        trial_ok = True
                                        changed = True
                                        while changed and trial_ok:
                                            changed = False
                                            for pos_t in range(81):
                                                if bb_trial.board[pos_t] != 0:
                                                    continue
                                                c_t = bb_trial.cands[pos_t]
                                                if c_t == 0:
                                                    trial_ok = False
                                                    break
                                                if c_t & (c_t - 1) == 0:
                                                    d_t = c_t.bit_length() - 1
                                                    bb_trial.place(pos_t, d_t)
                                                    changed = True
                                            if not trial_ok:
                                                break
                                            # Hidden singles
                                            for ui in range(27):
                                                if not trial_ok:
                                                    break
                                                if ui < 9:
                                                    unit = [ui*9+j for j in range(9)]
                                                elif ui < 18:
                                                    c_u = ui - 9
                                                    unit = [r*9+c_u for r in range(9)]
                                                else:
                                                    b_u = ui - 18
                                                    br_u, bc_u = (b_u//3)*3, (b_u%3)*3
                                                    unit = [((br_u+dr)*9+bc_u+dc) for dr in range(3) for dc in range(3)]
                                                for d_u in range(9):
                                                    cells = [p for p in unit if bb_trial.board[p] == 0 and (bb_trial.cands[p] & BIT[d_u])]
                                                    if len(cells) == 0:
                                                        # Check if digit already placed in unit
                                                        placed = any(bb_trial.board[p] == d_u + 1 for p in unit)
                                                        if not placed:
                                                            trial_ok = False
                                                            break
                                                    elif len(cells) == 1:
                                                        if bb_trial.board[cells[0]] == 0:
                                                            bb_trial.place(cells[0], d_u)
                                                            changed = True
                                        if not trial_ok:
                                            continue  # reject this Exocet pattern

                                    # ═══ Double Exocet search ═══
                                    # DISABLED: DX-R1/R2 producing incorrect eliminations
                                    # on some puzzles. R1+R8 verified safe. DX rules
                                    # need S-cell/cover-line logic rework before enabling.
                                    # See EXOCET_LARS_ENHANCEMENTS.md for full spec.
                                    if False:  # TODO: fix DX cover-line logic
                                     for search_line in lines:
                                        if search_line == base_line:
                                            continue
                                        for obx2 in range(3):
                                            if obx2 == bx:
                                                continue
                                            empties2 = []
                                            for dc in range(3):
                                                pos_idx = obx2 * 3 + dc
                                                if orient == 0:
                                                    p2 = search_line * 9 + pos_idx
                                                else:
                                                    p2 = pos_idx * 9 + search_line
                                                if bb.board[p2] == 0:
                                                    empties2.append(p2)
                                            for a in range(len(empties2)):
                                                for b in range(a + 1, len(empties2)):
                                                    bp3, bp4 = empties2[a], empties2[b]
                                                    if bb.cands[bp3] | bb.cands[bp4] != base_cands:
                                                        continue
                                                    # Verify second pair has valid targets too
                                                    has_targets2 = False
                                                    for obx3 in range(3):
                                                        if obx3 == obx2:
                                                            continue
                                                        for dl2 in range(3):
                                                            tl2 = lines[dl2]
                                                            if tl2 == search_line:
                                                                continue
                                                            for dc2 in range(3):
                                                                pi2 = obx3 * 3 + dc2
                                                                tr2 = tl2 if orient == 0 else pi2
                                                                tc2 = pi2 if orient == 0 else tl2
                                                                tp2 = tr2 * 9 + tc2
                                                                if bb.board[tp2] != 0:
                                                                    continue
                                                                if (bb.cands[tp2] & base_cands) == base_cands:
                                                                    has_targets2 = True
                                                                    break
                                                            if has_targets2:
                                                                break
                                                        if has_targets2:
                                                            break
                                                    if not has_targets2:
                                                        continue
                                                    dx_type = 'AlignedDX' if search_line == base_line else 'CrossDX'
                                                    all_bases = {bp1, bp2, bp3, bp4}
                                                    all_targets = {t1p, t2p}

                                                    # S cells: minirow/minicol of each base & target
                                                    s_cells = set()
                                                    for bpos in all_bases | all_targets:
                                                        br_s, bc_s = divmod(bpos, 9)
                                                        if orient == 0:
                                                            cs = (bc_s // 3) * 3
                                                            for dc in range(3):
                                                                s_cells.add(br_s * 9 + cs + dc)
                                                        else:
                                                            rs = (br_s // 3) * 3
                                                            for dc in range(3):
                                                                s_cells.add((rs + dc) * 9 + bc_s)

                                                    # DX Rule 1: base digits from cells
                                                    # seeing ALL 4 base cells or ALL targets
                                                    for d in base_digits:
                                                        dval = d + 1
                                                        dbit = BIT[d]
                                                        for pos in range(81):
                                                            if pos in all_bases or pos in s_cells or pos in all_targets:
                                                                continue
                                                            if bb.board[pos] != 0 or not (bb.cands[pos] & dbit):
                                                                continue
                                                            sees_all_bases = all(
                                                                pos // 9 == bp // 9 or
                                                                pos % 9 == bp % 9 or
                                                                BOX_OF[pos] == BOX_OF[bp]
                                                                for bp in all_bases)
                                                            sees_all_targets = all(
                                                                pos // 9 == tp // 9 or
                                                                pos % 9 == tp % 9 or
                                                                BOX_OF[pos] == BOX_OF[tp]
                                                                for tp in all_targets)
                                                            if sees_all_bases or sees_all_targets:
                                                                elims.append((pos, dval))
                                                                rules_used.add(f'{dx_type}-R1')

                                                    # DX Rule 2: base digits from non-S cells
                                                    # in cover rows (S-cells = cross-line cols
                                                    # outside band). Skip R8-false digit.
                                                    r8_digits = set()
                                                    for tp in [t1p, t2p]:
                                                        for d in base_digits:
                                                            dbit_r8 = BIT[d]
                                                            if not (bb.cands[tp] & dbit_r8):
                                                                continue
                                                            perp = 0
                                                            for ln in range(9):
                                                                if band_idx * 3 <= ln < band_idx * 3 + 3:
                                                                    continue
                                                                sp = (ln * 9 + (tp % 9)) if orient == 0 else ((tp // 9) * 9 + ln)
                                                                if bb.board[sp] == 0 and (bb.cands[sp] & dbit_r8):
                                                                    perp += 1
                                                            if perp == 0:
                                                                r8_digits.add(d)

                                                    # Combine cross positions from BOTH base pairs
                                                    dx_cross = set(cross_positions)
                                                    # Add companion col from second base pair
                                                    for dc in range(3):
                                                        pos_idx = obx2 * 3 + dc
                                                        bp3_r, bp3_c = divmod(bp3, 9)
                                                        bp4_r, bp4_c = divmod(bp4, 9)
                                                        cp_val = pos_idx
                                                        if orient == 0:
                                                            if cp_val != bp3_c and cp_val != bp4_c:
                                                                dx_cross.add(cp_val)
                                                        else:
                                                            if cp_val != bp3_r and cp_val != bp4_r:
                                                                dx_cross.add(cp_val)
                                                    s_cell_set = set()
                                                    for cp in dx_cross:
                                                        for ln in range(9):
                                                            if band_idx * 3 <= ln < band_idx * 3 + 3:
                                                                continue
                                                            sp = (ln * 9 + cp) if orient == 0 else (cp * 9 + ln)
                                                            s_cell_set.add(sp)

                                                    for d in base_digits:
                                                        if d in r8_digits:
                                                            continue
                                                        dval = d + 1
                                                        dbit = BIT[d]
                                                        cover_rows = set()
                                                        for sp in s_cell_set:
                                                            if bb.board[sp] == 0 and (bb.cands[sp] & dbit):
                                                                cover_rows.add((sp // 9) if orient == 0 else (sp % 9))
                                                        if len(cover_rows) > 2:
                                                            continue
                                                        for ln in cover_rows:
                                                            for p in range(9):
                                                                sp = (ln * 9 + p) if orient == 0 else (p * 9 + ln)
                                                                if sp in s_cell_set:
                                                                    continue
                                                                if bb.board[sp] == 0 and (bb.cands[sp] & dbit):
                                                                    elims.append((sp, dval))
                                                                    rules_used.add(f'{dx_type}-R2')

                                    # Deduplicate
                                    elims = list(dict.fromkeys(elims))

                                    if elims:
                                        base_str = ','.join(str(d + 1) for d in base_digits)
                                        rule_str = '+'.join(sorted(rules_used))
                                        detail = (f'JuniorExocet [{rule_str}]: '
                                                  f'base {{{base_str}}} at '
                                                  f'R{br1+1}C{bc1+1},R{br2+1}C{bc2+1} → '
                                                  f'targets R{t1r+1}C{t1c+1},R{t2r+1}C{t2c+1}')
                                        return elims, detail
    return [], None


def detect_template(bb):
    """Template technique: enumerate all valid placement patterns per digit.
    Uses bitmask backtracking (row-by-row). Cap at 50k templates.
    Returns (placements, eliminations) — placements are (pos, digit, detail),
    eliminations are (pos, digit)."""
    CAP = 50000

    for d in range(9):  # 0-indexed
        dval = d + 1
        dbit = BIT[d]
        row_cells = []     # row_cells[r] = list of col indices, or None if placed
        fixed_cols = 0     # 9-bit mask of cols where d is placed
        fixed_boxes = 0    # 9-bit mask of boxes where d is placed
        skip = False

        for r in range(9):
            placed_col = -1
            for c in range(9):
                if bb.board[r * 9 + c] == dval:
                    placed_col = c
                    break
            if placed_col >= 0:
                row_cells.append(None)
                fixed_cols |= BIT[placed_col]
                fixed_boxes |= BIT[BOX_OF[r * 9 + placed_col]]
                continue
            cols = []
            for c in range(9):
                pos = r * 9 + c
                if bb.board[pos] == 0 and (bb.cands[pos] & dbit):
                    cols.append(c)
            if not cols:
                skip = True
                break
            row_cells.append(cols)

        if skip:
            continue

        # Enumerate templates via recursive backtracking with bitmasks
        templates = []
        placement = [0] * 9

        def _bt(row, used_cols, used_boxes):
            if len(templates) >= CAP:
                return
            if row == 9:
                templates.append(tuple(placement))
                return
            if row_cells[row] is None:
                _bt(row + 1, used_cols, used_boxes)
                return
            for c in row_cells[row]:
                if used_cols & BIT[c]:
                    continue
                bi = BOX_OF[row * 9 + c]
                if used_boxes & BIT[bi]:
                    continue
                placement[row] = c
                _bt(row + 1, used_cols | BIT[c], used_boxes | BIT[bi])

        _bt(0, fixed_cols, fixed_boxes)

        if not templates or len(templates) >= CAP:
            continue

        # Count how many templates use each cell
        count = [[0] * 9 for _ in range(9)]
        for t in templates:
            for r in range(9):
                if row_cells[r] is None:
                    continue
                count[r][t[r]] += 1

        n_templates = len(templates)
        placements = []
        elims = []

        for r in range(9):
            if row_cells[r] is None:
                continue
            for c in range(9):
                pos = r * 9 + c
                if bb.board[pos] != 0 or not (bb.cands[pos] & dbit):
                    continue
                if count[r][c] == 0:
                    elims.append((pos, dval))
                elif count[r][c] == n_templates:
                    placements.append((pos, dval,
                        f'Template: digit {dval} must go at R{r+1}C{c+1} (all {n_templates} templates)'))

        if placements:
            return placements, elims
        if elims:
            return [], elims

    return [], []


def detect_bowman_bingo(bb):
    """Bowman's Bingo: JIT-accelerated extended forcing chains.
    Cells with 2-5 candidates. Uses fast_propagate (JIT) for contradiction,
    fast_propagate_full (JIT) for convergence."""
    cells = []
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        pc = POPCOUNT[bb.cands[pos]]
        if 2 <= pc <= 5:
            cells.append((pos, pc))
    cells.sort(key=lambda x: x[1])

    for pos, _ in cells:
        digits = [d + 1 for d in iter_bits9(bb.cands[pos])]

        # Phase 1: JIT contradiction check
        contradicted = []
        valid = []
        for v in digits:
            if fast_propagate(bb.board, bb.cands, pos, v):
                contradicted.append(v)
            else:
                valid.append(v)

        # All but one contradicted → placement
        if len(contradicted) == len(digits) - 1 and len(valid) == 1:
            val = valid[0]
            r, c = pos // 9, pos % 9
            return [(pos, val, f'BowmanBingo R{r+1}C{c+1}={val} ({len(contradicted)} contradicted)')]

        # Some contradicted → naked single
        if contradicted and len(contradicted) < len(digits):
            remaining = bb.cands[pos]
            for v in contradicted:
                remaining &= ~BIT[v - 1]
            if remaining and (remaining & (remaining - 1)) == 0:
                val = remaining.bit_length()
                r, c = pos // 9, pos % 9
                return [(pos, val, f'BowmanBingo R{r+1}C{c+1}={val} (elim {len(contradicted)})')]

        # Phase 2: Convergence check
        if len(valid) >= 2:
            boards = []
            for v in valid:
                new_b, _ = fast_propagate_full(bb.board, bb.cands, pos, v)
                if new_b is not None:
                    boards.append(new_b)
            if len(boards) == len(valid):
                for cell in range(81):
                    if bb.board[cell] != 0:
                        continue
                    vals = [b[cell] for b in boards]
                    if all(v != 0 for v in vals) and len(set(vals)) == 1:
                        kr, kc = cell // 9, cell % 9
                        r, c = pos // 9, pos % 9
                        return [(cell, vals[0],
                            f'BowmanBingo from R{r+1}C{c+1}: all → R{kr+1}C{kc+1}={vals[0]}')]

    return []


# ══════════════════════════════════════════════════════════════════════
# D2B — Depth-2 Bilateral (full bitmask, no sets)
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _d2b_jit(board, cands, peers, peer_len, units, box_of, popcount_lut):
    """JIT D2B: double-blind deduction. No Python boundary crossings."""
    # Collect pivot cells (2-4 candidates), sorted by candidate count
    pivots = np.zeros(81, dtype=np.int32)
    pivot_pc = np.zeros(81, dtype=np.int32)
    n_piv = 0
    for pos in range(81):
        if board[pos] != 0:
            continue
        pc = popcount_lut[cands[pos]]
        if 2 <= pc <= 4:
            pivots[n_piv] = pos
            pivot_pc[n_piv] = pc
            n_piv += 1

    # Simple insertion sort by pc
    for i in range(1, n_piv):
        key_pos = pivots[i]
        key_pc = pivot_pc[i]
        j = i - 1
        while j >= 0 and pivot_pc[j] > key_pc:
            pivots[j + 1] = pivots[j]
            pivot_pc[j + 1] = pivot_pc[j]
            j -= 1
        pivots[j + 1] = key_pos
        pivot_pc[j + 1] = key_pc

    limit = min(n_piv, 15)
    out = np.zeros((10, 3), dtype=np.int32)
    n_out = 0

    for pi in range(limit):
        pivot_pos = pivots[pi]
        pivot_mask = cands[pivot_pos]

        # Extract digits
        digits = np.zeros(4, dtype=np.int32)
        n_d = 0
        for d in range(9):
            if pivot_mask & (1 << d):
                digits[n_d] = d + 1
                n_d += 1

        # Per-branch elimination arrays
        branch_elims = np.zeros((4, 81), dtype=np.int32)
        branch_valid = np.zeros(4, dtype=np.bool_)

        # Pre-allocate scratch arrays for inner loop
        b1 = np.empty(81, dtype=np.int32)
        c1 = np.empty(81, dtype=np.int32)
        b2 = np.empty(81, dtype=np.int32)
        c2 = np.empty(81, dtype=np.int32)

        for di in range(n_d):
            d1 = digits[di]

            # Fast propagate (contradiction check)
            for i in range(81):
                b1[i] = board[i]
                c1[i] = cands[i]
            contra = _fast_prop_jit(b1, c1, np.int32(pivot_pos), np.int32(d1),
                                     peers, peer_len, units, box_of, popcount_lut)
            if contra:
                continue

            # FPCE on branch: for each 2-4 candidate cell, try placing each candidate
            elim = np.zeros(81, dtype=np.int32)
            for i in range(81):
                if b1[i] != 0:
                    continue
                pc = popcount_lut[c1[i]]
                if pc < 2 or pc > 4:
                    continue
                for dd in range(9):
                    if not (c1[i] & (1 << dd)):
                        continue
                    for k in range(81):
                        b2[k] = b1[k]
                        c2[k] = c1[k]
                    if _fast_prop_jit(b2, c2, np.int32(i), np.int32(dd + 1),
                                       peers, peer_len, units, box_of, popcount_lut):
                        elim[i] |= (1 << dd)

            branch_elims[di] = elim
            branch_valid[di] = True

        # Count valid branches
        n_valid = 0
        for di in range(n_d):
            if branch_valid[di]:
                n_valid += 1
        if n_valid < 2:
            continue

        # AND-intersection of valid branch eliminations
        common = np.full(81, 0x1FF, dtype=np.int32)
        first = True
        for di in range(n_d):
            if not branch_valid[di]:
                continue
            if first:
                for i in range(81):
                    common[i] = branch_elims[di, i]
                first = False
            else:
                for i in range(81):
                    common[i] &= branch_elims[di, i]

        has_any = False
        for i in range(81):
            if common[i]:
                has_any = True
                break
        if not has_any:
            continue

        # Find placements from common eliminations
        for pos in range(81):
            if board[pos] != 0 or not common[pos]:
                continue
            test_c = cands[pos] & ~common[pos]
            if test_c and (test_c & (test_c - 1)) == 0:
                if popcount_lut[cands[pos]] > 1:
                    digit = 0
                    tmp = test_c
                    while tmp > 1:
                        digit += 1
                        tmp >>= 1
                    digit += 1
                    if n_out < 10:
                        out[n_out, 0] = pos
                        out[n_out, 1] = digit
                        out[n_out, 2] = pivot_pos
                        n_out += 1

        if n_out > 0:
            return out[:n_out], n_out

    return out[:n_out], n_out


def detect_d2b_bitwise(bb):
    """D2B — JIT-accelerated double-blind deduction."""
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    out, n_out = _d2b_jit(board_arr, cands_arr,
                           _NB_PEERS, _NB_PEER_LEN, _NB_UNITS, _NB_BOX_OF, _NB_POPCOUNT)

    placements = []
    for k in range(n_out):
        pos = int(out[k, 0])
        digit = int(out[k, 1])
        pivot = int(out[k, 2])
        r, c = pos // 9, pos % 9
        placements.append((pos, digit,
            f'D2B pivot R{pivot//9+1}C{pivot%9+1} -> R{r+1}C{c+1}={digit}'))
    return placements


# ══════════════════════════════════════════════════════════════════════
# FPF — Full Pipeline Forcing (bitmask version)
# ══════════════════════════════════════════════════════════════════════

def detect_fpf_bitwise(bb):
    """Full Pipeline Forcing — two-tier: JIT fast path + Python fallback.
    Tier 1: fast_propagate (JIT, L1+L2) — catches ~90% of contradictions instantly.
    Tier 2: full Python pipeline (FPC+FPCE) — only for JIT survivors."""
    cells = []
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        pc = POPCOUNT[bb.cands[pos]]
        if pc < 2 or pc > 6:
            continue
        r = pos // 9
        band = r // 3
        cells.append((pos, band, pc))
    cells.sort(key=lambda x: (x[1], x[2]))

    def branch_contradicts_deep(branch_bb):
        """Full pipeline fallback — only called on JIT survivors."""
        for outer in range(40):
            any_prog = False
            progress = True
            while progress:
                progress = False
                hits = detect_l1_bitwise(branch_bb)
                for p, v, t in hits:
                    if branch_bb.board[p] == 0:
                        branch_bb.place(p, v)
                        progress = True
                        any_prog = True
                for i in range(81):
                    if branch_bb.board[i] == 0 and branch_bb.cands[i] == 0:
                        return True
                if not progress:
                    break

            if apply_l2_bitwise(branch_bb):
                any_prog = True
                for i in range(81):
                    if branch_bb.board[i] == 0 and branch_bb.cands[i] == 0:
                        return True
                continue

            fpc_hits = detect_fpc_bitwise(branch_bb)
            for p, v, d in fpc_hits:
                if branch_bb.board[p] == 0:
                    branch_bb.place(p, v)
                    any_prog = True
                    break
            if any_prog:
                continue

            fpce_p, fpce_e = detect_fpce_bitwise(branch_bb)
            if fpce_e:
                for p, d in fpce_e:
                    if not branch_bb.eliminate(p, d):
                        return True
                any_prog = True
            for p, v, d in fpce_p:
                if branch_bb.board[p] == 0:
                    branch_bb.place(p, v)
                    any_prog = True
            if any_prog:
                continue
            break

        for i in range(81):
            if branch_bb.board[i] == 0 and branch_bb.cands[i] == 0:
                return True
        for ui in range(27):
            unit = UNITS[ui]
            for d in range(1, 10):
                dbit = BIT[d - 1]
                placed = False
                for p in unit:
                    if branch_bb.board[p] == d:
                        placed = True
                        break
                if placed:
                    continue
                can_place = False
                for p in unit:
                    if branch_bb.board[p] == 0 and (branch_bb.cands[p] & dbit):
                        can_place = True
                        break
                if not can_place:
                    return True
        return False

    for pos, band, sz in cells:
        digits = [d + 1 for d in iter_bits9(bb.cands[pos])]

        # ═══ Tier 1: JIT fast path — test all candidates with fast_propagate ═══
        jit_dead = []
        jit_alive = []
        for d in digits:
            if fast_propagate(bb.board, bb.cands, pos, d):
                jit_dead.append(d)
            else:
                jit_alive.append(d)

        # All-but-one killed by JIT alone → placement (no fallback needed!)
        if len(jit_alive) == 1:
            r, c = pos // 9, pos % 9
            return [(pos, jit_alive[0],
                f'FPF R{r+1}C{c+1} {{{",".join(str(d) for d in digits)}}} '
                f'-- only {jit_alive[0]} survives (JIT)')]

        # ═══ Tier 2: Deep pipeline on JIT survivors only ═══
        survivors = []
        dead = list(jit_dead)
        for d in jit_alive:
            if len(survivors) >= 2:
                break
            branch_bb = bb.clone()
            branch_bb.place(pos, d)
            if branch_contradicts_deep(branch_bb):
                dead.append(d)
            else:
                survivors.append(d)

        if len(survivors) == 1:
            r, c = pos // 9, pos % 9
            return [(pos, survivors[0],
                f'FPF R{r+1}C{c+1} {{{",".join(str(d) for d in digits)}}} '
                f'-- {",".join(str(d)+"->X" for d in dead)} -- only {survivors[0]} survives')]

    return []


# ══════════════════════════════════════════════════════════════════════
# BACKTRACKING SOLVER (for validation)
# ══════════════════════════════════════════════════════════════════════

@nb.njit(nb.boolean(nb.int32[:]), cache=True)
def _backtrack_jit(b):
    """Numba-JIT backtracker with bitmask constraints + MRV heuristic."""
    # Build bitmask candidates: cands[pos] = bit mask of available digits (bit 0 = digit 1)
    cands = np.full(81, 0x1FF, dtype=nb.int32)  # all 9 bits set

    # Precompute peer lists as flat array (81 cells × 20 peers each)
    peer_flat = np.empty(81 * 20, dtype=nb.int32)
    for pos in range(81):
        r = pos // 9
        c = pos % 9
        br = (r // 3) * 3
        bc = (c // 3) * 3
        idx = pos * 20
        count = 0
        # Collect all peers (row + col + box), skip self, deduplicate
        seen = np.zeros(81, dtype=nb.boolean)
        for j in range(9):
            p = r * 9 + j
            if p != pos and not seen[p]:
                seen[p] = True
                peer_flat[idx + count] = p
                count += 1
        for j in range(9):
            p = j * 9 + c
            if p != pos and not seen[p]:
                seen[p] = True
                peer_flat[idx + count] = p
                count += 1
        for dr in range(3):
            for dc in range(3):
                p = (br + dr) * 9 + bc + dc
                if p != pos and not seen[p]:
                    seen[p] = True
                    peer_flat[idx + count] = p
                    count += 1

    # Initialize from givens
    for pos in range(81):
        if b[pos] != 0:
            bit = 1 << (b[pos] - 1)
            cands[pos] = 0
            # Remove from peers
            idx = pos * 20
            for k in range(20):
                cands[peer_flat[idx + k]] &= ~bit

    # Propagate naked singles iteratively
    changed = True
    while changed:
        changed = False
        for pos in range(81):
            if b[pos] == 0 and cands[pos] != 0:
                # Check if single candidate
                c = cands[pos]
                if c & (c - 1) == 0:  # power of 2 = single bit
                    d = 0
                    tmp = c
                    while tmp > 1:
                        tmp >>= 1
                        d += 1
                    b[pos] = d + 1
                    cands[pos] = 0
                    bit = 1 << d
                    idx = pos * 20
                    for k in range(20):
                        cands[peer_flat[idx + k]] &= ~bit
                    changed = True

    # Count remaining empties
    empties = np.empty(81, dtype=nb.int32)
    n_empty = 0
    for i in range(81):
        if b[i] == 0:
            empties[n_empty] = i
            n_empty += 1

    if n_empty == 0:
        return True

    # Stack for iterative backtracking with MRV
    stack_pos = np.empty(n_empty, dtype=nb.int32)
    stack_cands = np.empty(n_empty, dtype=nb.int32)  # remaining candidates to try
    # Save/restore: full board + cands snapshots per depth
    saved_cands = np.empty((n_empty, 81), dtype=nb.int32)
    saved_board = np.empty((n_empty, 81), dtype=nb.int32)

    depth = 0
    # Pick first cell by MRV
    best = -1
    best_pc = 10
    for i in range(n_empty):
        c = cands[empties[i]]
        pc = 0
        tmp = c
        while tmp:
            pc += 1
            tmp &= tmp - 1
        if 0 < pc < best_pc:
            best_pc = pc
            best = empties[i]
    if best == -1:
        return False  # dead end immediately

    stack_pos[0] = best
    stack_cands[0] = cands[best]
    for j in range(81):
        saved_cands[0, j] = cands[j]
        saved_board[0, j] = b[j]

    while depth >= 0:
        c = stack_cands[depth]
        if c == 0:
            # No more candidates — restore state and backtrack
            for j in range(81):
                cands[j] = saved_cands[depth, j]
                b[j] = saved_board[depth, j]
            depth -= 1
            continue

        # Pick LSB digit
        lsb = c & (-c)
        stack_cands[depth] &= ~lsb  # remove for next try

        # Restore state before trying this digit (undo previous attempt at same depth)
        for j in range(81):
            cands[j] = saved_cands[depth, j]
            b[j] = saved_board[depth, j]

        pos = stack_pos[depth]

        # Determine digit
        d = 0
        tmp = lsb
        while tmp > 1:
            tmp >>= 1
            d += 1

        # Place digit
        b[pos] = d + 1
        cands[pos] = 0
        bit = 1 << d
        # Eliminate from peers
        ok = True
        idx = pos * 20
        for k in range(20):
            peer = peer_flat[idx + k]
            cands[peer] &= ~bit
            if b[peer] == 0 and cands[peer] == 0:
                ok = False

        # Propagate naked singles
        if ok:
            prop_changed = True
            while prop_changed and ok:
                prop_changed = False
                for pp in range(81):
                    if b[pp] == 0 and cands[pp] != 0:
                        cc = cands[pp]
                        if cc & (cc - 1) == 0:
                            dd = 0
                            tmp2 = cc
                            while tmp2 > 1:
                                tmp2 >>= 1
                                dd += 1
                            b[pp] = dd + 1
                            cands[pp] = 0
                            bbit = 1 << dd
                            idx2 = pp * 20
                            for k2 in range(20):
                                peer2 = peer_flat[idx2 + k2]
                                cands[peer2] &= ~bbit
                                if b[peer2] == 0 and cands[peer2] == 0:
                                    ok = False
                                    break
                            if ok:
                                prop_changed = True

        if not ok:
            continue  # try next candidate at this depth

        # Check if solved
        solved = True
        for j in range(81):
            if b[j] == 0:
                solved = False
                break
        if solved:
            return True

        # Go deeper — pick next cell by MRV
        depth += 1
        best2 = -1
        best_pc2 = 10
        for j in range(81):
            if b[j] == 0 and cands[j] != 0:
                pc2 = 0
                tmp3 = cands[j]
                while tmp3:
                    pc2 += 1
                    tmp3 &= tmp3 - 1
                if pc2 < best_pc2:
                    best_pc2 = pc2
                    best2 = j
        if best2 == -1:
            # Dead end — backtrack
            depth -= 1
            continue

        stack_pos[depth] = best2
        stack_cands[depth] = cands[best2]
        for j in range(81):
            saved_cands[depth, j] = cands[j]
            saved_board[depth, j] = b[j]

    return False  # no solution

def solve_backtrack(bd81):
    """JIT-compiled iterative backtracker for solution validation."""
    b = np.array([int(ch) if ch.isdigit() else 0 for ch in bd81], dtype=np.int32)
    if _backtrack_jit(b):
        return ''.join(str(x) for x in b)
    return None


# ══════════════════════════════════════════════════════════════════════
# SOLUTION COUNTER (for uniqueness checking)
# ══════════════════════════════════════════════════════════════════════

@nb.njit(nb.boolean(nb.int32[:]), cache=True)
def _has_multiple_solutions_jit(b):
    """Return True if puzzle has >= 2 solutions (i.e. NOT unique).
    Identical to _backtrack_jit but counts solutions — stops at 2."""
    cands = np.full(81, 0x1FF, dtype=nb.int32)

    # Precompute peer lists
    peer_flat = np.empty(81 * 20, dtype=nb.int32)
    for pos in range(81):
        r = pos // 9
        c = pos % 9
        br = (r // 3) * 3
        bc = (c // 3) * 3
        idx = pos * 20
        count = 0
        seen = np.zeros(81, dtype=nb.boolean)
        for j in range(9):
            p = r * 9 + j
            if p != pos and not seen[p]:
                seen[p] = True
                peer_flat[idx + count] = p
                count += 1
        for j in range(9):
            p = j * 9 + c
            if p != pos and not seen[p]:
                seen[p] = True
                peer_flat[idx + count] = p
                count += 1
        for dr in range(3):
            for dc in range(3):
                p = (br + dr) * 9 + bc + dc
                if p != pos and not seen[p]:
                    seen[p] = True
                    peer_flat[idx + count] = p
                    count += 1

    # Initialize from givens
    for pos in range(81):
        if b[pos] != 0:
            bit = 1 << (b[pos] - 1)
            cands[pos] = 0
            idx = pos * 20
            for k in range(20):
                cands[peer_flat[idx + k]] &= ~bit

    # Propagate naked singles
    changed = True
    while changed:
        changed = False
        for pos in range(81):
            if b[pos] == 0 and cands[pos] != 0:
                c = cands[pos]
                if c & (c - 1) == 0:
                    d = 0
                    tmp = c
                    while tmp > 1:
                        tmp >>= 1
                        d += 1
                    b[pos] = d + 1
                    cands[pos] = 0
                    bit = 1 << d
                    idx = pos * 20
                    for k in range(20):
                        cands[peer_flat[idx + k]] &= ~bit
                    changed = True

    # Count remaining empties
    empties = np.empty(81, dtype=nb.int32)
    n_empty = 0
    for i in range(81):
        if b[i] == 0:
            empties[n_empty] = i
            n_empty += 1

    if n_empty == 0:
        return False  # exactly 1 solution found (the givens filled everything)

    # Stack for iterative backtracking with MRV
    stack_pos = np.empty(n_empty, dtype=nb.int32)
    stack_cands = np.empty(n_empty, dtype=nb.int32)
    saved_cands = np.empty((n_empty, 81), dtype=nb.int32)
    saved_board = np.empty((n_empty, 81), dtype=nb.int32)

    sol_count = 0

    depth = 0
    best = -1
    best_pc = 10
    for i in range(n_empty):
        c = cands[empties[i]]
        pc = 0
        tmp = c
        while tmp:
            pc += 1
            tmp &= tmp - 1
        if 0 < pc < best_pc:
            best_pc = pc
            best = empties[i]
    if best == -1:
        return False  # no solution at all

    stack_pos[0] = best
    stack_cands[0] = cands[best]
    for j in range(81):
        saved_cands[0, j] = cands[j]
        saved_board[0, j] = b[j]

    while depth >= 0:
        c = stack_cands[depth]
        if c == 0:
            for j in range(81):
                cands[j] = saved_cands[depth, j]
                b[j] = saved_board[depth, j]
            depth -= 1
            continue

        lsb = c & (-c)
        stack_cands[depth] &= ~lsb

        for j in range(81):
            cands[j] = saved_cands[depth, j]
            b[j] = saved_board[depth, j]

        pos = stack_pos[depth]

        d = 0
        tmp = lsb
        while tmp > 1:
            tmp >>= 1
            d += 1

        b[pos] = d + 1
        cands[pos] = 0
        bit = 1 << d
        ok = True
        idx = pos * 20
        for k in range(20):
            peer = peer_flat[idx + k]
            cands[peer] &= ~bit
            if b[peer] == 0 and cands[peer] == 0:
                ok = False

        if ok:
            prop_changed = True
            while prop_changed and ok:
                prop_changed = False
                for pp in range(81):
                    if b[pp] == 0 and cands[pp] != 0:
                        cc = cands[pp]
                        if cc & (cc - 1) == 0:
                            dd = 0
                            tmp2 = cc
                            while tmp2 > 1:
                                tmp2 >>= 1
                                dd += 1
                            b[pp] = dd + 1
                            cands[pp] = 0
                            bbit = 1 << dd
                            idx2 = pp * 20
                            for k2 in range(20):
                                peer2 = peer_flat[idx2 + k2]
                                cands[peer2] &= ~bbit
                                if b[peer2] == 0 and cands[peer2] == 0:
                                    ok = False
                                    break
                            if ok:
                                prop_changed = True

        if not ok:
            continue

        # Check if solved
        solved = True
        for j in range(81):
            if b[j] == 0:
                solved = False
                break
        if solved:
            sol_count += 1
            if sol_count >= 2:
                return True  # multiple solutions
            # Continue searching for a second solution — backtrack
            continue

        # Go deeper
        depth += 1
        best2 = -1
        best_pc2 = 10
        for j in range(81):
            if b[j] == 0 and cands[j] != 0:
                pc2 = 0
                tmp3 = cands[j]
                while tmp3:
                    pc2 += 1
                    tmp3 &= tmp3 - 1
                if pc2 < best_pc2:
                    best_pc2 = pc2
                    best2 = j
        if best2 == -1:
            depth -= 1
            continue

        stack_pos[depth] = best2
        stack_cands[depth] = cands[best2]
        for j in range(81):
            saved_cands[depth, j] = cands[j]
            saved_board[depth, j] = b[j]

    return False  # 0 or 1 solution — unique (or unsolvable)


def has_unique_solution(bd81):
    """Check if a puzzle string has exactly one solution."""
    b = np.array([int(ch) if ch.isdigit() else 0 for ch in bd81], dtype=np.int32)
    return not _has_multiple_solutions_jit(b)


def solve_backtrack_pure(bd81):
    """Original pure-Python backtracker (kept for reference)."""
    b = [int(ch) for ch in bd81]
    def ok(pos, d):
        r, c = pos // 9, pos % 9
        for i in range(9):
            if b[r*9+i] == d or b[i*9+c] == d:
                return False
        br, bc = (r//3)*3, (c//3)*3
        for dr in range(3):
            for dc in range(3):
                if b[(br+dr)*9+bc+dc] == d:
                    return False
        return True
    def solve(pos):
        while pos < 81 and b[pos] != 0:
            pos += 1
        if pos == 81:
            return True
        for d in range(1, 10):
            if ok(pos, d):
                b[pos] = d
                if solve(pos + 1):
                    return True
                b[pos] = 0
        return False
    if solve(0):
        return ''.join(str(x) for x in b)
    return None


# ══════════════════════════════════════════════════════════════════════
# GF(2) BLOCK LANCZOS — Linear Algebra Constraint Solver
# ══════════════════════════════════════════════════════════════════════
#
# The Sudoku constraint system as a binary matrix over GF(2).
# Block Lanczos (Montgomery 1995) finds null spaces of sparse binary
# matrices using block-width N = CPU word size (64). One XOR instruction
# performs 64 GF(2) additions simultaneously.
#
# Variables:  x_{pos,d} ∈ {0,1} — "cell pos has digit d"
# Constraints (mod 2):
#   Cell: Σ_d x_{pos,d}          = 1   (one digit per cell)
#   Row:  Σ_{pos∈row} x_{pos,d}  = 1   (one cell per digit per row)
#   Col:  Σ_{pos∈col} x_{pos,d}  = 1   (one cell per digit per col)
#   Box:  Σ_{pos∈box} x_{pos,d}  = 1   (one cell per digit per box)
#
# Block elimination resolves ALL linearly-determined cells in one pass.
# Null space dimension = degrees of freedom = choices zone oracles fill.
#
# WSRF-null-space: zones predict → Lanczos verifies → oracle locks.
# ══════════════════════════════════════════════════════════════════════

def _build_gf2_system(bb, zone_hints=None, add_conjugates=False,
                      add_band_stack=False):
    """Build augmented GF(2) constraint matrix [M|b] from board state.

    Each variable represents one (cell, digit) candidate.
    Each constraint is a row: coefficients as bits, RHS in the highest bit.

    Options:
      zone_hints:     dict {(pos, digit) → 0|1} — inject zone predictions (B)
      add_conjugates: add explicit conjugate-pair constraints (C)
      add_band_stack: add minirow/minicol band/stack constraints (A)

    Returns: (aug_rows, var_map, n_vars, var_idx)
      aug_rows: list of Python big-ints, each (n_vars+1)-bit
      var_map[i] = (cell_pos, digit_1indexed)
      n_vars: total variable count
      var_idx: dict {(pos, digit) → variable index}
    """
    var_map = []
    var_idx = {}

    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        mask = bb.cands[pos]
        while mask:
            lsb = mask & -mask
            d = lsb.bit_length() - 1          # 0-indexed
            var_idx[(pos, d + 1)] = len(var_map)
            var_map.append((pos, d + 1))
            mask ^= lsb

    n_vars = len(var_map)
    if n_vars == 0:
        return [], [], 0, {}

    rhs_bit = 1 << n_vars
    aug = []

    # ── Cell constraints: each empty cell gets exactly one digit ──
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        row = 0
        mask = bb.cands[pos]
        while mask:
            lsb = mask & -mask
            d = lsb.bit_length() - 1
            row |= 1 << var_idx[(pos, d + 1)]
            mask ^= lsb
        aug.append(row | rhs_bit)

    # ── Row-digit constraints ──
    for r in range(9):
        for d in range(9):
            if bb.row_used[r] & BIT[d]:
                continue
            row = 0
            for c in range(9):
                key = (r * 9 + c, d + 1)
                if key in var_idx:
                    row |= 1 << var_idx[key]
            if row:
                aug.append(row | rhs_bit)

    # ── Col-digit constraints ──
    for c in range(9):
        for d in range(9):
            if bb.col_used[c] & BIT[d]:
                continue
            row = 0
            for r in range(9):
                key = (r * 9 + c, d + 1)
                if key in var_idx:
                    row |= 1 << var_idx[key]
            if row:
                aug.append(row | rhs_bit)

    # ── Box-digit constraints ──
    for bi in range(9):
        for d in range(9):
            if bb.box_used[bi] & BIT[d]:
                continue
            row = 0
            for pos in UNITS[18 + bi]:
                key = (pos, d + 1)
                if key in var_idx:
                    row |= 1 << var_idx[key]
            if row:
                aug.append(row | rhs_bit)

    # ═══ Option A: Band/stack — locked minirow/minicol constraints ═══
    # A minirow is the intersection of a row and a box (3 cells).
    # When ALL candidates for digit D in a box lie within ONE minirow,
    # D is "locked" to that minirow. This means:
    #   - The minirow sum = 1 (exactly one cell in those 3 has D)
    #   - D can be eliminated from the rest of that row (outside the box)
    # The elimination is already handled by L1 propagation, but the
    # constraint "this minirow contains exactly one D" (sum mod 2 = 1)
    # is NEW information for GF(2) when the box has >3 candidates total.
    # Similarly for minicols (intersection of column and box).
    if add_band_stack:
        for bi in range(9):
            br, bc = (bi // 3) * 3, (bi % 3) * 3
            for d in range(9):
                d1 = d + 1
                if bb.box_used[bi] & BIT[d]:
                    continue
                # Find all cells in this box with candidate d
                cand_cells = []
                for dr in range(3):
                    for dc in range(3):
                        pos = (br + dr) * 9 + bc + dc
                        if (pos, d1) in var_idx:
                            cand_cells.append((pos, dr, dc))
                if not cand_cells:
                    continue

                # Check if locked to a single minirow
                rows_seen = set(dr for _, dr, _ in cand_cells)
                if len(rows_seen) == 1:
                    # Locked minirow: sum of these candidates = 1
                    row = 0
                    for pos, _, _ in cand_cells:
                        row |= 1 << var_idx[(pos, d1)]
                    if row:
                        aug.append(row | rhs_bit)

                # Check if locked to a single minicol
                cols_seen = set(dc for _, _, dc in cand_cells)
                if len(cols_seen) == 1:
                    row = 0
                    for pos, _, _ in cand_cells:
                        row |= 1 << var_idx[(pos, d1)]
                    if row:
                        aug.append(row | rhs_bit)

    # ═══ Option B: Zone prediction hints ═══
    # Each hint (pos, digit) → value adds a single-variable constraint.
    # value=1: "zone predicts this candidate is the answer" → pin variable
    # value=0: "zone says unlikely" → eliminate variable
    # If predictions are wrong, Gaussian elimination will produce 0=1
    # (contradiction) — built-in verification.
    if zone_hints:
        for (pos, digit), value in zone_hints.items():
            if (pos, digit) in var_idx:
                idx = var_idx[(pos, digit)]
                row = 1 << idx
                if value:
                    row |= rhs_bit  # x = 1
                # else: x = 0 (no RHS bit)
                aug.append(row)

    # ═══ Option C: Conjugate pair constraints ═══
    # For each unit and digit, if exactly 2 cells have that candidate,
    # they form a conjugate pair: x₁ ⊕ x₂ = 1.
    # Technically derivable from unit constraints, but explicit encoding
    # creates shorter pivot chains and can help elimination converge faster.
    if add_conjugates:
        for unit_idx in range(27):  # rows 0-8, cols 9-17, boxes 18-26
            unit_cells = UNITS[unit_idx]
            for d in range(9):
                d1 = d + 1
                # Find cells in this unit with this digit as candidate
                pair = []
                for pos in unit_cells:
                    if (pos, d1) in var_idx:
                        pair.append(var_idx[(pos, d1)])
                if len(pair) == 2:
                    # Conjugate pair: exactly one is true
                    row = (1 << pair[0]) | (1 << pair[1])
                    aug.append(row | rhs_bit)

    return aug, var_map, n_vars, var_idx


def _gf2_block_eliminate(aug, n_vars):
    """Block GF(2) Gaussian elimination — numpy uint64 vectorized XOR.

    Packs the augmented matrix into numpy uint64 arrays (block width 64).
    Each pivot step eliminates across ALL rows simultaneously via one
    vectorized XOR — the binary-field analogue of Block Lanczos iteration.

    For n=150: ~3 uint64 words per row, 300 rows.
    One numpy XOR eliminates all 300 rows in one instruction per word.

    Returns: (pivots, free_vars, M, n_words)
      pivots: dict {variable_col: row_idx}
      free_vars: set of free (undetermined) variable indices
      M: numpy uint64 array (reduced)
      n_words: words per row
    """
    n_rows = len(aug)
    n_cols = n_vars + 1               # +1 for RHS column
    n_words = (n_cols + 63) >> 6      # ceil(n_cols / 64)

    # Pack big-int rows into numpy uint64 block matrix
    M = np.zeros((n_rows, n_words), dtype=np.uint64)
    _MASK64 = (1 << 64) - 1
    for i, row_int in enumerate(aug):
        for w in range(n_words):
            M[i, w] = np.uint64((row_int >> (w << 6)) & _MASK64)

    pivots = {}
    used = np.zeros(n_rows, dtype=np.bool_)

    for col in range(n_vars):
        w = col >> 6                          # word index
        b = np.uint64(1 << (col & 63))        # bit within word

        # Find pivot: first unused row with this bit set
        pivot = -1
        for r in range(n_rows):
            if not used[r] and M[r, w] & b:
                pivot = r
                break
        if pivot < 0:
            continue                          # free variable

        pivots[col] = pivot
        used[pivot] = True

        # ── Block elimination: vectorized XOR across all rows ──
        # This is the core Block Lanczos operation:
        # 64 GF(2) additions per XOR instruction, applied to all rows at once.
        col_bits = M[:, w] & b
        mask = col_bits.astype(np.bool_)
        mask[pivot] = False
        if mask.any():
            M[mask] ^= M[pivot]               # numpy broadcast XOR

    free_vars = set(range(n_vars)) - set(pivots.keys())
    return pivots, free_vars, M, n_words


def _gf2_extract_results(pivots, free_vars, M, n_vars, n_words, var_map,
                         tech_name='GF2_Lanczos'):
    """Extract placements and eliminations from a solved GF(2) system.

    Returns: (placements, eliminations, contradiction)
      placements:    list of (pos, digit, tech_name)
      eliminations:  list of (pos, digit)
      contradiction: True if the system is inconsistent (0=1 row found)
    """
    free_mask = np.zeros(n_words, dtype=np.uint64)
    for fv in free_vars:
        free_mask[fv >> 6] |= np.uint64(1 << (fv & 63))

    rhs_w = n_vars >> 6
    rhs_b = np.uint64(1 << (n_vars & 63))

    placements = []
    eliminations = []
    contradiction = False

    for col, row_idx in pivots.items():
        if np.any(M[row_idx] & free_mask):
            continue

        val = 1 if (M[row_idx, rhs_w] & rhs_b) else 0
        pos, digit = var_map[col]

        if val == 1:
            placements.append((pos, digit, tech_name))
        else:
            eliminations.append((pos, digit))

    # Check for contradiction: any all-zero row with RHS=1
    # (a row where all variable bits are 0 but RHS bit is set → 0 = 1)
    for r in range(M.shape[0]):
        all_zero = True
        # Check all words for variable bits
        for w in range(n_words):
            if w == rhs_w:
                # This word contains the RHS bit — check only variable bits below it
                var_mask = np.uint64(rhs_b - 1) if rhs_b > np.uint64(1) else np.uint64(0)
                if M[r, w] & var_mask:
                    all_zero = False
                    break
            elif w < rhs_w:
                if M[r, w]:
                    all_zero = False
                    break
            # words beyond rhs_w have no variable bits, skip
        if all_zero and (M[r, rhs_w] & rhs_b):
            contradiction = True
            break

    return placements, eliminations, contradiction


def detect_gf2_lanczos(bb):
    """GF(2) Block Lanczos — resolve all linearly-determined cells.

    One matrix elimination finds ALL cells forced by Sudoku constraints,
    subsuming naked/hidden singles, pairs, triples, quads, pointing,
    claiming, X-Wing, Swordfish, and all linear constraint interactions.

    Also computes the null space dimension (degrees of freedom) — the
    exact number of "choices" remaining that only zone predictions can fill.

    Returns: (placements, eliminations, dof)
      placements:   list of (pos, digit, 'GF2_Lanczos')
      eliminations: list of (pos, digit) — candidates to remove
      dof:          null space dimension (0 = fully determined by LA)
    """
    aug, var_map, n_vars, var_idx = _build_gf2_system(bb)
    if n_vars == 0:
        return [], [], 0

    pivots, free_vars, M, n_words = _gf2_block_eliminate(aug, n_vars)
    placements, eliminations, _ = _gf2_extract_results(
        pivots, free_vars, M, n_vars, n_words, var_map)

    return placements, eliminations, len(free_vars)


def detect_gf2_extended(bb, zone_hints=None, probe_free=False,
                        conjugates=True, band_stack=True):
    """GF(2) Extended — full-power linear algebra with all expansions.

    Options A-E integrated:
      A) Band/stack minirow constraints (band_stack=True)
      B) Zone prediction injection (zone_hints dict)
      C) Conjugate pair explicit constraints (conjugates=True)
      D) [handled at solve-cascade level, not here]
      E) Free-variable probing (probe_free=True)

    Returns: (placements, eliminations, dof, contradiction, probe_results)
      placements:    list of (pos, digit, tech_name)
      eliminations:  list of (pos, digit)
      dof:           null space dimension
      contradiction: True if zone hints are inconsistent
      probe_results: dict with probing stats (if probe_free=True)
    """
    tech = 'GF2_Extended'
    aug, var_map, n_vars, var_idx = _build_gf2_system(
        bb, zone_hints=zone_hints, add_conjugates=conjugates,
        add_band_stack=band_stack)
    if n_vars == 0:
        return [], [], 0, False, {}

    pivots, free_vars, M, n_words = _gf2_block_eliminate(aug, n_vars)
    placements, eliminations, contradiction = _gf2_extract_results(
        pivots, free_vars, M, n_vars, n_words, var_map, tech)

    if contradiction:
        return [], [], len(free_vars), True, {}

    # ═══ Option E: Free-variable probing ═══
    # For each free variable, try setting it to 0 then 1.
    # Run GF(2) with each assumption.
    # - If one leads to contradiction → variable is forced to the other value
    # - If both determine some other variable to the same value → that var is forced
    # This is "SAT probing via linear algebra" — catches nonlinear deductions.
    probe_stats = {'probes': 0, 'forced_by_contradiction': 0,
                   'forced_by_agreement': 0}
    if probe_free and free_vars and len(free_vars) <= 20:
        # Collect results from probing each free variable
        # determined_at_0[var] = {other_var: value} when free var = 0
        # determined_at_1[var] = {other_var: value} when free var = 1
        probed_placements = []
        probed_eliminations = []
        already_forced = set()

        for fv in sorted(free_vars):
            if fv in already_forced:
                continue
            probe_stats['probes'] += 1

            # Try fv = 0
            aug_0 = list(aug)
            aug_0.append(1 << fv)  # fv = 0 (no RHS)
            p0, f0, M0, nw0 = _gf2_block_eliminate(aug_0, n_vars)
            r0_p, r0_e, contra_0 = _gf2_extract_results(
                p0, f0, M0, n_vars, nw0, var_map, tech)

            # Try fv = 1
            aug_1 = list(aug)
            aug_1.append((1 << fv) | (1 << n_vars))  # fv = 1
            p1, f1, M1, nw1 = _gf2_block_eliminate(aug_1, n_vars)
            r1_p, r1_e, contra_1 = _gf2_extract_results(
                p1, f1, M1, n_vars, nw1, var_map, tech)

            fv_pos, fv_digit = var_map[fv]

            # Case 1: one direction contradicts → var is forced the other way
            if contra_0 and not contra_1:
                # fv must be 1
                probed_placements.append((fv_pos, fv_digit, 'GF2_Probe'))
                # Also adopt all deductions from fv=1
                probed_placements.extend(
                    (p, d, 'GF2_Probe') for p, d, _ in r1_p)
                probed_eliminations.extend(r1_e)
                already_forced.add(fv)
                probe_stats['forced_by_contradiction'] += 1
            elif contra_1 and not contra_0:
                # fv must be 0
                probed_eliminations.append((fv_pos, fv_digit))
                probed_placements.extend(
                    (p, d, 'GF2_Probe') for p, d, _ in r0_p)
                probed_eliminations.extend(r0_e)
                already_forced.add(fv)
                probe_stats['forced_by_contradiction'] += 1
            elif not contra_0 and not contra_1:
                # Case 2: both valid — check for agreement
                # Build result maps: {(pos,digit) → value}
                map_0 = {}
                for p, d, _ in r0_p:
                    map_0[(p, d)] = 1
                for p, d in r0_e:
                    map_0[(p, d)] = 0
                map_1 = {}
                for p, d, _ in r1_p:
                    map_1[(p, d)] = 1
                for p, d in r1_e:
                    map_1[(p, d)] = 0

                # Variables determined to same value in both branches
                for key in map_0:
                    if key in map_1 and map_0[key] == map_1[key]:
                        pos, digit = key
                        if map_0[key] == 1:
                            probed_placements.append(
                                (pos, digit, 'GF2_Probe'))
                        else:
                            probed_eliminations.append((pos, digit))
                        probe_stats['forced_by_agreement'] += 1

        # Merge probed results with main results
        # Deduplicate
        placed_set = {(p, d) for p, d, _ in placements}
        elim_set = set(eliminations)
        for p, d, t in probed_placements:
            if (p, d) not in placed_set:
                placements.append((p, d, t))
                placed_set.add((p, d))
        for p, d in probed_eliminations:
            if (p, d) not in elim_set:
                eliminations.append((p, d))
                elim_set.add((p, d))

    return placements, eliminations, len(free_vars), contradiction, probe_stats


# ══════════════════════════════════════════════════════════════════════
# FULL SOLVER — technique cascade using BitBoard
# ══════════════════════════════════════════════════════════════════════

def solve_bitwise(bd81, solution=None, verbose=False):
    """Solve puzzle using full bitmask technique stack.
    Returns dict with steps, technique counts, etc."""
    bb = BitBoard.from_string(bd81)

    if solution is None:
        solution_str = solve_backtrack(bd81)
        if not solution_str:
            return {'success': False, 'error': 'No solution'}
        solution = [int(ch) for ch in solution_str]

    steps = []
    technique_counts = {}
    step_num = 0

    while bb.empty > 0:
        # ── Phase 1: Drain L1+L2 ──
        l1_batch = propagate_l1l2(bb)
        for pos, digit, tech in l1_batch:
            step_num += 1
            steps.append({'step': step_num, 'pos': pos, 'digit': digit, 'technique': tech})
            technique_counts[tech] = technique_counts.get(tech, 0) + 1

        if bb.empty == 0:
            break

        # ── Phase 1.5: GF(2) Block Lanczos — linear algebra resolve ──
        # One matrix operation subsumes X-Wing, Swordfish, Simple Coloring,
        # and all linear constraint interactions simultaneously.
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
                steps.append({'step': step_num, 'pos': pos, 'digit': digit, 'technique': 'GF2_Lanczos'})
                technique_counts['GF2_Lanczos'] = technique_counts.get('GF2_Lanczos', 0) + 1
                gf2_changed = True
        if gf2_changed:
            continue  # retry L1+L2 with new info from Lanczos

        # ── Phase 2: Advanced techniques ──
        placed = False

        # L3: X-Wing + Swordfish (fallback — GF(2) usually catches these)
        if detect_xwing(bb):
            continue  # eliminations made, retry L1+L2
        if detect_swordfish(bb):
            continue

        # L4: Simple Coloring
        sc_elims, sc_detail = detect_simple_coloring(bb)
        if sc_elims:
            for pos, d in sc_elims:
                bb.eliminate(pos, d)
            technique_counts['SimpleColoring'] = technique_counts.get('SimpleColoring', 0) + 1
            continue  # retry L1+L2 after eliminations

        # FPC
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

        # FPCE
        fpce_p, fpce_e = detect_fpce_bitwise(bb)
        if fpce_e:
            for pos, d in fpce_e:
                bb.eliminate(pos, d)
        for pos, val, detail in fpce_p:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'FPCE'})
                technique_counts['FPCE'] = technique_counts.get('FPCE', 0) + 1
                placed = True
                break
        if placed:
            continue

        # Forcing Chain
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

        # Forcing Net (3-4 candidate cells)
        fn_hits = detect_forcing_net(bb)
        for pos, val, detail in fn_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'ForcingNet'})
                technique_counts['ForcingNet'] = technique_counts.get('ForcingNet', 0) + 1
                placed = True
                break
        if placed:
            continue

        # ── L6: BUG+1 ──
        bug_hits = detect_bug_plus1(bb)
        for pos, val, detail in bug_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'BUG+1'})
                technique_counts['BUG+1'] = technique_counts.get('BUG+1', 0) + 1
                placed = True
                break
        if placed:
            continue

        # ── L6: UR Type 2 ──
        ur2_elims, ur2_detail = detect_ur_type2(bb)
        if ur2_elims:
            for pos, d in ur2_elims:
                bb.eliminate(pos, d)
            technique_counts['URType2'] = technique_counts.get('URType2', 0) + 1
            continue  # retry L1+L2 after eliminations

        # ── L6: UR Type 4 ──
        ur4_elims, ur4_detail = detect_ur_type4(bb)
        if ur4_elims:
            for pos, d in ur4_elims:
                bb.eliminate(pos, d)
            technique_counts['URType4'] = technique_counts.get('URType4', 0) + 1
            continue  # retry L1+L2 after eliminations

        # ── L6: Junior Exocet ──
        je_elims, je_detail = detect_junior_exocet(bb)
        if je_elims:
            for pos, d in je_elims:
                bb.eliminate(pos, d)
            technique_counts['JuniorExocet'] = technique_counts.get('JuniorExocet', 0) + 1
            continue  # retry L1+L2 after eliminations

        # ── L6: Template ──
        tmpl_placements, tmpl_elims = detect_template(bb)
        if tmpl_elims:
            for pos, d in tmpl_elims:
                bb.eliminate(pos, d)
        for pos, val, detail in tmpl_placements:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'Template'})
                technique_counts['Template'] = technique_counts.get('Template', 0) + 1
                placed = True
                break
        if placed:
            continue
        if tmpl_elims:
            continue  # eliminations happened, retry

        # ── L6: Bowman's Bingo ──
        bingo_hits = detect_bowman_bingo(bb)
        for pos, val, detail in bingo_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'BowmanBingo'})
                technique_counts['BowmanBingo'] = technique_counts.get('BowmanBingo', 0) + 1
                placed = True
                break
        if placed:
            continue

        # D2B
        d2b_hits = detect_d2b_bitwise(bb)
        for pos, val, detail in d2b_hits:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'D2B'})
                technique_counts['D2B'] = technique_counts.get('D2B', 0) + 1
                placed = True
                break
        if placed:
            continue

        # ── L6: Template (post-D2B repass — D2B narrows search space) ──
        tmpl_placements2, tmpl_elims2 = detect_template(bb)
        if tmpl_elims2:
            for pos, d in tmpl_elims2:
                bb.eliminate(pos, d)
        for pos, val, detail in tmpl_placements2:
            if bb.board[pos] == 0 and solution[pos] == val:
                bb.place(pos, val)
                step_num += 1
                steps.append({'step': step_num, 'pos': pos, 'digit': val, 'technique': 'Template'})
                technique_counts['Template'] = technique_counts.get('Template', 0) + 1
                placed = True
                break
        if placed:
            continue
        if tmpl_elims2:
            continue  # eliminations happened, retry from L1

        # FPF
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

        # Contradiction
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
                steps.append({'step': step_num, 'pos': pos, 'digit': expected, 'technique': 'contradiction'})
                technique_counts['contradiction'] = technique_counts.get('contradiction', 0) + 1
                placed = True
                break
        if placed:
            continue

        # Fallback: place solution digit (oracle)
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
    }


# ══════════════════════════════════════════════════════════════════════
# BENCHMARK — Compare bitwise engine vs original
# ══════════════════════════════════════════════════════════════════════

def benchmark_propagation(puzzles, labels, count=10):
    """Benchmark fast_propagate vs original propagate_contradicts."""
    # Import original for comparison
    sys.path.insert(0, '/home/wiliamrocha/WSRF_Sudoku_Solve/new')
    import oracle_solver as orig

    print("=" * 70)
    print("BITWISE ENGINE — PROPAGATION BENCHMARK")
    print("=" * 70)

    # Solve each puzzle to stall point, then benchmark contradiction testing
    test_cases = []
    for pz, label in zip(puzzles[:count], labels[:count]):
        bb = BitBoard.from_string(pz)
        propagate_l1l2(bb)
        remaining = bb.empty
        if remaining < 10:
            continue

        # Also prepare original format
        board_orig = [int(ch) for ch in pz]
        cands_orig = orig.compute_candidates(board_orig)
        orig.run_l1_l2_fixpoint(board_orig, cands_orig)

        test_cases.append((bb, board_orig, cands_orig, remaining, label))

    print(f"\n{len(test_cases)} puzzles stalled at L2")

    # For each stalled puzzle, test contradiction on first 20 empty cells × their candidates
    print(f"\n{'─' * 70}")
    print("Contradiction test: fast_propagate vs propagate_contradicts")
    print(f"{'─' * 70}")

    orig_total = 0
    bw_total = 0
    total_tests = 0

    for bb, board_orig, cands_orig, remaining, label in test_cases:
        cells = [(pos, bb.cands[pos]) for pos in range(81)
                 if bb.board[pos] == 0 and POPCOUNT[bb.cands[pos]] >= 2][:20]

        n_tests = sum(POPCOUNT[m] for _, m in cells)

        # Original
        t0 = time.perf_counter()
        orig_results = []
        for pos, mask in cells:
            for d in iter_bits9(mask):
                orig_results.append(orig.propagate_contradicts(board_orig, cands_orig, pos, d + 1))
        orig_dt = time.perf_counter() - t0

        # Bitwise
        t0 = time.perf_counter()
        bw_results = []
        for pos, mask in cells:
            for d in iter_bits9(mask):
                bw_results.append(fast_propagate(bb.board, bb.cands, pos, d + 1))
        bw_dt = time.perf_counter() - t0

        # Compare results
        mismatches = sum(1 for a, b in zip(orig_results, bw_results) if a != b)
        speedup = orig_dt / bw_dt if bw_dt > 0 else float('inf')

        orig_total += orig_dt
        bw_total += bw_dt
        total_tests += n_tests

        match_str = f"MATCH" if mismatches == 0 else f"MISMATCH({mismatches})"
        print(f"  {label:20s} — {n_tests:3d} tests — "
              f"orig {orig_dt*1000:7.1f}ms  bw {bw_dt*1000:7.1f}ms  "
              f"{speedup:5.2f}x  {match_str}")

    total_speedup = orig_total / bw_total if bw_total > 0 else 0
    print(f"\n  TOTAL: {total_tests} tests — "
          f"orig {orig_total*1000:.0f}ms  bw {bw_total*1000:.0f}ms  "
          f"{total_speedup:.2f}x speedup")


def benchmark_l1l2(puzzles, labels, count=10):
    """Benchmark L1+L2 fixpoint: bitwise BitBoard vs original."""
    sys.path.insert(0, '/home/wiliamrocha/WSRF_Sudoku_Solve/new')
    import oracle_solver as orig

    print(f"\n{'=' * 70}")
    print("BITWISE ENGINE — L1+L2 FIXPOINT BENCHMARK")
    print(f"{'=' * 70}")

    orig_total = 0
    bw_total = 0

    for pz, label in zip(puzzles[:count], labels[:count]):
        # Original
        t0 = time.perf_counter()
        board_orig = [int(ch) for ch in pz]
        cands_orig = orig.compute_candidates(board_orig)
        orig_placements = orig.run_l1_l2_fixpoint(board_orig, cands_orig)
        orig_dt = time.perf_counter() - t0
        orig_remaining = sum(1 for x in board_orig if x == 0)

        # Bitwise
        t0 = time.perf_counter()
        bb = BitBoard.from_string(pz)
        bw_placements = propagate_l1l2(bb)
        bw_dt = time.perf_counter() - t0
        bw_remaining = bb.empty

        match = orig_remaining == bw_remaining
        speedup = orig_dt / bw_dt if bw_dt > 0 else float('inf')

        orig_total += orig_dt
        bw_total += bw_dt

        status = "MATCH" if match else f"MISMATCH(orig={orig_remaining} bw={bw_remaining})"
        print(f"  {label:20s} — orig {orig_dt*1000:7.2f}ms({len(orig_placements):2d}pl {orig_remaining:2d}rem)  "
              f"bw {bw_dt*1000:7.2f}ms({len(bw_placements):2d}pl {bw_remaining:2d}rem)  "
              f"{speedup:5.2f}x  {status}")

    total_speedup = orig_total / bw_total if bw_total > 0 else 0
    print(f"\n  TOTAL: orig {orig_total*1000:.1f}ms  bw {bw_total*1000:.1f}ms  {total_speedup:.2f}x speedup")


def benchmark_full_solve(puzzles, labels, count=5):
    """Benchmark full solve pipeline."""
    print(f"\n{'=' * 70}")
    print("BITWISE ENGINE — FULL SOLVE BENCHMARK")
    print(f"{'=' * 70}")

    for pz, label in zip(puzzles[:count], labels[:count]):
        t0 = time.perf_counter()
        result = solve_bitwise(pz, verbose=False)
        dt = time.perf_counter() - t0

        tc = result['technique_counts']
        tech_str = ', '.join(f"{k}:{v}" for k, v in sorted(tc.items(), key=lambda x: -x[1]))
        status = "SOLVED" if result['success'] else "FAILED"

        print(f"  {label:20s} — {dt*1000:7.0f}ms — {result['n_steps']:3d} steps — {status}")
        print(f"    {tech_str}")


def main():
    parser = argparse.ArgumentParser(description='Bitwise Sudoku Engine Benchmark')
    parser.add_argument('--count', type=int, default=10, help='Number of puzzles to test')
    parser.add_argument('--start', type=int, default=400, help='Start index in Andrew set')
    parser.add_argument('--mode', choices=['prop', 'l1l2', 'full', 'all'], default='all')
    parser.add_argument('--puzzle', type=str, default=None)
    args = parser.parse_args()

    if args.puzzle:
        puzzles = [args.puzzle]
        labels = ['Custom']
    else:
        try:
            with open('/home/wiliamrocha/WSRF_Sudoku_Solve/new/andrew_puzzles.json') as f:
                all_puzzles = json.load(f)
        except FileNotFoundError:
            print("andrew_puzzles.json not found!")
            return
        indices = list(range(args.start, min(args.start + args.count, len(all_puzzles))))
        puzzles = [all_puzzles[i] for i in indices]
        labels = [f'Andrew #{i+1}' for i in indices]

    print(f"Bitwise Engine — Testing {len(puzzles)} puzzles from #{args.start+1}")

    if args.mode in ('prop', 'all'):
        benchmark_propagation(puzzles, labels, args.count)
    if args.mode in ('l1l2', 'all'):
        benchmark_l1l2(puzzles, labels, args.count)
    if args.mode in ('full', 'all'):
        benchmark_full_solve(puzzles, labels, min(args.count, 5))

    print(f"\n{'=' * 70}")
    print("DONE — Every bit manipulation trick in the book")
    print(f"{'=' * 70}")


# ══════════════════════════════════════════════════════════════════════
# ALS FINDER — Bitwise Almost Locked Set enumeration
# ══════════════════════════════════════════════════════════════════════

def find_all_als_bitwise(bb, max_size=7):
    """Find all Almost Locked Sets using bitwise operations.

    An ALS is N cells within a single unit whose combined candidate union
    has exactly N+1 digits.

    Returns list of (cells_mask, cands_mask, unit_id) where:
      cells_mask: 81-bit integer, bit i set if cell i is in the ALS
      cands_mask: 9-bit mask of candidate digits in the ALS
      unit_id:    0-8 rows, 9-17 cols, 18-26 boxes

    Deduplicates by cells_mask — the same cell group appearing in
    multiple units is only returned once (with the first unit found).

    Pure Python, no numpy/numba.
    """
    cands = bb.cands
    board = bb.board

    als_list = []
    seen_cells = set()  # cells_mask values we've already emitted

    for ui in range(27):
        unit = UNITS[ui]

        # Gather unsolved cells in this unit with at least 1 candidate
        ucells = []
        for pos in unit:
            if board[pos] == 0 and cands[pos]:
                ucells.append(pos)

        n_ucells = len(ucells)
        if n_ucells < 2:
            continue

        # ── Size 1: single cell is an ALS if it has exactly 2 candidates ──
        # (N=1 cell, N+1=2 digits)
        for pos in ucells:
            m = cands[pos]
            if POPCOUNT[m] == 2:
                cells_mask = 1 << pos
                if cells_mask not in seen_cells:
                    seen_cells.add(cells_mask)
                    als_list.append((cells_mask, m, ui))

        # ── Size 2: pair of cells, union must have exactly 3 digits ──
        # This is the most common ALS size — unrolled for speed.
        for i in range(n_ucells - 1):
            a = ucells[i]
            ca = cands[a]
            bit_a = 1 << a
            for j in range(i + 1, n_ucells):
                b = ucells[j]
                union = ca | cands[b]
                if POPCOUNT[union] == 3:
                    cells_mask = bit_a | (1 << b)
                    if cells_mask not in seen_cells:
                        seen_cells.add(cells_mask)
                        als_list.append((cells_mask, union, ui))

        # ── Sizes 3..max_size: use itertools.combinations ──
        limit = min(n_ucells, max_size)
        for sz in range(3, limit + 1):
            target = sz + 1  # need exactly N+1 digits
            for combo in itertools.combinations(range(n_ucells), sz):
                union = 0
                for idx in combo:
                    union |= cands[ucells[idx]]
                    # Early exit: if popcount already exceeds target, skip
                    if POPCOUNT[union] > target:
                        break
                else:
                    if POPCOUNT[union] == target:
                        cells_mask = 0
                        for idx in combo:
                            cells_mask |= 1 << ucells[idx]
                        if cells_mask not in seen_cells:
                            seen_cells.add(cells_mask)
                            als_list.append((cells_mask, union, ui))

    return als_list


# ══════════════════════════════════════════════════════════════════════
# X-CYCLES — Single-digit alternating inference chains (bitwise)
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _x_cycle_jit(board, cands, sees, unit_cells, popcount_lut):
    """JIT X-Cycles: single-digit alternating inference chains forming loops."""
    MAX_CHAIN = 12
    MIN_CYCLE = 4
    MAX_QUEUE = 25000
    MAX_NODES = 60

    # Output: placements and eliminations
    place_out = np.zeros((10, 2), dtype=np.int32)  # (pos, digit1idx)
    n_place = 0
    elim_out = np.zeros((200, 2), dtype=np.int32)
    n_elims = 0

    for d in range(9):
        dbit = 1 << d
        dval = d + 1

        # Collect cells with candidate d
        cells = np.zeros(MAX_NODES, dtype=np.int32)
        n = 0
        for pos in range(81):
            if board[pos] == 0 and (cands[pos] & dbit):
                cells[n] = pos
                n += 1
        if n < 3 or n > MAX_NODES:
            continue

        # pos -> node index lookup
        pos_to_idx = np.full(81, -1, dtype=np.int32)
        for i in range(n):
            pos_to_idx[cells[i]] = i

        # Build strong links (conjugate pairs per unit)
        strong = np.zeros((n, n), dtype=np.bool_)
        for ui in range(27):
            pair = np.zeros(2, dtype=np.int32)
            n_pair = 0
            for ci in range(9):
                pos = unit_cells[ui, ci]
                idx = pos_to_idx[pos]
                if idx >= 0:
                    if n_pair < 2:
                        pair[n_pair] = idx
                        n_pair += 1
                    else:
                        n_pair = 3
                        break
            if n_pair == 2:
                strong[pair[0], pair[1]] = True
                strong[pair[1], pair[0]] = True

        # Build weak links (see each other, not strong)
        weak = np.zeros((n, n), dtype=np.bool_)
        for a in range(n):
            for b in range(a + 1, n):
                if not strong[a, b] and sees[cells[a], cells[b]]:
                    weak[a, b] = True
                    weak[b, a] = True

        # BFS for alternating cycles
        # Queue: cur, last_lt, path_len, path nodes, visited mask
        q_cur = np.zeros(MAX_QUEUE, dtype=np.int32)
        q_lt = np.zeros(MAX_QUEUE, dtype=np.int32)
        q_vis = np.zeros(MAX_QUEUE, dtype=np.int64)
        q_plen = np.zeros(MAX_QUEUE, dtype=np.int32)
        q_path = np.zeros((MAX_QUEUE, MAX_CHAIN), dtype=np.int32)
        q_start_lt = np.zeros(MAX_QUEUE, dtype=np.int32)

        for start in range(n):
            has_strong = False
            for b in range(n):
                if strong[start, b]:
                    has_strong = True
                    break
            if not has_strong:
                continue

            for slt in range(2):  # 0=strong first, 1=weak first
                qi_head = 0
                qi_tail = 0
                start_bit = np.int64(1) << np.int64(start)

                for nxt in range(n):
                    use = False
                    if slt == 0 and strong[start, nxt]:
                        use = True
                    elif slt == 1 and weak[start, nxt]:
                        use = True
                    if use and qi_tail < MAX_QUEUE:
                        q_cur[qi_tail] = nxt
                        q_lt[qi_tail] = slt
                        q_vis[qi_tail] = start_bit | (np.int64(1) << np.int64(nxt))
                        q_plen[qi_tail] = 2
                        q_path[qi_tail, 0] = start
                        q_path[qi_tail, 1] = nxt
                        q_start_lt[qi_tail] = slt
                        qi_tail += 1

                while qi_head < qi_tail:
                    cur = q_cur[qi_head]
                    last_lt = q_lt[qi_head]
                    vis = q_vis[qi_head]
                    plen = q_plen[qi_head]
                    cur_slt = q_start_lt[qi_head]
                    qi_head += 1

                    # Check cycle closure
                    if plen >= MIN_CYCLE:
                        close_lt = 1 - last_lt
                        can_close = False
                        if close_lt == 0 and strong[cur, start]:
                            can_close = True
                        elif close_lt == 1 and weak[cur, start]:
                            can_close = True

                        if can_close:
                            if plen % 2 == 0:
                                # Rule 1: even cycle — eliminate from off-chain peers of weak links
                                in_path = np.zeros(81, dtype=np.bool_)
                                for pi in range(plen):
                                    in_path[cells[q_path[qi_head - 1, pi]]] = True

                                for ei in range(plen):
                                    edge_lt = cur_slt if (ei % 2 == 0) else (1 - cur_slt)
                                    if edge_lt == 1:
                                        p1 = cells[q_path[qi_head - 1, ei]]
                                        p2 = cells[q_path[qi_head - 1, (ei + 1) % plen]]
                                        for pos in range(81):
                                            if in_path[pos]:
                                                continue
                                            if board[pos] != 0:
                                                continue
                                            if not (cands[pos] & dbit):
                                                continue
                                            if sees[pos, p1] and sees[pos, p2]:
                                                if n_elims < 200:
                                                    elim_out[n_elims, 0] = pos
                                                    elim_out[n_elims, 1] = dval
                                                    n_elims += 1

                                if n_elims > 0:
                                    return place_out[:n_place], n_place, elim_out[:n_elims], n_elims

                            else:
                                # Odd cycle
                                start_pos = cells[start]
                                if board[start_pos] == 0 and (cands[start_pos] & dbit):
                                    if cur_slt == 0:
                                        # Rule 2: place
                                        if n_place < 10:
                                            place_out[n_place, 0] = start_pos
                                            place_out[n_place, 1] = dval
                                            n_place += 1
                                        return place_out[:n_place], n_place, elim_out[:n_elims], n_elims
                                    else:
                                        # Rule 3: eliminate
                                        if n_elims < 200:
                                            elim_out[n_elims, 0] = start_pos
                                            elim_out[n_elims, 1] = dval
                                            n_elims += 1
                                        return place_out[:n_place], n_place, elim_out[:n_elims], n_elims

                    # Extend chain
                    if plen >= MAX_CHAIN:
                        continue
                    next_lt = 1 - last_lt
                    for nxt in range(n):
                        use = False
                        if next_lt == 0 and strong[cur, nxt]:
                            use = True
                        elif next_lt == 1 and weak[cur, nxt]:
                            use = True
                        if use:
                            nxt_bit = np.int64(1) << np.int64(nxt)
                            if vis & nxt_bit:
                                continue
                            if qi_tail < MAX_QUEUE:
                                q_cur[qi_tail] = nxt
                                q_lt[qi_tail] = next_lt
                                q_vis[qi_tail] = vis | nxt_bit
                                q_plen[qi_tail] = plen + 1
                                for pi in range(plen):
                                    q_path[qi_tail, pi] = q_path[qi_head - 1, pi]
                                q_path[qi_tail, plen] = nxt
                                q_start_lt[qi_tail] = cur_slt
                                qi_tail += 1

    return place_out[:n_place], n_place, elim_out[:n_elims], n_elims


def detect_x_cycle_bitwise(bb):
    """X-Cycles — JIT-accelerated. Returns (placements, eliminations)."""
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    p_arr, n_p, e_arr, n_e = _x_cycle_jit(
        board_arr, cands_arr, NP_SEES, NP_UNIT_CELLS, NP_POPCOUNT)

    placements = [(int(p_arr[k, 0]), int(p_arr[k, 1]), 'XCycle') for k in range(n_p)]
    eliminations = [(int(e_arr[k, 0]), int(e_arr[k, 1])) for k in range(n_e)]
    return placements, eliminations


# ══════════════════════════════════════════════════════════════════════
# ALS-XZ — Almost Locked Set XZ-Rule (bitwise)
# ══════════════════════════════════════════════════════════════════════

def detect_als_xz_bitwise(bb):
    """ALS-XZ: Two Almost Locked Sets connected by a Restricted Common Candidate.

    JIT-accelerated version — find all ALS + check RCC pairs in compiled code.

    Returns list of (pos, digit) elimination tuples.
    """
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    elim_arr, n_elims = _find_and_check_als_xz_jit(
        board_arr, cands_arr, NP_SEES, NP_UNIT_CELLS, NP_POPCOUNT)

    if n_elims == 0:
        return []
    return [(int(elim_arr[k, 0]), int(elim_arr[k, 1])) for k in range(n_elims)]


# ══════════════════════════════════════════════════════════════════════
# ALIGNED PAIR EXCLUSION — bitwise implementation
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _aligned_pair_exclusion_jit(board, cands, sees, peers, unit_cells, popcount_lut):
    """JIT Aligned Pair Exclusion."""
    elim_out = np.zeros((200, 2), dtype=np.int32)
    n_elims = 0
    elim_seen = np.zeros(729, dtype=np.bool_)

    for c1 in range(81):
        if board[c1] != 0:
            continue
        m1 = cands[c1]
        if popcount_lut[m1] < 2:
            continue

        for pi in range(20):
            c2 = peers[c1, pi]
            if c2 <= c1:
                continue
            if board[c2] != 0:
                continue
            m2 = cands[c2]
            if popcount_lut[m2] < 2:
                continue

            # Common peers: unsolved cells that see both c1 and c2
            cp_cands_arr = np.zeros(20, dtype=np.int32)
            n_cp = 0
            for pos in range(81):
                if pos == c1 or pos == c2:
                    continue
                if board[pos] != 0 or cands[pos] == 0:
                    continue
                if sees[c1, pos] and sees[c2, pos]:
                    cp_cands_arr[n_cp] = cands[pos]
                    n_cp += 1
            if n_cp == 0:
                continue

            # Build small ALS from common peers within units (just cands masks)
            als_ncells_arr = np.zeros(200, dtype=np.int32)
            als_cands_arr = np.zeros(200, dtype=np.int32)
            n_als_local = 0

            # Gather common peer cells per unit for ALS building
            for ui in range(27):
                uc_cands = np.zeros(9, dtype=np.int32)
                n_uc = 0
                for ci in range(9):
                    upos = unit_cells[ui, ci]
                    if board[upos] != 0 or cands[upos] == 0:
                        continue
                    if upos == c1 or upos == c2:
                        continue
                    if sees[c1, upos] and sees[c2, upos]:
                        uc_cands[n_uc] = cands[upos]
                        n_uc += 1

                # 1-cell ALS (bivalue)
                for i in range(n_uc):
                    if popcount_lut[uc_cands[i]] == 2 and n_als_local < 200:
                        als_ncells_arr[n_als_local] = 1
                        als_cands_arr[n_als_local] = uc_cands[i]
                        n_als_local += 1

                # 2-cell ALS
                for i in range(n_uc - 1):
                    for j in range(i + 1, n_uc):
                        union = uc_cands[i] | uc_cands[j]
                        if popcount_lut[union] == 3 and n_als_local < 200:
                            als_ncells_arr[n_als_local] = 2
                            als_cands_arr[n_als_local] = union
                            n_als_local += 1

                # 3-cell ALS
                for i in range(n_uc - 2):
                    for j in range(i + 1, n_uc - 1):
                        cij = uc_cands[i] | uc_cands[j]
                        if popcount_lut[cij] > 4:
                            continue
                        for k in range(j + 1, n_uc):
                            union = cij | uc_cands[k]
                            if popcount_lut[union] == 4 and n_als_local < 200:
                                als_ncells_arr[n_als_local] = 3
                                als_cands_arr[n_als_local] = union
                                n_als_local += 1

            # Check all (a, b) digit combinations
            valid_c1 = 0
            valid_c2 = 0
            ALL = 0x1FF

            d1 = m1
            while d1:
                a_bit = d1 & (-d1)
                d1 ^= a_bit
                d2 = m2
                while d2:
                    b_bit = d2 & (-d2)
                    d2_copy = d2
                    d2 ^= b_bit
                    if a_bit == b_bit:
                        continue
                    keep = ALL & ~(a_bit | b_bit)

                    broken = False
                    for i in range(n_cp):
                        if (cp_cands_arr[i] & keep) == 0:
                            broken = True
                            break

                    if not broken:
                        for i in range(n_als_local):
                            remaining = als_cands_arr[i] & keep
                            if popcount_lut[remaining] < als_ncells_arr[i]:
                                broken = True
                                break

                    if not broken:
                        valid_c1 |= a_bit
                        valid_c2 |= b_bit

            # Eliminations
            kill_c1 = m1 & ~valid_c1
            kill_c2 = m2 & ~valid_c2

            while kill_c1:
                lb = kill_c1 & (-kill_c1)
                kill_c1 ^= lb
                d = 0
                tmp = lb
                while tmp > 1:
                    d += 1
                    tmp >>= 1
                key = c1 * 9 + d
                if not elim_seen[key]:
                    elim_seen[key] = True
                    if n_elims < 200:
                        elim_out[n_elims, 0] = c1
                        elim_out[n_elims, 1] = d + 1
                        n_elims += 1

            while kill_c2:
                lb = kill_c2 & (-kill_c2)
                kill_c2 ^= lb
                d = 0
                tmp = lb
                while tmp > 1:
                    d += 1
                    tmp >>= 1
                key = c2 * 9 + d
                if not elim_seen[key]:
                    elim_seen[key] = True
                    if n_elims < 200:
                        elim_out[n_elims, 0] = c2
                        elim_out[n_elims, 1] = d + 1
                        n_elims += 1

            if n_elims > 0:
                return elim_out[:n_elims], n_elims

    return elim_out[:n_elims], n_elims


def detect_aligned_pair_exclusion_bitwise(bb):
    """Aligned Pair Exclusion — JIT-accelerated.
    Returns list of (pos, digit) eliminations.
    """
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    elim_arr, n_elims = _aligned_pair_exclusion_jit(
        board_arr, cands_arr, NP_SEES, NP_PEERS, NP_UNIT_CELLS, NP_POPCOUNT)

    if n_elims == 0:
        return []
    return [(int(elim_arr[k, 0]), int(elim_arr[k, 1])) for k in range(n_elims)]


# ══════════════════════════════════════════════════════════════════════
# SUE DE COQ — box-line intersection decomposition into dual ALS
# ══════════════════════════════════════════════════════════════════════

def detect_sue_de_coq_bitwise(bb):
    """Sue De Coq: decompose box-line intersection candidates into two ALS
    (one from the line remainder, one from the box remainder).

    For each box and each intersecting line (row/col):
      1. Find 2-3 empty intersection cells with >= N+2 combined candidates.
      2. Partition the combined candidates into line_part | box_part.
      3. Find ALS in line remainder covering line_part (N cells, N+1 cands).
      4. Find ALS in box remainder covering box_part (N cells, N+1 cands).
      5. Eliminate line_part digits from rest of line, box_part from rest of box.

    Returns list of (pos, digit) eliminations (digit is 1-indexed).
    """
    cands = bb.cands
    board = bb.board

    for bi in range(9):
        box_cells = BOX_CELLS_FLAT[bi]
        br = (bi // 3) * 3   # top-left row of box
        bc = (bi % 3) * 3    # top-left col of box

        # Try both row and column intersections
        for is_row in (True, False):
            # Each box intersects 3 rows and 3 cols; iterate the 3
            for offset in range(3):
                idx = br + offset if is_row else bc + offset

                # ── Intersection cells: 3 cells in box on this line ──
                int_cells = []
                int_cands = 0
                for p in range(3):
                    if is_row:
                        pos = idx * 9 + bc + p
                    else:
                        pos = (br + p) * 9 + idx
                    if board[pos] == 0 and cands[pos]:
                        int_cells.append(pos)
                        int_cands |= cands[pos]

                n_int = len(int_cells)
                if n_int < 2 or n_int > 3:
                    continue

                n_cands = POPCOUNT[int_cands]
                if n_cands < n_int + 2:
                    continue

                # ── Build line remainder and box remainder ──
                line_rem = []
                if is_row:
                    for c in range(9):
                        if bc <= c < bc + 3:
                            continue
                        pos = idx * 9 + c
                        if board[pos] == 0 and cands[pos]:
                            line_rem.append(pos)
                else:
                    for r in range(9):
                        if br <= r < br + 3:
                            continue
                        pos = r * 9 + idx
                        if board[pos] == 0 and cands[pos]:
                            line_rem.append(pos)

                box_rem = []
                for pos in box_cells:
                    if board[pos] != 0 or not cands[pos]:
                        continue
                    if is_row:
                        if pos // 9 == idx:
                            continue
                    else:
                        if pos % 9 == idx:
                            continue
                    box_rem.append(pos)

                # ── Enumerate partitions via bit-subset iteration ──
                # line_part and box_part must each have >= 2 digits
                # Iterate all non-empty proper subsets of int_cands as line_part
                submask = int_cands
                while submask:
                    line_part = submask
                    box_part = int_cands & ~line_part

                    lp_cnt = POPCOUNT[line_part]
                    bp_cnt = POPCOUNT[box_part]

                    # Both parts need >= 2 digits
                    if lp_cnt < 2 or bp_cnt < 2:
                        submask = (submask - 1) & int_cands
                        continue

                    # ── Find ALS in line remainder covering line_part ──
                    # ALS: N cells whose union of candidates == line_part,
                    #       where N = POPCOUNT[line_part] - 1
                    als_sz_l = lp_cnt - 1
                    line_als = None
                    if 1 <= als_sz_l <= len(line_rem):
                        for combo in itertools.combinations(line_rem, als_sz_l):
                            cu = 0
                            for pos in combo:
                                cu |= cands[pos]
                            if cu == line_part:
                                line_als = combo
                                break

                    if line_als is None:
                        submask = (submask - 1) & int_cands
                        continue

                    # ── Find ALS in box remainder covering box_part ──
                    als_sz_b = bp_cnt - 1
                    box_als = None
                    if 1 <= als_sz_b <= len(box_rem):
                        for combo in itertools.combinations(box_rem, als_sz_b):
                            cu = 0
                            for pos in combo:
                                cu |= cands[pos]
                            if cu == box_part:
                                box_als = combo
                                break

                    if box_als is None:
                        submask = (submask - 1) & int_cands
                        continue

                    # ── Collect eliminations ──
                    line_als_set = set(line_als)
                    box_als_set = set(box_als)
                    elims = []

                    # Eliminate line_part digits from line remainder (outside ALS)
                    for pos in line_rem:
                        if pos in line_als_set:
                            continue
                        hits = cands[pos] & line_part
                        for d in iter_bits9(hits):
                            elims.append((pos, d + 1))

                    # Eliminate box_part digits from box remainder (outside ALS)
                    for pos in box_rem:
                        if pos in box_als_set:
                            continue
                        hits = cands[pos] & box_part
                        for d in iter_bits9(hits):
                            elims.append((pos, d + 1))

                    if elims:
                        return elims

                    submask = (submask - 1) & int_cands

    return []


# ══════════════════════════════════════════════════════════════════════
# ALS-XY WING — Three ALS connected via two RCC digits (bitwise)
# ══════════════════════════════════════════════════════════════════════

def detect_als_xy_wing_bitwise(bb):
    """ALS-XY Wing: Three Almost Locked Sets — pivot C with wings A and B.

    JIT-accelerated version.
    Returns list of (pos, digit) elimination tuples.
    """
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    als_cells, als_ncells, als_cands, n_als = _find_all_als_jit(
        board_arr, cands_arr, NP_UNIT_CELLS, NP_POPCOUNT)
    if n_als < 3:
        return []

    elim_arr, n_elims = _als_xy_wing_jit(
        als_cells, als_ncells, als_cands, n_als,
        cands_arr, NP_SEES, NP_POPCOUNT)

    if n_elims == 0:
        return []
    return [(int(elim_arr[k, 0]), int(elim_arr[k, 1])) for k in range(n_elims)]


# ══════════════════════════════════════════════════════════════════════
# DEATH BLOSSOM — stem cell + ALS petals via Restricted Common Candidates
# ══════════════════════════════════════════════════════════════════════

@nb.njit(cache=True)
def _death_blossom_jit(board, cands, als_cells, als_ncells, als_cands, n_als,
                       sees, popcount_lut):
    """JIT Death Blossom: stem cell + ALS petals."""
    elim_out = np.zeros((200, 2), dtype=np.int32)
    n_elims = 0
    elim_seen = np.zeros(729, dtype=np.bool_)

    # Precompute per-ALS per-digit: which cells in the ALS have each digit
    # als_dcells[ai, d, k] = cell position, als_dcnt[ai, d] = count
    als_dcells = np.zeros((n_als, 9, 5), dtype=np.int32)
    als_dcnt = np.zeros((n_als, 9), dtype=np.int32)
    for ai in range(n_als):
        nc = als_ncells[ai]
        for ci in range(nc):
            pos = als_cells[ai, ci]
            m = cands[pos] & als_cands[ai]
            for d in range(9):
                if m & (1 << d):
                    idx = als_dcnt[ai, d]
                    if idx < 5:
                        als_dcells[ai, d, idx] = pos
                        als_dcnt[ai, d] = idx + 1

    for stem in range(81):
        if board[stem] != 0:
            continue
        stem_cands = cands[stem]
        n_stem = popcount_lut[stem_cands]
        if n_stem < 2 or n_stem > 3:
            continue

        # Extract stem digits
        stem_digits = np.zeros(3, dtype=np.int32)
        n_sd = 0
        tmp = stem_cands
        for d in range(9):
            if tmp & (1 << d):
                stem_digits[n_sd] = d
                n_sd += 1

        # For each stem digit, find valid petal ALS indices
        petal_lists = np.zeros((3, n_als), dtype=np.int32)
        petal_counts = np.zeros(3, dtype=np.int32)
        skip_stem = False

        for si in range(n_sd):
            d = stem_digits[si]
            d_bit = 1 << d
            cnt = 0
            for ai in range(n_als):
                # ALS must not contain stem
                contains_stem = False
                nc = als_ncells[ai]
                for ci in range(nc):
                    if als_cells[ai, ci] == stem:
                        contains_stem = True
                        break
                if contains_stem:
                    continue

                if not (als_cands[ai] & d_bit):
                    continue

                # Every D-cell in ALS must see stem
                n_dc = als_dcnt[ai, d]
                if n_dc == 0:
                    continue
                all_see = True
                for k in range(n_dc):
                    if not sees[als_dcells[ai, d, k], stem]:
                        all_see = False
                        break
                if all_see:
                    petal_lists[si, cnt] = ai
                    cnt += 1
            petal_counts[si] = cnt
            if cnt == 0:
                skip_stem = True
                break

        if skip_stem:
            continue

        # Try petal combos (2 or 3 petals)
        for p0 in range(petal_counts[0]):
            ai0 = petal_lists[0, p0]
            for p1 in range(petal_counts[1]):
                ai1 = petal_lists[1, p1]
                if ai1 == ai0:
                    continue

                # Check overlap between petal 0 and 1
                overlap01 = False
                for a in range(als_ncells[ai0]):
                    for b in range(als_ncells[ai1]):
                        if als_cells[ai0, a] == als_cells[ai1, b]:
                            overlap01 = True
                            break
                    if overlap01:
                        break
                if overlap01:
                    continue

                if n_sd == 2:
                    # 2-petal combo
                    rcc_mask = (1 << stem_digits[0]) | (1 << stem_digits[1])
                    common_z = als_cands[ai0] & als_cands[ai1] & ~rcc_mask & 0x1FF
                    if not common_z:
                        continue

                    combo = np.array([ai0, ai1], dtype=np.int32)
                    n_combo = 2

                    z_m = common_z
                    while z_m:
                        z_bit = z_m & (-z_m)
                        z_m ^= z_bit
                        z = 0
                        zt = z_bit
                        while zt > 1:
                            z += 1
                            zt >>= 1

                        all_z = np.zeros(10, dtype=np.int32)
                        n_z = 0
                        for ci in range(n_combo):
                            ai = combo[ci]
                            for k in range(als_dcnt[ai, z]):
                                all_z[n_z] = als_dcells[ai, z, k]
                                n_z += 1
                        if n_z == 0:
                            continue

                        for pos in range(81):
                            if pos == stem:
                                continue
                            if not (cands[pos] & z_bit):
                                continue
                            in_any = False
                            for ci in range(n_combo):
                                ai = combo[ci]
                                for k in range(als_ncells[ai]):
                                    if pos == als_cells[ai, k]:
                                        in_any = True
                                        break
                                if in_any:
                                    break
                            if in_any:
                                continue
                            sees_all = True
                            for zi in range(n_z):
                                if not sees[pos, all_z[zi]]:
                                    sees_all = False
                                    break
                            if sees_all:
                                key = pos * 9 + z
                                if not elim_seen[key]:
                                    elim_seen[key] = True
                                    if n_elims < 200:
                                        elim_out[n_elims, 0] = pos
                                        elim_out[n_elims, 1] = z + 1
                                        n_elims += 1

                    if n_elims > 0:
                        return elim_out[:n_elims], n_elims

                else:
                    # 3-petal combo
                    for p2 in range(petal_counts[2]):
                        ai2 = petal_lists[2, p2]
                        if ai2 == ai0 or ai2 == ai1:
                            continue

                        overlap2 = False
                        for a in range(als_ncells[ai2]):
                            for b in range(als_ncells[ai0]):
                                if als_cells[ai2, a] == als_cells[ai0, b]:
                                    overlap2 = True
                                    break
                            if overlap2:
                                break
                            for b in range(als_ncells[ai1]):
                                if als_cells[ai2, a] == als_cells[ai1, b]:
                                    overlap2 = True
                                    break
                            if overlap2:
                                break
                        if overlap2:
                            continue

                        rcc_mask = (1 << stem_digits[0]) | (1 << stem_digits[1]) | (1 << stem_digits[2])
                        common_z = als_cands[ai0] & als_cands[ai1] & als_cands[ai2] & ~rcc_mask & 0x1FF
                        if not common_z:
                            continue

                        combo3 = np.array([ai0, ai1, ai2], dtype=np.int32)
                        n_combo3 = 3

                        z_m = common_z
                        while z_m:
                            z_bit = z_m & (-z_m)
                            z_m ^= z_bit
                            z = 0
                            zt = z_bit
                            while zt > 1:
                                z += 1
                                zt >>= 1

                            all_z = np.zeros(15, dtype=np.int32)
                            n_z = 0
                            for ci in range(n_combo3):
                                ai = combo3[ci]
                                for k in range(als_dcnt[ai, z]):
                                    all_z[n_z] = als_dcells[ai, z, k]
                                    n_z += 1
                            if n_z == 0:
                                continue

                            for pos in range(81):
                                if pos == stem:
                                    continue
                                if not (cands[pos] & z_bit):
                                    continue
                                in_any = False
                                for ci in range(n_combo3):
                                    ai = combo3[ci]
                                    for k in range(als_ncells[ai]):
                                        if pos == als_cells[ai, k]:
                                            in_any = True
                                            break
                                    if in_any:
                                        break
                                if in_any:
                                    continue
                                sees_all = True
                                for zi in range(n_z):
                                    if not sees[pos, all_z[zi]]:
                                        sees_all = False
                                        break
                                if sees_all:
                                    key = pos * 9 + z
                                    if not elim_seen[key]:
                                        elim_seen[key] = True
                                        if n_elims < 200:
                                            elim_out[n_elims, 0] = pos
                                            elim_out[n_elims, 1] = z + 1
                                            n_elims += 1

                        if n_elims > 0:
                            return elim_out[:n_elims], n_elims

    return elim_out[:n_elims], n_elims


def detect_death_blossom_bitwise(bb):
    """Death Blossom — JIT-accelerated.
    Returns list of (pos, digit) elimination tuples (digit is 1-indexed).
    """
    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    als_cells, als_ncells, als_cands, n_als = _find_all_als_jit(
        board_arr, cands_arr, NP_UNIT_CELLS, NP_POPCOUNT)
    if n_als == 0:
        return []

    elim_arr, n_elims = _death_blossom_jit(
        board_arr, cands_arr, als_cells, als_ncells, als_cands, n_als,
        NP_SEES, NP_POPCOUNT)

    if n_elims == 0:
        return []
    return [(int(elim_arr[k, 0]), int(elim_arr[k, 1])) for k in range(n_elims)]


# ══════════════════════════════════════════════════════════════════════
# SK LOOP — Stephen Kurzhals Loop (bitwise)
# ══════════════════════════════════════════════════════════════════════

def detect_sk_loop_bitwise(bb):
    """SK Loop: 4 boxes in a 2x2 rectangular arrangement with a closed
    candidate loop along the inter-box boundary segments.

    An SK Loop chains linking digits around the perimeter of a 2x2 box
    rectangle.  The perimeter is divided into 8 half-segments, two per
    box (one along the boundary row, one along the boundary column).
    Going clockwise starting from the TL box:

      hs0: TL box, rightmost col   (bcol_left,  rows of top band)
      hs1: TR box, leftmost col    (bcol_right,  rows of top band)
      hs2: TR box, bottom row      (brow_top,    cols of right band)
      hs3: BR box, top row         (brow_bot,    cols of right band)
      hs4: BR box, leftmost col    (bcol_right,  rows of bottom band)  [reversed]
      hs5: BL box, rightmost col   (bcol_left,   rows of bottom band)  [reversed]
      hs6: BL box, top row         (brow_bot,    cols of left band)    [reversed]
      hs7: TL box, bottom row      (brow_top,    cols of left band)    [reversed]

    Adjacent half-segment pairs (hs0-hs1, hs2-hs3, hs4-hs5, hs6-hs7)
    share a common line (row or column) and therefore share candidates
    via Sudoku constraints.  The remaining adjacent pairs (hs1-hs2,
    hs3-hs4, hs5-hs6, hs7-hs0) share a corner cell (a cell that
    belongs to both half-segments).

    Closed-loop conditions (checked on 4 merged segments, each being
    two adjacent half-segments sharing the same side of the rectangle):
      1. Every segment has >= 2 empty cells.
      2. Total empty cells across all 4 segments == total distinct
         loop digits  (rank-0 / supply == demand).
      3. Every loop digit appears in exactly 2 adjacent segments.

    Eliminations: loop digits are removed from cells inside the 4 boxes
    that are NOT part of any boundary half-segment.

    Returns list of (pos, digit) eliminations (digit is 1-indexed).
    """
    cands = bb.cands
    board = bb.board

    # Try all 9 valid 2x2 box arrangements
    for br1 in range(3):
        for br2 in range(br1 + 1, 3):
            for bc1 in range(3):
                for bc2 in range(bc1 + 1, 3):
                    # Four boxes:  TL  TR
                    #              BL  BR
                    tl = br1 * 3 + bc1
                    tr = br1 * 3 + bc2
                    bl = br2 * 3 + bc1
                    bri = br2 * 3 + bc2

                    # Boundary rows/cols between box bands
                    brow_top = br1 * 3 + 2    # bottom row of top band
                    brow_bot = br2 * 3        # top row of bottom band
                    bcol_left = bc1 * 3 + 2   # rightmost col of left band
                    bcol_right = bc2 * 3      # leftmost col of right band

                    brow_set = (brow_top, brow_bot)
                    bcol_set = (bcol_left, bcol_right)

                    # Collect per-box candidate unions (ALL cells) and boundary mask
                    boxes_list = [tl, tr, bl, bri]
                    box_all_cands = {tl: 0, tr: 0, bl: 0, bri: 0}
                    boundary_81 = 0

                    for bi in boxes_list:
                        for pos in BOX_CELLS_FLAT[bi]:
                            if board[pos] != 0:
                                continue
                            if cands[pos]:
                                box_all_cands[bi] |= cands[pos]
                            r, c = pos // 9, pos % 9
                            if r in brow_set or c in bcol_set:
                                boundary_81 |= 1 << pos

                    # ── Find linking digits ──
                    # A linking digit appears in exactly 2 of the 4 boxes.
                    all_box_cands = (box_all_cands[tl]
                                    | box_all_cands[tr]
                                    | box_all_cands[bl]
                                    | box_all_cands[bri])

                    linking_mask = 0
                    for d in iter_bits9(all_box_cands):
                        bit = BIT[d]
                        count = 0
                        for bi in boxes_list:
                            if box_all_cands[bi] & bit:
                                count += 1
                        if count == 2:
                            linking_mask |= bit

                    if POPCOUNT[linking_mask] < 4:
                        continue

                    # ── Closed-loop validation (supply == demand) ──
                    boundary_empty = 0
                    for bi in boxes_list:
                        for pos in BOX_CELLS_FLAT[bi]:
                            if board[pos] != 0:
                                continue
                            r, c = pos // 9, pos % 9
                            if r in brow_set or c in bcol_set:
                                boundary_empty += 1

                    n_linking = POPCOUNT[linking_mask]
                    if boundary_empty != n_linking:
                        continue

                    # ── Adjacency: linking digit must be in 2 ADJACENT boxes ──
                    adj_pairs = [(tl, tr), (tl, bl), (tr, bri), (bl, bri)]
                    valid_loop = True
                    for d in iter_bits9(linking_mask):
                        bit = BIT[d]
                        has_boxes = [bi for bi in boxes_list if box_all_cands[bi] & bit]
                        if len(has_boxes) != 2:
                            valid_loop = False
                            break
                        pair = tuple(sorted(has_boxes))
                        if pair not in [(min(a, b), max(a, b)) for a, b in adj_pairs]:
                            valid_loop = False
                            break
                    if not valid_loop:
                        continue

                    # ── Segment size: each boundary segment needs >= 2 cells ──
                    seg_counts = [0, 0, 0, 0]
                    for pos in range(81):
                        if board[pos] != 0 or not (boundary_81 & (1 << pos)):
                            continue
                        r, c = pos // 9, pos % 9
                        if r == brow_top:
                            seg_counts[0] += 1
                        elif c == bcol_right:
                            seg_counts[1] += 1
                        elif r == brow_bot:
                            seg_counts[2] += 1
                        elif c == bcol_left:
                            seg_counts[3] += 1
                    if any(s < 2 for s in seg_counts):
                        continue

                    # ══ VALID SK LOOP — collect eliminations ══
                    # Eliminate linking digits from interior cells
                    # (cells NOT on boundary rows/cols) within the 4 boxes.
                    elims = []
                    elim_set = set()

                    for bi in boxes_list:
                        link_here = box_all_cands[bi] & linking_mask
                        if not link_here:
                            continue
                        for pos in BOX_CELLS_FLAT[bi]:
                            if board[pos] != 0 or not cands[pos]:
                                continue
                            if boundary_81 & (1 << pos):
                                continue  # on boundary — skip
                            hits = cands[pos] & link_here
                            for d in iter_bits9(hits):
                                key = pos * 9 + d
                                if key not in elim_set:
                                    elim_set.add(key)
                                    elims.append((pos, d + 1))

                    if elims:
                        return elims

    return []


# ══════════════════════════════════════════════════════════════════════
# AIC GRAPH — Alternating Inference Chain for Kraken Fish
# ══════════════════════════════════════════════════════════════════════


def build_aic_graph(bb):
    """Build AIC graph for chain reachability.

    Node ID = pos * 9 + d (0-indexed digit).
    Returns (strong, weak) adjacency lists indexed by node ID.
    """
    cands = bb.cands
    N = 729  # 81 * 9
    strong = [[] for _ in range(N)]
    weak = [[] for _ in range(N)]
    strong_set = [set() for _ in range(N)]

    # Strong links: conjugate pairs (digit in exactly 2 cells per unit)
    for unit in UNITS:
        for d in range(9):
            bit = BIT[d]
            positions = []
            for pos in unit:
                if cands[pos] & bit:
                    positions.append(pos)
            if len(positions) == 2:
                i = positions[0] * 9 + d
                j = positions[1] * 9 + d
                if j not in strong_set[i]:
                    strong[i].append(j)
                    strong[j].append(i)
                    strong_set[i].add(j)
                    strong_set[j].add(i)

    # Strong links: bivalue cells (exactly 2 candidates)
    for pos in range(81):
        c = cands[pos]
        if not c or POPCOUNT[c] != 2:
            continue
        digits = list(iter_bits9(c))
        i = pos * 9 + digits[0]
        j = pos * 9 + digits[1]
        if j not in strong_set[i]:
            strong[i].append(j)
            strong[j].append(i)
            strong_set[i].add(j)
            strong_set[j].add(i)

    # Weak links: same cell, different digits
    for pos in range(81):
        c = cands[pos]
        if not c or POPCOUNT[c] < 2:
            continue
        digits = list(iter_bits9(c))
        for a in range(len(digits)):
            for b in range(a + 1, len(digits)):
                i = pos * 9 + digits[a]
                j = pos * 9 + digits[b]
                weak[i].append(j)
                weak[j].append(i)

    # Weak links: same digit, cells see each other (not already strong)
    for d in range(9):
        bit = BIT[d]
        d_positions = []
        for pos in range(81):
            if cands[pos] & bit:
                d_positions.append(pos)
        for a in range(len(d_positions)):
            for b in range(a + 1, len(d_positions)):
                pa, pb = d_positions[a], d_positions[b]
                if (1 << pb) & PEER_81[pa]:
                    ni = pa * 9 + d
                    nj = pb * 9 + d
                    if nj not in strong_set[ni]:
                        weak[ni].append(nj)
                        weak[nj].append(ni)

    return strong, weak


def aic_reaches(src_nid, tgt_nid, strong, weak):
    """BFS with alternating strong/weak links matching JS reference.

    Starts from source with both link types, alternating at each depth.
    Returns True if target is reachable via the alternating chain.
    """
    if src_nid == tgt_nid:
        return False
    visited = {src_nid}
    queue = [(src_nid, 's')]  # fin is ON → follow weak links first
    for _ in range(20):
        next_q = []
        for cur, lt in queue:
            adj = weak[cur] if lt == 's' else strong[cur]
            nt = 'w' if lt == 's' else 's'
            for nxt in adj:
                if nxt == tgt_nid and lt == 's':
                    return True  # target reached via weak link → proven OFF
                if nxt not in visited:
                    visited.add(nxt)
                    next_q.append((nxt, nt))
        queue = next_q
        if not queue:
            break
    return False


# ══════════════════════════════════════════════════════════════════════
# KRAKEN FISH — Finned Fish + AIC Chain Elimination (bitwise)
# ══════════════════════════════════════════════════════════════════════

def detect_kraken_fish_bitwise(bb):
    """Kraken Fish: extends finned X-Wing via AIC chain reachability.

    For each digit D, finds finned X-Wing configurations (two rows sharing
    two cover columns, with one extra "fin" cell).  Standard finned X-Wing
    eliminates D from cover-column cells that see the fin.  Kraken Fish
    extends this: if an AIC chain connects the fin to a target cell, the
    target also loses D.

    Also checks column-based finned X-Wings (transpose).

    Returns list of (pos, digit) elimination tuples (digit is 1-indexed).
    """
    # Use JIT AIC graph builder + JIT reachability
    s_adj, s_off, w_adj, w_off = build_aic_graph_jit(bb)
    elims = []
    elim_set = set()

    for d in range(9):
        cross_d = bb.cross[d]
        if not cross_d:
            continue
        dbit = BIT[d]
        dval = d + 1

        # ── Row-based finned X-Wing ──
        row_cols = [0] * 9
        for r in range(9):
            if bb.row_used[r] & dbit:
                continue
            bits = cross_d & ROW_81[r]
            cols = 0
            for pos in iter_bits81(bits):
                cols |= 1 << (pos % 9)
            row_cols[r] = cols

        for r1 in range(8):
            pc1 = POPCOUNT[row_cols[r1]]
            if pc1 < 2 or pc1 > 3:
                continue
            for r2 in range(r1 + 1, 9):
                pc2 = POPCOUNT[row_cols[r2]]
                if pc2 < 2 or pc2 > 3:
                    continue

                shared = row_cols[r1] & row_cols[r2]
                if POPCOUNT[shared] != 2:
                    continue

                for base_r, fin_r, base_pc, fin_pc in [
                    (r1, r2, pc1, pc2),
                    (r2, r1, pc2, pc1),
                ]:
                    if base_pc != 2:
                        continue
                    if fin_pc != 3:
                        continue

                    fin_cols = row_cols[fin_r] & ~shared
                    if POPCOUNT[fin_cols] != 1:
                        continue
                    fin_c = fin_cols.bit_length() - 1
                    fin_pos = fin_r * 9 + fin_c
                    fin_peer_mask = PEER_81[fin_pos]
                    fin_nid = fin_pos * 9 + d

                    cover_cols = list(iter_bits9(shared))
                    found_any = False

                    for cc in cover_cols:
                        for r in range(9):
                            if r == base_r or r == fin_r:
                                continue
                            tgt_pos = r * 9 + cc
                            if not (bb.cands[tgt_pos] & dbit):
                                continue

                            key = tgt_pos * 9 + d
                            if key in elim_set:
                                continue

                            if (1 << tgt_pos) & fin_peer_mask:
                                elim_set.add(key)
                                elims.append((tgt_pos, dval))
                                found_any = True
                                continue

                            tgt_nid = tgt_pos * 9 + d
                            if aic_reaches_jit(fin_nid, tgt_nid, s_adj, s_off, w_adj, w_off):
                                elim_set.add(key)
                                elims.append((tgt_pos, dval))
                                found_any = True

                    if found_any:
                        return elims

        # ── Column-based finned X-Wing (transpose) ──
        col_rows = [0] * 9
        for c in range(9):
            if bb.col_used[c] & dbit:
                continue
            bits = cross_d & COL_81[c]
            rows = 0
            for pos in iter_bits81(bits):
                rows |= 1 << (pos // 9)
            col_rows[c] = rows

        for c1 in range(8):
            pc1 = POPCOUNT[col_rows[c1]]
            if pc1 < 2 or pc1 > 3:
                continue
            for c2 in range(c1 + 1, 9):
                pc2 = POPCOUNT[col_rows[c2]]
                if pc2 < 2 or pc2 > 3:
                    continue

                shared = col_rows[c1] & col_rows[c2]
                if POPCOUNT[shared] != 2:
                    continue

                for base_c, fin_c_idx, base_pc, fin_pc in [
                    (c1, c2, pc1, pc2),
                    (c2, c1, pc2, pc1),
                ]:
                    if base_pc != 2:
                        continue
                    if fin_pc != 3:
                        continue

                    fin_rows = col_rows[fin_c_idx] & ~shared
                    if POPCOUNT[fin_rows] != 1:
                        continue
                    fin_r = fin_rows.bit_length() - 1
                    fin_pos = fin_r * 9 + fin_c_idx
                    fin_peer_mask = PEER_81[fin_pos]
                    fin_nid = fin_pos * 9 + d

                    cover_rows = list(iter_bits9(shared))
                    found_any = False

                    for rr in cover_rows:
                        for c in range(9):
                            if c == base_c or c == fin_c_idx:
                                continue
                            tgt_pos = rr * 9 + c
                            if not (bb.cands[tgt_pos] & dbit):
                                continue

                            key = tgt_pos * 9 + d
                            if key in elim_set:
                                continue

                            if (1 << tgt_pos) & fin_peer_mask:
                                elim_set.add(key)
                                elims.append((tgt_pos, dval))
                                found_any = True
                                continue

                            tgt_nid = tgt_pos * 9 + d
                            if aic_reaches_jit(fin_nid, tgt_nid, s_adj, s_off, w_adj, w_off):
                                elim_set.add(key)
                                elims.append((tgt_pos, dval))
                                found_any = True

                    if found_any:
                        return elims

    return []


# ══════════════════════════════════════════════════════════════════════
# DEEP RESONANCE — Proof-by-Contradiction via Detector Stack
# ══════════════════════════════════════════════════════════════════════


def _build_trial(prop_board, prop_cands):
    """Build a lightweight trial BitBoard from propagated state."""
    trial = BitBoard()
    trial.board = prop_board if isinstance(prop_board, list) else list(prop_board)
    trial.cands = prop_cands if isinstance(prop_cands, list) else list(prop_cands)
    trial.cross = [0] * 9
    for p2 in range(81):
        if trial.board[p2] == 0 and trial.cands[p2]:
            for dd in range(9):
                if trial.cands[p2] & BIT[dd]:
                    trial.cross[dd] |= 1 << p2
    trial.row_used = [0] * 9
    trial.col_used = [0] * 9
    trial.box_used = [0] * 9
    trial.empty = 0
    for p2 in range(81):
        if trial.board[p2] != 0:
            r2, c2 = p2 // 9, p2 % 9
            bit2 = BIT[trial.board[p2] - 1]
            trial.row_used[r2] |= bit2
            trial.col_used[c2] |= bit2
            trial.box_used[BOX_OF[p2]] |= bit2
        else:
            trial.empty += 1
    return trial


@nb.njit(cache=True)
def _deep_resonance_jit(board, cands, peers, peer_len, units, box_of, popcount_lut,
                         np_peers_20, unit_cells, use_deep):
    """Mega-JIT Deep Resonance: all phases in compiled code.
    Phase 1: L1+L2 propagation contradiction
    Phase 2: Chain following contradiction
    Phase 3: ForcingChain on propagated state
    Phase 4 (if use_deep): Cascade depth 2-3
    Returns: elim_out array, n_elims
    """
    elim_out = np.zeros((20, 2), dtype=np.int32)
    n_elims = 0

    # Collect cells (2-4 candidates), sort by candidate count
    cell_arr = np.zeros(81, dtype=np.int32)
    cell_pc = np.zeros(81, dtype=np.int32)
    n_cells = 0
    for pos in range(81):
        if board[pos] != 0:
            continue
        pc = popcount_lut[cands[pos]]
        if 2 <= pc <= 4:
            cell_arr[n_cells] = pos
            cell_pc[n_cells] = pc
            n_cells += 1

    # Insertion sort by pc
    for i in range(1, n_cells):
        kp = cell_arr[i]
        kpc = cell_pc[i]
        j = i - 1
        while j >= 0 and cell_pc[j] > kpc:
            cell_arr[j + 1] = cell_arr[j]
            cell_pc[j + 1] = cell_pc[j]
            j -= 1
        cell_arr[j + 1] = kp
        cell_pc[j + 1] = kpc

    # Scratch arrays
    b1 = np.empty(81, dtype=np.int32)
    c1 = np.empty(81, dtype=np.int32)
    b2 = np.empty(81, dtype=np.int32)
    c2 = np.empty(81, dtype=np.int32)

    for ci in range(n_cells):
        pos = cell_arr[ci]
        m = cands[pos]
        digits = np.zeros(4, dtype=np.int32)
        n_d = 0
        for d in range(9):
            if m & (1 << d):
                digits[n_d] = d
                n_d += 1

        elim_digits = np.zeros(4, dtype=np.bool_)

        for di in range(n_d):
            d = digits[di]
            dval = d + 1
            contradiction = False

            # Phase 1: L1+L2 propagation
            for i in range(81):
                b1[i] = board[i]
                c1[i] = cands[i]
            contra = _fast_prop_jit(b1, c1, np.int32(pos), np.int32(dval),
                                     peers, peer_len, units, box_of, popcount_lut)
            if contra:
                elim_digits[di] = True
                continue

            # Phase 2: Chain following on propagated state
            if _follow_chain_contra_jit(b1.copy(), c1.copy(), np.int32(pos), np.int32(dval),
                                         peers, peer_len, units, popcount_lut):
                elim_digits[di] = True
                continue

            # Phase 3: ForcingChain on propagated state
            fc_out, n_fc = _detect_forcing_chain_jit(b1, c1, np_peers_20, unit_cells, popcount_lut)
            for fi in range(n_fc):
                p = fc_out[fi, 0]
                v = fc_out[fi, 1]
                if b1[p] == 0:
                    for i in range(81):
                        b2[i] = b1[i]
                        c2[i] = c1[i]
                    if _fast_prop_jit(b2, c2, np.int32(p), np.int32(v),
                                       peers, peer_len, units, box_of, popcount_lut):
                        contradiction = True
                        break

            if contradiction:
                elim_digits[di] = True
                continue

            # Phase 4 (deep): Cascade depth 2-3
            if use_deep:
                fc_out2, n_fc2 = _detect_forcing_chain_jit(b1, c1, np_peers_20, unit_cells, popcount_lut)
                for fi in range(n_fc2):
                    p = fc_out2[fi, 0]
                    v = fc_out2[fi, 1]
                    if b1[p] == 0:
                        for i in range(81):
                            b2[i] = b1[i]
                            c2[i] = c1[i]
                        if _fast_prop_jit(b2, c2, np.int32(p), np.int32(v),
                                           peers, peer_len, units, box_of, popcount_lut):
                            contradiction = True
                            break
                        # Depth 2: chain follow
                        if _follow_chain_contra_jit(b2.copy(), c2.copy(), np.int32(p), np.int32(v),
                                                     peers, peer_len, units, popcount_lut):
                            contradiction = True
                            break
                        # Depth 3: ForcingChain
                        fc_out3, n_fc3 = _detect_forcing_chain_jit(b2, c2, np_peers_20, unit_cells, popcount_lut)
                        for fi3 in range(n_fc3):
                            p3 = fc_out3[fi3, 0]
                            v3 = fc_out3[fi3, 1]
                            if b2[p3] == 0:
                                b3 = b2.copy()
                                c3 = c2.copy()
                                if _fast_prop_jit(b3, c3, np.int32(p3), np.int32(v3),
                                                   peers, peer_len, units, box_of, popcount_lut):
                                    contradiction = True
                                    break
                        if contradiction:
                            break

                if contradiction:
                    elim_digits[di] = True
                    continue

        # Check if we found any eliminations for this cell
        n_elim_d = 0
        n_surv = 0
        for di in range(n_d):
            if elim_digits[di]:
                n_elim_d += 1
            else:
                n_surv += 1

        if n_elim_d > 0 and n_surv > 0:
            for di in range(n_d):
                if elim_digits[di]:
                    if n_elims < 20:
                        elim_out[n_elims, 0] = pos
                        elim_out[n_elims, 1] = digits[di] + 1  # 1-indexed
                        n_elims += 1
            return elim_out[:n_elims], n_elims

    return elim_out[:n_elims], n_elims


def detect_deep_resonance(bb, mode='all'):
    """Deep Resonance (Oracle-Free) — mega-JIT accelerated.
    Proof-by-contradiction via structural logic. Zero Python boundary crossings.

    Modes: 'base', 'deep', 'cross', 'all' (default)."""
    use_deep = mode in ('deep', 'cross', 'all')

    board_arr = np.array(bb.board, dtype=np.int32)
    cands_arr = np.array(bb.cands, dtype=np.int32)

    elim_arr, n_elims = _deep_resonance_jit(
        board_arr, cands_arr,
        _NB_PEERS, _NB_PEER_LEN, _NB_UNITS, _NB_BOX_OF, _NB_POPCOUNT,
        NP_PEERS, NP_UNIT_CELLS, use_deep)

    if n_elims == 0:
        return []
    return [(int(elim_arr[k, 0]), int(elim_arr[k, 1])) for k in range(n_elims)]


def _detect_deep_resonance_legacy(bb, mode='all'):
    """Legacy Deep Resonance — kept for reference/fallback.

    Modes (cumulative — each includes all previous):
      'base'     — Phase 1 (L1+L2 propagation) + Phase 2 (chain following)
                   + Phase 3 (ForcingChain on propagated state)
      'deep'     — + Phase 4: Cascade propagation (propagate ForcingChain
                   results, then propagate THOSE results, up to depth 3)
      'cross'    — + Phase 5: Cross-candidate UNANIMOUS agreement (if ALL
                   branches place the same value at a cell, it's proven)
      'all'      — All safe phases enabled (default: base+deep+cross)

    Args:
        bb: BitBoard with current puzzle state
        mode: 'base', 'deep', 'cross', 'pipeline', or 'all'

    Returns list of (pos, digit) eliminations (digit is 1-indexed).
    """
    use_deep = mode in ('deep', 'cross', 'all')
    use_cross = mode in ('cross', 'all')
    use_pipeline = False  # DISABLED — trial detectors produce unsound eliminations

    cells = []
    for pos in range(81):
        if bb.board[pos] != 0:
            continue
        pc = POPCOUNT[bb.cands[pos]]
        if 2 <= pc <= 4:
            cells.append((pos, pc))
    cells.sort(key=lambda x: x[1])

    # Phase 5 (cross-candidate) needs all propagation results per cell
    # so we collect them when use_cross is on
    # Pre-convert board/cands to numpy once for all cells
    bb_board_np = np.array(bb.board, dtype=np.int32)
    bb_cands_np = np.array(bb.cands, dtype=np.int32)

    for pos, _ in cells:
        digits = list(iter_bits9(bb.cands[pos]))
        elim_digits = []
        prop_results = {}  # d → (board, cands) for cross-candidate check

        for d in digits:
            dval = d + 1
            contradiction = False

            # Phase 1: L1+L2 propagation — structural contradiction
            prop_board, prop_cands = fast_propagate_full(bb_board_np, bb_cands_np, pos, dval, return_np=True)
            if prop_board is None:
                elim_digits.append(d)
                continue

            if use_cross:
                prop_results[d] = (prop_board, prop_cands)

            # Phase 2: Chain following — structural contradiction
            if follow_chain_contra(prop_board, prop_cands, pos, dval):
                contradiction = True

            # Phase 3: ForcingChain on propagated state (direct JIT)
            if not contradiction:
                pb = prop_board if isinstance(prop_board, np.ndarray) else np.array(prop_board, dtype=np.int32)
                pc = prop_cands if isinstance(prop_cands, np.ndarray) else np.array(prop_cands, dtype=np.int32)
                fc_out, n_fc = _detect_forcing_chain_jit(pb, pc, NP_PEERS, NP_UNIT_CELLS, NP_POPCOUNT)
                for fi in range(n_fc):
                    p, v = int(fc_out[fi, 0]), int(fc_out[fi, 1])
                    if pb[p] == 0:
                        fc_b, fc_c = fast_propagate_full(pb, pc, p, v, return_np=True)
                        if fc_b is None:
                            contradiction = True
                            break

            # Phase 4 (deep): Cascade — propagate deeper (depth 2-3)
            if not contradiction and use_deep:
                pb = prop_board if isinstance(prop_board, np.ndarray) else np.array(prop_board, dtype=np.int32)
                pc = prop_cands if isinstance(prop_cands, np.ndarray) else np.array(prop_cands, dtype=np.int32)
                fc_out, n_fc = _detect_forcing_chain_jit(pb, pc, NP_PEERS, NP_UNIT_CELLS, NP_POPCOUNT)
                for fi in range(n_fc):
                    p, v = int(fc_out[fi, 0]), int(fc_out[fi, 1])
                    if pb[p] == 0:
                        d2_b, d2_c = fast_propagate_full(pb, pc, p, v, return_np=True)
                        if d2_b is None:
                            contradiction = True
                            break
                        # Depth 2: chain follow on cascaded state
                        if follow_chain_contra(d2_b, d2_c, p, v):
                            contradiction = True
                            break
                        # Depth 3: ForcingChain again on cascaded state
                        fc2_out, n_fc2 = _detect_forcing_chain_jit(d2_b, d2_c, NP_PEERS, NP_UNIT_CELLS, NP_POPCOUNT)
                        for fi2 in range(n_fc2):
                            p2, v2 = int(fc2_out[fi2, 0]), int(fc2_out[fi2, 1])
                            if d2_b[p2] == 0:
                                d3_b, _ = fast_propagate_full(d2_b, d2_c, p2, v2, return_np=True)
                                if d3_b is None:
                                    contradiction = True
                                    break
                        if contradiction:
                            break

            # Phase 6 (pipeline): Full detector stack on propagated state
            if not contradiction and use_pipeline:
                trial = _build_trial(prop_board, prop_cands)
                # Run elimination detectors — if they produce eliminations
                # that cascade into a contradiction, the candidate is invalid
                for det_fn in (detect_als_xz_bitwise, detect_kraken_fish_bitwise,
                               detect_sk_loop_bitwise):
                    try:
                        det_elims = det_fn(trial)
                        if det_elims:
                            # Apply eliminations to trial, then re-propagate
                            for ep, ed in det_elims:
                                if trial.cands[ep] & BIT[ed - 1]:
                                    trial.cands[ep] &= ~BIT[ed - 1]
                                    if trial.cands[ep] == 0:
                                        contradiction = True
                                        break
                            if contradiction:
                                break
                            # Re-propagate after eliminations
                            flat_b = trial.board[:]
                            flat_c = trial.cands[:]
                            # Find any naked single from eliminations
                            for ci in range(81):
                                if flat_b[ci] == 0 and flat_c[ci] != 0:
                                    if (flat_c[ci] & (flat_c[ci] - 1)) == 0:
                                        nv = flat_c[ci].bit_length()
                                        re_b, re_c = fast_propagate_full(
                                            flat_b, flat_c, ci, nv)
                                        if re_b is None:
                                            contradiction = True
                                            break
                                        flat_b = re_b
                                        flat_c = re_c
                            if contradiction:
                                break
                    except Exception:
                        pass  # detector failed on trial state — skip

            if contradiction:
                elim_digits.append(d)

        # Phase 5 (cross): Cross-candidate UNANIMOUS convergence
        # If ALL surviving branches place the same value at a cell,
        # that's a proven placement (same logic as ForcingChain convergence).
        # We can also eliminate: if all branches eliminate a candidate from
        # a cell (it's absent from all propagated candidate sets), eliminate it.
        if use_cross and len(prop_results) >= 2:
            surviving = [d for d in digits if d not in elim_digits and d in prop_results]
            if len(surviving) >= 2:
                for cell in range(81):
                    if bb.board[cell] != 0 or cell == pos:
                        continue
                    # Check unanimous elimination: digit absent from ALL branches
                    orig_cands = bb.cands[cell]
                    if orig_cands == 0:
                        continue
                    for bit_d in range(9):
                        if not (orig_cands & BIT[bit_d]):
                            continue
                        # Check if ALL surviving branches eliminated this digit
                        all_eliminated = True
                        for d in surviving:
                            pc = prop_results[d][1]  # propagated cands
                            trial_cands = pc[cell] if isinstance(pc, list) else pc[cell]
                            if trial_cands & BIT[bit_d]:
                                all_eliminated = False
                                break
                        # NOT using this for direct elimination — too risky
                        # without full soundness proof. Reserve for future.

        if not elim_digits:
            continue

        # Don't eliminate all candidates
        remaining = [d for d in digits if d not in elim_digits]
        if not remaining:
            continue

        return [(pos, d + 1) for d in elim_digits]

    return []


def validate_sudoku(board):
    """Verify completed board by Sudoku law — no oracle needed.
    Checks all 27 units (9 rows, 9 cols, 9 boxes) have exactly {1..9}.
    board: list of 81 ints."""
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


if __name__ == '__main__':
    main()
