# Techniques

Larsdoku implements a pipeline of **35 detectors** across 7 levels. The pipeline escalates from simple to profound — each technique fires only when everything above it has stalled.

```
L1 Singles → L2 GF(2) → L3 Fish → L4 Coloring/Cycles → L5 ALS/FPC/Forcing → L6 Exotic → L7 DeepResonance/FPF
```

---

## L1 — Foundation

The bread and butter. These solve ~90% of all cells across all puzzles.

### Full House
Last empty cell in a row, column, or box. If 8 of 9 cells are filled, the remaining digit is forced.

### Naked Single
A cell where all candidates but one have been eliminated. Only one digit can go here.

### Hidden Single (crossHatch / lastRemaining)
A digit that can only go in one cell within a row, column, or box. Even if the cell has multiple candidates, this digit has nowhere else to go.

**Top1465 stats:** 78,244 placements (90.2% of all steps)

---

## L2 — Linear Algebra

### GF(2) Block Lanczos

Encodes Sudoku constraints as a system of linear equations over GF(2) (binary arithmetic) and solves via Block Lanczos decomposition. This finds forced digits through algebraic relationships that classical scanning techniques miss entirely.

Think of it as asking: "Given all the parity constraints in this puzzle, which candidates are algebraically impossible?"

**Top1465 stats:** 216 firings

---

## L3 — Fish Patterns

### X-Wing
When a digit appears in exactly 2 cells in each of 2 rows, and those cells share the same 2 columns, the digit can be eliminated from all other cells in those columns (and vice versa for column-based X-Wings).

### Swordfish
The 3x3 generalization of X-Wing. A digit confined to at most 3 positions in each of 3 rows, aligned on the same 3 columns.

**Top1465 stats:** 134 firings

---

## L4 — Chain Logic

### Simple Coloring
For a single digit, build a chain of conjugate pairs (cells where the digit appears in exactly 2 spots in a unit). Color them alternately. If two cells of the same color see each other — contradiction. The other color is true.

### X-Cycles
Single-digit alternating inference chains. Follows strong and weak links for a digit through conjugate pairs across units. Rule 1: if a chain forms a loop with all strong links, candidates seeing two chain nodes are eliminated. Rule 2: a discontinuous loop with a strong-link conflict forces a placement. Rule 3: a weak-link conflict eliminates.

**Top1465 stats (L4):** 354+ firings

---

## L5 — Forcing & Set Logic

### ALS-XZ
Almost Locked Sets linked by a restricted common candidate. Two ALS that share a digit (the restricted common) can eliminate other shared digits from cells that see both sets.

### ALS-XY Wing
Three ALS linked in a chain via two restricted commons. More powerful than ALS-XZ — finds eliminations that require a longer chain of set interactions.

### Sue De Coq
A cell intersection pattern between a box and a line. When the combined candidates in the intersection can be partitioned into disjoint subsets assigned to the line-remainder and box-remainder, candidates are eliminated from both.

### Aligned Pair Exclusion
Two cells in a common unit whose candidate combinations are constrained by peers. Invalid digit pairs are excluded by checking whether any peer cell would be left with no candidates.

### Death Blossom
A stem cell whose candidates each map to a different ALS petal. Common eliminations across all petals are proven — whichever candidate the stem takes, the corresponding petal forces the same conclusion.

### FPC (Finned Pointing Chain) ★

*WSRF invention.*

Detects pointing patterns with a fin cell that forces a hidden single. A visual, human-friendly technique: spot the pointing pair, notice the fin, place the digit. No elimination step needed — it goes straight to placement.

**Top1465 stats:** 4,050 placements (4.7% of all steps) — the #1 advanced technique

### FPCE (FPC Elimination) ★

*WSRF invention.*

Generalized contradiction testing. Assume a candidate is true, propagate through L1+L2 logic. If a contradiction emerges (a cell with zero candidates, a unit with no place for a digit), that candidate is eliminated.

The single most powerful elimination technique in the pipeline.

**Top1465 stats:** 453 eliminations

### Forcing Chain
Pick a bivalue cell (exactly 2 candidates). Branch on each candidate and propagate. If both branches force the same conclusion in some other cell — that conclusion is proven.

Cleaner and more traceable than Nishio, with full contradiction paths.

### Forcing Net
The wider sibling of Forcing Chain. Branch on cells with 3-4 candidates, propagate deeper through the constraint network. When all branches converge on the same elimination, it's proven across the entire possibility space.

---

## L6 — Advanced Patterns

### BUG+1 (Bivalue Universal Grave)
If the puzzle reaches a state where every unsolved cell has exactly 2 candidates except one cell with 3 — the extra candidate in that cell must be the solution. Eliminating it would create a deadly pattern with multiple solutions.

### Unique Rectangle (Type 2 & Type 4)
Detects potentially deadly rectangle patterns that would allow multiple solutions, and eliminates candidates to prevent them. Based on the assumption that a valid Sudoku has exactly one solution.

### Junior Exocet
A complex pattern involving minirows in aligned boxes. When base cells share candidate digits and cover cells are constrained by cross-line eliminations, digits can be forced or eliminated.

### Template
Full-board analysis for a single digit. Enumerates all valid placements (templates) for a digit across the entire board, then eliminates candidates that don't appear in any valid template.

### Bowman's Bingo
Deep contradiction chains. Assume a candidate, propagate extensively, and if a contradiction is found many steps deep, eliminate the original assumption.

### Kraken Fish
An X-Wing or Swordfish with forcing chain verification. When a fish pattern has extra fin candidates, Kraken tests whether each fin leads (via chain logic) to the same eliminations the finless fish would make. If so, the eliminations are proven despite the fins.

### SK Loop
Stephen Kurzhal's Loop — a rare pattern involving alternating box/line intersections that form a closed loop. The loop constrains candidates so tightly that digits outside the loop pattern can be eliminated from the loop cells. Often produces massive elimination counts (8-20+ at once).

### D2B (Depth-2 Bilateral) ★

*WSRF invention.*

Pick a bivalue cell. Branch on each candidate and run the full FPCE engine on both branches. Any elimination that appears in **every** branch is proven — a two-level proof by exhaustion.

---

## L7 — Final Backstop

### DeepResonance ★

*WSRF invention. Requires Autotrust.*

Proof-by-contradiction at industrial scale. For each candidate in a cell, assume it's true and run the **entire technique stack** (L1-L6) against it. If the pipeline stalls or contradicts, that candidate is eliminated. When all but one candidate is destroyed, the survivor is placed.

DeepResonance is the technique that makes Autotrust transformative. Pure logic alone might stall at L6 — but with a trusted solution to verify against, DeepResonance can swing the full weight of 35 detectors at each candidate and prove eliminations that no single technique could find. This is where the backtracker's answer stops being a crutch and starts being a launchpad.

### FPF (Full Pipeline Forcing) ★

*WSRF invention.*

The ultimate technique. Branch on each candidate in a cell, run the **entire solver pipeline** on each branch. If all but one candidate leads to contradiction, the surviving candidate is proven.

This is computationally expensive but logically airtight. It fires only when every other technique has stalled, and it has never failed to break through.

---

## WSRF Inventions Summary

Five techniques in Larsdoku are original contributions not found in standard Sudoku solving literature:

| Technique | Level | Type | Role |
|---|---|---|---|
| **FPC** | L5 | Placement | High-volume placement engine |
| **FPCE** | L5 | Elimination | Contradiction-based candidate removal |
| **D2B** | L6 | Bilateral proof | Two-level exhaustive elimination |
| **DeepResonance** | L7 | Full-stack contradiction | Autotrust-powered proof-by-exhaustion |
| **FPF** | L7 | Full pipeline forcing | Final backstop — eliminates all remaining |

Together, these five techniques account for the gap between "most puzzles solved" and "**every** puzzle solved."

---

## A Note on Autotrust

The traditional Sudoku solving world treats the backtracker as gospel: find the solution, then reverse-engineer a logical path to it. But the backtracker doesn't *understand* Sudoku — it enumerates. Its solution depends on implementation details (branching order, cell selection heuristic), and for near-degenerate puzzles, different backtrackers may return different valid solutions.

Larsdoku takes a different stance. With **Autotrust** enabled, the solver uses pure logic for every placement — the backtracker's solution is a verification target, not a roadmap. When DeepResonance eliminates a candidate, it does so because 35 detectors collectively failed to resolve the board after assuming that candidate. That's not guessing. That's a proof no single technique could produce alone.

The solver doesn't trust the backtracker. It trusts itself — and uses the backtracker's answer to verify that trust was warranted.

---

## Stuart's JuniorExocet

The `larstech` preset includes Andrew Stuart's validated Junior Exocet implementation with strict cover-line validation (≤2 perpendicular lines per base digit in S-cells outside the band).

**Batch results:**
- Andrew's 686 weekly puzzles: **686/686 = 100%**, 122 legitimate firings
- 2500 hardest (11+): 2498/2500, JuniorExocet fires on 1087 puzzles

The strict cover-line check rejects false patterns that look structurally valid but don't satisfy Bird's Exocet constraint. On sub-11+ puzzles (where Andrew uses Exocet), it fires correctly every time.

---

## ScandolousExocet

Post-solve Exocet validation. Solves the puzzle with pure logic first (no Exocet), then scans the original board for Exocet patterns and validates them against the known solution.

```bash
larsdoku --scandalous-tech "980700600750000040003080070..." --preset larstech
```

If both target answers are base digits → **CONFIRMED** (real Exocet). If not → **FALSE PATTERN**.

The name is the feature: it's honest about checking the answer key. The validation data feeds back into improving the real JuniorExocet detector.

---

## Zone Position Hidden Single ★

*Discovered by Lars Rocha, March 2026.*

A new technique with **zero overlap** with any existing Sudoku technique.

The 9 box positions (TL, TC, TR, ML, MC, MR, BL, BC, BR) form 9 groups of 9 cells. Each group contains one cell from each box, all at the same relative position. If a digit appears as a candidate in only ONE cell of its position group — that's a Zone Hidden Single.

| Property | Value |
|----------|-------|
| Accuracy (pinned) | 50.5% |
| Accuracy (unpinned) | 28.3% |
| Overlap with standard hidden singles | **0%** |
| Average per puzzle | 12.1 |

This technique captures structural relationships that cross row/col/box boundaries — a constraint dimension the Sudoku community has never formalized.

See [HYPERSIRO](hypersiro.md) for full details.

---

## Cascade Analysis

Not a technique per se, but a way to understand puzzle difficulty. The `--cascade` flag classifies each solver step as:

- **Bottleneck** (L3+): the hard technique moves
- **Cascade** (L1-L2): naked singles and crosshatch that follow

**50 hardest puzzles — bottleneck depth distribution:**

| Depth | Puzzles | Meaning |
|-------|---------|---------|
| 0 | 2 | Pure cascade, no hard moves needed |
| 1 | 13 | One hard move cracks it |
| 2 | 11 | Two hard moves |
| 3 | 9 | Three hard moves |
| Average | **2.8** | Just 3 hard moves for the world's hardest puzzles |

The cascade ratio (cascade placements per bottleneck) ranges from 1:6 to 1:57. The best case: **1 hard move → 57 cells cascade through singles.**
