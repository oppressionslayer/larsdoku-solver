# Hunting New Sudoku Techniques with larsdoku + AI

A research guide for joining the party.

larsdoku 3.4.7 is a pure-logic sudoku solver with 44 pattern detectors. It is
also a research instrument: when you give it a hard puzzle and it stalls, the
stall is a **fingerprint of a technique nobody has named yet**. This guide
shows you how to install it, run it in research mode, and use any AI assistant
(Claude, ChatGPT, etc.) to help cluster the stall fingerprints into a real,
publishable new technique.

The methodology described here is the same one used to discover six WSRF
techniques already in the solver: **FPC, FPCE, D2B, FPF, DeepResonance, and
LZWing**.

---

## Why this is interesting

Every named sudoku technique — from naked single up through Junior Exocet —
was once an unnamed pattern someone noticed. The pattern came first, the
name and the proof came later.

larsdoku gives you a way to find those patterns at scale:

1. Run thousands of hard puzzles through the standard 44-detector chain.
2. When the chain stalls, use **WSRF zone math** (a rank-1 cell oracle from
   the Self-Informing Rank Oracle / SIRO system) to nudge the puzzle past
   exactly one cell.
3. Record where the nudge happened — the cell, the zone slot, and the board
   state at that moment.
4. Cluster the recordings across the corpus. Cells that share a structural
   shape are candidates for the same undiscovered technique.

Step 2 sounds magical but it is not — it is a deterministic prediction
based on row/column/box rank statistics, validated against the backtracker
solution at every step (so you know the nudge is correct without trusting
it blindly). The point of the nudge is **not to solve the puzzle**, it is
to mark the location of the gap in a way that lets you compare gaps across
many puzzles.

---

## Install

```bash
pip install larsdoku
```

Or, for the bleeding-edge build:

```bash
git clone <repo>
cd larsdoku
pip install -e .
```

Verify:

```bash
larsdoku --version
# larsdoku 3.4.8
```

---

## Solve a puzzle the normal way

```bash
larsdoku '1.3..67.9.57..9.3669...351..6584..............71.......1.9...75......3......6.9.1' --level 7
```

You will see the technique cascade. `--level 7` enables every detector
(L1-L7); the default `--level 99` is the same as 7 plus oracle-only
techniques.

---

## Solve a puzzle in research mode

This is the new flag in 3.4.7:

```bash
larsdoku '12..56.89.5...92.6......15.2.1...96..65....2889....5.1....7..........81..1283....' --with-zoneded --level 7 --verbose
```

Output:

```
[zd-loop] round 1: remaining=50
[zd-loop]   wrong placement R2C3=8 (truth=7) — abort technique cascade
[zd-loop]   placed 1, result.steps=46, result.success=False, remaining_after=49
  ★ ZONE DEDUCTION #1 (round 1): R1C7=7  zone=TL  [CROSS-DIGIT]
[zd-loop] round 2: remaining=48
[zd-loop]   placed 48, result.steps=48, result.success=True, remaining_after=0

Status: SOLVED
Technique steps: 49
Zone deductions: 1
|Zones: TL|
...
Zone Deduction Points (technique gaps — research signal):
  #1: R1C7=7  zone=TL  [cross-digit]  (stall round 1) — missing technique here
```

The important line is the last one. It tells you:

- **Cell:** R1C7 — row 1, column 7
- **Zone:** TL — this cell's slot inside its 3x3 box (top-left)
- **Subtype:** cross-digit — which family of zone oracle fired
- **Stall round:** 1 — how many technique rounds had completed before
  the stall

The `|Zones: TL|` line is a grep-friendly array of every zone slot used in
this puzzle, in order. If a puzzle needed two deductions you would see
something like `|Zones: TL,MC|`.

---

## What "zone" means here

Each 3x3 box has 9 cells. The WSRF system labels each cell by its position
**inside its own box**, giving 9 zone names:

```
TL TC TR     ← Top-Left, Top-Center, Top-Right of the box
ML MC MR     ← Middle-Left, Middle-Center, Middle-Right
BL BC BR     ← Bottom-Left, Bottom-Center, Bottom-Right
```

There are nine cells with each label across the whole grid (one per box).
Treating them as a single group is the WSRF idea: the centers (MC) form one
group, the top-rights (TR) form another, and so on. Many discovered
techniques act on relationships within or between these groups.

When the research output says `zone=TR`, it means the cell where the
deduction landed is the top-right cell of its 3x3 box. Across a corpus you
will find that some zones appear far more often than others — that
asymmetry is a real research signal, not noise.

---

## Run a whole corpus

For batch research, use the supplied script (adjust the input/output
paths at the top of the file to match your local puzzle corpus):

```bash
python mith_158k_solve.py
```

It writes one line per puzzle to `mith_larsdoku_new_solve.txt`:

```
puzzle_number|puzzle|status|kind|empty_remaining|zones|technique_counts
```

Where `kind` is one of:

- `-`       — solved by techniques alone (no zone help needed)
- `Zoned`   — solved but needed at least one zone deduction
- `Stalled` — stuck even with zone deductions
- `Failed`  — exception during solve

And `zones` is a comma-separated list like `TL,MC` of every zone slot used,
or `-` if none.

Grep recipes:

```bash
# All puzzles that needed zone help (the research material)
grep "|true|Zoned|" mith_larsdoku_new_solve.txt

# Puzzles that stalled even with zone help (rarer, harder)
grep "|Stalled|" mith_larsdoku_new_solve.txt

# Puzzles that needed a TR-zone deduction
grep "|Zoned|.*|TR" mith_larsdoku_new_solve.txt | head

# Puzzles needing exactly two deductions
grep "|Zoned|.*|.*,.*|" mith_larsdoku_new_solve.txt
```

---

## Reading the corpus stats

After running a batch, you can count how often each zone appears:

```bash
awk -F'|' '$6 != "-" {
    n = split($6, zs, ",")
    for (i=1; i<=n; i++) cnt[zs[i]]++
}
END {
    for (z in cnt) printf "  %-3s  %5d\n", z, cnt[z]
}' mith_larsdoku_new_solve.txt | sort -k2 -rn
```

A non-uniform distribution is a finding. From a recent 559-puzzle slice of
the mith corpus:

```
  TR    67  28.3%
  TC    64  27.0%
  ML    37  15.6%
  MC    22   9.3%
  BR    13   5.5%
  MR    12   5.1%
  BL    10   4.2%
  TL     8   3.4%
  BC     4   1.7%
```

The top row (TL+TC+TR) holds 58.7% of the deductions. That is not random.
It is structural information about either the puzzle generator or the
detectors — and it tells you where to look for the next technique.

---

## The five steps to a new technique

1. **Run a corpus** (a few thousand puzzles is plenty to start) with
   `mith_158k_solve.py` or similar.
2. **Filter to one zone class** — say, all puzzles where a TR deduction
   was needed. Often the gap shape is different per zone.
3. **Reconstruct the board state** at the stall for each puzzle. (See the
   "Replaying a stall" recipe below.)
4. **Look for a shared structural pattern** in those board states. Common
   things to check: constraint groups around the stall cell, candidate
   parities, peer-clique shapes, restricted commons.
5. **Formalise the pattern** as a rule, validate it on a held-out batch,
   write it up, ship it.

This is the loop that produced FPC, FPCE, D2B, FPF, DeepResonance, and
LZWing. Each one started as a cluster of stall fingerprints and ended as
a sound, named technique with a 3-coloring proof.

---

## Replaying a stall

If you have a puzzle from the corpus you want to inspect, just rerun it
in verbose mode:

```bash
larsdoku '<the puzzle>' --with-zoneded --level 7 --verbose
```

The `--verbose` output shows you exactly which cells the technique chain
placed before stalling, and at which round. Combine with `--steps` for
even more detail.

To dump the candidate board at a specific stall point, the easiest path
right now is:

```python
from larsdoku.engine import BitBoard, solve_backtrack
from larsdoku.cli import solve_selective

p = '<your puzzle>'
sol = solve_backtrack(p)
sol_list = [int(c) for c in sol]
bb = BitBoard.from_string(p)

# Run techniques up to (but not past) the stall
result = solve_selective(p, max_level=7)
for step in result['steps']:
    pos, digit = step['pos'], step['digit']
    if sol_list[pos] != digit:
        break  # this is where corruption / stall begins
    bb.place(pos, digit)

# bb is now the stall-point board. Inspect bb.cands[i] for candidates
# at each cell, bb.board[i] for placed digits.
for r in range(9):
    print(' '.join(str(bb.board[r*9+c]) if bb.board[r*9+c] else '.' for c in range(9)))
```

---

## Using AI as your research partner

The pattern-finding step is where an AI assistant earns its keep. Here are
prompts that work.

### Prompt 1 — clustering

Paste a handful of stall-point boards into the chat with this prompt:

> I have N sudoku puzzles where larsdoku's full L1-L7 technique chain
> stalls, and a SIRO zone deduction at zone slot TR breaks the stall every
> time. Below are the candidate boards at the stall point for ten of these
> puzzles. The cell that needed the zone deduction is marked with a star.
> What structural pattern do these boards share around the starred cell?
> List specific things to check, ranked by how strongly they appear in the
> sample.

The AI will not always nail it on the first try. Iterate: after it lists
candidates, give it a smaller second sample and ask which of its candidate
patterns hold up.

### Prompt 2 — proving soundness

Once you have a candidate rule, ask:

> Here is a proposed sudoku elimination rule: <rule>. Construct a
> 3-coloring argument for it: assign colors to the cells named in the
> rule, list the unit constraints between them, and check whether any
> consistent coloring leaves the eliminated digit alive at the target.
> If yes, the rule is unsound — show me the witness assignment. If no,
> walk me through the forced contradiction.

This is the same check `WXYZ_CASE_STUDY.md` walks through manually for the
WXYZ-Wing heuristic. **Do this step before claiming a new technique is
sound.** The history of larsdoku's WXYZ-Wing — which is unsound on a
documented 12% of fires — is a reminder that benchmark performance does
not equal soundness.

### Prompt 3 — implementation sketch

> Here is a sound rule for sudoku eliminations: <rule>. Sketch a Python
> detector that finds all instances of this pattern on a 9x9 candidate
> bitboard. The interface should match larsdoku's existing detectors:
> `def detect_<name>(bb): return list of (pos, digit) eliminations`.
> Optimize for clarity first, speed second.

You will iterate on the sketch a few times. That is fine. The goal of the
AI prompt is to get a working draft fast, not to skip code review.

### What to share with the AI, and what not to

Share liberally:
- Puzzle strings (these are public data)
- Candidate boards and stall points
- Technique fire logs
- Your hypothesis and counter-examples

Do not share:
- Production code outside the public larsdoku source tree
- Private benchmarks or unpublished puzzle generators

### Verifying AI output

Every AI suggestion gets verified two ways before it touches the codebase:

1. **Manual 3-coloring check** on at least three positive examples and
   three negative examples (where the rule fires but the elimination is
   wrong). The wxyz case study has the template.
2. **Automated test** against a held-out corpus with the
   `trust_solution=` path of `solve_selective` (which blocks unsound
   eliminations and reports them so you know exactly which fires were
   wrong).

If both checks pass, the rule is real and you can write it up.

---

## Sharing your findings

When you find a candidate technique, the format that works best is a
short markdown file with these sections:

1. **Name** and one-sentence description
2. **Pattern definition** — formal statement of what counts as an instance
3. **Soundness proof** — the 3-coloring argument
4. **Examples** — 3 sound positive cases (rule fires, elimination correct),
   3 controlled negative cases (rule does not fire here, and why)
5. **Coverage** — how often it fires on a named corpus and how many
   puzzles it newly solves vs. the existing chain
6. **Comparison to existing techniques** — does it subsume any? Is it
   subsumed by any?

`LZWING_PAPER.md` and `WXYZ_CASE_STUDY.md` in this repository are
worked examples of this format.

Submit findings as a pull request, an issue with the markdown attached,
or just an email — whichever is easiest.

---

## Good first PRs (known gaps)

If you're looking for a smaller, well-specified contribution to warm
up on before hunting new techniques, the larsdoku L2 detector layer
is missing three standard textbook subset rules. They're documented
in every solver reference, sound by construction (no 3-colouring
needed — they follow directly from pigeonhole), and their absence
is a small but real coverage gap.

| Missing | Dual of | Where it would live |
|---|---|---|
| **Hidden Triple** | Naked Triple | `src/larsdoku/engine.py` `apply_l2_bitwise`, next to `Hidden Pairs` (around line 1057) |
| **Hidden Quad** | Naked Quad | same function, just below Hidden Triple |
| **Naked Quad** | Naked Triple (size-4 generalization) | same function, next to `Naked Triples` (around line 938) |

The docstring at `engine.py:19` claims Naked Quad is implemented;
it isn't. The header comment is the only evidence it ever existed.

**Reference rules** (Andrew Stuart's SudokuWiki):

- *Naked Quad*: four cells in a unit whose candidate union has
  exactly four digits. Eliminate those four digits from every other
  cell in the unit.
- *Hidden Triple*: three digits whose appearances in a unit are
  confined to exactly the same three cells. Eliminate every *other*
  digit from those three cells.
- *Hidden Quad*: same idea, four digits in four cells.

**How to verify your implementation:**

1. Add the detector to `apply_l2_bitwise` next to its sibling.
2. Run `larsdoku '<a known hidden-triple puzzle>' --level 7 --steps`
   and confirm the elimination fires.
3. Re-run the curated benchmarks (Weekly Expert 686, Forum Hardest
   11+ first 2500) and confirm no regressions: 686/686 and
   2498+/2500 should both hold.
4. Run the soundness audit script if you want belt-and-braces — a
   sound L2 addition will produce zero root-cause truth kills.

This is roughly a 30–60 minute task per detector and a fine
on-ramp for the rest of the codebase.

---

## Honesty notes

- **Zone deductions are not magic.** They are skip-oracle validated rank-1
  predictions. They are only as trustworthy as the backtracker that
  validates them.
- **A high zone-deduction count is not a quality signal.** It just means
  the standard chain has gaps in that puzzle. Some puzzles need many
  deductions; some need none.
- **The TR/TC dominance in the mith corpus is not yet explained.** It
  could be a generator artefact, a detector blind spot, a rank-1 cache
  bias, or a real new technique. Investigating it is exactly the kind of
  open question this guide is designed to invite help with.
- **WXYZ-Wing is in the chain but is documented as unsound** (heuristic
  Z>=3 gate, 174/1500 wrong fires on the audit corpus). Read
  `WXYZ_CASE_STUDY.md` for the full picture before publishing anything
  that depends on it. Sound replacement is `LZWing` (`detect_lzwing`).

---

## Where to start

If you want to dive in right now:

1. Install larsdoku 3.4.7
2. Run `larsdoku '<any hard puzzle>' --with-zoneded --level 7 --verbose`
3. When you see a `Zone Deduction Points` line, that is a missing
   technique. Pick a zone slot you find interesting, gather 20-50
   stall-point boards in that slot, paste them at your favourite AI
   chatbot with Prompt 1 above.
4. When the AI suggests a pattern, verify it manually with Prompt 2.
5. Write it up and send it over.

The corpus, the solver, the validation infrastructure, and the AI tools
are all open. Welcome to the party.
