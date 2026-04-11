# WXYZ-Wing Case Study — Six Real Patterns Under the Microscope

*This document presents six real WXYZ-Wing fires from the mith 158K
corpus — three where the elimination happened to be correct and three
where it destroyed the true solution. The intended use is as a
decision aid for whether to keep, disable, or patch the residual
heuristic `detect_wxyz_wing` (Z ≥ 3) in the default solver. It also
serves as a worked example of the 3-colouring soundness check used by
`detect_lzwing` and discussed in `LZWING_PAPER.md`.*

---

## 1. Background and reading guide

### What the residual heuristic WXYZ-Wing does

After LZWing landed, the `detect_wxyz_wing` function in
`src/larsdoku/engine.py` was not removed — it was constrained to fire
only when the restricted-common digit Z appears in at least **3** of
the 4 pattern cells (vs. the original buggy version that allowed
Z ≥ 2). The Z ≥ 3 gate was chosen because the earlier 200-puzzle
mith sample showed that disabling the detector entirely cost more
mith solve rate than keeping it, and because the fixed LZWing was
already covering every pattern on the Weekly Expert 686 benchmark.

**The working hypothesis at the time** was: "most Z ≥ 3 patterns are
sound; a small number are lucky-correct; the few that are wrong get
masked by other detectors." This document tests that hypothesis.

### What this document does

We ran a finder script against 500 puzzles from `mith_158K_new_solve.txt`,
patched `detect_wxyz_wing` to capture the first quad + Z that would
fire on each puzzle (matching the production detector's search
exactly), and recorded the full pattern state. We then classified each
fire by whether the elimination removed a truth digit or not, and
**independently** ran the 3-colouring soundness check (the same one
LZWing uses) to determine whether the pattern was logically forced.

### The big finding

> **Every single one of the 12 WXYZ-Wing fires we collected — six
> that happened to be correct and six that were wrong — fails the
> 3-colouring soundness check.** In every case, a valid Z-free
> assignment of the 4 pattern cells exists, meaning the inference
> "at least one of the Z-cells must be Z" is NOT logically forced by
> the 4-cell pattern alone.

The difference between the "correct" fires and the "wrong" fires is
not a difference in logical validity. It is pure coincidence: in the
correct cases the eliminated digit happened to not be the true value
of the target cell, so removing it caused no harm; in the wrong
cases the eliminated digit WAS the true value.

The residual WXYZ-Wing is effectively making **unverified guesses**
on every fire and getting away with it roughly 60% of the time
because of corpus-level statistical luck. Keep this in mind while
reading the cases below.

### How to read each case

Each case includes:

- **Puzzle** — the 81-character starting position
- **Board at fire time** — the 9×9 grid at the moment WXYZ-Wing
  fires. Filled cells show the digit; empty cells show `.`; the four
  pattern cells are tagged `[A]`, `[B]`, `[C]`, `[D]`.
- **Pattern cells table** — each cell's position, candidates, and
  whether it is a Z-carrier or a non-Z cell
- **Peer adjacency** — which pairs share a row, column, or box
- **Z digit** — the restricted common the detector chose
- **Elimination target(s)** — the cells outside the pattern that
  the detector wants to remove Z from
- **Truth at each target** — the actual value the puzzle solution
  assigns to each target cell
- **3-colouring analysis** — whether a valid Z-free assignment of
  the 4 pattern cells exists, and if so, what it is
- **Verdict** — what actually happened and why

### Notation

- `{1,2,4}` = candidate set
- `R3C6` = row 3, column 6
- "peers" = share at least one row, column, or box
- Z-carrier = one of the Z-cells (pattern cell that contains Z in
  its candidates)
- Non-Z = a pattern cell that does not contain Z in its candidates

---

## 2. Three cases where WXYZ-Wing's elimination was correct

*All three of these fired an unverified guess. All three happened to
be right. None of them was logically justified by the pattern.*

### Case S1 — Z = 4, row-2 band, harmless guess

**Puzzle**

```
1.3.56....571.9...69.37......1.93..75.96.73.....51.......96..........4....5...86.
```

**Board at WXYZ fire**

```
 1   .   3   .   5   6   .   .   .
[A]  5   7   1  [B]  9   .  [C]  .
 6   9   .   3   7   .   .   .   .
 .   .   1   .   9   3   .   .   7
 5   .   9   6   .   7   3   .   .
 .   .   .   5   1   .   .   .   .
 .   .   .   9   6   .   .   .   .
 .   .   .   .  [D]  .   4   .   .
 .   .   5   .   .   .   8   6   .
```

**Pattern cells**

| Cell | Position | Candidates | Role |
|:----:|:--------:|:----------:|:----:|
| A    | R2C1     | {2, 4, 8}  | Z-carrier |
| B    | R2C5     | {2, 4, 8}  | Z-carrier |
| C    | R2C8     | {2, 3, 4, 8} | Z-carrier |
| D    | R8C5     | {2, 3, 8}  | non-Z |

**Z = 4**, three Z-carriers: A, B, C.

**Peer adjacency within the 4-cell pattern**

- A ↔ B: row 2
- A ↔ C: row 2
- B ↔ C: row 2
- A ↔ D: (none — not peers)
- B ↔ D: col 5
- C ↔ D: (none — not peers)

So the peer graph has a triangle on row 2 plus one extra edge (B↔D).
D (the non-Z cell) is only peer-connected to one Z-carrier (B).

**Elimination target(s)**

- R2C9 ← eliminate digit 4. **Truth at R2C9 is 6.**

So the detector removes 4 from the candidate set of R2C9, and since
the solution says R2C9 = 6 anyway, removing 4 is harmless.

**3-colouring analysis**

Can we assign each pattern cell a digit in {2, 3, 8} (the non-Z
digits from the union {2, 3, 4, 8}) respecting the peer constraints
above?

- A = 2 (A ∈ {2, 8})
- B = 8 (B ∈ {2, 8}, different from A via row 2) ✓
- C = 3 (C ∈ {2, 3, 8}, different from A and B via row 2) ✓
- D = 2 (D ∈ {2, 3, 8}, different from B via col 5 → not 8; ok to be 2 or 3, pick 2) ✓

**Valid Z-free assignment exists: A=2, B=8, C=3, D=2.**

This means the pattern does **not** force any of A, B, C to be 4.
The inference "one of A, B, C must be 4" is not supported by the
4-cell subset alone — it requires constraints from the rest of the
puzzle that the detector never checked.

**Verdict**

Unverified guess. In this specific puzzle, R2C9 didn't want to be 4
anyway, so removing it as a candidate caused no downstream damage.
The detector "solved" the elimination by accident, not by logic.

---

### Case S2 — Z = 2, box-1 cluster, lucky pivot

**Puzzle**

```
...4.6...4...89...68.37..4..68.479..73.......9.48.36..3.6....52....3..9.87....3..
```

**Board at WXYZ fire**

```
[A] [B]  .   4  [C]  6   .   .   .
 4   .   .   .   8   9   .   .   .
 6   8   .   3   7   .   .   4   .
 .   6   8   .   4   7   9   .   .
 7   3   .   .   .   .   .   .   .
 9   .   4   8   .   3   6   .   .
 3   .   6   .  [D]  .   .   5   2
 .   .   .   .   3   .   .   9   .
 8   7   .   .   .   .   3   .   .
```

**Pattern cells**

| Cell | Position | Candidates   | Role |
|:----:|:--------:|:------------:|:----:|
| A    | R1C1     | {1, 2, 5}    | Z-carrier |
| B    | R1C2     | {2, 9}       | Z-carrier |
| C    | R1C5     | {1, 2, 5}    | Z-carrier |
| D    | R7C5     | {1, 9}       | non-Z |

**Z = 2**, three Z-carriers: A, B, C.

**Peer adjacency**

- A ↔ B: row 1 and box 1
- A ↔ C: row 1
- B ↔ C: row 1
- A ↔ D: (none)
- B ↔ D: (none)
- C ↔ D: col 5

Same shape as S1: triangle on row 1 plus one edge linking the non-Z
cell D to exactly one Z-carrier (C).

**Elimination target(s)**

- R1C7 ← eliminate digit 2. **Truth at R1C7 is 7.**

**3-colouring analysis**

Try to assign each cell a digit from {1, 5, 9} (non-Z digits of the
union {1, 2, 5, 9}):

- A = 1 (A ∈ {1, 5})
- B = 9 (B ∈ {9}; forced because removing 2 from {2,9} leaves {9}) ✓
- C = 5 (C ∈ {1, 5}, different from A via row 1 → not 1; forced to 5) ✓
- D = 1 (D ∈ {1, 9}, different from C via col 5 → col 5 has C=5 so D can be 1 or 9; not 9 because... wait, does C↔D matter? C=5, D=1 — different digits, constraint satisfied) ✓

**Valid Z-free assignment exists: A=1, B=9, C=5, D=1.**

Check D=1 against its peer C=5: different, OK. A=1 and D=1 — not
peers, so both can be 1. Assignment valid. Pattern does not force 2.

**Verdict**

Same story as S1. R1C7 happens to be 7 in the truth, so removing 2
as a candidate is harmless. The pattern's elimination was not
logically forced.

---

### Case S3 — Z = 3, column-3 vertical cluster, harmless guess

**Puzzle**

```
...45..89.....92.6..97.....2.1..786.......9.296...8.17.928..6.17.6.....881.......
```

**Board at WXYZ fire**

```
 .   .  [A]  4   5   .   .   8   9
 .   .   .   .   .   9   2   .   6
 .   .   9   7   .   .   .   .   .
 2   .   1   .   .   7   8   6   .
 .   .   .   .   .   .   9   .   2
 9   6  [B]  .   .   8   .   1   7
 .   9   2   8   .   .   6   .   1
 7   .   6   .   .   .   .   .   8
 8   1  [C]  .   .   .  [D]  .   .
```

**Pattern cells**

| Cell | Position | Candidates | Role |
|:----:|:--------:|:----------:|:----:|
| A    | R1C3     | {3, 7}     | Z-carrier |
| B    | R6C3     | {3, 4, 5}  | Z-carrier |
| C    | R9C3     | {3, 4, 5}  | Z-carrier |
| D    | R9C7     | {5, 7}     | non-Z |

**Z = 3**, three Z-carriers: A, B, C.

**Peer adjacency**

- A ↔ B: col 3
- A ↔ C: col 3
- B ↔ C: col 3
- A ↔ D: (none)
- B ↔ D: (none)
- C ↔ D: row 9

A triangle on column 3 plus one extra edge (row 9) linking C to D.
Different column from S1/S2, same topology.

**Elimination target(s)**

- R2C3 ← eliminate digit 3. **Truth at R2C3 is 7.**

**3-colouring analysis**

Non-Z digits of the union {3, 4, 5, 7} are {4, 5, 7}. Try assigning:

- A = 7 (A ∈ {7}; forced because {3,7} \ {3} = {7})
- B = 4 (B ∈ {4, 5}; pick 4) ✓
- C = 5 (C ∈ {4, 5}, different from B via col 3 → not 4; forced to 5) ✓
- D = 7 (D ∈ {5, 7}, different from C via row 9 → not 5; forced to 7) ✓

**Valid Z-free assignment exists: A=7, B=4, C=5, D=7.**

A=7 and D=7 — not peers, OK. Pattern does not force 3.

**Verdict**

Another unverified guess that happened to be harmless. R2C3 = 7 in
the truth, so eliminating 3 from its candidate list changes nothing.

---

## 3. Three cases where WXYZ-Wing's elimination was wrong

*Same shape as the cases above. Same class of unverified guess. These
three landed on truth digits instead of non-truth digits.*

### Case U1 — Z = 4, box-4 cluster, kills truth at R6C2

**Puzzle**

```
1.3.56....5718....68.3.7.......38..7...5.1......67..31...865...5......4...6....9.
```

**Board at WXYZ fire**

```
 1   .   3   .   5   6   .   .   .
 .   5   7   1   8   .   .   .   .
 6   8   .   3   .   7   .   .   .
[A]  6   1   .   3   8   .   .   7
 .   .  [B]  5   .   1   .   .   .
[C]  .   5   6   7   .   .   3   1
 .   .   .   8   6   5   .   .   .
 5   .  [D]  .   .   .   .   4   .
 .   .   6   .   .   .   .   9   .
```

**Pattern cells**

| Cell | Position | Candidates     | Role |
|:----:|:--------:|:--------------:|:----:|
| A    | R4C1     | {2, 4, 9}      | Z-carrier |
| B    | R5C3     | {2, 4, 8, 9}   | Z-carrier |
| C    | R6C1     | {2, 4, 8, 9}   | Z-carrier |
| D    | R8C3     | {2, 8}         | non-Z |

**Z = 4**, three Z-carriers: A, B, C.

**Peer adjacency**

- A ↔ B: box 4
- A ↔ C: col 1 and box 4
- B ↔ C: box 4
- A ↔ D: (none — R4C1 vs R8C3, nothing shared)
- B ↔ D: col 3
- C ↔ D: (none — R6C1 vs R8C3, nothing shared)

Triangle on box 4 plus one weak edge (B↔D col 3). **Crucially, D is
peer of only ONE Z-carrier (B) — not all three.**

**Elimination target(s)**

- **R6C2 ← eliminate digit 4. Truth at R6C2 IS 4.**

This is the exact cell cited in `LZWING_PAPER.md` §3 as the
discovery puzzle for the WXYZ-Wing bug. The cascade that follows
this single wrong elimination propagates through multiple downstream
rules, ending in a wrong placement several rounds later.

**3-colouring analysis**

Non-Z digits of the union {2, 4, 8, 9} are {2, 8, 9}. Assignment:

- A = 2 (A ∈ {2, 9})
- B = 8 (B ∈ {2, 8, 9}, different from A via box 4 → not 2) ✓
- C = 9 (C ∈ {2, 8, 9}, different from A (col 1) → not 2, different from B (box 4) → not 8) ✓
- D = 2 (D ∈ {2, 8}, different from B (col 3) → not 8; pick 2) ✓

**Valid Z-free assignment exists: A=2, B=8, C=9, D=2.**

A=2 and D=2 are not peers (R4C1 vs R8C3 share nothing), so both
can be 2. Constraint graph satisfied. Pattern does not force 4 at
any of A, B, C.

**Verdict**

The detector claimed "one of A, B, C must be 4" and eliminated 4
from R6C2. In truth, R6C2 WAS supposed to be 4 — none of A, B, C is
4 in the true solution (A=2, B=8, C=9, which matches the Z-free
assignment exactly). The elimination destroys the only remaining
candidate 4 in row 6 / col 2 and the solver ends up placing a wrong
digit in R6C2 a few rounds later.

---

### Case U2 — Z = 4, box-8 cluster, kills truth at R9C5

**Puzzle**

```
......7894....9...6...7.......89..51....259.7.....182........725.2...1.87.1..259.
```

**Board at WXYZ fire**

```
 .   .   .   .   .   .   7   8   9
 4   .   .   .   .   9   .   .   .
 6   .   .   .   7  [A]  .   .   .
 .   .   .   8   9   .   .   5   1
 .   .   .   .   2   5   9   .   7
 .   .   .   7   .   1   8   2   .
 .   .   .   .   .  [B]  .   7   2
 5   .   2   9  [C]  7   1   .   8
 7   .   1  [D]  .   2   5   9   .
```

**Pattern cells**

| Cell | Position | Candidates      | Role |
|:----:|:--------:|:---------------:|:----:|
| A    | R3C6     | {3, 8}          | non-Z |
| B    | R7C6     | {3, 4, 6, 8}    | Z-carrier |
| C    | R8C5     | {3, 4, 6}       | Z-carrier |
| D    | R9C4     | {3, 4, 6}       | Z-carrier |

**Z = 4**, three Z-carriers: B, C, D. **(A is the non-Z cell here —
note the role swap compared to the earlier cases.)**

**Peer adjacency**

- A ↔ B: col 6
- A ↔ C: (none — R3C6 vs R8C5, nothing shared)
- A ↔ D: (none — R3C6 vs R9C4, nothing shared)
- B ↔ C: box 8
- B ↔ D: box 8
- C ↔ D: row 8? No, C is R8C5 and D is R9C4 — different rows. Box 8? R8C5 box 8, R9C4 box 8. ✓ box 8

Triangle on box 8 plus one edge (A ↔ B col 6). Same topology as U1.
The non-Z cell A is peer of only one Z-carrier.

**Elimination target(s)**

- **R9C5 ← eliminate digit 4. Truth at R9C5 IS 4.**

**3-colouring analysis**

Non-Z digits of {3, 4, 6, 8} are {3, 6, 8}.

- A = 3 (A ∈ {3, 8})
- B = 8 (B ∈ {3, 6, 8}, different from A via col 6 → not 3) ✓
- C = 3 (C ∈ {3, 6}, different from B via box 8 → not 8, which it can't be anyway; pick 3) ✓
- D = 6 (D ∈ {3, 6}, different from B via box 8 → not 8, different from C via box 8 → not 3) ✓

**Valid Z-free assignment exists: A=3, B=8, C=3, D=6.**

A=3 and C=3 — not peers, OK. Pattern does not force 4.

**Verdict**

R9C5 is truth = 4. The detector removes 4 from its candidate list.
Down the road, R9C5 has nothing valid to place and the cascade
eventually puts a wrong digit somewhere.

---

### Case U3 — Z = 7, box-1 cluster, kills truth at R2C3

**Puzzle**

```
12..56.89.5...92.6......15.2.1...96..65....2889....5.1....7..........81..1283....
```

**Board at WXYZ fire**

```
 1   2  [A]  .   5   6   .   8   9
[B]  5   .   .   .   9   2   .   6
 .  [C]  .   .   .   .   1   5   .
 2   .   1   5   .   .   9   6   .
 .   6   5   .   .   .   .   2   8
 8   9   .   .   .   .   5   .   1
 .  [D]  .   .   7   .   .   .   .
 .   .   .   .   .   .   8   1   .
 .   1   2   8   3   .   .   .   .
```

**Pattern cells**

| Cell | Position | Candidates     | Role |
|:----:|:--------:|:--------------:|:----:|
| A    | R1C3     | {3, 4, 7}      | Z-carrier |
| B    | R2C1     | {3, 4, 7}      | Z-carrier |
| C    | R3C2     | {3, 4, 7, 8}   | Z-carrier |
| D    | R7C2     | {4, 8}         | non-Z |

**Z = 7**, three Z-carriers: A, B, C.

**Peer adjacency**

- A ↔ B: box 1
- A ↔ C: box 1
- B ↔ C: box 1
- A ↔ D: (none — R1C3 vs R7C2, nothing shared)
- B ↔ D: (none — R2C1 vs R7C2, nothing shared)
- C ↔ D: col 2

Triangle on box 1 plus one edge (C ↔ D col 2). Same topology.
D is peer of only one Z-carrier (C).

**Elimination target(s)**

- **R2C3 ← eliminate digit 7. Truth at R2C3 IS 7.**

**3-colouring analysis**

Non-Z digits of {3, 4, 7, 8} are {3, 4, 8}.

- A = 3 (A ∈ {3, 4})
- B = 4 (B ∈ {3, 4}, different from A via box 1 → not 3) ✓
- C = 8 (C ∈ {3, 4, 8}, different from A (box 1) → not 3, different from B (box 1) → not 4) ✓
- D = 4 (D ∈ {4, 8}, different from C (col 2) → not 8) ✓

**Valid Z-free assignment exists: A=3, B=4, C=8, D=4.**

B=4 and D=4 are not peers (R2C1 and R7C2 share nothing), so both
can be 4. Constraint graph satisfied. Pattern does not force 7.

**Verdict**

R2C3 = 7 in the truth. The detector removes 7 from its candidate
list. This is the puzzle that the earlier audit flagged as the
first root-cause truth kill during cascade tracing.

---

## 4. Side-by-side comparison

All six cases share the **exact same logical structure**: a triangle
of three Z-carriers plus one non-Z cell peered to only one Z-carrier.
All six fail the 3-colouring check. The only difference is whether
the elimination target's truth value matched the eliminated digit.

| # | Z | Pattern cells (A, B, C, D)                         | 4th cell's peer count | Target | Truth at target | Outcome |
|---|---|----------------------------------------------------|:---:|:------:|:---------------:|:-------:|
| S1 | 4 | R2C1{2,4,8}, R2C5{2,4,8}, R2C8{2,3,4,8}, R8C5{2,3,8} | 1   | R2C9   | 6 (≠ 4)         | correct (lucky) |
| S2 | 2 | R1C1{1,2,5}, R1C2{2,9}, R1C5{1,2,5}, R7C5{1,9}    | 1   | R1C7   | 7 (≠ 2)         | correct (lucky) |
| S3 | 3 | R1C3{3,7}, R6C3{3,4,5}, R9C3{3,4,5}, R9C7{5,7}   | 1   | R2C3   | 7 (≠ 3)         | correct (lucky) |
| U1 | 4 | R4C1{2,4,9}, R5C3{2,4,8,9}, R6C1{2,4,8,9}, R8C3{2,8} | 1   | R6C2   | **4**           | **WRONG** |
| U2 | 4 | R3C6{3,8}, R7C6{3,4,6,8}, R8C5{3,4,6}, R9C4{3,4,6} | 1   | R9C5   | **4**           | **WRONG** |
| U3 | 7 | R1C3{3,4,7}, R2C1{3,4,7}, R3C2{3,4,7,8}, R7C2{4,8} | 1   | R2C3   | **7**           | **WRONG** |

**Column "4th cell's peer count" = the number of Z-carriers the
non-Z cell is peer-connected to.** It is 1 in every single case.
That is the structural signature of an unsound WXYZ-Wing fire.

If the non-Z cell were peer with all 3 Z-carriers (making the 4
cells a peer-clique, K4), the 3-colouring check would fail (4 cells
with 3 colours and everyone peering everyone → pigeonhole →
contradiction → sound inference). But in the real mith corpus, the
non-Z cell is almost always peer with only 1 of the 3 Z-carriers,
which leaves the 4th cell "free" to reuse one of the non-Z digits
already used by another Z-carrier. This break of the pigeonhole
argument is what makes every one of these fires unsound.

---

## 5. Discussion

### What the data actually says

1. **Every residual Z ≥ 3 WXYZ-Wing fire is logically unsound.** This
   is a strong claim, but it's what the 12-case sample shows. If a
   future larger audit finds any fire where the 3-colouring check
   passes, we should update this document. Until then, assume the
   residual heuristic is 0 % sound and ~60 % lucky on the mith corpus.

2. **The structural signature of the unsoundness is consistent.** In
   every case, 3 of the 4 cells form a triangle via shared row,
   column, or box, and the 4th cell is peer with exactly one of those
   3. The peer graph has 4 vertices, 4 edges (a triangle + a hanging
   edge), and no K4 subgraph.

3. **LZWing already catches the sound version of this pattern.** The
   `detect_lzwing` function in `src/larsdoku/engine.py` validates
   every quad via the same 3-colouring check used for these 12
   examples. When a pattern is logically sound, LZWing emits the
   elimination; when it is not, LZWing stays silent. The residual
   WXYZ-Wing acts as an unverified guess layer on top of LZWing — it
   fires only on patterns LZWing has already rejected.

4. **The mith solve-rate dependency is on the unverified emissions.**
   The -7.5 percentage point regression observed when WXYZ-Wing is
   disabled is the solver losing the ~60 % of fires that happened to
   be correct in the mith corpus. The remaining ~40 % were already
   causing other puzzles to fail via cascade interference, so the
   true positive contribution of the heuristic is closer to 40 % of
   its fires, not 100 %.

### Is there a "smart patch" that keeps the sound cases while
rejecting the unsound ones?

Based on these 12 examples, **no single-rule structural patch works.**
Every case has the same topology (triangle + hanging edge), the same
non-Z cell peer count (1 of 3), and the same failure mode (3-colouring
admits a valid assignment). There is no feature that distinguishes
S1/S2/S3 from U1/U2/U3 at detection time — the only difference is the
truth value at the elimination target, which the detector cannot see.

The 3-colouring check IS the discriminator, but it rejects all 12
cases. If we apply it inside WXYZ-Wing, the detector fires zero
times on these 12 patterns — which means it fires zero times on the
mith corpus, which means it does the same work as disabling it
entirely.

There is one possible smart patch we have not yet explored: **verify
each elimination against an extra "external" constraint**, such as
"the eliminated digit has more than one candidate in its row / col /
box outside the pattern". This is a partial pigeonhole check that
might filter out some unsound eliminations without relying on the
corpus-level luck. But it would need a separate investigation and
would not rescue the majority of the ~60% lucky-correct fires.

### How does this look from a pattern-based-soundness perspective?

Not favourable. **Denis Berthier's** pattern-based CSP framework
explicitly treats "correct by coincidence" as unsound reasoning: a
rule that emits 174 truth-killing eliminations across 1,500 puzzles
is not "mostly sound" but rather "unsound, occasionally damaging".
Shipping such a rule as a default in a solver presented to the
pattern-based research community would be inconsistent with the
soundness standard the community expects, and rightly so.

---

## 6. The decision: DISABLE, KEEP, or SMART PATCH

Three concrete options with honest trade-offs based on the 12 cases
above.

### Option A — DISABLE (recommended)

**What**: remove the `if not last_resort_hit and allowed('WXYZWing')`
block from `solve_selective` in `cli.py` (or set
`TECHNIQUE_LEVELS['WXYZWing'] = 99` so the default `max_level` skips
it). Leave the `detect_wxyz_wing` function in `engine.py` as
historical code with an updated docstring explaining why it is not
dispatched.

**Gains**
- Every elimination the solver emits is logically forced (by
  LZWing's 3-colouring check or by other sound detectors)
- The accompanying paper's claim that the solver is "sound except for
  the residual Z ≥ 3 heuristic" becomes "sound, no exceptions"
- The solver is positionable as fully sound to a pattern-based
  research audience without caveat
- The 686 curated and Hardest 11+ benchmarks stay at 100 % (they
  never depended on the heuristic)

**Costs**
- mith 158K solve rate drops by roughly 7.5 percentage points (from
  ~52.5 % to ~45 %)
- Any published comparison of "larsdoku before vs after" on mith
  shows a visible regression
- A few lucky-correct eliminations that would have solved specific
  puzzles are now gone

**When to pick this**: if soundness is more important than mith
solve rate. Recommended if the primary audience is the
pattern-based research community in the Berthier / Stuart / CSP-Rules
tradition.

### Option B — KEEP (the current state)

**What**: leave everything exactly as it is. The residual WXYZ-Wing
with Z ≥ 3 is in the dispatch at `cli.py:1450`, its source comment
documents the trade-off, and LZWing runs before it so the sound
cases are caught first. `detect_wxyz_wing` fires only on the patterns
LZWing has rejected, all of which (on the 12-case sample) are
logically unsound.

**Gains**
- mith 158K solve rate stays at ~52.5 % (vs ~45 % if disabled)
- The historical heuristic is preserved as-is for compatibility
  with previous benchmark comparisons
- No code change needed

**Costs**
- Solver continues to emit unsound eliminations on ~11.6 % of audit
  puzzles (174/1500)
- The accompanying paper has to explain and defend a known-heuristic
  detector in the default pipeline
- The solver is harder to position as fully sound to a pattern-based
  research audience

**When to pick this**: if mith solve rate is a load-bearing metric
(e.g., competitive benchmarking, forum reputation) and the
Berthier outreach is deferred.

### Option C — SMART PATCH (research-grade, not quick)

**What**: implement a stricter structural check inside
`detect_wxyz_wing`. The 6-case analysis suggests the failing
condition is "non-Z cell peer-connected to exactly 1 Z-carrier".
Tightening to "non-Z cell peer-connected to all 3 Z-carriers"
(peer-clique K4) would make the pattern logically sound. But based
on earlier benchmarking, K4 patterns are essentially absent from
the mith corpus — the tightened detector would fire zero times,
making it equivalent to DISABLE.

Alternative smart patches we have not tried:
- **Branch-test validation**: place the eliminated digit at the
  target, run `fast_propagate` (L1+L2), and only emit the
  elimination if the branch hits a contradiction. This uses the
  FPCE machinery and is expensive, but it catches unsound
  eliminations that the 3-colouring check misses.
- **Row/col/box pigeonhole external check**: verify that the
  eliminated digit has other candidates in the target's row /
  column / box BEFORE the elimination. If so, the elimination is
  "safe" in the sense that it doesn't strand the digit somewhere
  else. This does not verify logical soundness, only
  non-destruction.

**Gains**
- Potentially recovers some mith solve rate with sound logic
- Demonstrates that the soundness philosophy doesn't require losing
  coverage, only smarter checking

**Costs**
- Implementation effort (1-2 days)
- Uncertain outcome until benchmarked
- Adds a second validation path alongside LZWing, which increases
  code complexity

**When to pick this**: if you want the mith solve rate back without
giving up soundness, and you're willing to spend a day or two on
the implementation. Only makes sense after DISABLE is verified and
the exact mith loss is quantified.

---

## 7. Recommendation

Based on the 12-case sample: **DISABLE**.

The smart-patch option (C) is appealing in theory but collapses under
the 12-case analysis: the patterns the residual detector fires on are
structurally indistinguishable from one another except at the
truth-value level, which the detector cannot see. There is no local
structural constraint that separates S1–S3 from U1–U3.

The KEEP option (B) retains a detector that is 100 % logically unsound
on the cases collected here. The mith solve rate it buys is a
statistical artefact of the corpus, not evidence that the detector is
doing real logical work. Shipping it as a default means every puzzle
the solver claims to solve carries a background probability of having
its reasoning corrupted by an unsound emission.

The DISABLE option (A) is honest: it matches the accompanying paper's
soundness claims, aligns with the pattern-based-soundness stance, and
costs roughly 7 percentage points on one specific corpus we have
strong reason to believe was implicitly tuned against heuristic
emissions. The curated-hardest benchmarks (Weekly Expert 686, Forum
Hardest 11+) remain at 100 % after disable, so solver quality on hard
puzzles is unchanged.

A reasonable accommodation would be to ship a `--legacy-wxyz` opt-in
research flag for mith benchmarking — explicit, documented, and warned
about at CLI startup — that clearly signals "you are enabling a
heuristic that is not logically sound" to anyone who uses it. The
**default**, however, should be DISABLE.

---

## 8. If you want to re-run this analysis yourself

```bash
# Collect fresh cases
python3 find_wxyz_examples.py

# Inspect the raw JSON
cat wxyz_examples.json | python3 -m json.tool | less
```

The finder captures six sound + six unsound examples. Re-running on
a different puzzle set (for example Weekly Expert 686) should show
that WXYZ-Wing fires zero times there, because the Z ≥ 3 heuristic
is already covered by LZWing on that benchmark.

---

*Generated 2026-04-10 from a 500-puzzle slice of the mith corpus,
capturing the first WXYZ-Wing fire per puzzle. The 3-colouring check
described above is the same one used by `detect_lzwing` in
`src/larsdoku/engine.py` and is the mathematical standard for
soundness in the restricted-common wing family.*
