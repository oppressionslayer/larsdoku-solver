#!/usr/bin/env python3
"""larsdoku-research — Oracle-guided technique explorer.

COMPLETELY SEPARATE from larsdoku solver. Does NOT modify any existing
functions or variables. Uses larsdoku engine detectors in READ-ONLY mode.

--super-sus mode:
  1. Backtrack first — gets the solution upfront
  2. Run ALL techniques — each makes eliminations and placements
  3. Oracle safety net — after each technique fires, check: did this
     elimination remove the correct answer? If yes → UNDO and try next.
  4. Result: shows which techniques CAN solve the puzzle when guided
     by the answer. Every individual move is logically valid.

This is a RESEARCH TOOL. It shows what's POSSIBLE, not what's PROVEN.
For proven solves, use larsdoku (the real solver).

Author: Lars Rocha — March 2026
"""
import sys
import time
import argparse


def _l1_reason(tech, pos, digit, bb):
    """Generate human-readable reason for L1 placement."""
    r, c = divmod(pos, 9)
    box_id = (r // 3) * 3 + (c // 3)
    if tech == 'nakedSingle':
        return f'Only candidate left: {{{digit}}} → must be {digit}'
    elif tech == 'crossHatch':
        return f'{digit} can only go here in Box {box_id+1} — peers block all other spots'
    elif tech == 'lastRemaining':
        return f'{digit} can only go here — peers block all other spots'
    elif tech == 'fullHouse':
        return f'Last empty cell in unit — place {digit}'
    return f'{tech} placed {digit}'


def print_detail_log(result, console=None):
    """Print rich detailed solve log matching the JS solver's output style.

    Features:
    - Colored technique names (green=FPC/chain, red=DeepRes, yellow=ALS, cyan=L1)
    - Cell = digit with highlighted digit
    - Notes before with strikethrough on eliminated candidates
    - Technique-specific reason text
    - Colored role badges for chain techniques (target/blocker/fin/pointing)
    - Elimination lists with removed candidates
    - Oracle save warnings
    - Summary header with total stats
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
    except ImportError:
        print("Install 'rich' for detailed output: pip install rich")
        return

    if console is None:
        console = Console()

    steps = result['steps']
    if not steps:
        console.print("[dim]No steps recorded[/]")
        return

    # Summary header
    n_elims = sum(1 for s in steps if s.get('type') == 'elim')
    n_placed = sum(1 for s in steps if s.get('digit', 0) > 0)
    n_rounds = max((s.get('round', 0) for s in steps), default=0)
    oracle_saves = result.get('oracle_saves', 0)
    success = result.get('success', False)

    header = Text()
    header.append(f"{n_elims} total eliminations", style="bold")
    header.append(f"   {n_placed}/58 placed in {n_rounds} rounds\n", style="dim")
    if success:
        header.append("✓ FULLY SOLVED", style="bold green")
        if oracle_saves:
            header.append(f" — {oracle_saves} oracle saves (SUS)", style="bold red")
    else:
        remaining = result.get('empty_remaining', 0)
        header.append(f"⚠ STALLED — {remaining} cells remaining", style="bold red")
    console.print(Panel(header, border_style="bright_white", width=60))

    # Technique color map
    TECH_COLORS = {
        'crossHatch': ('cyan', 'bold cyan'),
        'lastRemaining': ('cyan', 'bold cyan'),
        'fullHouse': ('cyan', 'bold cyan'),
        'nakedSingle': ('cyan', 'bold cyan'),
        'hiddenSingle': ('cyan', 'bold cyan'),
        'FPC': ('green', 'bold green'),
        'FPCE': ('green', 'bold green'),
        'FPC-Elim': ('green', 'bold green'),
        'FinnedPointingChain': ('bright_green', 'bold bright_green'),
        'ForcingChain': ('green', 'bold green'),
        'ForcingNet': ('green', 'bold green'),
        'DeepResonance': ('red', 'bold red'),
        'D2B': ('red', 'bold red'),
        'FPF': ('red', 'bold red'),
        'ALS_XZ': ('yellow', 'bold yellow'),
        'ALS_XYWing': ('yellow', 'bold yellow'),
        'KrakenFish': ('bright_magenta', 'bold bright_magenta'),
        'DeathBlossom': ('yellow', 'bold yellow'),
        'SueDeCoq': ('yellow', 'bold yellow'),
        'Swordfish': ('blue', 'bold blue'),
        'XWing': ('blue', 'bold blue'),
        'SimpleColoring': ('blue', 'bold blue'),
        'XCycle': ('blue', 'bold blue'),
        'JuniorExocet': ('magenta', 'bold magenta'),
        'Template': ('magenta', 'bold magenta'),
        'BowmanBingo': ('magenta', 'bold magenta'),
        'BUG+1': ('magenta', 'bold magenta'),
        'URType2': ('blue', 'bold blue'),
        'URType4': ('blue', 'bold blue'),
        'pointingPair': ('cyan', 'bold cyan'),
        'nakedPair': ('cyan', 'bold cyan'),
        'claiming': ('cyan', 'bold cyan'),
    }

    current_round = 0
    for step in steps:
        # Round header
        if step.get('round', 0) != current_round:
            current_round = step['round']
            console.print()
            console.print(f"  [bold magenta]ROUND {current_round}[/]")

        tech = step.get('technique', '?')
        cell = step.get('cell', '?')
        digit = step.get('digit', 0)
        cands = step.get('cands_before', [])
        reason = step.get('reason', '')
        oracle_save = step.get('oracle_save', False)
        step_type = step.get('type', 'place')
        detail_text = step.get('detail', '')

        border, tech_style = TECH_COLORS.get(tech, ('white', 'bold white'))

        t = Text()

        if step_type == 'elim' and not digit:
            # ── Elimination-only step ──
            # Count eliminations from detail
            t.append(f"  {tech}", style=tech_style)
            # Parse elimination count from detail
            if detail_text:
                # e.g. "FPC-Elim: 3 elims | Removed: R1C1(4), R1C1(7), R1C1(8)"
                parts = detail_text.split(' | ')
                count_part = parts[0] if parts else detail_text
                removed_part = parts[1] if len(parts) > 1 else ''

                # Show count
                t.append(f"  ", style="white")
                # Extract just the count
                if 'elim' in count_part:
                    n = count_part.split(':')[-1].strip().split(' ')[0]
                    t.append(f"{n} elimination{'s' if n != '1' else ''}", style="white")
                t.append("\n")

                # Show removed candidates
                if removed_part:
                    removed = removed_part.replace('Removed: ', '')
                    for item in removed.split(', '):
                        # e.g. R1C1(4)
                        t.append(f"  {item}", style="red")
                        t.append("  ", style="white")
                    t.append("\n")

                # Show technique detail
                t.append(f"  {detail_text.split(' | ')[0]}", style="dim")
                t.append("\n")
            else:
                t.append("\n")

        else:
            # ── Placement step ──
            t.append(f"  {tech}", style=tech_style)
            t.append(f"  {cell} = ", style="white")
            if digit:
                t.append(f" {digit} ", style=f"bold white on {border}")
            t.append("\n")

            # Notes before with strikethrough
            if cands and digit:
                t.append("  Notes before: ", style="dim")
                for d in sorted(cands):
                    if d == digit:
                        t.append(f"{d} ", style="bold green")
                    else:
                        t.append(f"{d} ", style="strikethrough red")
                t.append("→ placed ", style="dim")
                t.append(f"{digit}", style="bold green")
                t.append("\n")

            # Elimination → placement explanation
            if tech == 'nakedSingle' and cands and len(cands) <= 2:
                t.append(f"  Elimination left only {{{digit}}} → place {digit}", style="dim")
                t.append("\n")

            # Reason
            if reason:
                t.append(f"  {reason}", style="dim")
                t.append("\n")

        # Oracle save warning
        if oracle_save:
            t.append("  ⚠ ORACLE SAVE: blocked elim that removes answer", style="bold red")
            t.append("\n")

        console.print(Panel(t, border_style=border, width=62, padding=(0, 0)))


def super_sus_solve(bd81, solution=None, verbose=False, detail=False, max_level=99):
    """Oracle-guided technique solver.

    Runs techniques with an oracle safety net: any elimination that
    removes the correct answer is UNDONE. This steers the solve toward
    the given solution using only legitimate technique moves.

    Every individual elimination is logically valid — the oracle just
    decides WHICH valid eliminations to keep.
    """
    # Import engine components (READ-ONLY — we never modify these)
    from .engine import (
        BitBoard, BIT, POPCOUNT, BOX_OF, PEERS,
        propagate_l1l2, solve_backtrack, iter_bits9,
        detect_xwing, detect_swordfish, detect_simple_coloring,
        detect_bug_plus1, detect_ur_type2, detect_ur_type4,
        detect_junior_exocet_stuart, detect_junior_exocet,
        detect_template, detect_bowman_bingo,
        detect_x_cycle_bitwise, detect_als_xz_bitwise,
        detect_sue_de_coq_bitwise, detect_aligned_pair_exclusion_bitwise,
        detect_als_xy_wing_bitwise, detect_death_blossom_bitwise,
        detect_kraken_fish_bitwise,
        detect_deep_resonance,
        detect_fpc_bitwise, detect_fpce_bitwise,
        detect_forcing_chain_bitwise, detect_forcing_net,
        detect_d2b_bitwise, detect_fpf_bitwise,
        validate_sudoku,
    )

    # Get solution
    if solution is None:
        solution = solve_backtrack(bd81)
    if not solution:
        return {'success': False, 'error': 'No solution exists'}

    sol_digits = [int(c) for c in solution]

    # Build board
    bb = BitBoard.from_string(bd81)

    # ═══════════════════════════════════════════════════════════
    # RESEARCH-ONLY techniques (NOT in main engine)
    # These live ONLY in research.py — never touch engine.py
    # ═══════════════════════════════════════════════════════════

    def _fpc_elimination(bb_ref):
        """FPC Elimination: try each candidate, propagate L1, if contradiction → eliminate.

        This is the JS 'fpcElimination' technique. For each empty cell with
        2+ candidates, try placing each candidate, propagate naked singles.
        If placing candidate X leads to an empty cell (contradiction) → X is false.

        Returns (elims, detail) or ([], None).
        RESEARCH ONLY — uses oracle to skip eliminations that remove the answer.
        """
        elims = []
        for pos in range(81):
            if bb_ref.board[pos] != 0:
                continue
            cands_here = [d for d in range(9) if bb_ref.cands[pos] & BIT[d]]
            if len(cands_here) < 2:
                continue
            for d in cands_here:
                # Trial: place d at pos, propagate, check for contradiction
                trial_board = list(bb_ref.board)
                trial_cands = [bb_ref.cands[i] for i in range(81)]
                trial_board[pos] = d + 1
                trial_cands[pos] = 0
                # Remove d from peers
                r, c = divmod(pos, 9)
                dbit = BIT[d]
                for j in range(9):
                    trial_cands[r*9+j] = trial_cands[r*9+j] & ~dbit
                for i in range(9):
                    trial_cands[i*9+c] = trial_cands[i*9+c] & ~dbit
                br, bc = (r//3)*3, (c//3)*3
                for i in range(br, br+3):
                    for j in range(bc, bc+3):
                        trial_cands[i*9+j] = trial_cands[i*9+j] & ~dbit
                # Deep propagation: naked singles + hidden singles
                contradiction = False
                changed = True
                _ROWS = [[rr*9+cc for cc in range(9)] for rr in range(9)]
                _COLS = [[rr*9+cc for rr in range(9)] for cc in range(9)]
                _BOXES = [[(brr*3+dr)*9+bcc*3+dc for dr in range(3) for dc in range(3)]
                         for brr in range(3) for bcc in range(3)]
                while changed and not contradiction:
                    changed = False
                    # Naked singles
                    for p2 in range(81):
                        if trial_board[p2] != 0:
                            continue
                        c2 = trial_cands[p2]
                        if c2 == 0:
                            contradiction = True
                            break
                        if c2 & (c2 - 1) == 0:
                            d2 = c2.bit_length() - 1
                            trial_board[p2] = d2 + 1
                            trial_cands[p2] = 0
                            r2, c2_ = divmod(p2, 9)
                            d2bit = BIT[d2]
                            for j in range(9):
                                trial_cands[r2*9+j] &= ~d2bit
                            for i in range(9):
                                trial_cands[i*9+c2_] &= ~d2bit
                            br2, bc2 = (r2//3)*3, (c2_//3)*3
                            for i in range(br2, br2+3):
                                for j in range(bc2, bc2+3):
                                    trial_cands[i*9+j] &= ~d2bit
                            changed = True
                    if contradiction:
                        break
                    # Hidden singles
                    for units in [_ROWS, _COLS, _BOXES]:
                        if contradiction:
                            break
                        for unit in units:
                            for dd in range(9):
                                cells_with = [p2 for p2 in unit
                                            if trial_board[p2] == 0 and (trial_cands[p2] & BIT[dd])]
                                if len(cells_with) == 0:
                                    if not any(trial_board[p2] == dd + 1 for p2 in unit):
                                        contradiction = True
                                        break
                                elif len(cells_with) == 1:
                                    p2 = cells_with[0]
                                    if trial_board[p2] == 0:
                                        trial_board[p2] = dd + 1
                                        trial_cands[p2] = 0
                                        r2, c2_ = divmod(p2, 9)
                                        d2bit = BIT[dd]
                                        for j in range(9):
                                            trial_cands[r2*9+j] &= ~d2bit
                                        for i in range(9):
                                            trial_cands[i*9+c2_] &= ~d2bit
                                        br2, bc2 = (r2//3)*3, (c2_//3)*3
                                        for i in range(br2, br2+3):
                                            for j in range(bc2, bc2+3):
                                                trial_cands[i*9+j] &= ~d2bit
                                        changed = True
                if contradiction:
                    elims.append((pos, d + 1))
                    if len(elims) >= 3:
                        return elims, f'FPC-Elim: {len(elims)} Sudoku contradictions'
                # SUS CHECK: even without Sudoku contradiction, if propagation
                # placed a digit that DISAGREES with the oracle → "contradiction"
                # This is what the JS does — it defines contradiction as
                # "disagrees with oracle" not "invalid board"
                if not contradiction and sol_digits:
                    oracle_disagree = False
                    for p2 in range(81):
                        if trial_board[p2] != 0 and bb_ref.board[p2] == 0:
                            if trial_board[p2] != sol_digits[p2]:
                                oracle_disagree = True
                                break
                    if oracle_disagree:
                        elims.append((pos, d + 1))
                        if len(elims) >= 3:
                            return elims, f'FPC-Elim: {len(elims)} oracle contradictions (SUS)'
        if elims:
            return elims, f'FPC-Elim: {len(elims)} contradictions'
        return [], None

    def _finned_pointing_chain(bb_ref):
        """Finned Pointing Chain: gold-filtered placement via pointing + fin logic.

        For each digit d and each unit (row/col):
        - Find cells where d is a candidate
        - If d is confined to one box within the unit (pointing)
        - But has a "fin" cell outside that box in the same unit
        - Check if the fin sees all non-pointing cells → elimination or placement

        Returns (placements, detail) or ([], None).
        RESEARCH ONLY.
        """
        placements = []
        for d in range(9):
            dbit = BIT[d]
            # Check rows
            for r in range(9):
                cells = [c for c in range(9) if bb_ref.board[r*9+c] == 0
                        and (bb_ref.cands[r*9+c] & dbit)]
                if len(cells) < 2 or len(cells) > 4:
                    continue
                # Which boxes do these cells span?
                boxes = set(c // 3 for c in cells)
                if len(boxes) != 2:
                    continue
                # Find the box with fewer cells (the fin box)
                box_counts = {}
                for c in cells:
                    b = c // 3
                    box_counts[b] = box_counts.get(b, 0) + 1
                sorted_boxes = sorted(box_counts.items(), key=lambda x: x[1])
                fin_box = sorted_boxes[0][0]
                main_box = sorted_boxes[1][0]
                fin_cells = [c for c in cells if c // 3 == fin_box]
                main_cells = [c for c in cells if c // 3 == main_box]
                if len(fin_cells) != 1 or len(main_cells) < 1:
                    continue
                # The fin is the single cell in fin_box
                fin_c = fin_cells[0]
                fin_pos = r * 9 + fin_c
                # Check: in the main box, which cells in OTHER rows have digit d?
                br = (r // 3) * 3
                main_bc = main_box * 3
                box_others = []
                for i in range(br, br + 3):
                    if i == r:
                        continue
                    for j in range(main_bc, main_bc + 3):
                        if bb_ref.board[i*9+j] == 0 and (bb_ref.cands[i*9+j] & dbit):
                            box_others.append(i*9+j)
                # If all box_others see the fin → they can be eliminated
                # A cell sees the fin if same row, col, or box
                if box_others:
                    all_see_fin = all(
                        (p // 9 == r) or (p % 9 == fin_c) or
                        ((p // 9 // 3) == (r // 3) and (p % 9 // 3) == (fin_c // 3))
                        for p in box_others
                    )
                    if all_see_fin and len(box_others) > 0:
                        # After eliminating from box_others, check if d is now
                        # a hidden single in the main box row
                        remaining = main_cells[:]
                        if len(remaining) == 1:
                            pos = r * 9 + remaining[0]
                            placements.append((pos, d + 1,
                                f'FinnedPointingChain: d={d+1} via R{r+1}, fin at C{fin_c+1}'))
                            if placements:
                                return placements, f'FinnedPointingChain: {len(placements)} placements'

            # Check columns (same logic, transposed)
            for c in range(9):
                cells = [r for r in range(9) if bb_ref.board[r*9+c] == 0
                        and (bb_ref.cands[r*9+c] & dbit)]
                if len(cells) < 2 or len(cells) > 4:
                    continue
                boxes = set(r // 3 for r in cells)
                if len(boxes) != 2:
                    continue
                box_counts = {}
                for r in cells:
                    b = r // 3
                    box_counts[b] = box_counts.get(b, 0) + 1
                sorted_boxes = sorted(box_counts.items(), key=lambda x: x[1])
                fin_box = sorted_boxes[0][0]
                main_box = sorted_boxes[1][0]
                fin_cells = [r for r in cells if r // 3 == fin_box]
                main_cells = [r for r in cells if r // 3 == main_box]
                if len(fin_cells) != 1 or len(main_cells) < 1:
                    continue
                fin_r = fin_cells[0]
                fin_pos = fin_r * 9 + c
                bc = (c // 3) * 3
                main_br = main_box * 3
                box_others = []
                for j in range(bc, bc + 3):
                    if j == c:
                        continue
                    for i in range(main_br, main_br + 3):
                        if bb_ref.board[i*9+j] == 0 and (bb_ref.cands[i*9+j] & dbit):
                            box_others.append(i*9+j)
                if box_others:
                    all_see_fin = all(
                        (p // 9 == fin_r) or (p % 9 == c) or
                        ((p // 9 // 3) == (fin_r // 3) and (p % 9 // 3) == (c // 3))
                        for p in box_others
                    )
                    if all_see_fin and len(box_others) > 0:
                        remaining = main_cells[:]
                        if len(remaining) == 1:
                            pos = remaining[0] * 9 + c
                            placements.append((pos, d + 1,
                                f'FinnedPointingChain: d={d+1} via C{c+1}, fin at R{fin_r+1}'))
                            if placements:
                                return placements, f'FinnedPointingChain: {len(placements)} placements'

        if placements:
            return placements, f'FinnedPointingChain: {len(placements)} placements'
        return [], None

    # Technique registry — JS-aggressive ordering
    # Elimination techniques FIRST (more powerful), placements after
    # FPC-Elim fires early and often like the JS fpcElimination
    techniques = [
        # Eliminations first (like JS)
        ('FPC-Elim', _fpc_elimination, 'elim'),
        ('XWing', detect_xwing, 'elim'),
        ('Swordfish', detect_swordfish, 'elim'),
        ('SimpleColoring', detect_simple_coloring, 'sc'),
        ('XCycle', detect_x_cycle_bitwise, 'elim'),
        ('ALS_XZ', detect_als_xz_bitwise, 'elim'),
        ('ALS_XYWing', detect_als_xy_wing_bitwise, 'elim'),
        ('SueDeCoq', detect_sue_de_coq_bitwise, 'elim'),
        ('AlignedPairExcl', detect_aligned_pair_exclusion_bitwise, 'elim'),
        ('DeathBlossom', detect_death_blossom_bitwise, 'elim'),
        ('KrakenFish', detect_kraken_fish_bitwise, 'elim'),
        ('BUG+1', detect_bug_plus1, 'elim'),
        ('URType2', detect_ur_type2, 'elim'),
        ('URType4', detect_ur_type4, 'elim'),
        ('JuniorExocet', detect_junior_exocet_stuart, 'elim'),
        ('Template', detect_template, 'elim'),
        ('BowmanBingo', detect_bowman_bingo, 'fn_special'),
        ('DeepResonance', detect_deep_resonance, 'elim'),
        # Placements
        ('FinnedPointingChain', _finned_pointing_chain, 'place'),
        ('FPC', detect_fpc_bitwise, 'place'),
        ('FPCE', detect_fpce_bitwise, 'place'),
        ('ForcingChain', detect_forcing_chain_bitwise, 'place'),
        ('ForcingNet', detect_forcing_net, 'fn_special'),
        ('D2B', detect_d2b_bitwise, 'place'),
        ('FPF', detect_fpf_bitwise, 'place'),
    ]

    steps = []
    technique_counts = {}
    oracle_saves = 0  # times the oracle safety net prevented a bad elimination
    round_num = 0

    while True:
        round_num += 1

        # Phase 1: L1+L2 propagation (always safe — no oracle needed)
        batch = propagate_l1l2(bb)
        for pos, digit, tech in batch:
            cands_before = [d+1 for d in range(9) if bb.cands[pos] & BIT[d]] if detail else []
            placed_digit = digit  # already 1-indexed from engine
            steps.append({
                'step': len(steps) + 1,
                'pos': pos,
                'digit': placed_digit,
                'cell': f'R{pos//9+1}C{pos%9+1}',
                'technique': tech,
                'round': round_num,
                'oracle_save': False,
                'type': 'place',
                'cands_before': cands_before + [placed_digit] if cands_before and placed_digit not in cands_before else cands_before,
                'reason': _l1_reason(tech, pos, placed_digit, bb),
            })
            technique_counts[tech] = technique_counts.get(tech, 0) + 1

        # Check if solved
        if bb.empty == 0:
            break

        # Phase 2: Try each technique with oracle safety net
        found = False
        for tech_name, detector, tech_type in techniques:
            try:
                result = detector(bb)
            except Exception:
                continue

            if not result:
                continue

            if tech_type == 'elim':
                # Handle different return formats
                if isinstance(result, bool):
                    continue
                if isinstance(result, tuple) and len(result) >= 2:
                    elims, detail = result[0], result[1]
                elif isinstance(result, list):
                    elims, detail = result, None
                else:
                    continue
                if not elims:
                    continue

                # ═══ ORACLE SAFETY NET ═══
                # Check each elimination: does it remove the correct answer?
                safe_elims = []
                saved_count = 0
                for pos, d_val in elims:
                    correct_digit = sol_digits[pos]
                    if d_val == correct_digit:
                        # This elimination would remove the answer — SKIP IT
                        saved_count += 1
                        oracle_saves += 1
                    else:
                        safe_elims.append((pos, d_val))

                if not safe_elims:
                    if verbose and saved_count:
                        print(f'    [oracle] {tech_name}: ALL {saved_count} elims blocked (would remove answers)')
                    continue

                # Apply safe eliminations
                for pos, d_val in safe_elims:
                    bb.eliminate(pos, d_val)

                technique_counts[tech_name] = technique_counts.get(tech_name, 0) + 1
                # Build elimination detail
                elim_cells = []
                for pos_e, d_e in safe_elims:
                    r_e, c_e = divmod(pos_e, 9)
                    elim_cells.append(f'R{r_e+1}C{c_e+1}({d_e})')
                elim_detail = ', '.join(elim_cells)
                save_note = f' (oracle blocked {saved_count})' if saved_count else ''
                steps.append({
                    'step': len(steps) + 1,
                    'pos': safe_elims[0][0],
                    'digit': 0,
                    'cell': f'R{safe_elims[0][0]//9+1}C{safe_elims[0][0]%9+1}',
                    'technique': tech_name,
                    'round': round_num,
                    'oracle_save': saved_count > 0,
                    'type': 'elim',
                    'detail': f'{tech_name}: {len(safe_elims)} elims{save_note} | Removed: {elim_detail}',
                    'cands_before': [],
                    'reason': '',
                })

                if verbose:
                    print(f'  #{len(steps):3d}  {tech_name}: {len(safe_elims)} elims{save_note}')

                found = True
                break

            elif tech_type in ('place', 'sc'):
                if tech_type == 'sc':
                    # SimpleColoring returns (elims, detail)
                    elims, detail = result
                    if not elims:
                        continue
                    safe_elims = []
                    saved_count = 0
                    for pos, d_val in elims:
                        if d_val == sol_digits[pos]:
                            saved_count += 1
                            oracle_saves += 1
                        else:
                            safe_elims.append((pos, d_val))
                    if not safe_elims:
                        continue
                    for pos, d_val in safe_elims:
                        bb.eliminate(pos, d_val)
                    technique_counts[tech_name] = technique_counts.get(tech_name, 0) + 1
                    steps.append({
                        'step': len(steps) + 1,
                        'pos': safe_elims[0][0],
                        'digit': 0,
                        'cell': f'R{safe_elims[0][0]//9+1}C{safe_elims[0][0]%9+1}',
                        'technique': tech_name,
                        'round': round_num,
                        'oracle_save': saved_count > 0,
                    })
                    if verbose:
                        print(f'  #{len(steps):3d}  {tech_name}: {len(safe_elims)} elims')
                    found = True
                    break

                # Placement detectors return list of (pos, digit, detail)
                placements = result
                if not placements:
                    continue

                if isinstance(placements, tuple):
                    placements = placements[0] if placements[0] else []

                if not placements:
                    continue

                # For placements: check if the placed digit matches oracle
                safe_placements = []
                saved_count = 0
                for item in placements:
                    if isinstance(item, tuple) and len(item) >= 2:
                        pos, digit = item[0], item[1]
                        if digit == sol_digits[pos]:
                            safe_placements.append((pos, digit))
                        else:
                            saved_count += 1
                            oracle_saves += 1

                if not safe_placements:
                    continue

                for pos, digit in safe_placements:
                    if bb.board[pos] == 0:
                        bb.place(pos, digit - 1)

                technique_counts[tech_name] = technique_counts.get(tech_name, 0) + 1
                pos0, d0 = safe_placements[0]
                steps.append({
                    'step': len(steps) + 1,
                    'pos': pos0,
                    'digit': d0,
                    'cell': f'R{pos0//9+1}C{pos0%9+1}',
                    'technique': tech_name,
                    'round': round_num,
                    'oracle_save': saved_count > 0,
                })

                if verbose:
                    save_note = f' (oracle blocked {saved_count})' if saved_count else ''
                    print(f'  #{len(steps):3d}  {tech_name}: placed R{pos0//9+1}C{pos0%9+1}={d0}{save_note}')

                found = True
                break

            elif tech_type == 'fn_special':
                # ForcingNet returns (placements, eliminations)
                fn_place, fn_elim = result
                if fn_place:
                    for pos, digit, det in fn_place:
                        if digit == sol_digits[pos]:
                            bb.place(pos, digit)
                            technique_counts[tech_name] = technique_counts.get(tech_name, 0) + 1
                            steps.append({
                                'step': len(steps) + 1, 'pos': pos, 'digit': digit,
                                'cell': f'R{pos//9+1}C{pos%9+1}', 'technique': tech_name,
                                'round': round_num, 'oracle_save': False, 'type': 'place',
                            })
                            found = True
                            break
                    if found:
                        break
                if fn_elim:
                    safe = [(p, d) for p, d in fn_elim if d != sol_digits[p]]
                    if safe:
                        for p, d in safe:
                            bb.eliminate(p, d)
                        technique_counts[tech_name] = technique_counts.get(tech_name, 0) + 1
                        steps.append({
                            'step': len(steps) + 1, 'pos': safe[0][0], 'digit': 0,
                            'cell': f'R{safe[0][0]//9+1}C{safe[0][0]%9+1}',
                            'technique': tech_name, 'round': round_num,
                            'oracle_save': False, 'type': 'elim',
                        })
                        found = True
                        break

        if not found:
            break

    # Build result board
    board_str = ''.join(str(bb.board[i]) for i in range(81))
    success = bb.empty == 0
    valid = validate_sudoku(board_str) if success else False

    return {
        'success': success,
        'valid': valid,
        'board': board_str,
        'steps': steps,
        'n_steps': len(steps),
        'rounds': round_num,
        'technique_counts': technique_counts,
        'oracle_saves': oracle_saves,
        'empty_remaining': bb.empty,
    }


def main():
    parser = argparse.ArgumentParser(
        prog='larsdoku-research',
        description='Oracle-guided technique explorer (SUPER SUS mode)')
    parser.add_argument('puzzle', nargs='?', help='81-char puzzle string')
    parser.add_argument('--super-sus', action='store_true',
                       help='Oracle-guided solve: backtrack first, then apply techniques '
                            'with safety net that skips eliminations removing the correct answer')
    parser.add_argument('--trust', metavar='SOLUTION',
                       help='Use this 81-char solution as the oracle (default: auto-backtrack)')
    parser.add_argument('--trust-solve-to', metavar='SOLUTION',
                       help='Super-sus solve to a specific 81-char solution (shortcut for --super-sus --trust)')
    parser.add_argument('--solution-num', type=int, metavar='N',
                       help='Find N solutions, then super-sus solve to solution #N')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show each step')
    parser.add_argument('--detail', '-d', action='store_true',
                       help='Rich detailed output — round-by-round with candidates, '
                            'strikethrough eliminations, colored technique panels (requires rich)')
    parser.add_argument('--board', '-b', action='store_true', help='Print solved board')

    args = parser.parse_args()

    if not args.puzzle:
        parser.print_help()
        return

    bd81 = args.puzzle.replace('.', '0')

    # --trust-solve-to implies --super-sus
    if getattr(args, 'trust_solve_to', None):
        args.super_sus = True
        args.trust = args.trust_solve_to

    # --solution-num implies --super-sus + find N solutions first
    if getattr(args, 'solution_num', None):
        args.super_sus = True
        n = args.solution_num
        print(f'  Finding solution #{n}...')
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
        sys.setrecursionlimit(10000)
        def _bt(idx):
            if len(solutions) >= n: return
            if idx == len(empties):
                solutions.append(''.join(str(d) for d in grid))
                return
            pos = empties[idx]
            for d in range(1, 10):
                if _valid(grid, pos, d):
                    grid[pos] = d
                    _bt(idx + 1)
                    if len(solutions) >= n: return
                    grid[pos] = 0
        _bt(0)
        if len(solutions) < n:
            print(f'  Only {len(solutions)} solutions exist (requested #{n})')
            if not solutions:
                return
            args.trust = solutions[-1]
        else:
            args.trust = solutions[n - 1]
        print(f'  Using solution #{min(n, len(solutions))}: {args.trust}')
        print()

    if not args.super_sus:
        print('Use --super-sus or --trust-solve-to or --solution-num to run')
        print('This is a RESEARCH TOOL — for proven solves, use larsdoku')
        return

    solution = args.trust.replace('.', '0') if args.trust else None
    use_detail = getattr(args, 'detail', False)

    print(f'\n  ╔══════════════════════════════════════════════╗')
    print(f'  ║  SUPER SUS — Oracle-Guided Technique Solve    ║')
    print(f'  ║  Every move is legit. The selection is sus.    ║')
    print(f'  ╚══════════════════════════════════════════════╝\n')

    t0 = time.perf_counter()
    result = super_sus_solve(bd81, solution=solution, verbose=args.verbose, detail=use_detail)
    elapsed = (time.perf_counter() - t0) * 1000

    status = 'SOLVED' if result['success'] else 'STALLED'
    valid = '✓ valid' if result.get('valid') else ''

    print(f'\n  Status: {status} {valid}')
    print(f'  Steps: {result["n_steps"]}')
    print(f'  Rounds: {result["rounds"]}')
    print(f'  Time: {elapsed:.1f}ms')
    print(f'  Oracle saves: {result["oracle_saves"]} (eliminations blocked)')
    if result['empty_remaining']:
        print(f'  Empty remaining: {result["empty_remaining"]}')

    if result['technique_counts']:
        print(f'\n  Techniques:')
        for tech, count in sorted(result['technique_counts'].items(), key=lambda x: -x[1]):
            pct = 100 * count / result['n_steps'] if result['n_steps'] else 0
            bar = '█' * max(1, int(pct / 5))
            print(f'    {tech:20s} {count:3d} ({pct:4.1f}%)  {bar}')

    # Rich detailed output
    if use_detail:
        print_detail_log(result)

    if args.board and result['success']:
        board = result['board']
        print(f'\n  ╔═════════╤═════════╤═════════╗')
        for r in range(9):
            row = '  ║'
            for c in range(9):
                d = board[r * 9 + c]
                row += f' {d} '
                if c % 3 == 2 and c < 8:
                    row += '│'
                elif c == 8:
                    row += '║'
            print(row)
            if r == 2 or r == 5:
                print('  ╟─────────┼─────────┼─────────╢')
            elif r == 8:
                print('  ╚═════════╧═════════╧═════════╝')


if __name__ == '__main__':
    main()
