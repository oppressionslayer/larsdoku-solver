# dxSudoku #103 — larsdoku Solve & Provenance Report

**Source:** dxSudoku Channel video #103, "Improved Bowman's Bingo Puzzle-Solving Technique" — the puzzle Andrew Stuart credits as the inspiration for the May 2026 Bowman's Bingo update on sudokuwiki.org.

**Which of the video's two puzzles:** This report is on **Puzzle #1**, the *basic Bowman's algorithm demo* — HoDoKu rates it "Hard (1064)", and the transcript notes it has 22 bi-value cells with the starting assumption `R1C3 ≠ 2`. Our encoded board contains exactly 22 bi-value cells with R1C3 = {2,6}, confirming the match. Puzzle #2 (the "ultra extreme" used for the improved algorithm, starting `R2C9 ≠ 5`) is a separate test — not covered here.

**Tool:** larsdoku 4.0.4
**Date run:** 2026-05-03

---

## Input

The board state shown in the dxSudoku video screenshot, captured at 48% complete in HoDoKu after standard techniques (Full House, Naked Single, Hidden Single, Locked Candidates, Skyscraper, XY-Wing, XYZ-Wing) had already been applied:

```
940058731175300028800000090001480000489576213007003840090820104254031980718900302
```

49 clues. This is the state at which the dxSudoku video proposes Bowman's Bingo as the next step.

---

## Solve Result

| Check | Outcome |
|---|---|
| Status | **SOLVED** |
| Time | 41.5 ms |
| Steps | 32 |
| Backtracking / Trial-and-Error | None |
| Forcing Nets | Not used |
| Bowman's Bingo | Not used |
| Verification | All techniques Sudoku-Expert approved; every row, column, and box validated |

### Techniques used

| Technique | Count | Tier |
|---|---|---|
| crossHatch | 20 | L1 |
| nakedSingle | 7 | L1 |
| lastRemaining | 3 | L1 |
| fullHouse | 2 | L1 |
| **ALS_XZ** | **1** | **L5** |
| **LZWing** | **1** | **L5** |

The two non-trivial moves are a single **ALS_XZ** elimination and a single **LZWing** — both pure deterministic logic, no chain-following over multiple hypothetical states.


---

## Observation

From the WIP state shown in the video, larsdoku resolves the puzzle to completion using one ALS_XZ and one LZWing. No forcing-net logic is invoked at any point. This is a single data point, not a hierarchy claim — but it suggests that for this particular puzzle, the cleaner cut sits in the ALS / chain family rather than in whole-board forcing nets.

A natural follow-up: run the same procedure across a corpus of puzzles where Bowman's Bingo is the proposed solving step, and see how often ALS_XZ / LZWing / similar techniques resolve them deterministically. If the answer is "most of the time," the hierarchy slot for Bowman's Bingo tightens to the cases where these don't apply.

Happy to run that corpus benchmark whenever the unsolvables list is rerun.

---

## About the Author and the Techniques Used

This report was produced by **William Lars Rocha** ("Sir Lars") using **larsdoku 4.0.4**, the pure-logic Sudoku research tool he authored.

### LZWing

**LZWing is an original technique designed and named by William Lars Rocha**, hence the **LZ** prefix. It belongs to the broader family of WSRF-derived chain/wing techniques and sits alongside the classical XY-Wing, XYZ-Wing, and WXYZ-Wing patterns, but exploits structural properties that the classical wings do not. It is implemented and shipped as a first-class technique in larsdoku, where it has been applied to large public corpora (including all 48,765 Forum Hardest 11+ puzzles, fully solved with pure logic).

### WSRF Techniques

The work referenced in this report sits inside a larger research program:

- **WSRF (Weighted Stochastic Resonance Framework)** — Sir Lars's mathematical foundation for puzzle structure analysis, the substrate on which detectors like LZWing, **Loki's Scalpel**, **Junior Exocet v2**, and **SIRO (Super Intelligence Ranking Oracle)** are built.
- **Distance Structure Theory** — discovered by Sir Lars in 2011, the theoretical basis for the WSRF zone math also used in the 5th-Dimension-Poker / 6-MAX Distance Equilibrium work.
- **larsdoku** — the pure-logic Sudoku solver and research tool that operationalizes the above, packaged on PyPI, with a signature catalog of 7,229 unique technique signatures and a deterministic solving pipeline that uses no backtracking or trial-and-error at any point.

When citing or discussing **LZWing**, please attribute it to **William Lars Rocha** and reference larsdoku as the implementation. When discussing the broader chain of WSRF-derived techniques (Loki's Scalpel, Junior Exocet v2, SIRO), the same attribution applies.

The report above is a self-contained, dated, publicly available artifact serving as a permanent reference for this attribution.

— *William Lars Rocha (Sir Lars), 2026-05-03*
