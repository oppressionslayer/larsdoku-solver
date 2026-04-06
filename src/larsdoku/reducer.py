"""Auto-reduce puzzles to find seed ancestry + reverse-lookup seeds in the Lars Seed Database.

Strategies:
  #1  Check Lars signature at EVERY strip step (not just the end)
  #2  Multi-order reduction (scan, reverse, + N random shuffles)
  #3  Zone-preserving strip priority (strip from dense regions first)
  #4  Signature-guided steering (bias strips toward known hash families)
  #5  Exhaustive combinatorial search (small remaining sets)

Usage from larsdoku CLI:
    larsdoku --auto-reduce <puzzle>
    larsdoku --seed-lookup <bd81_or_hash>
    larsdoku --reduce-solve <puzzle>
"""
from __future__ import annotations

import itertools
import random
import subprocess
import time

import numpy as np

from .engine import has_unique_solution, solve_backtrack
from .lars_forge import (
    LARS_SEEDS,
    LARS_SEEDS_HASHES,
    LARS_SEEDS_L1_HASHES,
    lars_mask_hash,
    lars_provenance,
)

RANDOM_ORDERINGS = 5


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

def _mask_from_puzzle(puzzle):
    return [1 if ch != "." and ch != "0" else 0 for ch in puzzle]


def _hash_distance(h1, h2):
    def _flatten(t):
        out = []
        for item in t:
            if isinstance(item, tuple):
                out.extend(_flatten(item))
            else:
                out.append(item)
        return out
    f1, f2 = _flatten(h1), _flatten(h2)
    if len(f1) != len(f2):
        return 999
    return sum(abs(a - b) for a, b in zip(f1, f2))


def _check_registry(puzzle):
    mask = _mask_from_puzzle(puzzle)
    h = str(lars_mask_hash(mask))
    if h in LARS_SEEDS_HASHES:
        return {"confidence": "exact (core seed)", "seed": LARS_SEEDS_HASHES[h], "hash": h}
    if h in LARS_SEEDS_L1_HASHES:
        return {"confidence": "L1 variant (high)", "seed": LARS_SEEDS_L1_HASHES[h], "hash": h}
    return None


def _all_known_hashes():
    return set(LARS_SEEDS_HASHES.keys()) | set(LARS_SEEDS_L1_HASHES.keys())


def _seed_technique(seed_bd81):
    seeds_data = LARS_SEEDS.get("seeds", {})
    techs = []
    if seed_bd81 in seeds_data.get("deepres", []):
        techs.append("DeepResonance")
    if seed_bd81 in seeds_data.get("d2b", []):
        techs.append("D2B")
    return techs or ["Unknown"]


def _seed_index(seed_bd81):
    seeds_data = LARS_SEEDS.get("seeds", {})
    for tech in ("deepres", "d2b"):
        pool = seeds_data.get(tech, [])
        if seed_bd81 in pool:
            return pool.index(seed_bd81)
    return None


def board_diagram(puzzle):
    lines = []
    for r in range(9):
        if r and r % 3 == 0:
            lines.append("------+-------+------")
        row_chars = []
        for c in range(9):
            if c and c % 3 == 0:
                row_chars.append("|")
            row_chars.append(puzzle[r * 9 + c])
        lines.append(" ".join(row_chars))
    return "\n".join(lines)


def _indent(text, prefix="    "):
    return "\n".join(prefix + line for line in text.split("\n"))


# ══════════════════════════════════════════════════════════════
# Strategy #3: zone-preserving strip priority
# ══════════════════════════════════════════════════════════════

def _density_order(puzzle):
    clue_positions = [i for i, ch in enumerate(puzzle) if ch != "." and ch != "0"]
    m = np.array(_mask_from_puzzle(puzzle), dtype=np.int8).reshape(9, 9)
    scores = {}
    for pos in clue_positions:
        r, c = pos // 9, pos % 9
        band = r // 3
        stack = c // 3
        box_r, box_c = (r // 3) * 3, (c // 3) * 3
        row_density = int(m[r, :].sum())
        col_density = int(m[:, c].sum())
        band_density = int(m[band * 3:(band + 1) * 3, :].sum())
        stack_density = int(m[:, stack * 3:(stack + 1) * 3].sum())
        box_density = int(m[box_r:box_r + 3, box_c:box_c + 3].sum())
        scores[pos] = row_density + col_density + band_density + stack_density + box_density
    return sorted(clue_positions, key=lambda p: -scores[p])


# ══════════════════════════════════════════════════════════════
# Strategy #4: signature-guided steering
# ══════════════════════════════════════════════════════════════

def _signature_guided_order(puzzle):
    known = _all_known_hashes()
    if not known:
        return [i for i, ch in enumerate(puzzle) if ch != "." and ch != "0"]
    known_tuples = []
    for h_str in list(known)[:200]:
        try:
            known_tuples.append(eval(h_str))
        except Exception:
            pass
    if not known_tuples:
        return [i for i, ch in enumerate(puzzle) if ch != "." and ch != "0"]
    clue_positions = [i for i, ch in enumerate(puzzle) if ch != "." and ch != "0"]
    b = list(puzzle)
    scores = {}
    for pos in clue_positions:
        orig = b[pos]
        b[pos] = "."
        trial_hash = lars_mask_hash(_mask_from_puzzle("".join(b)))
        trial_dist = min(_hash_distance(trial_hash, kt) for kt in known_tuples)
        scores[pos] = trial_dist
        b[pos] = orig
    return sorted(clue_positions, key=lambda p: scores[p])


# ══════════════════════════════════════════════════════════════
# Core reducer
# ══════════════════════════════════════════════════════════════

def reduce_with_tracking(puzzle, clue_order, label="scan"):
    b = list(puzzle)
    clue_positions = list(clue_order)
    removed = []
    matches = []
    match = _check_registry("".join(b))
    if match:
        matches.append({"clues": sum(1 for ch in b if ch != "."), "puzzle": "".join(b), "match": match})
    changed = True
    while changed:
        changed = False
        for pos in list(clue_positions):
            digit = b[pos]
            if digit == ".":
                continue
            b[pos] = "."
            if has_unique_solution("".join(b)):
                removed.append((pos, digit))
                clue_positions.remove(pos)
                changed = True
                current = "".join(b)
                match = _check_registry(current)
                if match:
                    clue_count = sum(1 for ch in current if ch != ".")
                    matches.append({"clues": clue_count, "puzzle": current, "match": match})
            else:
                b[pos] = digit
    return {"base": "".join(b), "removed": removed, "matches": matches, "label": label}


def exhaustive_reduce(puzzle, max_try_remove=3):
    clue_positions = [i for i, ch in enumerate(puzzle) if ch != "." and ch != "0"]
    extra_matches = []
    for k in range(1, min(max_try_remove + 1, len(clue_positions) + 1)):
        for combo in itertools.combinations(clue_positions, k):
            b = list(puzzle)
            for pos in combo:
                b[pos] = "."
            candidate = "".join(b)
            if has_unique_solution(candidate):
                match = _check_registry(candidate)
                if match:
                    clue_count = sum(1 for ch in candidate if ch != ".")
                    extra_matches.append({"clues": clue_count, "puzzle": candidate, "match": match, "combo_removed": combo})
    return extra_matches


# ══════════════════════════════════════════════════════════════
# Command: --auto-reduce
# ══════════════════════════════════════════════════════════════

def _normalize_puzzle(puzzle):
    """Normalize puzzle: replace 0 with . for display."""
    return puzzle.replace("0", ".")


def _count_clues(puzzle):
    return sum(1 for ch in puzzle if ch != "." and ch != "0")


def cmd_auto_reduce(puzzle):
    puzzle = _normalize_puzzle(puzzle)
    clue_count = _count_clues(puzzle)
    t0 = time.time()
    print("=" * 70)
    print("  AUTO-REDUCE: Full Seed Ancestry Analysis")
    print("=" * 70)
    print(f"  Input:  {puzzle}")
    print(f"  Clues:  {clue_count}")
    print(f"  Unique: {has_unique_solution(puzzle)}")
    print()
    print(board_diagram(puzzle))
    print()
    raw_prov = lars_provenance(puzzle)
    if raw_prov.get("matched"):
        seed = raw_prov.get("seed", "N/A")
        techs = _seed_technique(seed)
        idx = _seed_index(seed)
        conf = raw_prov.get("confidence", "unknown")
        conf_str = "core seed 100%" if conf == "exact" else "L1 variant ~99%"
        idx_str = f", #{idx}" if idx is not None else ""
        print(f"  >>> Already in Lars Seed Database ({conf_str}, {', '.join(techs)}{idx_str}) <<<")
        print()
        # Solve it normally
        r = _larsdoku_solve(puzzle)
        print(f"  Status: {r['status']}")
        if r['wsrf']:
            print(f"  WSRF:   {r['wsrf']}")
        if r['techniques']:
            print(f"  Techniques:")
            for t in r['techniques']:
                print(f"    {t}")
        elapsed = time.time() - t0
        print()
        print(f"  No reduction needed — puzzle is already a known seed derivative.")
        print(f"  Time: {elapsed:.1f}s")
        print("=" * 70)
        return
    else:
        print(f"  Input: NOT in Lars Seed Database (need reduction)")
    print()
    clue_positions = [i for i, ch in enumerate(puzzle) if ch != "." and ch != "0"]
    orderings = [
        ("scan", list(clue_positions)),
        ("reverse", list(reversed(clue_positions))),
        ("density", _density_order(puzzle)),
        ("sig-guided", _signature_guided_order(puzzle)),
    ]
    for k in range(RANDOM_ORDERINGS):
        shuffled = list(clue_positions)
        random.shuffle(shuffled)
        orderings.append((f"random-{k + 1}", shuffled))
    all_results = []
    all_matches = []
    seen_bases = set()
    print("-" * 70)
    print(f"  Running {len(orderings)} reduction passes (5 strategies)...")
    print("-" * 70)
    for label, order in orderings:
        result = reduce_with_tracking(puzzle, order, label)
        base = result["base"]
        base_clues = sum(1 for ch in base if ch != ".")
        all_results.append(result)
        seen_bases.add(base)
        match_str = f" >>> {len(result['matches'])} MATCH(ES)!" if result["matches"] else ""
        print(f"  [{label:>12}]  base = {base_clues} clues, stripped = {len(result['removed'])}{match_str}")
        for m in result["matches"]:
            all_matches.append({**m, "strategy": label})
    best_base = min(seen_bases, key=lambda b: sum(1 for ch in b if ch != "."))
    best_base_clues = sum(1 for ch in best_base if ch != ".")
    print()
    print(f"  Exhaustive search on {best_base_clues}-clue base (up to 3 more removals)...")
    exhaust_matches = exhaustive_reduce(best_base, max_try_remove=3)
    if exhaust_matches:
        for em in exhaust_matches:
            print(f"  [exhaustive]   {em['clues']} clues >>> MATCH!")
            all_matches.append({**em, "strategy": "exhaustive"})
    else:
        print(f"  [exhaustive]   No additional matches found")
    elapsed = time.time() - t0
    unique_matches = {}
    for m in all_matches:
        key = m["puzzle"]
        if key not in unique_matches:
            m["strategies_hit"] = [m.get("strategy", "?")]
            unique_matches[key] = m
        else:
            existing = unique_matches[key]
            strat = m.get("strategy", "?")
            if strat not in existing["strategies_hit"]:
                existing["strategies_hit"].append(strat)
    print()
    print("=" * 70)
    print("  SEED ANCESTRY TRACE")
    print("=" * 70)
    sorted_matches = sorted(unique_matches.values(), key=lambda x: -x["clues"])
    print(f"  Input:  {clue_count} clues ──── {'IN DB' if raw_prov.get('matched') else 'NOT IN DB'}")
    for m in sorted_matches:
        match_info = m["match"]
        seed = match_info.get("seed", "N/A")
        techs = _seed_technique(seed) if seed != "N/A" else ["?"]
        idx = _seed_index(seed) if seed != "N/A" else None
        stripped = clue_count - m["clues"]
        conf = match_info["confidence"]
        strategies = m["strategies_hit"]
        print(f"    | strip {stripped}")
        conf_short = "CORE 100%" if "exact" in conf else "L1 ~99%"
        idx_str = f"  [#{idx}]" if idx is not None else ""
        print(f"  {m['clues']} clues ──── {conf_short}  {', '.join(techs)}{idx_str}")
        print(f"    |  Seed:     {seed}")
        print(f"    |  Hash:     {match_info.get('hash', 'N/A')}")
        print(f"    |  Found by: {', '.join(strategies)}")
    best_result = min(all_results, key=lambda r: sum(1 for ch in r["base"] if ch != "."))
    best_base = best_result["base"]
    best_base_clues = sum(1 for ch in best_base if ch != ".")
    base_match = _check_registry(best_base)
    if not base_match or best_base not in unique_matches:
        stripped_from_input = clue_count - best_base_clues
        print(f"    | strip {stripped_from_input}")
        print(f"  {best_base_clues} clues ──── BASE UNIQUE (NEW)")
    print()
    if unique_matches:
        print("-" * 70)
        print(f"  SEED MATCHES: {len(unique_matches)}")
        print("-" * 70)
        for i, (puz, m) in enumerate(sorted(unique_matches.items(), key=lambda x: -x[1]["clues"]), 1):
            match_info = m["match"]
            seed = match_info.get("seed", "N/A")
            techs = _seed_technique(seed)
            idx = _seed_index(seed)
            strategies = m["strategies_hit"]
            print()
            print(f"  Match #{i}:")
            print(f"    Clues:      {m['clues']}")
            print(f"    Confidence: {match_info['confidence']}")
            print(f"    Technique:  {', '.join(techs)}")
            if idx is not None:
                print(f"    Seed index: #{idx}")
            print(f"    Seed bd81:  {seed}")
            print(f"    Hash:       {match_info.get('hash', 'N/A')}")
            print(f"    Reduced:    {puz}")
            print(f"    Strategy:   {', '.join(strategies)}")
            print()
            print(f"    Seed board:")
            print(_indent(board_diagram(seed.replace("0", ".")), "      "))
            print()
            print(f"    Reduced board:")
            print(_indent(board_diagram(puz), "      "))
            print()
    else:
        print()
        print("  NO SEED MATCHES FOUND at any reduction level.")
        print()
    print("-" * 70)
    print("  BASE UNIQUES (all orderings)")
    print("-" * 70)
    bases_by_clues = {}
    for r in all_results:
        base = r["base"]
        bc = sum(1 for ch in base if ch != ".")
        if base not in bases_by_clues:
            bases_by_clues[base] = {"clues": bc, "labels": []}
        bases_by_clues[base]["labels"].append(r["label"])
    for base, info in sorted(bases_by_clues.items(), key=lambda x: x[1]["clues"]):
        print(f"  {info['clues']} clues  [{', '.join(info['labels'])}]")
        print(f"    {base}")
        print()
    promotion = list(reversed(best_result["removed"]))
    print("-" * 70)
    print(f"  BEST BASE UNIQUE: {best_base_clues} clues  [{best_result['label']}]")
    print("-" * 70)
    print(f"  {best_base}")
    print()
    print(board_diagram(best_base))
    print()
    print(f"  PROMOTION SEQUENCE ({len(promotion)} steps, base -> full):")
    for step, (pos, digit) in enumerate(promotion, 1):
        r, c = pos // 9 + 1, pos % 9 + 1
        print(f"    step {step:2d}: +R{r}C{c}={digit}  (pos={pos})")
    print()
    print(f"  Total time: {elapsed:.1f}s")
    print(f"  Strategies: {len(orderings)} orderings + exhaustive")
    print(f"  Lars DB:    10,698 signatures | 438,564 seeds | 1.1 quintillion puzzles")
    print(f"              {len(LARS_SEEDS_HASHES)} core + {len(LARS_SEEDS_L1_HASHES)} variant hashes")
    print("=" * 70)


# ══════════════════════════════════════════════════════════════
# Command: --seed-lookup
# ══════════════════════════════════════════════════════════════

def cmd_seed_lookup(query):
    t0 = time.time()
    print("=" * 70)
    print("  SEED LOOKUP")
    print("=" * 70)
    print(f"  Query: {query}")
    print()
    is_hash = query.startswith("(")
    is_bd81 = len(query) == 81 and all(ch in "0123456789." for ch in query)
    if is_hash:
        _seed_lookup_by_hash(query)
    elif is_bd81:
        _seed_lookup_by_bd81(query)
    else:
        print(f"  ERROR: Unrecognized query format.")
        print(f"  Expected: 81-char bd81 string or hash tuple string")
        print()
        return
    elapsed = time.time() - t0
    print(f"  Time: {elapsed * 1000:.1f}ms")
    print("=" * 70)


def _seed_lookup_by_hash(hash_str):
    found_core = hash_str in LARS_SEEDS_HASHES
    found_l1 = hash_str in LARS_SEEDS_L1_HASHES
    if found_core:
        seed = LARS_SEEDS_HASHES[hash_str]
        techs = _seed_technique(seed)
        idx = _seed_index(seed)
        clues = sum(1 for ch in seed if ch != "0" and ch != ".")
        print(f"  FOUND: Core seed (100% confidence)")
        print(f"  Technique:  {', '.join(techs)}")
        if idx is not None:
            print(f"  Seed index: #{idx}")
        print(f"  Seed bd81:  {seed}")
        print(f"  Clues:      {clues}")
        print(f"  Hash:       {hash_str}")
        print()
        print(f"  Board:")
        print(_indent(board_diagram(seed.replace("0", ".")), "    "))
        print()
    elif found_l1:
        seed = LARS_SEEDS_L1_HASHES[hash_str]
        techs = _seed_technique(seed)
        idx = _seed_index(seed)
        clues = sum(1 for ch in seed if ch != "0" and ch != ".")
        print(f"  FOUND: L1 variant (high confidence)")
        print(f"  Technique:  {', '.join(techs)}")
        if idx is not None:
            print(f"  Seed index: #{idx}")
        print(f"  Seed bd81:  {seed}")
        print(f"  Clues:      {clues}")
        print(f"  Hash:       {hash_str}")
        print()
        print(f"  Board:")
        print(_indent(board_diagram(seed.replace("0", ".")), "    "))
        print()
    else:
        print(f"  NOT FOUND in Lars Seed Database.")
        print(f"  Hash: {hash_str}")
        print()


def _seed_lookup_by_bd81(bd81):
    norm = bd81.replace(".", "0")
    clues = sum(1 for ch in norm if ch != "0")
    mask = [1 if ch != "0" else 0 for ch in norm]
    h = str(lars_mask_hash(mask))
    print(f"  Clues: {clues}")
    print(f"  Hash:  {h}")
    print()
    seeds_data = LARS_SEEDS.get("seeds", {})
    is_deepres = norm in seeds_data.get("deepres", [])
    is_d2b = norm in seeds_data.get("d2b", [])
    is_seed = is_deepres or is_d2b
    if is_seed:
        techs = []
        if is_deepres:
            techs.append("DeepResonance")
        if is_d2b:
            techs.append("D2B")
        idx = _seed_index(norm)
        print(f"  >>> EXACT SEED MATCH <<<")
        print(f"  This bd81 IS a registered seed.")
        print(f"  Technique:  {', '.join(techs)}")
        if idx is not None:
            print(f"  Seed index: #{idx}")
        print()
    else:
        print(f"  This bd81 is NOT a registered seed (checking mask hash)...")
        print()
    found_core = h in LARS_SEEDS_HASHES
    found_l1 = h in LARS_SEEDS_L1_HASHES
    if found_core:
        matched_seed = LARS_SEEDS_HASHES[h]
        techs = _seed_technique(matched_seed)
        idx = _seed_index(matched_seed)
        matched_clues = sum(1 for ch in matched_seed if ch != "0")
        same = (norm == matched_seed)
        print(f"  CORE HASH MATCH (100% confidence)")
        print(f"  Matched seed: {matched_seed}")
        print(f"  Seed clues:   {matched_clues}")
        print(f"  Technique:    {', '.join(techs)}")
        if idx is not None:
            print(f"  Seed index:   #{idx}")
        print(f"  Same puzzle:  {'YES' if same else 'NO (structural equivalent)'}")
        print()
        print(f"  Matched seed board:")
        print(_indent(board_diagram(matched_seed.replace("0", ".")), "    "))
        print()
    elif found_l1:
        matched_seed = LARS_SEEDS_L1_HASHES[h]
        techs = _seed_technique(matched_seed)
        idx = _seed_index(matched_seed)
        matched_clues = sum(1 for ch in matched_seed if ch != "0")
        same = (norm == matched_seed)
        print(f"  L1 VARIANT MATCH (high confidence)")
        print(f"  Matched seed: {matched_seed}")
        print(f"  Seed clues:   {matched_clues}")
        print(f"  Technique:    {', '.join(techs)}")
        if idx is not None:
            print(f"  Seed index:   #{idx}")
        print(f"  Same puzzle:  {'YES' if same else 'NO (structural equivalent)'}")
        print()
        print(f"  Matched seed board:")
        print(_indent(board_diagram(matched_seed.replace("0", ".")), "    "))
        print()
    else:
        print(f"  NO MATCH in Lars Seed Database for this mask hash.")
        print()
    print(f"  Input board:")
    print(_indent(board_diagram(bd81.replace("0", ".")), "    "))
    print()
    try:
        unique = has_unique_solution(bd81)
        print(f"  Unique: {unique}")
    except Exception:
        print(f"  Unique: (could not check)")
    print()


# ══════════════════════════════════════════════════════════════
# Command: --reduce-solve
# ══════════════════════════════════════════════════════════════

def _larsdoku_solve(puzzle, exclude=None):
    cmd = ["larsdoku", puzzle]
    if exclude:
        cmd.extend(["--exclude", exclude])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout + result.stderr
        status = "SOLVED" if "Status: SOLVED" in output else "FAILED"
        techniques = []
        in_techs = False
        for line in output.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Techniques:"):
                in_techs = True
                continue
            if in_techs:
                if not stripped or stripped.startswith("=") or stripped.startswith("-"):
                    break
                techniques.append(stripped)
        wsrf = ""
        for line in output.split("\n"):
            if line.strip().startswith("WSRF:"):
                wsrf = line.strip().split("WSRF:")[1].strip()
                break
        return {"status": status, "techniques": techniques, "wsrf": wsrf, "output": output}
    except Exception as e:
        return {"status": "ERROR", "techniques": [], "wsrf": "", "output": str(e)}


def _solve_with_je_fallback_cli(puzzle):
    r = _larsdoku_solve(puzzle)
    if r["status"] == "SOLVED":
        return r, "default"
    r2 = _larsdoku_solve(puzzle, exclude="JuniorExocet,JETest")
    if r2["status"] == "SOLVED":
        return r2, "JE-excluded"
    return r, "FAILED"


def cmd_reduce_solve(puzzle):
    puzzle = _normalize_puzzle(puzzle)
    clue_count = _count_clues(puzzle)
    t0 = time.time()
    print("=" * 70)
    print("  REDUCE-SOLVE: Strip Promotions, Solve, Map Back")
    print("=" * 70)
    print(f"  Input:  {puzzle}")
    print(f"  Clues:  {clue_count}")
    print()
    solution = solve_backtrack(puzzle)
    if not solution:
        print("  ERROR: Puzzle has no solution!")
        print("=" * 70)
        return
    print(f"  Solution: {solution}")
    print()

    # If already in provenance, skip reduction and just solve normally
    raw_prov = lars_provenance(puzzle)
    if raw_prov.get("matched"):
        seed = raw_prov.get("seed", "N/A")
        techs = _seed_technique(seed)
        idx = _seed_index(seed)
        conf = raw_prov.get("confidence", "unknown")
        conf_str = "core seed 100%" if conf == "exact" else "L1 variant ~99%"
        idx_str = f", #{idx}" if idx is not None else ""
        print(f"  >>> Already in Lars Seed Database ({conf_str}, {', '.join(techs)}{idx_str}) <<<")
        print()

        # Just solve it normally
        r = _larsdoku_solve(puzzle)
        print(f"  Status: {r['status']}")
        if r['wsrf']:
            print(f"  WSRF:   {r['wsrf']}")
        print()
        if r['techniques']:
            print(f"  Techniques:")
            for t in r['techniques']:
                print(f"    {t}")
        print()
        print(f"  SOLUTION: {solution}")
        print()
        print(board_diagram(solution))
        elapsed = time.time() - t0
        print()
        print(f"  Total time: {elapsed:.1f}s")
        print("=" * 70)
        return

    print("  Reducing...")
    clue_positions = [i for i, ch in enumerate(puzzle) if ch != "." and ch != "0"]
    orderings = [
        ("scan", list(clue_positions)),
        ("reverse", list(reversed(clue_positions))),
        ("density", _density_order(puzzle)),
        ("sig-guided", _signature_guided_order(puzzle)),
    ]
    for k in range(RANDOM_ORDERINGS):
        shuffled = list(clue_positions)
        random.shuffle(shuffled)
        orderings.append((f"random-{k + 1}", shuffled))
    all_results = []
    all_matches = {}
    for label, order in orderings:
        result = reduce_with_tracking(puzzle, order, label)
        all_results.append(result)
        for m in result["matches"]:
            key = m["puzzle"]
            if key not in all_matches:
                m["strategies_hit"] = [label]
                all_matches[key] = m
            else:
                if label not in all_matches[key].get("strategies_hit", []):
                    all_matches[key].setdefault("strategies_hit", []).append(label)
    sorted_matches = sorted(all_matches.values(), key=lambda x: -x["clues"])
    if not sorted_matches:
        print("  No seed matches found during reduction.")
        print()
    print()
    print("-" * 70)
    print("  SOLVE MATRIX")
    print("-" * 70)
    print(f"  {'Puzzle':<28} {'Clues':>5}  {'Status':>10}  {'Mode':<14}  {'WSRF'}")
    print(f"  {'─' * 28} {'─' * 5}  {'─' * 10}  {'─' * 14}  {'─' * 20}")
    solve_results = []
    je_fallback_used = False
    r, mode = _solve_with_je_fallback_cli(puzzle)
    if mode == "JE-excluded":
        je_fallback_used = True
    solve_results.append(("Original", clue_count, r, mode, puzzle))
    print(f"  {'Original':<28} {clue_count:>5}  {r['status']:>10}  {mode:<14}  {r['wsrf']}")
    seen_puzzles = {puzzle}
    for m in sorted_matches:
        reduced = m["puzzle"]
        match_info = m["match"]
        seed_bd81 = match_info.get("seed", "")
        seed_techs = _seed_technique(seed_bd81) if seed_bd81 else ["?"]
        idx = _seed_index(seed_bd81) if seed_bd81 else None
        if reduced not in seen_puzzles:
            seen_puzzles.add(reduced)
            r, mode = _solve_with_je_fallback_cli(reduced)
            if mode == "JE-excluded":
                je_fallback_used = True
            label = f"Reduced {m['clues']}cl"
            solve_results.append((label, m["clues"], r, mode, reduced))
            print(f"  {label:<28} {m['clues']:>5}  {r['status']:>10}  {mode:<14}  {r['wsrf']}")
        if seed_bd81 and seed_bd81 not in seen_puzzles:
            seen_puzzles.add(seed_bd81)
            r, mode = _solve_with_je_fallback_cli(seed_bd81)
            if mode == "JE-excluded":
                je_fallback_used = True
            idx_str = f" #{idx}" if idx is not None else ""
            tech_str = ','.join(seed_techs)
            label = f"Seed {tech_str}{idx_str}"
            seed_clues = sum(1 for ch in seed_bd81 if ch != "0" and ch != ".")
            solve_results.append((label, seed_clues, r, mode, seed_bd81))
            print(f"  {label:<28} {seed_clues:>5}  {r['status']:>10}  {mode:<14}  {r['wsrf']}")
    best_result = min(all_results, key=lambda r: sum(1 for ch in r["base"] if ch != "."))
    best_base = best_result["base"]
    best_base_clues = sum(1 for ch in best_base if ch != ".")
    if best_base not in seen_puzzles:
        r, mode = _solve_with_je_fallback_cli(best_base)
        if mode == "JE-excluded":
            je_fallback_used = True
        solve_results.append(("Base unique", best_base_clues, r, mode, best_base))
        print(f"  {'Base unique':<28} {best_base_clues:>5}  {r['status']:>10}  {mode:<14}  {r['wsrf']}")
    if je_fallback_used:
        print()
        print("  NOTE: JuniorExocet excluded (fallback due to unimplemented")
        print("  technique interaction — fix scheduled for future version).")
    print()
    print("-" * 70)
    print("  BEST SOLVE PATH")
    print("-" * 70)
    best_solve = None
    for label, clues, r, mode, puz in solve_results:
        if r["status"] != "SOLVED":
            continue
        priority = (0 if mode == "default" else 1, clues)
        if best_solve is None or priority < best_solve[0]:
            best_solve = (priority, label, clues, mode, r, puz)
    if best_solve:
        _, label, clues, mode, result, puz = best_solve
        mode_note = f" (JuniorExocet excluded — known bug)" if mode == "JE-excluded" else ""
        print(f"  Solved via:   {label} ({clues} clues, {mode}){mode_note}")
        print(f"  WSRF:         {result['wsrf']}")
        print(f"  Puzzle:       {puz}")
        print()
        print(f"  Techniques:")
        for t in result["techniques"]:
            print(f"    {t}")
    else:
        print("  No solve path found at any reduction level!")
    print()
    print(f"  SOLUTION: {solution}")
    print()
    print(board_diagram(solution))
    elapsed = time.time() - t0
    print()
    print(f"  Total time: {elapsed:.1f}s")
    print("=" * 70)
