# dxSudoku #103 — larsdoku Solve & Provenance Report

**Source:** dxSudoku Channel video #103, "Improved Bowman's Bingo Puzzle-Solving Technique" — the puzzle Andrew Stuart credits as the inspiration for the May 2026 Bowman's Bingo update on sudokuwiki.org.

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


`LZWing` is a post-catalog technique, so the catalog-era lookup uses only the techniques tracked at the time the catalog was built. The puzzle is genuinely new to the registry from this WIP state.

---

## Observation

From the WIP state shown in the video, larsdoku resolves the puzzle to completion using one ALS_XZ and one LZWing. No forcing-net logic is invoked at any point. This is a single data point, not a hierarchy claim — but it suggests that for this particular puzzle, the cleaner cut sits in the ALS / chain family rather than in whole-board forcing nets.

A natural follow-up: run the same procedure across a corpus of puzzles where Bowman's Bingo is the proposed solving step, and see how often ALS_XZ / LZWing / similar techniques resolve them deterministically. If the answer is "most of the time," the hierarchy slot for Bowman's Bingo tightens to the cases where these don't apply.

Happy to run that corpus benchmark whenever the unsolvables list is rerun.
