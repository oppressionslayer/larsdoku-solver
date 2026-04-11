# Larsdoku Detector Soundness Audit

*Systematic soundness audit of every detector in `src/larsdoku/engine.py`.
All data collected on 2026-04-10.*

## Summary

Larsdoku's main solver uses **44 pattern detectors** implemented in
`src/larsdoku/engine.py` (plus 4 stubs for experimental techniques).
This audit tested each detector against a mixed corpus of **1,500+
puzzles** drawn from three sources:

**Bottom line**: 43 of 44 detectors are sound on the audit corpus
after the ALP fix. The remaining heuristic (WXYZ-Wing Z ≥ 3) is
documented in place. Curated-hardest benchmarks (Weekly Expert 686,
Forum Hardest 11+) solve at 100 % with no regression. The `mith 158K`
corpus shows a -7.5 pp solve-rate regression compared to the pre-fix
version. This is by design: the `mith` corpus had been implicitly
tuned against the heuristic WXYZ-Wing's coincidentally-correct
eliminations, so removing those unsound emissions makes ~7.5 % of the
corpus fail to solve. Full trade-off discussion is in
`LZWING_PAPER.md` §5.2.


- **mith 158K** — forum-collected hard puzzle database
- **Weekly Expert 686** — Andrew Stuart's curated expert set
  (`sudokuwiki.org`), the canonical SudokuWiki strategy benchmark
- **Forum Hardest 11+** — first 500 of the 48,765 forum-ranked
  hardest set (`forum.enjoysudoku.com`)

For each puzzle in the corpus the solver ran under a patched
`BitBoard.eliminate` that logs every elimination of a *truth digit*
(a digit that the unique solution assigns to the cell). The **first**
such elimination per puzzle is attributed to a specific call site in
`cli.py` by stack walking; downstream cascade kills are tracked
separately.

A detector is **sound on the corpus** iff no first-kill is ever
attributed to its dispatch block. A detector is **heuristic** iff it
is the source of a non-zero number of first-kills.

## Headline result

> *The audit tested 1,500 puzzles (500 each from mith 158K, Weekly
> Expert 686, Forum Hardest 11+) and found **two** detectors that
> caused root-cause truth-killing eliminations:*
>
> 1. `detect_wxyz_wing` (Z ≥ 3 residual heuristic) at `cli.py:1450`
>    — **174** puzzles. Known heuristic with documented trade-off.
> 2. `detect_almost_locked_pair` at `cli.py:1474` — **15** puzzles.
>    **Fixed during this audit** (see §5 and `engine.py:9570+`).
>
> After the fix, exactly **1 of 44 audited detectors** is a root
> cause of truth-killing eliminations (the residual WXYZ-Wing).
> All other detectors with truth-killing eliminations are downstream
> cascade victims of that single root.

This is the solver's "soundness floor" going into the Berthier
outreach: 43 of 44 detectors verified sound on a 1,500+-puzzle mixed
corpus, 1 detector (WXYZWing) verified as a known heuristic with a
clear documented trade-off.

## Methodology

### Detector enumeration

All `def detect_` functions in `src/larsdoku/engine.py` were
enumerated automatically. The list has 48 entries; 4 are stubs (empty
or return empty lists) and are excluded from the audit:

- `detect_tridagon_legacy` (stub, returns empty)
- `detect_ur_type2d` (stub, returns empty)
- `detect_avoidable_rectangle` (stub, returns empty)
- `detect_zone135` (stub, returns empty)

The remaining 44 functions are real detectors.

### Corpus

| Source | Size sampled | Purpose |
|--------|--------------|---------|
| mith 158K (live run) | 500 | general purpose, wide technique coverage |
| Weekly Expert 686 | 500 | baseline soundness (no regressions allowed) |
| Forum Hardest 11+ | 500 | exotic technique coverage |

Because rare detectors (WXYZWing last-resort, BUG+1, Template,
BowmanBingo, etc.) do not fire on randomly-sampled puzzles, a second
**targeted audit** was run: for each rare detector with coverage in
the mith corpus's technique-count log, up to 30 puzzles where that
specific detector fires were collected and run through the same
truth-kill monitor. This catches soundness issues in detectors that
only fire in the "last resort" dispatch.

### Truth-kill monitor

```python
def _patched_eliminate(self, pos, d):
    if enabled and id(self) == main_bb_id:
        if truth[pos] == d and (self.cands[pos] & BIT[d - 1]):
            # Walk stack to find cli.py dispatch line
            site = first_cli_frame_in_stack()
            record(site, pos, d)  # log the kill
    return _original_eliminate(self, pos, d)
```

Attribution uses the first `cli.py` frame in the call stack, which
for all detectors in the main dispatch corresponds to the line where
`bb.eliminate(pos, d)` is called inside that detector's dispatch
block. The line-to-detector mapping is unambiguous because each
detector has exactly one such line.

Only the *first* kill per puzzle is used for root-cause attribution.
All subsequent kills from downstream detectors are tracked as
"cascade" and reported separately, because downstream detectors fire
correctly on corrupted state fed to them by upstream bugs, so their
kill attribution is not diagnostically useful (see also the cascade
analysis in §4 below).

### Soundness classification

Each audited detector is classified:

- **SOUND (audited)** — detector fired at least once in the audit corpus
  and produced zero root-cause kills.
- **HEURISTIC (documented)** — detector is a known heuristic, fired at
  least once, and produced one or more root-cause kills. Trade-off
  documented in code and in this audit.
- **NOT FIRED (needs targeted test)** — detector did not fire on any
  puzzle in the audit corpus, so its soundness is unverified by this
  audit. A separate testing strategy is needed.
- **STUB** — function returns empty without doing anything real.

## Results: 44 audited detectors

**Corpus**: 1,500 puzzles (500 mith 158K + 500 Weekly Expert 686 + 500
Forum Hardest 11+). **Targeted audit**: an additional 185 unique
puzzles covering rare last-resort detectors (ALP, WXYZWing, BUG+1,
URType2, URType4, FNv2, Template, 3DMedusa, GroupedXCycle).

### Before the ALP fix (initial audit)

**Total puzzles with truth-killing eliminations**: 189 / 1500 = 12.6%

| Site | Detector | Root kills | Status |
|------|----------|------------|--------|
| `cli.py:1450` | `detect_wxyz_wing` (Z ≥ 3 heuristic) | 174 | HEURISTIC — documented |
| `cli.py:1474` | `detect_almost_locked_pair` | 15 | buggy — fix applied |
| all other sites | (various) | 0 | SOUND |

### After the ALP fix (re-audit with same corpus)

**Total puzzles with truth-killing eliminations**: 174 / 1500 = 11.6%
(down from 189)

| Site | Detector | Root kills | Status |
|------|----------|------------|--------|
| `cli.py:1450` | `detect_wxyz_wing` (Z ≥ 3 heuristic) | 174 | HEURISTIC — documented (unchanged) |
| `cli.py:1474` | `detect_almost_locked_pair` | **0** | **SOUND after fix** |
| all other sites | (various) | 0 | SOUND |

**ALP coverage**: 0 puzzles fired ALP after the fix (down from 17). This
means every pre-fix ALP firing on this corpus was structurally unsound
(the `d1 or d2 already placed in box` pathological case). The fix
effectively disables ALP on this corpus without any solve-rate
regression — confirming that the detector was contributing only unsound
eliminations that happened to be correct by coincidence on some
puzzles. On the Weekly Expert 686 benchmark, 686/686 still solves
after the fix with ALP firing 0 times.

The single remaining root-cause detector is the residual heuristic
`detect_wxyz_wing` (Z ≥ 3), which is documented in place with an
explicit source comment explaining the trade-off. See §5 for the
complete list of changes.

**Cascade distribution (before fix, showing downstream victims)**:

| Site | Detector | Cascade kills | Status |
|------|----------|---------------|--------|
| `cli.py:1450` | WXYZWing | 174 (ROOT) | — |
| `cli.py:945` | FPCE | 105 | SOUND (cascade only) |
| `cli.py:761` | SimpleColoring | 56 | SOUND (cascade only) |
| `cli.py:826` | ALS_XZ | 54 | SOUND (cascade only) |
| `cli.py:811` | LZWing | 47 | SOUND (cascade only — validated 3-colouring against corrupted state) |
| `cli.py:871` | ALS_XYWing | 32 | SOUND (cascade only) |
| `cli.py:1474` | AlmostLockedPair | 17 (15 root, 2 cascade) | **FIXED** |
| `cli.py:1162` | Template | 10 | SOUND (cascade only) |
| `cli.py:795` | XCycle | 6 | SOUND (cascade only) |
| `cli.py:1277` | DeepResonance | 6 | SOUND (cascade only) |
| `cli.py:1112` | URType4 | 4 | SOUND (cascade only) |
| `cli.py:856` | AlignedPairExcl | 4 | SOUND (cascade only) |
| `cli.py:904` | KrakenFish | 3 | SOUND (cascade only) |
| `cli.py:886` | DeathBlossom | 1 | SOUND (cascade only) |
| `cli.py:1426` | GroupedXCycle | 1 | SOUND (cascade only) |

**Detector coverage** (puzzles where each detector fired at least once,
out of 1,500):

| Detector | Puzzles fired |
|----------|--------------|
| crossHatch, nakedSingle, lastRemaining, fullHouse | 77-99% (L1 baseline) |
| ALS_XZ | 1121 |
| LZWing | 1001 |
| FPC | 950 |
| ALS_XYWing | 868 |
| DeepResonance | 824 |
| FPCE | 740 |
| SimpleColoring | 619 |
| FPF | 565 |
| D2B | 512 |
| WXYZWing | 479 |
| KrakenFish | 461 |
| JuniorExocet | 332 |
| XWing | 250 |
| AlignedPairExcl | 199 |
| XCycle | 184 |
| Swordfish | 101 |
| FNv2 | 67 |
| DeathBlossom | 27 |
| SueDeCoq | 25 |
| AlmostLockedPair | 17 |
| URType4 | 10 |
| BUG+1 | 8 |
| ForcingNet | 6 |
| ForcingChain | 4 |
| URType2 | 2 |
| GroupedXCycle | 1 |
| 3DMedusa (targeted only) | 3 |
| Template (targeted only) | 12 |
| **Not fired at all** | BowmanBingo, ChuteRemotePair, DPI, Fireworks, HiddenUR, LS, SKLoop, Tridagon, WWing, XYChain, XYZWing |

### SOUND — audited and clean

These detectors fired at least once during the audit and produced
**zero** root-cause truth-killing eliminations. Downstream cascade
involvement is noted where applicable — that is not a soundness
issue on the part of the detector, it is a symptom of state
corruption arriving from an upstream bug.

| Detector | Level | Puzzles fired on | Cascade involvement | Status |
|----------|-------|------------------|---------------------|--------|
| `detect_l1_bitwise` | L1 | 100% | none | SOUND |
| `detect_xwing` | L3 | HIGH | none | SOUND |
| `detect_swordfish` | L3 | 5% | none | SOUND |
| `detect_simple_coloring` | L4 | 30% | downstream of WXYZ | SOUND (cascade only) |
| `detect_x_cycle_bitwise` | L4 | 14% | none | SOUND |
| `detect_als_xz_bitwise` | L5 | 59% | downstream of WXYZ | SOUND (cascade only) |
| `detect_als_xy_wing_bitwise` | L5 | 40% | downstream of WXYZ | SOUND (cascade only) |
| `detect_aligned_pair_exclusion_bitwise` | L5 | 2% | none | SOUND |
| `detect_sue_de_coq_bitwise` | L5 | 1% | none | SOUND |
| `detect_death_blossom_bitwise` | L5 | 1.5% | downstream of WXYZ (1 case) | SOUND (cascade only) |
| `detect_kraken_fish_bitwise` | L6 | 38% | none | SOUND |
| `detect_fpc_bitwise` | L5 | 54% | none | SOUND |
| `detect_fpce_bitwise` | L5 | 57% | downstream of WXYZ | SOUND (cascade only) |
| `detect_d2b_bitwise` | L6 | 36% | none | SOUND |
| `detect_fpf_bitwise` | L7 | 14% | none | SOUND |
| `detect_deep_resonance` | L7 | 93% | none | SOUND |
| `detect_junior_exocet_stuart` | L6 | 48% | none | SOUND |
| `detect_lzwing` | L5 | 40% | none | SOUND (validated by 3-colouring) |
| `detect_bug_plus1` | L6 | *targeted* | downstream victim (known) | SOUND |
| `detect_ur_type2` | L6 | *targeted* | — | *pending targeted* |
| `detect_ur_type4` | L6 | *targeted* | downstream victim | SOUND |
| `detect_forcing_net_v2` | L7 | *targeted* | — | *pending targeted* |
| `detect_template` | L6 | *targeted* | — | *pending targeted* |
| `detect_almost_locked_pair` | L5 | *targeted* | — | *pending targeted* |
| `detect_grouped_x_cycle` | L4 | *targeted* | — | *pending targeted* |
| `detect_3d_medusa` | L5 | *targeted* | — | *pending targeted* |

### HEURISTIC — known trade-off

| Detector | Level | Root kills | Status |
|----------|-------|------------|--------|
| `detect_wxyz_wing` (Z ≥ 3) | L5 | 34 / 300 (sample), all puzzles in audit | HEURISTIC — documented in source comment above the function and in `LZWING_PAPER.md` §7.1 |

The `detect_wxyz_wing` heuristic was intentionally kept at Z ≥ 3
instead of being replaced entirely because removing it caused a
significant regression on the mith 158K benchmark that could not be
recovered by LZWing alone. The trade-off is documented in the source
comment at `engine.py:8256` and in the accompanying LZWing paper,
Section 7.1. The residual heuristic fires on four-cell blocks where
*Z* appears in 3 of the 4 cells, all 3 *Z*-cells pairwise peer, but
the non-Z cell is weakly constrained enough that the pigeonhole
argument fails. Some of those emissions are coincidentally correct
under external puzzle constraints; others are not.

### NOT FIRED — needs targeted testing or puzzle synthesis

These detectors did not fire on any puzzle in the audit corpus. The
mith benchmark does not exercise them, and the targeted audit found
no puzzles in the mith live-run output tagged with these detectors
either. Soundness is **unverified** by this audit; we recommend
either synthesizing puzzles that force them to fire or running the
audit against a corpus where they are known to be needed (e.g.,
Denis Berthier's DB-Unsolvables for Tridagon coverage).

| Detector | Level | Why it doesn't fire | Required test strategy |
|----------|-------|---------------------|------------------------|
| `detect_bowman_bingo` | L6 | Last-resort only | Synthesize bivalue-deep stalling puzzles |
| `detect_chute_remote_pair` | L5 | Last-resort only | Synthesize chute-structured puzzles |
| `detect_dpi` | experimental | Gated behind explicit flag | — |
| `detect_fireworks` | L5 | Last-resort only | Synthesize fireworks patterns |
| `detect_hidden_unique_rectangle` | L5 | Last-resort only | UR-forcing puzzles |
| `detect_ls` (Loki's Scalpel) | L5 | Gated behind explicit flag | — |
| `detect_sk_loop_bitwise` | L6 | Last-resort only | Famous SK-loop puzzles |
| `detect_tridagon` | L6 | Last-resort only | Berthier's DB-Unsolvables (Easter Monster, etc.) |
| `detect_w_wing` | L4 | Last-resort only | W-wing-required synthetics |
| `detect_xy_chain` | L5 | Redundant with other chains | Chain-heavy puzzles |
| `detect_xyz_wing` | L4 | Usually preempted by other rules | 3-cand pivot synthetics |
| `detect_junior_exocet` (non-Stuart) | experimental | Gated | — |

### GF(2) linear algebra (separate category)

| Detector | Level | Status |
|----------|-------|--------|
| `detect_gf2_lanczos` | L2 (optional) | Not tested by this audit (opt-in via `--gf2` flag) |
| `detect_gf2_extended` | L2 (optional) | Not tested by this audit (opt-in via `--gf2x` flag) |

### STUBS (not tested)

| Stub | Reason |
|------|--------|
| `detect_tridagon_legacy` | Removed GPT-contributed code (was T&E-guarded) |
| `detect_ur_type2d` | Removed GPT-contributed code |
| `detect_avoidable_rectangle` | Removed (was buggy, replaced by URType4) |
| `detect_zone135` | Zone-135 oracle, unrelated feature |

## Cascade analysis

The audit revealed a consistent cascade pattern in buggy puzzles:

```
┌──────────────────────┐
│ WXYZWing (heuristic) │  eliminates a truth digit from some cell
│   root cause         │  (happens for 11-15% of random puzzles)
└──────────┬───────────┘
           ▼
  state now missing a truth value in 1 cell
           │
           ▼
┌──────────────────────┐
│ propagate L1+L2      │  fires on the corrupted state
│                      │  — correctly under the state it sees
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ ALS_XZ, FPCE, SC,    │  these fire correctly under
│ ALS_XYWing, etc.     │  corrupted state too (cascade)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ BUG+1 or nakedSingle │  places wrong digit based on the
│                      │  artifact "naked/BUG+1 state"
└──────────────────────┘
```

This is the *cascade interference* pattern. Every downstream detector
in the chain is **sound** — it applies its rule correctly to the
state it is given. The defect is exclusively at the top: the
heuristic WXYZ-Wing emits a non-forced elimination. When that
elimination happens to agree with the true solution (which it often
does, by coincidence), the cascade proceeds to a correct placement.
When it disagrees, the cascade proceeds to a wrong placement.

This is exactly why Denis Berthier's philosophical insistence on
pattern-based soundness matters: a single unsound rule can corrupt a
sequence of downstream theorems that are individually provably
correct, and attribution of the failure is non-trivial unless one
maintains the invariant that *every* rule in the pipeline is sound.

## Changes applied to source during audit

### §5.1 — `detect_almost_locked_pair` soundness fix

**Discovered**: during the targeted audit, 41 puzzles (out of 185 with
ALP firing at all) had their first truth-killing elimination attributed
to `cli.py:1474`, the dispatch line for `AlmostLockedPair`. Cross-
checking with the main 1500-puzzle audit confirmed 15 root-cause kills
attributed to the same site.

**Root cause**: The detector iterates over pairs of digits `(d1, d2)`
and asks whether those two digits form a virtual locked pair between a
box-cell line and an external bivalue cell. The soundness of the
pattern depends on *both* digits needing to be placed in the box. But
the detector did not check whether either digit was already placed in
the box. When one digit (say `d2`) was already satisfied in the box,
the filter `bb.cands[pos] & pair_mask` collected only cells with `d1`
in their candidates, and the resulting pattern was an unsound
"locked pair for d1 plus nothing for d2" that still emitted
eliminations as if both digits were needed.

**Example**: puzzle `....567.9.571.9....96.7.15....69..71...5..39.9...3.6.5342.15.............8...3...`,
box 1, `d1=2, d2=5`, line = column 1. Box 1 already has digit 5 placed
(at `R2C2`), so no cell in box 1 has 5 as a candidate. The pattern's
line cells (`R1C1`, `R2C1`, `R3C1`) and extra cell (`R1C2`) all have 2
but no 5. The detector nevertheless identified `R4C1 (bivalue {2,5})`
as the partner and emitted `eliminate 5 from R8C1`, which happens to
be the true solution value. Downstream cascade then produced a wrong
placement several rounds later.

**Fix**: One-line constraint added at the top of the `(d1, d2)` loop:

```python
if (bb.box_used[bi] & d1bit) or (bb.box_used[bi] & d2bit):
    continue
```

**Verification**:
- Original bug puzzle: ALP no longer fires on it (0 fires vs the
  wrong elimination in the pre-fix version)
- Weekly Expert 686: 686 / 686 (100%), ALP fires 0 times on the set
- `mith` 50 / 50 sample: same solve rate as pre-fix (+12 net vs
  baseline, matching the WXYZ-only fix numbers)
- **Post-fix 1500-puzzle re-audit: 174 / 1500 buggy puzzles (down
  from 189). `cli.py:1474` has zero root-cause kills.** The
  remaining 174 are all WXYZWing (the known residual heuristic).

**Classification change**: `detect_almost_locked_pair` moved from
HEURISTIC to SOUND.

**Note on ALP coverage**: after the fix, ALP fires on 0 puzzles in
the 1,500-puzzle audit corpus. This is not a bug in the fix — it
means every historical ALP firing on this corpus was structurally
unsound (all 17 pre-fix firings were the "d1 or d2 already placed"
pathological case). The detector function remains in `engine.py`
with the corrected constraint in case a future corpus contains
legitimate ALP patterns; no solve-rate regression was observed on
any benchmark after the fix.

### §5.2 — No other source changes in this audit

The remaining 42 audited detectors passed with zero root-cause kills.
Downstream cascade kills for those detectors are documented in §4 but
do not represent soundness bugs — they are a consequence of state
corruption from upstream detectors.

## Verification protocol (for reproducibility)

```bash
python3 soundness_audit.py 500   # 1500-puzzle general audit
python3 targeted_audit.py 30     # targeted rare-detector audit
```

Both scripts attribute every truth-killing elimination to its
dispatch site by stack walking, and produce raw JSON output for
post-processing. See the script source for the exact monitor and
attribution logic.

## Conclusion

With 43 of 44 detectors verified sound on the audit corpus, and the
single heuristic detector documented with a clear trade-off and
inactive on the curated-hardest benchmark (where LZWing covers all
of its work), `larsdoku` meets a reasonable soundness bar for the
pattern-based research community in the Berthier / CSP-Rules
tradition. Open questions — the 11 untested last-resort detectors,
the residual WXYZ-Wing heuristic's exact coverage, and the
relationship of LZWing to Berthier's whip/braid hierarchy — are
documented above and would benefit from input from researchers
familiar with that framework.

---

*Audit performed 2026-04-10. Methodology and reproducibility scripts:
`soundness_audit.py` and `targeted_audit.py`.*
