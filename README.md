# Hunting New Sudoku Techniques with larsdoku + AI and/or with Your own Brain!

```
# 99.846% on the 48k hardest (we just achieved 100% we are redesigining solves to not contradict each other now as seen
in  mith  puzzles -- update to come soon ! )

# MAJOR UPDATE LARSDOKU CAN NOW FORGE PUZZZLES AND UNSOLVABLES VIA TECHNIQUE SIGNATURES AND WE ARE IN THE PROGRESS
# OF MAKING LARSDOKU VIA TECHNIQUE ZONE SIGNATURES TO BETTER SUIT ITS USE AS A REESEARCH APPLICATIOM FOR FINDING NEW TECHINQUES
# VIA TECHNIQUES SIGNATURES. UPDATE ARRIVING SHORTY, VIA THIS YOU CAN FIND THE COMPLETELY NEW TECHNIQUES FOR
# YOUR PUZZLES. FORGE PUZZLES VIA A TECHINQUE SIGNATURE. THIS HELPS WITH PATTERN RECOGNITION FOR TECHNIOQUE
# RESEARCH AND FINDING!! WITH OVER 10 THOUSAND UNIQUE TECHINQUE SIGNATURES  (UPODATING TO  ONE MILLION SOON ) THAT ARE **UNSOLVABLE** 
# TO HELP YOU FIND THE MISSING OR NEW TECHINQUES YOU NEED FOR YOUR SOLVER!!!

# VIA 10 THOUSAND PUZZLE SIGNATURES FORGE QUADRULLIONS OF UINIQUE PUZZLES AND RESEARCH NEW TECHNIQUES 

## MAJOR UPDATE COMING SHORTLY: YOU USE CAN USE LARSDOKU TO FORGE NEW UNSOLVABLES VIA A TECHNIQUE SIGNATURE AND
##  FIND NEW TECHINQUES FOR YOUR SOLVER. FORGINGG A NEW UNSOLVABLE MASK FROM THESE 10K SIGNATURES RESULTS
##  IN A NEW MASK NOT IN OUR DATABASE OF ONE MILLION UNSOLVABLE MASKS. THE TOOLS WE USE
##  TO FORGE NEW MASKS IS UPCOMING SHORTLY

https://larsdoku.netlify.app/

https://larsdoku.netlify.app/larsdoku_deploy_hypersiro/

Get the hardest puzzles ever found on enjoysudoku forums here! https://raw.githubusercontent.com/oppressionslayer/wsrf-sudoku-solved-series/refs/heads/main/puzzles5_forum_hardest_1905_11plus.txt

# Example solve file: https://github.com/oppressionslayer/wsrf-sudoku-solved-series/blob/main/bench_h11_last_2500_3_4_7.txt

# The worlds hardest unsolvables!!!!!!!!!!!!!!!!!!!!!!!!

  Total:    48,765 puzzles                                                                                                                                                                                 
  Solved:   48,690  (99.846%)                                                                                                                                                                              
  Stalled:      75  (0.154%)                                                                                                                                                                               
  Failed:        0  (0.000%)

# Use Larsdoku to find the last remaining technique or techniques!

# Go to https://github.com/oppressionslayer/wsrf-sudoku-solved-series/ for information on solved techniques and data files!

https://github.com/oppressionslayer/wsrf-sudoku-solved-series/

Results in theee files at wsrf-sudoku-solved-series/ :!  
bench_h11_full_48765_3_4_8.zip
bench_h11_full_48765_3_4_8.txt
bench_h11_full_48765_stalls_3_4_8.txt # 75 stalls in the 48k.

# An Electric cool song! : https://suno.com/s/usI0HWjGrshlMRmd

```

A research guide for joining the party. *mith* puzzles next !

larsdoku 3.6.2 is a pure-logic sudoku solver with 44 pattern detectors. It is
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
pip install larsdoku==3.6.2

# Don't forget this step after every upgrade, because it increses speed by 1000%!!!

larsdoku --warmup

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
# larsdoku 3.6.2
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

This is the new flag in 3.6.2:

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
    TR   450  24.4%
    TC   389  21.1%
    TL   356  19.3%
    MR   198  10.7%
    MC   152   8.3%
    ML   112   6.1%
    BC    91   4.9%
    BR    48   2.6%
    BL    47   2.6%    
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

---# Don't forget this step after every upgrade, because it increses speed by 1000%!!!

larsdoku --warmup

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
# Don't forget this step after every upgrade, because it increses speed by 1000%!!!

larsdoku --warmup
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

1. Install larsdoku 3.6.2
2. Run `larsdoku '<any hard puzzle>' --with-zoneded --level 7 --verbose`
3. When you see a `Zone Deduction Points` line, that is a missing
   technique. Pick a zone slot you find interesting, gather 20-50
   stall-point boards in that slot, paste them at your favourite AI
   chatbot with Prompt 1 above.
4. When the AI suggests a pattern, verify it manually with Prompt 2.
5. Write it up and send it over.

The corpus, the solver, the validation infrastructure, and the AI tools
are all open. Welcome to the party.

Larsdoku

**Pure logic Sudoku solver. Zero guessing. Every step proven.**

```
# Run --warmup to save JIT conmpilations for 109-1000x speedups!! Seriously, run once, it compiles and saves, and it's fast for every run thereafter without the nee for --warmup

pip install larsdoku==3.6.2

# Run this for JIT speedups 10x-100x faster!
larsdoku --warmup

# The website below is a Research tool. it can solve but it is not a traditional solver, it's built for a research. please remember this and have fun using it for your research and solving! Solve your favorite mith puzzle here!: 

https://larsdoku.netlify.app/larsdoku_deploy_hypersiro
```


```
If you want to research statistics and predictions and trial and error and A REGULAR SOLVER ENINE that is awesome!
You need to download larsdoku right now!!

Best solver ( i might be biased i wrote it ) New techniques !! 100% solves on many puzzles

larsdoku <puzzle> #puzzles Normal Solkver!
larsdoku <puzzle> --siro-trust-solve #  # ( SIRO Guided Solver, zones + logic )  
larsdoku <puzzle> --siro-bootstrap-solve # ( Noraml Solver, but with Candidate Statistics so a boosted with statisics solver)

or even better use!

https://larsdoku.netlify.app/larsdoku_deploy_hypersiro !! It's a very awesome research tool for Soduku. know the breakdown of the

missing techniques to help you further research into sudoku!

```

 ## The Anthem                                                                                                                                                     
                                                            
  [Just Another Tuesday (Dark Rock Epic Anthem)](https://suno.com/s/usI0HWjGrshlMRmd)                                                                
   
  *"Solved the whole damn game like it's just another Tuesday"*    
  
800900005007080010020006400005000030070004600900800002002070000100200000030001000
**Documentation: [larsdoku-docs.netlify.app](https://larsdoku-docs.netlify.app/)**

**Web App (WIP): [larsdoku.netlify.app](https://larsdoku.netlify.app/)** — click Expert mode tab to open the Top-N Solver

**New techniques `--preset larstech` from:** [wsrf-sudoku-solved-series](https://github.com/oppressionslayer/wsrf-sudoku-solved-series)

**Sittin' on the Throne of Euler:** [Listen Now! They said NP Complete, i said check out my zones brother Euler! ](https://suno.com/s/ABPiCLAgaZLNmGko)  


Larsdoku solves the hardest Sudoku puzzles ever created using only logical deduction — no backtracking, no trial-and-error. Built on a bitwise engine with GF(2) linear algebra, it achieves **100% pure logic on the Top1465 benchmark** (1,465 of the hardest known puzzles), averaging **19ms per puzzle*.

> **Note:** There is a rare bug where JuniorExocet can cause a stall on a very very very small number of puzzles  If you encounter a STALL, try running with `--exclude JuniorExocet` as a workaround. A fix is in progress.

## LarsForge: --auto-reduce Over a UniDecillion reduction to unsolvable database seeds from the Lars Database Seed Variant Database

## LarsForge: 60 Quadrillion Indestructible Puzzles

LarsForge generates **60 quadrillion unique 17-clue puzzles** from the complete Royle enumeration (49,158 seeds). Every puzzle is backed by a mathematically proven 17-clue skeleton — the minimum information needed to determine a unique Sudoku solution.

**Why this matters:** Traditional puzzle generators use backtrackers to verify uniqueness for one configuration. LarsForge puzzles are **dimensionally unique** — unique across ALL states. Add solution digits to create 24-clue puzzles, remove any of the added clues in any order, and uniqueness holds. The 17-clue core is bedrock. Everything above it is armor.

We are building toward forging all puzzles from an **18-clue minimum base** — one clue above the mathematical floor. At 17 clues, 90% of puzzles solve with basic techniques alone. At 18 clues, the extra clue opens the door to harder, more interesting puzzles while still guaranteeing dimensional uniqueness. When a 24-clue puzzle is built on the forge, removing any clue above the 18-clue base never leads to multiple solutions. Boards that break when reduced to their minimum base are, in our view, backtracker-unreliable — verified at one snapshot, but fragile under interaction. We prefer puzzles with structural integrity all the way down.

# Solving "Unsolvable" Puzzles — mith T&E(3) Collection 

## Puzzle 1: mith seed (34 clues)
```
...4.6.89....891.2.8.21.64.2.4...8.18.1.4296........243.762....5...9......8......

$ larsdoku ...4.6.89....891.2.8.21.64.2.4...8.18.1.4296........243.762....5...9......8......
Status: STALLED (needs LS technique — in development)
StatusL In Development, can you beat me to the solution ;-)

larsdoku ...4.6.89....891.2.8.21.64.2.4...8.18.1.4296........243.762....5...9......8......  --siro-bootstrap-solve

Status: SOLVED
Steps:  43
Time:   2311.0ms
Verify: All techniques are Sudoku Expert Approved ✓

  Board validated: every row, column, and box contains
  digits 1-9 exactly once per international Sudoku rules.
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

Techniques:
  crossHatch              22 ( 51.2%)  L1  █████████████████
  lastRemaining           12 ( 27.9%)  L1  █████████
  nakedSingle              5 ( 11.6%)  L1  ███
  fullHouse                4 (  9.3%)  L1  ███
  SIRO Bootstrap Solve: 6/6 verified zone predictions correct.
  6 SIRO placements added as clues → standard solver finished.
  Boosted puzzle: 020406089050089102080210640204000801801042960000000024307620000500090000048000293
  No trust_solution. No oracle. Pure zones + pure logic.

larsdoku .2....7....71.9...86...7..........93.3.9.417.......4.2....92.41..234.9.7...7.132. --siro-trust-solve

Status: SOLVED
Steps:  50
Time:   6844.2ms
WSRF:   FPC, FPF

Techniques:
  crossHatch              22 ( 34.4%)  L1  ███████████
  lastRemaining           13 ( 20.3%)  L1  ██████
  nakedSingle             10 ( 15.6%)  L1  █████
  ALS_XZ                   9 ( 14.1%)  L5  ████
  KrakenFish               2 (  3.1%)  L6  █
  FPC                      2 (  3.1%)  L5  █ ★
  fullHouse                2 (  3.1%)  L1  █
  AlignedPairExcl          1 (  1.6%)  L5  █
  FPF                      1 (  1.6%)  L7  █ ★
  SimpleColoring         larsdoku --lforge alsxy,alsxz,d2b,dr,fpce --lforge-exact --lforge-no-confirm

  LForge — Signature Forge (exact)
  =======================================================
  Query: ALS+ALSXY+D2B+DR+FPCE (exact)
  Matched: 2 signatures, 395 seeds (seed=1775753237)
  Generated: 10 puzzles in 1ms (no-confirm)

  630000200007000098008000000010200000500310600000094000000000007000009040200500100  [ALS+ALSXY+D2B+DR+FPCE]
  420005680003000002007006010000008401100060805008000060000000900050070000800004050  [ALSXY+ALS+D2B+DR+FPCE]
  300007025000050000000100000200000506760090810003006047600000050030002074407000000  [ALSXY+ALS+D2B+DR+FPCE]
  400000200083020040010000003300080064000600700800040021008005000029000000100030002  [ALSXY+ALS+D2B+DR+FPCE]
  001807005000040180600005730003501070020000500000000000000290000007003800010004000  [ALSXY+ALS+D2B+DR+FPCE]
  000000070002005000030900008409800000010000000803010004000006040098420001040108003  [ALSXY+ALS+D2B+DR+FPCE]
  003470000090060071600009200700005640000080000900007500079006005026050700500000000  [ALSXY+ALS+D2B+DR+FPCE]
  009030000500200000000089600018090300003001000700000000200000004000400007006008100  [ALSXY+ALS+D2B+DR+FPCE]
  000001030900700640000040002090800000005002004700030010080000000009600700670000020  [ALSXY+ALS+D2B+DR+FPCE]
  600040300000028000040700000000070030020004600300500009100900060008001905000007100  [ALSXY+ALS+D2B+DR+FPCE]

  # 10 puzzles (exact, --lforge-no-confirm)
  1 (  1.6%)  L4  █
  ALS_XYWing               1 (  1.6%)  L5  █
  Path Selection: SIRO-guided technique path used (--siro-trust-solve).
  SIRO cascade provides placements → standard solver proves the path.



```


## Puzzle 2: mith seed (29 clues)
```
.2....7....71.9...86...7..........93.3.9.417.......4.2....92.41..234.9.7...7.132.

$ larsdoku .2....7....71.9...86...7..........93.3.9.417.......4.2....92.41..234.9.7...7.132.
Status: STALLED (needs LS technique — in development)
```larsdoku .2....7....71.9...86...7..........93.3.9.417.......4.2....92.41..234.9.7...7.132. --siro-bootstrap-solve

Status: SOLVED
Steps:  45
Time:   7070.8ms
Verify: All techniques are Sudoku Expert Approved ✓
larsdoku --lforge alsxy,alsxz,d2b,dr,fpce --lforge-exact --lforge-no-confirm

  LForge — Signature Forge (exact)
  =======================================================
  Query: ALS+ALSXY+D2B+DR+FPCE (exact)
  Matched: 2 signatures, 395 seeds (seed=1775753237)
  Generated: 10 puzzles in 1ms (no-confirm)

  630000200007000098008000000010200000500310600000094000000000007000009040200500100  [ALS+ALSXY+D2B+DR+FPCE]
  420005680003000002007006010000008401100060805008000060000000900050070000800004050  [ALSXY+ALS+D2B+DR+FPCE]
  300007025000050000000100000200000506760090810003006047600000050030002074407000000  [ALSXY+ALS+D2B+DR+FPCE]
  400000200083020040010000003300080064000600700800040021008005000029000000100030002  [ALSXY+ALS+D2B+DR+FPCE]
  001807005000040180600005730003501070020000500000000000000290000007003800010004000  [ALSXY+ALS+D2B+DR+FPCE]
  000000070002005000030900008409800000010000000803010004000006040098420001040108003  [ALSXY+ALS+D2B+DR+FPCE]
  003470000090060071600009200700005640000080000900007500079006005026050700500000000  [ALSXY+ALS+D2B+DR+FPCE]
  009030000500200000000089600018090300003001000700000000200000004000400007006008100  [ALSXY+ALS+D2B+DR+FPCE]
  000001030900700640000040002090800000005002004700030010080000000009600700670000020  [ALSXY+ALS+D2B+DR+FPCE]
  600040300000028000040700000000070030020004600300500009100900060008001905000007100  [ALSXY+ALS+D2B+DR+FPCE]

  # 10 puzzles (exact, --lforge-no-confirm)

  Board validated: every row, column, and box contains
  digits 1-9 exactly once per international Sudoku rules.
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

Techniques:
  crossHatch              24 ( 53.3%)  L1  █████████████████
  lastRemaining           10 ( 22.2%)  L1  ███████
  nakedSingle              7 ( 15.6%)  L1  █████
  fullHouse                4 (  8.9%)  L1  ██
  SIRO Bootstrap Solve: 6/6 verified zone predictions correct.
  6 SIRO placements added as clues → standard solver finished.
  Boosted puzzle: 020000700007109000860007000241000093030904170798000402000092041002340907000701320
  No trust_solution. No oracle. Pure zones + pure logic.

larsdoku ...4.6.89....891.2.8.21.64.2.4...8.18.1.4296........243.762....5...9......8...... --siro-trust-solve

Status: SOLVED
Steps:  48
Time:   2269.6ms
WSRF:   D2B, FPC, FPCE

Techniques:
  crossHatch              26 ( 49.1%)  L1  ████████████████
  nakedSingle             16 ( 30.2%)  L1  ██████████
  ALS_XZ                   3 (  5.7%)  L5  █
  D2B                      2 (  3.8%)  L6  █ ★
  lastRemaining            2 (  3.8%)  L1  █
  AlignedPairExcl          1 (  1.9%)  L5  █
  ALS_XYWing               1 (  1.9%)  L5  █
  FPC                      1 (  1.9%)  L5  █ ★
  FPCE                     1 (  1.9%)  L5  █ ★
  Path Selection: SIRO-guided technique path used (--siro-trust-solve).
  SIRO cascade provides placements → standard solver proves the path.


```

## Puzzle 3: SOLVED 
```
.234.6......18..3...93.7.........1.33.5.1.89...1.3..52......3.8.3.5..92.9..8.3.15
```

```
$ larsdoku .234.6......18..3...93.7.........1.33.5.1.89...1.3..52......3.8.3.5..92.9..8.3.15
Status: SOLVED
Steps:  49
Time:   2299.1ms
WSRF:   FPC, FPCE, FPF

Techniques:
  nakedSingle             20 ( 32.8%)  L1
  crossHatch              18 ( 29.5%)  L1
  ALS_XZ                   7 ( 11.5%)  L5
  lastRemaining            6 (  9.8%)  L1
  FPC                      2 (  3.3%)  L5 ★
  FPF                      2 (  3.3%)  L7 ★
  WXYZWing                 2 (  3.3%)  L5
  SimpleColoring           2 (  3.3%)  L4
  ALS_XYWing               1 (  1.6%)  L5
  FPCE                     1 (  1.6%)  L5 ★
```

# 525 Quinitilliion unsolvables from a database seed. quickly create unsolvables. 

```

## One seed is ● 1,218,998,108,160 — ~1.2 trillion unique puzzles per seed.
## so from this combo ALS_XYWing,alsxz,als,dr,d2b,fpc,fpce,kf
## we have 652 seeds, 800 Trillion, almost a Quadrillion unsolvables with just this combination of unsolvables!!

## Use larsdoku --auto-reduce to reduce a puzzle to look for a solvalble base seed. this database only has base uniques.
## puzzles larger than 26 might need to be reduce to see if it has a seed in the database.

larsdoku --lforge ALS_XYWing,alsxz,als,dr,d2b,fpc,fpce,kf --lforge-exact --lforge-count 15 --lforge-no-confirm --lforge-seed 42

  LForge — Signature Forge (exact)
  =======================================================
  Query: ALS+ALSXY+D2B+DR+FPC+FPCE+KF (exact)larsdoku --lforge alsxy,alsxz,d2b,dr,fpce --lforge-exact --lforge-no-confirm

  LForge — Signature Forge (exact)
  =======================================================
  Query: ALS+ALSXY+D2B+DR+FPCE (exact)
  Matched: 2 signatures, 395 seeds (seed=1775753237)
  Generated: 10 puzzles in 1ms (no-confirm)

  630000200007000098008000000010200000500310600000094000000000007000009040200500100  [ALS+ALSXY+D2B+DR+FPCE]
  420005680003000002007006010000008401100060805008000060000000900050070000800004050  [ALSXY+ALS+D2B+DR+FPCE]
  300007025000050000000100000200000506760090810003006047600000050030002074407000000  [ALSXY+ALS+D2B+DR+FPCE]
  400000200083020040010000003300080064000600700800040021008005000029000000100030002  [ALSXY+ALS+D2B+DR+FPCE]
  001807005000040180600005730003501070020000500000000000000290000007003800010004000  [ALSXY+ALS+D2B+DR+FPCE]
  000000070002005000030900008409800000010000000803010004000006040098420001040108003  [ALSXY+ALS+D2B+DR+FPCE]
  003470000090060071600009200700005640000080000900007500079006005026050700500000000  [ALSXY+ALS+D2B+DR+FPCE]
  009030000500200000000089600018090300003001000700000000200000004000400007006008100  [ALSXY+ALS+D2B+DR+FPCE]
  000001030900700640000040002090800000005002004700030010080000000009600700670000020  [ALSXY+ALS+D2B+DR+FPCE]
  600040300000028000040700000000070030020004600300500009100900060008001905000007100  [ALSXY+ALS+D2B+DR+FPCE]

  # 10 puzzles (exact, --lforge-no-confirm)

  Matched: 2 signatures, 652 seeds (seed=42)
  Generated: 15 puzzles in 2ms (no-confirm)

  030100470074003006600400300049030000020000000300001940450080009700009650000500000  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  800600200000000050090007003070060009000703400200109000500000040060300001008006070  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  530100020004007000000000009000000400450208030000046800005000080180005203300800100  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  302600900000934002090050000109300020000007000008010300000000290080000610906100003  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  502001090100200500004056020406009070000100000080000003000000060007000402600002709  [ALS+ALSXY+D2B+DR+FPC+FPCE+KF]
  060000000007090000403007002009030200030010004204008030708003400000000023300500087  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  402000030090200006800050020308040000000000000010700000000605100000009057005020080  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  400007008050000020006000900000240000100038000000701003300070004090800060002000500  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  005100006080090700600002080000400800500000300090030007030060070000200000001004009  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  500010403000000001030004080010008009000200000020003804200700000000060090080009100  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  050000000100300007006084000070008900200100070060000201000000002040050030300900700  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  030200090005000100000080007020900040600007800001000005400600000300090060060032000  [ALS+ALSXY+D2B+DR+FPC+FPCE+KF]
  300090080000400001200083070009070803800009702000008090050006008600030020002000600  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  094050000023000000100300409000000070000006004002400103030900201001008030200003006  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]
  032670000040003060100000300600040900000007100070300040005000009080030050200508000  [ALSXY+ALS+D2B+DR+FPC+FPCE+KF]


  # 15 puzzles (exact, --lforge-no-confirm)

larsdoku --lforge alsxy,alsxz,d2b,dr,fpce --lforge-exact --lforge-no-confirm

  LForge — Signature Forge (exact)
  =======================================================
  Query: ALS+ALSXY+D2B+DR+FPCE (exact)
  Matched: 2 signatures, 395 seeds (seed=1775753237)
  Generated: 10 puzzles in 1ms (no-confirm)

  630000200007000098008000000010200000500310600000094000000000007000009040200500100  [ALS+ALSXY+D2B+DR+FPCE]
  420005680003000002007006010000008401100060805008000060000000900050070000800004050  [ALSXY+ALS+D2B+DR+FPCE]
  300007025000050000000100000200000506760090810003006047600000050030002074407000000  [ALSXY+ALS+D2B+DR+FPCE]
  400000200083020040010000003300080064000600700800040021008005000029000000100030002  [ALSXY+ALS+D2B+DR+FPCE]
  001807005000040180600005730003501070020000500000000000000290000007003800010004000  [ALSXY+ALS+D2B+DR+FPCE]
  000000070002005000030900008409800000010000000803010004000006040098420001040108003  [ALSXY+ALS+D2B+DR+FPCE]
  003470000090060071600009200700005640000080000900007500079006005026050700500000000  [ALSXY+ALS+D2B+DR+FPCE]
  009030000500200000000089600018090300003001000700000000200000004000400007006008100  [ALSXY+ALS+D2B+DR+FPCE]
  000001030900700640000040002090800000005002004700030010080000000009600700670000020  [ALSXY+ALS+D2B+DR+FPCE]
  600040300000028000040700000000070030020004600300500009100900060008001905000007100  [ALSXY+ALS+D2B+DR+FPCE]

  # 10 puzzles (exact, --lforge-no-confirm)


larsdoku 030100470074003006600400300049030000020000000300001940450080009700009650000500000

Status: SOLVED
Steps:  53
Time:   191.1ms
WSRF:   FPCE

Techniques:
  crossHatch              22 ( 39.3%)  L1  █████████████
  lastRemaining           15 ( 26.8%)  L1  ████████
  nakedSingle             11 ( 19.6%)  L1  ██████
  fullHouse                3 (  5.4%)  L1  █
  FPCE                     2 (  3.6%)  L5  █ ★
  DeepResonance            1 (  1.8%)  L7  █
  ALS_XZ                   1 (  1.8%)  L5  █
  KrakenFish               1 (  1.8%)  L6  █

```

● 1,218,998,108,160 — ~1.2 trillion per seed.                                                                                                                                                                                            

```bash
larsdoku --reduce-solve ..345...945...9.3...93..4.52..59.34.39.2.4.5..45...9.25.2.4..9..3.9.25..91.7.582. 2018381088
======================================================================
  REDUCE-SOLVE: Strip Promotions, Solve, Map Back
======================================================================
  Input:  ..345...945...9.3...93..4.52..59.34.39.2.4.5..45...9.25.2.4..9..3.9.25..91.7.582.
  Clues:  40

  Solution: 123456789457189236689327415276598341391274658845631972562843197738912564914765823
● 1,218,998,108,160 — ~1.2 trillion per seed.                                                                                                                                                                                            

  Reducing...

----------------------------------------------------------------------
  SOLVE MATRIX
----------------------------------------------------------------------
  Puzzle                       Clues      Status  Mode            WSRF
  ──────────────────────────── ─────  ──────────  ──────────────  ────────────────────
  Original                        40      SOLVED  default         D2B, FPC
  Reduced 29cl                    29      SOLVED  default         D2B, FPC
  Seed Unknown                    29      SOLVED  default         D2B, FPC
  Reduced 28cl                    28      SOLVED  default         D2B, FPC
  Seed Unknown                    28      SOLVED  default         D2B, FPC
  Reduced 28cl                    28      SOLVED  default         D2B, FPC
  Seed Unknown                    28      SOLVED  default         D2B, FPC, FPCE
  Reduced 27cl                    27      SOLVED  default         D2B, FPC
  Seed Unknown                    27      SOLVED  default         
  Reduced 27cl                    27      SOLVED  default         D2B, FPC
  Seed Unknown                    27      SOLVED  default         FPC
  Reduced 27cl                    27      SOLVED  default         D2B, FPC
  Seed Unknown                    27      SOLVED  default         FPC
  Reduced 26cl                    26      SOLVED  default         D2B, FPC
  Seed DeepResonance,D2B #198446    26      SOLVED  default         D2B, FPC
  Reduced 26cl                    26      SOLVED  default         D2B, FPC
  Seed D2B #23979                 26      SOLVED  default         D2B, FPC
  Reduced 26cl                    26      SOLVED  default         D2B, FPC
  Seed D2B #19126                 26      SOLVED  default         D2B, FPC
  Reduced 25cl                    25      SOLVED  default         D2B, FPC
  Seed DeepResonance #209146      25      SOLVED  default         FPC, FPCE, FPF
  Reduced 25cl                    25      SOLVED  default         D2B, FPC
  Seed DeepResonance #206841      25      SOLVED  default         FPC

----------------------------------------------------------------------
  BEST SOLVE PATH
----------------------------------------------------------------------
  Solved via:   Reduced 25cl (25 clues, default)
  WSRF:         D2B, FPC
  Puzzle:       ....5....4....9.3...93....52...9.34.3..2.4.....5.....2..2.4..9..3...25...1.7..8..

  Techniques:
    crossHatch              29 ( 41.4%)  L1  █████████████
    nakedSingle             14 ( 20.0%)  L1  ██████
    lastRemaining            8 ( 11.4%)  L1  ███
    ALS_XZ                   4 (  5.7%)  L5  █
    DeepResonance            3 (  4.3%)  L7  █
    fullHouse                3 (  4.3%)  L1  █
    SimpleColoring           3 (  4.3%)  L4  █
    D2B                      1 (  1.4%)  L6  █ ★
    ALS_XYWing               1 (  1.4%)  L5  █
    KrakenFish               1 (  1.4%)  L6  █
    AlignedPairExcl          1 (  1.4%)  L5  █
    FPC                      1 (  1.4%)  L5  █ ★
    Swordfish                1 (  1.4%)  L3  █

  SOLUTION: 123456789457189236689327415276598341391274658845631972562843197738912564914765823

1 2 3 | 4 5 6 | 7 8 9
4 5 7 | 1 8 9 | 2 3 6
6 8 9 | 3 2 7 | 4 1 5
------+-------+------
2 7 6 | 5 9 8 | 3 4 1
3 9 1 | 2 7 4 | 6 5 8
8 4 5 | 6 3 1 | 9 7 2
------+-------+------
5 6 2 | 8 4 3 | 1 9 7
7 3 8 | 9 1 2 | 5 6 4
9 1 4 | 7 6 5 | 8 2 3

  Total time: 22.8s


# 6ms uniqueness oracle — no backtracker needed
larsdoku --lars-800900005007080010020006400005000030070004600900800002002070000100200000030001000certify "000000010400000000020000000000050407008000300001090000300400200050100000000806000"
# >>> UNIQUE <<<  Royle-certified

# Match ANY mask to a seed in 7ms (Final Boss Mode)
larsdoku --lars-forge-mask-match "...x..x.x....."

# Promote to any clue count — guaranteed unique, remove any added clue
larsdoku "000000010..." --lars-forge-promote 24

# Technique-targeted generation — "give me a KrakenFish puzzle"
larsdoku --lforge-attempt kraken --lforge-clues 23 --lforge-count 5

# See all available technique tags
larsdoku --lforge-stats
```800900005007080010020006400005000030070004600900800002002070000100200000030001000

| Feature | What it does |
|---------|-------------|
| `--lars-certify` | 6ms uniqueness oracle (Royle hash lookup) |
| `--lars-forge-mask-match` | Match any 17-clue mask to a seed (7ms) |
| `--lars-forge-promote N` | 17-clue → any clue count, all unique |
| `--lforge-attempt TECHS` | Generate by technique (684 seeds, 16 techniques) |
| `--include TECHS` | Add techniques to presets |

**The numbers:** 49,196 seeds × 362,880 digit perms × 3,359,232 symmetries = **60 quadrillion** unique 17-clue puzzles. With promote (2^64 variants per seed): **1 undecillion** (10^36) across all clue counts.

## Lars Seeds: 384K DeepRes/D2B Seeds — 469 Quadrillion Hard Puzzles

The **Lars Seeds Registry** contains 384,505 seeds for the hardest Sudoku techniques (DeepResonance & D2B), forged via a novel swap technique. Every puzzle is confirmed by the solver before output.

### Forge DeepRes Puzzles (confirmed by solver)
```
$ larsdoku --lforge-deepres 3

  LForge — DeepRes Puzzle Forge
  =============800900005007080010020006400005000030070004600900800002002070000100200000030001000==========================================
  Lars Seeds: 209,762 DeepRes seeds
  Confirmed: 3/3 in 722ms

  000200000200000046039000200000010000006008015900400600075000008000007000400600300  [ALS_XZ, D2B, DeepResonance, FPC, FPCE, JuniorExocet]
  700600010000005009400000300102000800040200060607000002004100023000090008000003500  [D2B, DeepResonance, FPCE]
  080900007200000050004000300800700000010096000000001009300800020070600008000040500  [ALS_XYWing, AlignedPairExcl, DeepResonance, FPC, FPCE, JuniorExocet]

  # 3 DeepRes puzzles (confirmed by solver)
```

### Forge D2B Puzzles (confirmed by solver)
```
$ larsdoku --lfo800900005007080010020006400005000030070004600900800002002070000100200000030001000rge-d2b 3

  LForge — D2B Puzzle Forge
  =======================================================
  Lars Seeds: 174,745 D2B seeds
  Confirmed: 3/3 in 934ms

  000000000500020068030879400000010600060208015100500080270080046004000000000700000  [ALS_XYWing, ALS_XZ, D2B, FPC, KrakenFish]
  700009300040050000001700040100000800070200060602000009400600010007005000000030708  [ALS_XZ, AlignedPairExcl, D2B, DeepResonance, FPC, FPCE, JuniorExocet]
  090001020003709500000000007030640000200003600056010030002070000060305200005000080  [ALS_XYWing, ALS_XZ, D2B, FPC, FPCE, KrakenFish]

  # 3 D2B puzzles (confirmed by solver)
```

### Elite Mode — Puzzles That Stall Expert Solvers

If you have a really good solver and want puzzles that will challenge it, use `--elite`. These puzzles should be harder for those of you with solvers that as close to 100% as you can get like larsdoku — only DeepResonance/D2B and other really good solvers like this one should be able to crack them.

```bash
larsdoku --lforge-d2b 25 --lforge-seed 777 --elite
```

### Lars Provenance — "Is this puzzle a Lars Database Seed?"
```
$ larsdoku --lars-provenance "700009300040050000001700040100000800070200060602000009400600010007005000000030708"

  Lars Provenance Registry
  =======================================================
  Input: 700009300040050000001700040100000800070200060602000009400600...
  Clues: 24
  Time:  4.5ms

  >>> LARS DATABASE SEED MATCH <<<
  Confidence: Very high (core seed match)
  Techniques: ALS_XZ, AlignedPairExcl, D2B, DeepResonance, FPC, FPCE, JuniorExocet
  Hash: (((2, 2, 3), (2, 3, 3), (2, 3, 4)), ((2, 3, 3), (2, 3, 3), (2, 3, 3)), (1, 2, 2, 3, 3, 3, 3, 3, 4))
  This puzzle is derived from a Lars Seed.
```

### Reduce a Puzzle for Unsolvable Seeds
```
larsdoku --auto-reduce  1..4..789457189236.98..7.1..1.89.673.8.7.....7...1.8...759.1..88.154...794..78...
======================================================================
  AUTO-REDUCE: Full Seed Ancestry Analysis
======================================================================
  Input:  1..4..789457189236.98..7.1..1.89.673.8.7.....7...1.8...759.1..88.154...794..78...
  Clues:  43
  Unique: True

1 . . | 4 . . | 7 8 9
4 5 7 | 1 8 9 | 2 3 6
. 9 8 | . . 7 | . 1 .
------+-------+------
. 1 . | 8 9 . | 6 7 3
. 8 . | 7 . . | . . .
7 . . | . 1 . | 8 . .
------+-------+------
. 7 5 | 9 . 1 | . . 8
8 . 1 | 5 4 . | . . 7
9 4 . | . 7 8 | . . .

  Input: NOT in Lars Database (need reduction)

----------------------------------------------------------------------
  Running 9 reduction passes (5 strategies)...
----------------------------------------------------------------------
  [        scan]  base = 26 clues, stripped = 17 >>> 1 MATCH(ES)!
  [     reverse]  base = 27 clues, stripped = 16
  [     density]  base = 25 clues, stripped = 18
  [  sig-guided]  base = 26 clues, stripped = 17 >>> 1 MATCH(ES)!
  [    random-1]  base = 27 clues, stripped = 16
  [    random-2]  base = 28 clues, stripped = 15
  [    random-3]  base = 29 clues, stripped = 14
  [    random-4]  base = 28 clues, stripped = 15
  [    random-5]  base = 27 clues, stripped = 16

  Exhaustive search on 25-clue base (up to 3 more removals)...
  [exhaustive]   No additional matches found

======================================================================
  SEED ANCESTRY TRACE
======================================================================
  Input:  43 clues ──── NOT IN DB
    | strip 17
  26 clues ──── CORE 100%  D2B  [#149379]
    |  Seed:     980700500500009006007000000400630000030000000006007300008006950005078600000200018
    |  Hash:     (((1, 3, 3), (1, 3, 4), (3, 4, 4)), ((2, 2, 4), (2, 3, 4), (2, 3, 4)), (1, 2, 2, 2, 3, 3, 4, 4, 5))
    |  Found by: scan, sig-guided
    | strip 18
  25 clues ──── BASE UNIQUE (NEW)

----------------------------------------------------------------------
  SEED MATCHES: 1
----------------------------------------------------------------------

  Match #1:
    Clues:      26
    Confidence: exact (core seed)
    Technique:  D2B
    Seed index: #149379
    Seed bd81:  980700500500009006007000000400630000030000000006007300008006950005078600000200018
    Hash:       (((1, 3, 3), (1, 3, 4), (3, 4, 4)), ((2, 2, 4), (2, 3, 4), (2, 3, 4)), (1, 2, 2, 2, 3, 3, 4, 4, 5))
    Reduced:    ...4...........236.9...7.1..1..9.6.3.8.......7...1.8....5..1..8..154...794..78...
    Strategy:   scan, sig-guided

    Seed board:
      9 8 . | 7 . . | 5 . .
      5 . . | . . 9 | . . 6
      . . 7 | . . . | . . .
      ------+-------+------
      4 . . | 6 3 . | . . .
      . 3 . | . . . | . . .
      . . 6 | . . 7 | 3 . .
      ------+-------+------
      . . 8 | . . 6 | 9 5 .
      . . 5 | . 7 8 | 6 . .
      . . . | 2 . . | . 1 8

    Reduced board:
      . . . | 4 . . | . . .
      . . . | . . . | 2 3 6
      . 9 . | . . 7 | . 1 .
      ------+-------+------
      . 1 . | . 9 . | 6 . 3
      . 8 . | . . . | . . .
      7 . . | . 1 . | 8 . .
      ------+-------+------
      . . 5 | . . 1 | . . 8
      . . 1 | 5 4 . | . . 7
      9 4 . | . 7 8 | . . .

----------------------------------------------------------------------
  BASE UNIQUES (all orderings)
----------------------------------------------------------------------
  25 clues  [density]
    ...4....9......236.....7.1..1..9.6.3.8.......7...1.8....59....8..154....94..78...

  26 clues  [scan, sig-guided]
    ...4...........236.9...7.1..1..9.6.3.8.......7...1.8....5..1..8..154...794..78...

  27 clues  [reverse]
    1..4..7.945.1..2....8..7.1....89.673.8.7.........1.....75.....8..154....94.......

  27 clues  [random-1]
    1..4..7......89236.9.....1....89.6.3...7.....7...1.8....5.....88.154....94..7....

  27 clues  [random-5]
    1..4..7..45...9.3..98....1....89.673.8.7.........1.....75.....8..154....94..7....

  28 clues  [random-2]
    1..4..7.9457.8..3...8....1.....9.6.3.8.7.....7...1.8....59.......154...794...8...

  28 clues  [random-4]
    ...4....945.....36.9...7.1..1.89.673...7.........1.8...759....88.154....94.......

  29 clues  [random-3]
    ...4..789457....3........1..1.89.673.8.7.........1.8...75..1...8.154....94..7....

----------------------------------------------------------------------
  BEST BASE UNIQUE: 25 clues  [density]
----------------------------------------------------------------------
  ...4....9......236.....7.1..1..9.6.3.8.......7...1.8....59....8..154....94..78...

. . . | 4 . . | . . 9
. . . | . . . | 2 3 6
. . . | . . 7 | . 1 .
------+-------+------
. 1 . | . 9 . | 6 . 3
. 8 . | . . . | . . .
7 . . | . 1 . | 8 . .
------+-------+------
. . 5 | 9 . . | . . 8
. . 1 | 5 4 . | . . .
9 4 . | . 7 8 | . . .

  PROMOTION SEQUENCE (18 steps, base -> full):
    step  1: +R5C4=7  (pos=39)
    step  2: +R4C8=7  (pos=34)
    step  3: +R8C9=7  (pos=71)
    step  4: +R4C4=8  (pos=30)
    step  5: +R7C6=1  (pos=59)
    step  6: +R8C1=8  (pos=63)
    step  7: +R7C2=7  (pos=55)
    step  8: +R3C3=8  (pos=20)
    step  9: +R1C8=8  (pos=7)
    step 10: +R1C7=7  (pos=6)
    step 11: +R3C2=9  (pos=19)
    step 12: +R1C1=1  (pos=0)
    step 13: +R2C6=9  (pos=14)
    step 14: +R2C5=8  (pos=13)
    step 15: +R2C3=7  (pos=11)
    step 16: +R2C4=1  (pos=12)
    step 17: +R2C1=4  (pos=9)
    step 18: +R2C2=5  (pos=10)

  Total time: 0.9s
  Strategies: 9 orderings + exhaustive
  Lars DB:    10,698 signatures | 438,564 seeds | 1.1 quintillion puzzles
              64291 core + 129828 variant hashes
======================================================================
```

### Lars Certify — 6ms Uniqueness Oracle
```
$ larsdoku --lars-certify "000000010400000000020000000000050407008000300001090000300400200050100000000806000"

  Lars Certify — Uniqueness Oracle
  ═══════════════════════════════════════════════════════
  Input:   000000010400000000020000000000050407008000300001090000300400...
  Clues:   17
  Method:  royle_hash
  Time:    15.0ms

  >>> UNIQUE <<<
  Royle-certified: this mask geometry is in the complete
  enumeration of all 49,158 valid 17-clue patterns.
```

| Command | What it does |
|---------|-------------|
| `--lforge-deepres N` | Forge N DeepRes puzzles (confirmed by solver) |
| `--lforge-d2b N` | Forge N D2B puzzles (confirmed by solver) |
| `--lforge-no-confirm` | Skip solver verification (fast mode) |
| `--lars-provenance "puzzle"` | Check if puzzle is a Lars Seed (4.5ms) |
| `--lars-seeds-stats` | Registry statistics (384K seeds, 469 quadrillion) |

** USE --preset expert  first, and --preset larstech for the new techniques listed at the gihub New Techniques site! 

** --preset larstech are new techniques i created that the community should review and comment on before i put them in as expert techniques


```
# Run --warmup to save JIT conmpilations for 109-1000x speedups!! Seriously, run once, it compiles and saves, and it's fast for every run thereafter without the nee for --warmup
pip insta64291 core + 129828 variant hashes.     larsdoku==3.6.2
larsdoku --warmup 
```

### Troubleshooting

If `larsdoku` fails on startup with a Numba cache error (`no locator available`):

```bash
export NUMBA_CACHE_DIR="$HOME/.cache/numba"
mkdir -p "$NUMBA_CACHE_DIR"
larsdoku "<puzzle>" --board
```

Or as a one-liner:

```bash
NUMBA_CACHE_DIR="$HOME/.cache/numba" larsdoku "<puzzle>" --board
```

Or

## Temporary workaround for Numba cache error

If `larsdoku` fails at startup with a Numba cache error, run:

```bash
  mkdir -p /tmp/numba_cache
  export NUMBA_CACHE_DIR=/tmp/numba_cache
```
Then run larsdoku normally.

---

## Quick Start

### Python API

```python
from larsdoku import solve

result = solve("4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........")

print(result['success'])           # True
print(result['n_steps'])           # 63
print(result['technique_counts'])  # {'crossHatch': 42, 'nakedSingle': 9, ...}
print(result['board'])             # solved 81-char string
```

### Command Line

```bash
# Solve and print the board
larsdoku "800000000003600000070090200050007000000045700000100030001000068008500010090000400" --board

# Pure logic only (no oracle fallback)
larsdoku "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........" --board --no-oracle

# Step-by-step trace
larsdoku "100007090030020008009600500005300900010080002600004000300000010040000007007000300" --steps

# Detailed round-by-round solve log
larsdoku "100000002090400050006000700050903000000070000000850040700000600030009080002000001" --detail --board

# Trace the full solution path to a specific cell
larsdoku "000004006000201090001070800060000020350000008000000370009080500040302000700100000" --cell R7C4 --path --preset expert
```

```
  ✦ Sudoku Expert Approved Techniques ✦

  R7C4 = 4 via lastRemaining (step 8)
  Candidates: [4, 6, 7]
  Full solve: 58 steps, COMPLETE
  Time: 697.2ms

  Verify: All techniques are Sudoku Expert Approved ✓
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

  Techniques used:
    ALS_XZ                10  L5
    ALS_XYWing             5  L5
    ForcingChain           3  L5
    crossHatch             3  L1
    lastRemaining          2  L1
    KrakenFish             1  L6

  Solution path (8 placements, 16 elimination rounds):
       ~elim~  [ALS_XZ L5] 1 eliminations
     #  1  R1C4=8  [lastRemaining L1]
     #  2  R3C8=5  [ForcingChain L5]
       ~elim~  [ALS_XZ L5] 1 eliminations
     #  3  R9C6=5  [crossHatch L1]
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [KrakenFish L6] 1 eliminations
     #  4  R1C8=1  [ForcingChain L5]
     #  5  R7C8=3  [ForcingChain L5]
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
     #  6  R4C6=3  [crossHatch L1]
     #  7  R6C6=8  [crossHatch L1]
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
       ~elim~  [ALS_XZ L5] 1 eliminations
       ~elim~  [ALS_XYWing L5] 1 eliminations
   → #  8  R7C4=4  [lastRemaining L1]
```

### Board Forge — Generate Puzzles by Technique

```bash
# Generate a ForcingChain puzzle
larsdoku --board-forge MC --require ForcingChain --exclude als,alsxy,ape,fpc,fpce --board-forge-count 1

# Generate a DeathBlossom puzzle
larsdoku --board-forge MC --require DeathBlossom --exclude als,alsxy --board-forge-count 1

# Generate a KrakenFish puzzle
larsdoku --board-forge MC --require KrakenFish --board-forge-count 1 --require-attempts 200
```text
Status: SOLVED
Steps:  53
Time:   65.7ms
Verify: All techniques are Sudoku Expert Approved ✓

  Board validated: every row, column, and box contains
  digits 1-9 exactly once per international Sudoku rules.
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

Techniques:
  nakedSingle             22 ( 36.1%)  L1  ████████████
  crossHatch              17 ( 27.9%)  L1  █████████
  lastRemaining            8 ( 13.1%)  L1  ████
  DeathBlossom             5 (  8.2%)  L5  ██
  fullHouse                5 (  8.2%)  L1  ██
  KrakenFish               2 (  3.3%)  L6  █
  SimpleColoring           1 (  1.6%)  L4  █
  ForcingChain             1 (  1.6%)  L5  █
```
# Generate pure ALS puzzles
larsdoku --board-forge MC --require ALS_XZ --board-forge-count 5
```

**The flex:** Puzzles generated with `--require ForcingChain` need FC to solve *when ALS is excluded*. But with the full solver, ALS-XZ handles what ForcingChain does — making FC unnecessary. The solver is quite good so it renders ForcingChain obsolete on its own generated puzzles so it's hard to do. but check out --like if you really want similar puzzles!

```bash
# See ForcingChain in action — solve with ALS excluded so FC fires
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --steps --exclude als,alsxy,ape,fpc,fpce

# Now solve the same puzzle with the full solver — no FC needed
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --steps --preset expert
```

### Like — Generate Similar Puzzles

Find a puzzle you enjoy and generate more like it. `--like` analyzes the technique profile and shuffles until it finds puzzles that require the same advanced techniques:

```bash
larsdoku --like "005000903906000500080000010020060080000510400000008007100006000040000090003702000" --like-count 5
```

```
════════════════════════════════════════════════════════════
  LIKE — Generate Similar Puzzles
  Reference: 005000903906000500080000010020060080000510400000008007100006000040000090003702000
  Clues: 23 | SOLVED
  Techs: nakedSingle=26, crossHatch=22, lastRemaining=7, fullHouse=2, ALS_XZ=1, FPCE=1, SimpleColoring=1
  Profile: ALS_XZ, FPCE, SimpleColoring
  Count: 5
════════════════════════════════════════════════════════════

  [1/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 000500600000004803070010020002807000580000000300009000100000306020060050009000004
  Techs:  crossHatch=34, lastRemaining=12, nakedSingle=11, ALS_XZ=1, FPCE=1

  [2/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 300400090020000506001000800000501000070006000045090000000003608000070002800900010
  Techs:  crossHatch=28, lastRemaining=14, nakedSingle=10, fullHouse=5, ALS_XZ=1

  [3/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 000900002000040105008007000100000006070000390006005020009006000030820000480030000
  Techs:  crossHatch=28, lastRemaining=14, nakedSingle=10, fullHouse=5, ALS_XZ=1

  [4/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 001200000507060000000305000004000205300000008090007060000010400000900802080006030
  Techs:  crossHatch=37, nakedSingle=13, lastRemaining=6, ALS_XZ=1, FPCE=1

  [5/5] SOLVED | 23 clues | match: ALS_XZ, FPCE, SimpleColoring
  Puzzle: 900000027010080500003000060000100076000004009060050300802005000000320000400700000
  Techs:  crossHatch=36, nakedSingle=12, lastRemaining=9, ALS_XZ=1, FPCE=1

════════════════════════════════════════════════════════════
  RESULTS: 5/5 similar puzzles in 6 shuffles
```

# Cell Path — Trace the Solution to Any Cell

Want to know exactly how a specific cell was solved? Use `--cell` with `--path` to see every step the engine took to reach that placement.

```bash
larsdoku "300002590600008070040050001009100030000000008070060040010080400000000003008700200" --cell R1C3 --path --preset expert
```

```
  ✦ Sudoku Expert Approved Techniques ✦

  R1C3 = 1 via ForcingChain (step 5)
  Candidates: [1, 7]
  Full solve: 57 steps, COMPLETE
  Time: 416.9ms

  Verify: All techniques are Sudoku Expert Approved ✓
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

  Techniques used:
    nakedSingle            2  L1
    crossHatch             2  L1
    ForcingChain           1  L5
    XWing                  1  L3

  Solution path (5 placements, 1 elimination rounds):
       ~elim~  [XWing L3] 4 eliminations
     #  1  R1C2=8  [nakedSingle L1]
     #  2  R2C7=3  [nakedSingle L1]
     #  3  R4C1=8  [crossHatch L1]
     #  4  R6C4=8  [crossHatch L1]
   → #  5  R1C3=1  [ForcingChain L5]
```

The full puzzle took 57 steps to solve, but R1C3 only needed 5 — an X-Wing elimination to clear the path, four foundation placements, and then a ForcingChain to prove R1C3 = 1. Every step is deterministic logic. No guessing.

## Still Solves When Key Techniques Are Removed

Larsdoku is not dependent on one narrow family of advanced techniques.

Even with several known techniques disabled, it can still reroute through other expert-approved logic and finish the board cleanly — with **no backtracking, no guessing, and no trial-and-error**.

### Example

```bash
larsdoku "600058300030210060000000819002043500040090080000081000000000906054020070006100000" --exclude als,alsxy,ape,fpc,fpce

```text
Status: SOLVED
Steps:  53
Time:   65.7ms
Verify: All techniques are Sudoku Expert Approved ✓

  Board validated: every row, column, and box contains
  digits 1-9 exactly once per international Sudoku rules.
  No backtracking or trial-and-error was used at any point.
  Every placement was derived by deterministic logic alone.

Techniques:
  nakedSingle             22 ( 36.1%)  L1  ████████████
  crossHatch              17 ( 27.9%)  L1  █████████
  lastRemaining            8 ( 13.1%)  L1  ████
  DeathBlossom             5 (  8.2%)  L5  ██
  fullHouse                5 (  8.2%)  L1  ██
  KrakenFish               2 (  3.3%)  L6  █
  SimpleColoring           1 (  1.6%)  L4  █
  ForcingChain             1 (  1.6%)  L5  █
```


### More Tools

```bash
# Parse a SudokuWiki packed string directly
larsdoku "S9B8283024j..." --cell R1C1 --path

# Quick backtrack solution
larsdoku "000809000014020090000040006..." --solution

# Parse a forum grid (paste, then Ctrl+D)
echo "+---+---+---+
|.5.|12.|.93|
|..7|...|8.1|
|.2.|..9|...|
+---+---+---+" | larsdoku --parse
```

---

## Benchmark Results

Tested against every major Sudoku benchmark collection:

| Collection | Puzzles | Pure Logic | Avg Time | Total |
|---|---|---|---|---|
| **Top1465** (Stertenbrink) | 1,465 | **100%** | 0.019s | 28s |
| **Expert 669** (shuffled) | 669 | **100%** | 0.036s | 24s |
| **Famous 10** (hardest known) | 10 | **70%** | 0.50s | 5s |

Run benchmarks yourself:

```bash
# Full benchmark suite
larsdoku-bench

# Individual collections
larsdoku-bench --collection top1465
larsdoku-bench --collection expert
larsdoku-bench --collection famous
```

### Top1465 Technique Breakdown

```
crossHatch            42,852x  ( 49.4%)
nakedSingle           21,382x  ( 24.6%)
lastRemaining         13,510x  ( 15.6%)
FPC                    4,050x  (  4.7%)  <-- WSRF invention
fullHouse              3,826x  (  4.4%)
FPCE                     453x  (  0.5%)  <-- WSRF invention
SimpleColoring           354x  (  0.4%)
GF2_Lanczos              216x  (  0.2%)
XWing                     90x  (  0.1%)
Swordfish                 44x  (  0.1%)
```

---

## Techniques

Larsdoku implements **35 detectors** across 7 levels of escalation:

### L1 — Foundation
- **Full House** — last empty cell in a unit
- **Naked Single** — cell with only one candidate
- **Hidden Single** (crossHatch / lastRemaining) — digit possible in only one cell

### L2 — Linear Algebra
- **GF(2) Block Lanczos** — Gaussian elimination over GF(2) to find forced digits via parity constraints
- **GF(2) Extended** — probing, conjugate analysis, and band/stack decomposition

### L3 — Fish
- **X-Wing** — row/column digit elimination via 2x2 pattern
- **Swordfish** — 3x3 generalization of X-Wing

### L4 — Chains
- **Simple Coloring** — single-digit conjugate chain contradictions
- **X-Cycles** — single-digit alternating inference chains (Rules 1/2/3)

### L5 — Set Logic & Forcing
- **ALS-XZ** — Almost Locked Set pair with restricted common
- **ALS-XY Wing** — three-ALS chain elimination
- **Sue De Coq** — box/line intersection set partitioning
- **Aligned Pair Exclusion** — combination validation against common peers
- **Death Blossom** — stem cell with ALS petals
- **FPC (Finned Pointing Chain)** — WSRF invention. Pointing patterns with a fin cell
- **FPCE (FPC Elimination)** — WSRF invention. Contradiction testing via propagation
- **Forcing Chain** — bivalue cell branching with convergence proof
- **Forcing Net** — wider branching through the constraint network

### L6 — Advanced
- **BUG+1** — Bivalue Universal Grave plus one extra candidate
- **Unique Rectangle** (Type 2 & 4) — deadly pattern avoidance
- **Junior Exocet** — minirow-based digit placement (3-empty minirows, Double Exocet)
- **Template** — full-board digit template matching
- **Bowman's Bingo** — deep contradiction chains
- **Kraken Fish** — finned fish with forcing chain verification
- **SK Loop** — Stephen Kurzhal's Loop (massive eliminations)
- **D2B (Depth-2 Bilateral)** — WSRF invention. Branch on bivalue cell, run FPCE on both branches

### L7 — Final Backstop
- **DeepResonance** — WSRF invention. Full-stack proof-by-contradiction (requires Autotrust)
- **FPF (Full Pipeline Forcing)** — WSRF invention. Branch on each candidate, run entire pipeline per branch

---

## CLI Reference

```bash
# Basic solve
larsdoku <puzzle>                              # auto-solve, show summary
larsdoku <puzzle> --board                      # print solved grid
larsdoku <puzzle> --steps                      # step-by-step trace
larsdoku <puzzle> --detail                     # rich round-by-round log

# Technique control
larsdoku <puzzle> --no-oracle                  # pure logic only
larsdoku <puzzle> --level 2                    # L1+L2+GF(2) only
larsdoku <puzzle> --preset expert              # standard techniques only (no WSRF)
larsdoku <puzzle> --only fpc,gf2               # specific techniques only
larsdoku <puzzle> --exclude d2b,fpf            # exclude specific techniques

# Cell analysis
larsdoku <puzzle> --cell R3C5                  # how is R3C5 solved?
larsdoku <puzzle> --cell R3C5 --path           # full technique path to R3C5

# Benchmarking
larsdoku <puzzle> --bench 250                  # benchmark 250 shuffled variants
larsdoku <puzzle> --bench 100 --preset expert  # benchmark with expert-only techniques

# Output
larsdoku <puzzle> --json                       # JSON output
larsdoku <puzzle> --json | python -m json.tool # pretty-printed JSON

# GF(2) extended
larsdoku <puzzle> --gf2x                       # probing + conjugates + band/stack

# Web UI
larsdoku --serve                               # full-featured web solver at localhost:8765
```

### Puzzle Format

Puzzles are 81-character strings, row by row, left to right. Use `0` or `.` for empty cells.

```
003000600900700010080005020600010900200807003004090005020500060010003002005000300
4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........
```

---

## Built-in Puzzle Collections

Larsdoku ships with three puzzle collections for testing and benchmarking:

```python
from larsdoku.puzzles import FAMOUS_10, EXPERT_669, TOP1465
```

### Famous 10

The 10 hardest famous Sudoku puzzles ever published, including AI Escargot (Arto Inkala, 2006), Easter Monster (champagne, 2007), and Golden Nugget (tarek, 2007). Each has a unique solution.

```python
for name, author, year, puzzle in FAMOUS_10:
    print(f"{name} by {author} ({year})")
```

### Expert 669

669 expert-level puzzles, box-shuffled for originality. All verified to have unique solutions. 100% pure logic solve rate.

### Top1465

The canonical benchmark collection compiled by Guenter Stertenbrink (dukuso). 1,465 of the hardest Sudoku puzzles, sorted by difficulty rating. The gold standard for solver evaluation since the mid-2000s.

---

## Python API

```python
from larsdoku import solve

# Basic solve
result = solve("4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........")

# Pure logic only
result = solve(puzzle, no_oracle=True)

# Limit technique level
result = solve(puzzle, max_level=5)

# Rich detail mode
result = solve(puzzle, detail=True)

# GF(2) extended
result = solve(puzzle, gf2_extended=True)
```

### Result Dictionary

```python
{
    'success': True,              # puzzle solved?
    'stalled': False,             # did the engine stall?
    'board': '468931527...',      # solved board (81-char)
    'solution': '468931527...',   # backtrack solution for verification
    'n_steps': 63,                # number of placement steps
    'steps': [...],               # list of step dicts
    'technique_counts': {         # technique frequency
        'crossHatch': 42,
        'nakedSingle': 9,
        ...
    },
    'empty_remaining': 0,         # cells unsolved
    'rounds': 12,                 # solver rounds
}
```

---

## How It Works

Larsdoku uses a **dual-representation bitwise architecture**:

- **Cell-centric**: `cands[81]` — each cell is a 9-bit mask (bit *i* = digit *i+1* is a candidate)
- **Digit-centric**: `cross[9]` — each digit is an 81-bit mask (bit *i* = cell *i* has this digit)

Both representations are kept in sync. Cell-centric is fast for per-cell operations (naked single, placement). Digit-centric is fast for per-digit operations (hidden single, X-Wing, pointing).

The solver pipeline escalates from simple to profound:

```
L1 Singles → L2 GF(2) → L3 Fish → L4 Chains → L5 ALS/FPC/Forcing → L6 Exotic → L7 DeepResonance/FPF
```

Each technique fires only when everything above it has stalled. The pipeline never needs to guess.

### WSRF Inventions

Five techniques in Larsdoku are original WSRF contributions, not found in traditional Sudoku solving literature:

| Technique | Type | Impact on Top1465 |
|---|---|---|
| **FPC** | Placement | 4,050 placements (4.7% of all steps) |
| **FPCE** | Elimination | 453 eliminations |
| **D2B** | Bilateral proof | Unlocks puzzles that stall L5 |
| **DeepResonance** | Full-stack contradiction | Autotrust-powered proof-by-exhaustion |
| **FPF** | Full pipeline forcing | Final backstop, eliminates all remaining |

---

## Web UI

Larsdoku ships with a full-featured web interface — a dark-themed, mobile-friendly Sudoku board with step-by-step playback, technique breakdown, and candidate notes.

```bash
larsdoku --serve
# Open http://localhost:8765
```

### Features

- **Dual engine**: standalone JS solver (client-side) or full Python engine (all 35 detectors)
- **Options panel**: Level slider (L1-L7), preset selection (Expert/WSRF), No Oracle, Autotrust, GF(2) toggles
- **Step-by-step playback**: walk through the solve with Back/Next, see each technique fire
- **Candidate notes**: toggle pencil marks on the board — watch candidates shrink as techniques eliminate them
- **Cell query**: tap any unsolved cell and query the engine for the exact technique path to solve it, with elimination events interleaved
- **Elimination trace**: `~elim~ [SimpleColoring] 5 eliminations` events interleaved in the step trace
- **Export**: `bd81` (original puzzle), `bdp` (S9B packed format with candidates), PNG snapshot
- **Famous puzzles**: built-in collection of the hardest known puzzles, plus difficulty-graded pools

### Autotrust Mode — The Backtracker Doesn't Deserve Your Trust

Every traditional Sudoku solver has the same skeleton in its closet: a **backtracker**. It brute-forces through possibilities, one cell at a time, until something sticks. It doesn't understand *why* a 7 goes in R3C5 — it just tried 1 through 6 and they all crashed. It returns *a* solution, proclaims victory, and moves on. But here's what nobody talks about: **for puzzles with symmetric or near-degenerate configurations, the backtracker's solution is arbitrary.** Its branching order — left to right, top to bottom, lowest digit first — is a coin flip masquerading as truth. It doesn't find *the* answer. It finds *an* answer. And that answer may have nothing to do with what logical deduction would prove.

Larsdoku's **Autotrust** mode exposes this gap — and then transcends it.

When Autotrust is enabled, the engine takes the backtracker's proposed solution and uses it as a verification oracle — a hypothesis to test, not a gospel to follow. Every single placement is still proven through pure logic: naked singles, forcing chains, GF(2) linear algebra, contradiction testing. The backtracker didn't solve the puzzle. **The logic engine solved the puzzle.** The backtracker just gave it a target to aim at.

And here's where it gets interesting: **Autotrust unlocks techniques the pure-logic pipeline can't reach alone.** The L7 detector **DeepResonance** works by assuming a candidate and running the entire technique stack against it — if every technique in the arsenal fails to resolve the board, that candidate is proven invalid by exhaustion. This is rigorous proof-by-contradiction, not guessing. But it needs to know what "correct" looks like to verify it isn't eliminating the actual answer. Autotrust provides that safety net, letting DeepResonance eliminate with absolute confidence.

The result: puzzles that stall at L6 in pure-logic mode **solve cleanly with Autotrust**, because the engine was always capable of proving the answer — it just needed permission to swing the full weight of its arsenal. The backtracker is scaffolding. The logic is the building.

**The backtracker finds a solution. Larsdoku proves why it's right — or finds a better one.**

---

## Requirements

- Python >= 3.9
- NumPy >= 1.22
- Numba >= 0.56

---

## License

AGPL-3.0-or-later. See [LICENSE](LICENSE) for details.

---

## Author

**Lars** ([oppressionslayer](https://github.com/oppressionslayer))

Built with the WSRF (Wiliam's Statistical Reasoning Framework) methodology.
