"""Larsdoku — Technique registry, levels, aliases, and presets."""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════
# TECHNIQUE LEVELS
# ══════════════════════════════════════════════════════════════

TECHNIQUE_LEVELS = {
    'crossHatch': 1, 'nakedSingle': 1, 'fullHouse': 1, 'lastRemaining': 1,
    'GF2_Lanczos': 2, 'GF2_Extended': 2, 'GF2_Probe': 2,
    'XWing': 3, 'Swordfish': 3, 'SimpleColoring': 4,
    'XCycle': 4,
    'ALS_XZ': 5, 'ALS_XYWing': 5, 'DeathBlossom': 5,
    'SueDeCoq': 5, 'AlignedPairExcl': 5,
    'FPC': 5, 'FPCE': 5,
    'ForcingChain': 5, 'ForcingNet': 5,
    'KrakenFish': 5,
    'BUG+1': 6, 'URType2': 6, 'URType4': 6,
    'JuniorExocet': 6, 'Template': 6, 'BowmanBingo': 6,
    'SKLoop': 6,
    'D2B': 6, 'FPF': 7,
    'contradiction': 7, 'ORACLE_ONLY': 99,
}

TECHNIQUE_ALIASES = {
    'fpc': 'FPC', 'fpce': 'FPCE', 'fc': 'ForcingChain', 'fn': 'ForcingNet',
    'd2b': 'D2B', 'fpf': 'FPF', 'gf2': 'GF2_Lanczos',
    'gf2x': 'GF2_Extended', 'gf2p': 'GF2_Probe',
    'xwing': 'XWing', 'swordfish': 'Swordfish', 'coloring': 'SimpleColoring',
    'xcycle': 'XCycle', 'als': 'ALS_XZ', 'alsxy': 'ALS_XYWing',
    'death': 'DeathBlossom', 'sdc': 'SueDeCoq', 'kraken': 'KrakenFish',
    'ape': 'AlignedPairExcl', 'skloop': 'SKLoop', 'sk': 'SKLoop',
    'bug': 'BUG+1', 'ur2': 'URType2', 'ur4': 'URType4',
    'exocet': 'JuniorExocet', 'template': 'Template', 'bowman': 'BowmanBingo',
    'l1': 'L1', 'l2': 'L2',
}

# WSRF inventions (excluded from expert-approved preset)
WSRF_INVENTIONS = {'FPC', 'FPCE', 'D2B', 'FPF', 'GF2_Lanczos', 'GF2_Extended', 'GF2_Probe'}

# Exotic techniques — well-known advanced techniques from the Sudoku community
EXOTIC_TECHNIQUES = {'ALS_XZ', 'ALS_XYWing', 'DeathBlossom', 'SueDeCoq',
                     'XCycle', 'KrakenFish', 'AlignedPairExcl', 'SKLoop'}

# Sudoku Expert Approved — standard L1-L6 techniques only (no WSRF inventions)
EXPERT_APPROVED = {
    tech for tech, lvl in TECHNIQUE_LEVELS.items()
    if lvl <= 6 and tech not in WSRF_INVENTIONS and tech not in EXOTIC_TECHNIQUES
    and tech != 'ORACLE_ONLY'
}

PRESETS = {
    'expert': EXPERT_APPROVED,
    'exotic': EXPERT_APPROVED | EXOTIC_TECHNIQUES,
    'wsrf': None,  # None = all techniques (full WSRF stack)
}
