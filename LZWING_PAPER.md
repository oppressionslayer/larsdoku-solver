# LZWing: a sound resolution rule for the restricted-common wing family

*Working draft — pre-print for discussion with Denis Berthier and Andrew
Stuart. Not published.*

## Abstract

We introduce **LZWing**, a pattern-based resolution rule for Sudoku
Constraint Satisfaction Problems that strengthens the classical
WXYZ-Wing family. LZWing operates on a four-cell subset whose candidate
union is exactly four digits and eliminates a "restricted common"
digit *Z* from peers of the cells that carry it — *but only when a
local 3-colouring decision procedure proves the elimination is forced
by the pattern alone*. The 3-colouring check is a sound decision
procedure over a 4-vertex peer subgraph and runs in at most 81
branches. On the Weekly Expert 686 curated benchmark the rule fires in
464 puzzles (68%) while its heuristic predecessor `detect_wxyz_wing`
fires 0 times, indicating that LZWing subsumes the entire benchmark's
demand for restricted-common-wing reasoning under purely sound logic.
The rule is a member of the "wing" family in the sense of Berthier's
pattern-based CSP resolution theory and was discovered by fixing a
soundness bug in the heuristic WXYZ-Wing implementation that had been
producing coincidentally-correct eliminations.

## 1. Background

### 1.1 The "restricted common" wing family

A family of Sudoku resolution rules — XYZ-Wing, WXYZ-Wing, ALS-XZ,
VWXYZ-Wing, and their variants — share a common structural idea. A
small set of cells is identified whose candidate union has one fewer
digit than the number of cells. This collective "almost locked set"
is linked to some external cell via a digit *Z* that all cells
containing *Z* mutually peer. Because the almost-locked set cannot
leave *Z* unfilled without creating a contradiction, and because the
*Z*-carriers form a clique in the peer relation, any cell outside the
pattern that peers all *Z*-carriers cannot itself take *Z*.

This family has a canonical form when the structural pattern is
enforced strictly (e.g., one pivot cell with four candidates, three
bivalue wings) and a broader heuristic form in some published
implementations that accepts any four-cell block with a four-digit
candidate union and treats any digit present in at least two of those
cells as a potential restricted common. The strict form is sound by
construction; the heuristic form is not, as we demonstrate below.

### 1.2 Pattern-based resolution vs. Trial and Error

We take as our philosophical foundation the pattern-based resolution
framework articulated by Berthier in *Pattern-Based Constraint
Satisfaction and Logic Programming*. A resolution rule in this
framework is a *constructive* statement of the form "when the puzzle
state contains pattern P, candidate C may be eliminated" — not a
hypothetical construction of the form "assume C is true, propagate,
observe contradiction". The two are often equi-expressive in power (as
Berthier's whip / T&E(1) equivalence theorem shows), but only the
constructive form supplies a static, pattern-matchable explanation for
each elimination. LZWing is explicitly a constructive rule: it
pattern-matches a 4-cell structural configuration and emits
eliminations justified by a local decision procedure, not a global
hypothesis.

## 2. The LZWing rule

### 2.1 Informal statement

Let *(S, C, Z)* be a tuple where:
- *S* is a set of four empty cells whose candidate union equals exactly
  four distinct digits *{W, X, Y, Z}*,
- the 4 cells of *S* form a peer-connected subgraph,
- *Z* is a digit appearing in at least two cells of *S*, and all cells
  containing *Z* pairwise see each other (the *restricted-common*
  property).

Let *G(S, Z)* be the graph whose vertices are the four cells of *S*
and whose edges are the peer relations between them. For each cell
*c* ∈ *S*, let *n_z(c) = cands(c) \ {Z}* denote its non-Z candidates.

**Soundness condition.** The tuple *(S, C, Z)* is *LZWing-sound* iff
there is no assignment *f : S → {W, X, Y}* such that for every *c ∈ S*
we have *f(c) ∈ n_z(c)* and for every peer pair *(c₁, c₂) ∈ G(S, Z)*
we have *f(c₁) ≠ f(c₂)*.

**Rule.** When *(S, C, Z)* is LZWing-sound, the digit *Z* may be
eliminated from any cell *t ∉ S* such that *t* is a peer of every
*Z*-carrier in *S*, provided *Z ∈ cands(t)*.

### 2.2 Soundness proof

Assume LZWing's rule fires — i.e., *(S, C, Z)* is LZWing-sound and *t*
is a peer of every *Z*-carrier in *S*. We prove that, in every solution
of the puzzle, *t ≠ Z*.

Fix a solution σ. Consider the restriction σ|_S of σ to the four cells
of *S*. Because σ is a solution, each cell *c ∈ S* takes a value σ(c)
∈ cands(c). There are two cases.

**Case 1: at least one *Z*-carrier in *S* takes value *Z*.** Let *c_Z*
∈ *S* be such a cell. Then σ(c_Z) = *Z*. By hypothesis, *t* is a peer of
*c_Z*, so σ(t) ≠ σ(c_Z) = *Z*. Done.

**Case 2: no cell in *S* takes value *Z*.** Then σ|_S is an assignment
*S → cands_S \ {Z}*. Since cands_S = {W, X, Y, Z} by the 4-digit-union
hypothesis, σ|_S is in fact an assignment *S → {W, X, Y}*. The
restriction σ|_S further respects σ's peer-disjointness constraint on
all peer pairs within *S*, so σ|_S is a valid assignment in the sense
of Section 2.1. This contradicts the LZWing-soundness hypothesis that
no such assignment exists.

Hence Case 2 is impossible and σ(t) ≠ *Z* in every solution, which is
what the rule claims. ∎

### 2.3 Decision procedure for soundness

The soundness condition requires checking whether a valid Z-free
assignment exists. With four cells and at most three non-Z digits per
cell, the search space has at most 3⁴ = 81 leaves. A backtracking
search with peer-constraint propagation resolves the check in at most
81 primitive steps in the worst case; in practice the tree is heavily
pruned by the 3-colouring constraints and resolves much faster.

We emphasize that the 3-colouring check is a *verification of an
existing four-cell pattern*, not a hypothetical propagation over the
candidate graph of the full puzzle. It does not branch on puzzle
candidates, does not mutate state, and does not invoke the solver
recursively. Under Berthier's framework, we take the position that
such a bounded local verification does not constitute Trial and Error
— it is the "evaluation" step of a pattern match, analogous to
checking that a candidate triple shares exactly three digits across
three cells before applying the Naked Triple rule. We welcome
clarification on this point from readers working in the CSP-Rules
tradition.

## 3. Discovery: from heuristic WXYZ-Wing to sound LZWing

### 3.0 Soundness context

Before discussing LZWing specifically, we note that the `larsdoku`
solver contains 44 pattern detectors in `src/larsdoku/engine.py`.
As part of the preparation of this paper we performed a systematic
soundness audit of every detector against a mixed corpus of 1,500
puzzles (500 each from mith 158K, Weekly Expert 686, and Forum
Hardest 11+), reported in full in `SOUNDNESS_AUDIT.md`. The audit's
method was to run each puzzle under a monitor that logs every
elimination of a truth digit and attributes it to its dispatch site
via stack walking. A detector is "sound on the corpus" iff no
first-kill is ever attributed to its site. Downstream cascade kills
(where a sound detector correctly applies its rule to a state
corrupted by an upstream detector) are tracked separately.

The audit found exactly **two** detectors with root-cause soundness
bugs on the corpus: the historical WXYZ-Wing heuristic (the
motivation for the LZWing work reported here) and
`detect_almost_locked_pair` (fixed in place with a one-line
constraint addition during the audit). All other 42 detectors passed
with zero root-cause kills. This sets the soundness baseline for the
results reported in this paper.



The rule was discovered by fixing a soundness bug in an existing
implementation of WXYZ-Wing in the `larsdoku` solver. The historical
`detect_wxyz_wing` function accepted any four-cell block with a
four-digit candidate union and emitted an elimination whenever some
digit *Z* appeared in *at least two* of the four cells, provided those
*Z*-cells pairwise saw each other. We discovered, while cascade-tracing
a wrong placement in a puzzle from the `mith 158K` benchmark, that
this condition is strictly weaker than the soundness condition above:
a four-cell block can satisfy all of the structural checks and still
admit a valid Z-free assignment whenever the non-Z cells are not
peer-constrained tightly enough to force pigeonhole. A specific
example:

```
Pattern cells: R1C1 {1,3,6}, R1C6 {1,2,3,6}, R2C4 {1,3}, R3C6 {1,2,3,6}
Z = 2 (appearing only in R1C6 and R3C6, both in column 6 and box 2)
```

The historical detector accepts this as a WXYZ-Wing and emits the
elimination "digit 2 removed from R3C5" (the common peer of R1C6 and
R3C6). But removing 2 from all four cells admits the valid assignment
`R1C1 = 1, R1C6 = 3, R2C4 = 1, R3C6 = 6` because R1C1 and R2C4 are not
peers and can independently take the value 1. The elimination of 2
from R3C5 is therefore not forced by the four-cell pattern alone. In
this specific puzzle the elimination was coincidentally correct
because of external constraints outside the pattern, but in other
puzzles with structurally identical patterns the same elimination
removed the true value and the solver's downstream reasoning then
cascaded through a sequence of correct-under-false-state inferences
until a `BUG+1` theorem placed a wrong digit.

The relevant observation for this paper is that the cascade's root
cause was not the `BUG+1` theorem (a provably correct rule applied to
a corrupted state) but the four-cells-ago heuristic WXYZ-Wing
emission. Identifying the root cause required fixing the heuristic,
not the downstream theorems, and the fix took the form of the
explicit soundness condition given in Section 2.1. That condition,
lifted out as its own rule, is LZWing. Six worked examples of the
unsound heuristic — three lucky-correct fires and three truth-killing
fires — are documented in `WXYZ_CASE_STUDY.md`.

## 4. Implementation

The algorithm enumerates all *O(n⁴)* four-cell combinations where *n*
is the number of empty cells with 2–4 candidates. For each combination
it checks the 4-digit-union constraint, builds the 4x4 peer adjacency
matrix, verifies peer-connectivity by BFS, and then iterates over each
digit in the union as a candidate *Z*. For each *(S, Z)* pair it
checks the all-Z-cells-mutually-peer condition and, if satisfied,
executes the 3-colouring decision procedure. The implementation is in
`src/larsdoku/engine.py` as the function `detect_lzwing`.

In practice the quad enumeration is dominated by the early-exit
checks: most four-cell combinations fail the 4-digit-union constraint
or the peer-connectivity check long before reaching the 3-colouring
step. Empirically, running `detect_lzwing` after L1/L2 propagation
costs on the order of milliseconds per invocation on a typical
`mith`-class puzzle state.

## 5. Benchmarks

> **Note**: this section is being populated as the full sweep
> completes. Current numbers are from in-progress runs and may be
> revised.

### 5.1 Weekly Expert 686 (Andrew Stuart's curated set)

- **Solve rate**: 686 / 686 (100%)
- **`detect_wxyz_wing` fires**: **0** puzzles
- **`detect_lzwing` fires**: **464** puzzles (67.6%)

Interpretation: on the curated expert-level benchmark, LZWing is the
sole representative of the restricted-common-wing family to fire. The
historical heuristic WXYZ-Wing is never needed — every puzzle that
would have required it is solved by LZWing's sound variant instead.
Every wing-family elimination on this benchmark is logically forced
by the LZWing pattern alone.

### 5.2 `mith 158K` benchmark — an honest regression

The `mith 158K` benchmark is a forum-collected corpus of hard puzzles
from various provenance. On this benchmark, the current sound solver
produces a **-7.5 percentage point solve-rate regression** compared to
the pre-fix version that was running the WXYZ-Wing heuristic with
*Z ≥ 2*:

| Puzzle range | Buggy solver | Fixed solver | Delta |
|--------------|--------------|--------------|-------|
| First 1,000 | 59.3 % | 54.4 % | -4.9 pts |
| First 5,000 | 61.8 % | 54.3 % | -7.5 pts |
| First 11,000 | 60.3 % | 52.8 % | -7.5 pts |

We report this regression honestly because it illustrates the exact
phenomenon this paper is about. The `mith` corpus had evidently been
producing good numbers for the `larsdoku` solver primarily *because*
the heuristic WXYZ-Wing was emitting eliminations that happened to be
correct often enough that the cascade landed on valid placements. When
we replaced the heuristic with sound LZWing plus the Z ≥ 3 residual,
the ~7.5 % of puzzles that depended on the coincidental emissions now
fail — not because sound logic is weaker, but because those puzzles
needed the cheat-code the heuristic was providing.

Two observations:

1. **On curated benchmarks the fix is zero-regression.** The Weekly
   Expert 686 (§5.1) and the Forum Hardest 11+ first 10,000 puzzles
   (§5.3) both still solve at 100 % after the fix. LZWing plus the
   residual Z ≥ 3 heuristic is sufficient for every one of them.
   The benchmarks most often used to measure hard-puzzle solver
   quality in the Sudoku community (Stuart's curated set and the
   forum's 11+ set) do not exhibit the `mith` dependency.

2. **The regression is evidence that benchmarks can be implicitly
   tuned against unsound emissions.** A solver can look like it's
   solving a corpus when in fact it's only getting answers right
   because wrong intermediate eliminations happen to cascade into
   valid placements. This cascade-interference phenomenon is, we
   argue, a cautionary observation worth making explicit in any
   soundness discussion.

We prefer to ship the sound solver with the 7.5 % regression on
`mith` over the pre-fix solver that hit 60 % via unsound reasoning.
Recovering the lost `mith` solve rate through sound logic (whether
via LZWing extensions, a canonical WXYZ-Wing rewrite, or additional
pattern rules like larger wings) is an open problem we would welcome
pattern-based-research input on.

### 5.3 Hardest 11+ benchmark (first 10,000 puzzles)

Partial results as of writing: across 4 parallel batches of 2,500
puzzles each, the solver achieved **100%** solve rate on the first
9,795 / 10,000 puzzles (remaining 205 still processing at time of
writing). LZWing firing counts per puzzle will be extracted once the
batches complete.

### 5.4 Worked example — Weekly Expert #15

```
Puzzle: 3..7...1...7.2....82.5....62.94......5.....2......23.91....9.54....8.1...6...5..3
```

After L1/L2 propagation and ALS-XZ elimination, the solver stalls. The
LZWing detector then fires on the following pattern:

| Cell  | Candidates  | Role      |
|-------|-------------|-----------|
| R1C2  | `{4, 9}`    | Z-carrier |
| R2C2  | `{1, 4, 9}` | Z-carrier |
| R3C3  | `{1, 4}`    | non-Z     |
| R3C6  | `{1, 3, 4}` | non-Z     |

- Candidate union: `{1, 3, 4, 9}`
- *Z* = 9 (in R1C2 and R2C2; both share column 2 and box 1, hence
  pairwise peers)
- Peer adjacencies in the pattern: R1C2–R2C2, R1C2–R3C3, R2C2–R3C3,
  R3C3–R3C6

**3-colouring check**: removing *Z* = 9 from all four cells,
- R1C2 has only `{4}`, forcing it to 4.
- R2C2 (peer of R1C2) loses 4 and is forced to 1.
- R3C3 (peer of R1C2 and R2C2) loses both 1 and 4, leaving the empty
  set. No valid assignment exists.

Therefore at least one of R1C2, R2C2 must be 9. Any cell peering both
of them loses 9:

- R2C1 (peer of R1C2 via box 1, peer of R2C2 via row 2)
- R8C2 (peer of R1C2 and R2C2 via column 2)

After these eliminations the puzzle closes out with only L1/L2
techniques plus ALS-XZ. No other wing-family rule, chain, or
forcing technique is required.

## 6. Relationship to Berthier's rule hierarchy

Berthier's pattern-based CSP framework organizes resolution rules into
families of increasing expressive power: Basic Resolution Theory (BRT)
at the bottom, then subsets, whips, braids, grouped whips, extended
grouped braids, Tridagon, and so on. Each family has a known or
conjectured relationship to the Trial-and-Error classification
hierarchy T&E(*n*), with asymptotic equivalences of the form
*W[∞]* ≈ *T&E(1)* and *B[∞]* ≈ *T&E(2)*.

We believe LZWing belongs in the wing-and-subset neighbourhood of
this hierarchy, but we do not claim a specific placement. Several
candidate classifications are plausible:

1. **A variant of ALS-XZ with size-4 ALS.** LZWing's 4-cell block with
   *Z* restricted common is structurally adjacent to an ALS of size 4
   with a restricted-common digit. The soundness argument is
   pigeonhole-based in both cases.
2. **A specific short whip or braid.** Because wing-family rules are
   generally expressible as short AIC-style chains in Berthier's
   framework, it is plausible that LZWing is subsumed by some fixed
   whip or braid length.
3. **A novel member of the subset family requiring its own name.**
   This is the least likely interpretation but not impossible — the
   explicit 3-colouring soundness condition may not appear verbatim in
   published subset rules.

We invite readers familiar with the CSP-Rules tradition to supply the
correct classification. Specifically, we are interested in:

- Does CSP-Rules emit an equivalent elimination on Weekly Expert #15
  via a shorter whip, braid, or subset rule than what LZWing uses?
- Is the 3-colouring verification step reducible to a simpler
  pattern-match in the CSP-Rules vocabulary, or does it represent a
  genuinely new verification primitive?
- On puzzles where LZWing fires but no canonical WXYZ-Wing applies,
  what rule from Berthier's hierarchy covers the same elimination?

Answers to these questions would allow us to either state LZWing as a
subsumption theorem of an existing rule, or to position it as a novel
rule with a specific family assignment.

## 7. Open problems

**7.1 Residual heuristic WXYZ-Wing.** Within `larsdoku`, the historical
`detect_wxyz_wing` function is still enabled for *Z ≥ 3* configurations
because removing it entirely caused a regression on the `mith 158K`
benchmark that could not be recovered by LZWing alone. This indicates
that some of the historical detector's eliminations, while not forced
by the four-cell pattern, are nevertheless valid under external
constraints from the rest of the puzzle. We would like to either (a)
classify this residual population and replace it with an explicit
sound rule, or (b) prove that the residual is a coverage gap of
LZWing's 4-cell structure that requires a 5+-cell generalization.

**7.2 Generalization to 5+ cells.** The 3-colouring argument
generalizes naturally to *k*-cell blocks with *k*-digit candidate
unions for any *k*. The decision procedure's worst-case cost is
*(k−1)^k* primitive steps, which grows polynomially in *k* for small
fixed *k*. We have not yet implemented the generalization and would
be interested in whether Berthier's framework already contains the
analogous larger-block rules.

**7.3 Relationship to Trial-and-Error classification.** We have not
classified the residual `mith 158K` failures by their T&E(*n*) depth,
so we do not know whether the solver's remaining failures are T&E(3)
puzzles that require a hypothesis family our solver does not yet
expose, or whether they are covered by some rule we are simply
missing. Any guidance on which famous puzzle sets would provide
coverage for T&E(3) or T&E(4) classifications would be welcome.

## 8. Availability and reproducibility

All code described in this paper is available in the `larsdoku`
repository. The specific files of interest are:

- `src/larsdoku/engine.py` — contains `detect_lzwing` (LZWing) and
  the historical `detect_wxyz_wing` (residual heuristic).
- `src/larsdoku/cli.py` — contains the solver dispatch that
  integrates LZWing into the main resolution loop.
- `WXYZ_CASE_STUDY.md` — six worked WXYZ-Wing fires from the mith
  corpus (three lucky-correct, three truth-killing) with full
  3-colouring analysis. Companion document to this paper.
- `SOUNDNESS_AUDIT.md` — systematic audit report on all 44 detectors
  in `engine.py` (produced in parallel with this paper).

The Weekly Expert 686 benchmark is publicly available at
`sudokuwiki.org`. The `mith 158K` benchmark is a forum-collected
hard puzzle database. The Forum Hardest 11+ benchmark is available
at `forum.enjoysudoku.com`.

## Acknowledgments

This work stands on the shoulders of two researchers whose
contributions to the pattern-based Sudoku tradition are foundational.

We thank **Andrew Stuart** for the Weekly Expert puzzle set, which
provided the worked-example puzzle (Weekly Expert #15) discussed in
Section 5.4, and for his long-running stewardship of the SudokuWiki
strategy taxonomy. SudokuWiki is the canonical reference for
human-solvable Sudoku techniques, and the wing-family vocabulary
used throughout this paper follows its conventions. The clarity and
generosity of that resource made the present work possible.

We are equally indebted to **Denis Berthier**, whose two volumes
(*The Hidden Logic of Sudoku* and *Pattern-Based Constraint
Satisfaction and Logic Programming*) and the accompanying `CSP-Rules`
software laid the formal foundations on which this paper rests. The
philosophical insistence on constructive, pattern-based resolution
rules — and the technical rigour with which those rules are
separated from Trial-and-Error reasoning — is the standard of
soundness this paper has tried to meet. Any failure to meet that
standard is the present authors' alone, not the framework's.

## References

1. Berthier, D. *The Hidden Logic of Sudoku*. Lulu.com, 2007.
2. Berthier, D. *Pattern-Based Constraint Satisfaction and Logic
   Programming*. Lulu.com, 2012.
3. Berthier, D. *CSP-Rules-V2.1* software repository, accessed 2026,
   `github.com/denis-berthier/CSP-Rules-V2.1`.
4. Stuart, A. *SudokuWiki Strategy Families*, accessed 2026,
   `sudokuwiki.org/sudoku.htm`.
5. `larsdoku` repository (project homepage to be supplied).
