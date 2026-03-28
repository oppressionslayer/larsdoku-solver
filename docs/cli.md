# CLI Reference

Larsdoku installs three commands: `larsdoku` (solver), `larsdoku-bench` (benchmarks), and `larsdoku-research` (oracle-guided research tool).

## larsdoku

### Basic Usage

```bash
larsdoku <puzzle> [options]
```

### Core Options

| Flag | Short | Description |
|---|---|---|
| `--board` | `-b` | Print solved board grid |
| `--steps` | `-s` | Show step-by-step solution trace |
| `--detail` | `-d` | Rich round-by-round output with candidates and explanations |
| `--rich-output` | | Colored terminal output with panels and technique highlighting (requires `rich`) |
| `--no-oracle` | `-n` | Pure logic only — stop when stalled, no guessing |
| `--level N` | `-l N` | Max technique level (1-7) |
| `--only TECHS` | `-o` | Only use specific techniques (comma-separated) |
| `--exclude TECHS` | `-x` | Exclude specific techniques |
| `--preset NAME` | | Use preset: `expert`, `larstech`, or `wsrf` |
| `--verbose` | `-v` | Verbose output during solve |
| `--json` | `-j` | Output as JSON |

### Analysis Tools

| Flag | Description |
|---|---|
| `--cascade` | Cascade analysis: find bottleneck moves and show how the puzzle avalanches |
| `--cascade --batch N` | Batch cascade: generate N shuffled variants and show bottleneck distribution |
| `--siro-table` | Quick SIRO prediction table for all cells — no solving needed |
| `--inspector CELL` | Full cell inspector with SIRO, zone metrics, technique prediction, cascade depth |
| `--cell-placement CELL` | Predict and place a specific cell |
| `--predict-path` | Predict which technique places each cell |
| `--cell CELL` | `-c` | Query solution for a specific cell (e.g., R3C5) |
| `--path` | `-p` | Show technique path to `--cell` |

### Puzzle Utilities

| Flag | Description |
|---|---|
| `--unique` | Check if puzzle has a unique solution |
| `--solutions N` | Find first N solutions (for multi-solution puzzles) |
| `--backtrack-solve` | Solve using backtracker — always finds a solution, prints board |
| `--solution` | Print backtrack solution string only (fast, no techniques) |

### Exocet & Experimental

| Flag | Description |
|---|---|
| `--scandalous-tech` | Post-solve Exocet scan: solve with pure logic, then validate Exocet patterns against the solution (ScandolousExocet — 100% accurate) |
| `--experimental` | Enable experimental techniques (JETest — research Exocet detector) |

### Technique Presets

| Preset | Description |
|---|---|
| `expert` | Standard L1-L6 techniques only (no WSRF inventions, no exotic) |
| `larstech` | All techniques including WSRF inventions (FPC, FPCE, D2B, FPF) + Stuart's JuniorExocet |
| `wsrf` | Full WSRF stack |

### Technique Aliases

Use these short names with `--only` and `--exclude`:

| Alias | Technique |
|---|---|
| `fpc` | FPC |
| `fpce` | FPCE |
| `fc` | ForcingChain |
| `fn` | ForcingNet |
| `d2b` | D2B |
| `fpf` | FPF |
| `gf2` | GF2_Lanczos |
| `gf2x` | GF2_Extended |
| `xwing` | XWing |
| `swordfish` | Swordfish |
| `coloring` | SimpleColoring |
| `xcycle` | XCycle |
| `als`, `alsxz` | ALS_XZ |
| `alsxy` | ALS_XYWing |
| `sdc`, `suedecoq` | SueDeCoq |
| `ape` | AlignedPairExcl |
| `db`, `deathblossom` | DeathBlossom |
| `kraken` | KrakenFish |
| `skloop` | SKLoop |
| `dr`, `deepresonance` | DeepResonance |
| `bug` | BUG+1 |
| `ur2` | URType2 |
| `ur4` | URType4 |
| `exocet` | JuniorExocet |
| `jetest`, `je` | JETest (experimental) |
| `template` | Template |
| `bowman` | BowmanBingo |

### Mask & Forge Tools

| Flag | Description |
|---|---|
| `--to-mask PUZZLE` | Convert a puzzle string to its mask (`0` → `0`, nonzero → `X`) |
| `--forge-permute PUZZLE` | Constellation Forge: digit-permutation forge from a unique puzzle. Generates up to 362,880 unique puzzles by relabeling digits 1-9. Accepts bd81, `..X...`, or `00X000` formats |
| `--forge-permute-count N` | Number of permuted puzzles to output (default 10, max 362,880) |
| `--forge-solve MASK` | Forge guaranteed-unique puzzles from a mask, then solve each one |
| `--forge-count N` | Number of forged puzzles to solve (default 5) |
| `--test-mask MASK` | Test a mask: generate 25 puzzles + 25 shuffled variants, report solve rates |
| `--test-mask-count N` | Puzzles per round in `--test-mask` (default 25) |

### Examples

**Solve with rich terminal output:**

```bash
larsdoku "800000000003600000070090200050007000000045700000100030001000068008500010090000400" --detail --rich-output --board
```

**Cascade analysis — find the bottleneck:**

```bash
larsdoku --cascade "980700600700000090006050000400003000007500060000000002009600280008200050000010900"
```

Output:
```
═══ Cascade Analysis ═══
Empty: 58 cells
Bottleneck depth: 1
Cascade placements: 57
Cascade ratio: 1:57 (each bottleneck unlocks ~57 cells)
```

**Quick SIRO predictions for all cells:**

```bash
larsdoku --siro-table "980700600700000090006050000..."
```

**Check if a puzzle has a unique solution:**

```bash
larsdoku --unique "000003020300080009000900300..."
```

**Find 10 solutions of a multi-solution puzzle:**

```bash
larsdoku --solutions 10 "000003020300080009000900300..."
```

**ScandolousExocet — post-solve validated Exocet scan:**

```bash
larsdoku --scandalous-tech "980700600750000040003080070..." --preset larstech
```

**Cell inspector with HYPERSIRO metrics:**

```bash
larsdoku --inspector R6C2 "980700600700000090006050000..."
```

**Batch cascade distribution:**

```bash
larsdoku --cascade --batch 20 "980700600700000090006050000..."
```

**Constellation Forge — generate 362,880 unique puzzles from one:**

```bash
# Generate 10 unique puzzles via digit permutation
larsdoku --forge-permute "000060010000300007000001300007000080020400006100005900003050060800009500040200091"

# Generate 1000 and pipe to file
larsdoku --forge-permute "000060010000300007..." --forge-permute-count 1000 >> puzzles.txt

# Generate ALL 362,880 permutations
larsdoku --forge-permute "000060010000300007..." --forge-permute-count 362880 >> all_362k.txt
```

Every output puzzle is guaranteed unique. The summary goes to stderr so piping stays clean.

**Watch the engine solve step by step:**

```bash
larsdoku "100007090030020008009600500005300900010080002600004000300000010040000007007000300" --steps
```

**Expert-approved techniques only:**

```bash
larsdoku "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........" --preset expert --no-oracle --board
```

---

## larsdoku-research

Oracle-guided technique explorer. **Completely separate from the main solver.** Uses legitimate techniques with an oracle safety net — every individual move is logically valid, but the selection is guided by the answer.

### Usage

```bash
larsdoku-research <puzzle> [options]
```

### Options

| Flag | Description |
|---|---|
| `--super-sus` | Oracle-guided solve: backtrack first, then apply techniques with safety net |
| `--trust SOLUTION` | Use this 81-char solution as the oracle |
| `--trust-solve-to SOLUTION` | Super-sus solve to a specific solution (shortcut for `--super-sus --trust`) |
| `--solution-num N` | Find N solutions, then super-sus solve to solution #N |
| `--detail` | Rich detailed output with colored panels and technique breakdowns |
| `--verbose` | `-v` | Show each step |
| `--board` | `-b` | Print solved board |

### How Super-Sus Works

1. **Backtrack first** — gets the solution upfront
2. **Run techniques** — each makes eliminations and placements
3. **Oracle safety net** — after each technique fires, checks: "did this elimination remove the correct answer?" If yes → undo it and try the next technique
4. **Result** — shows which techniques CAN solve the puzzle when guided by the answer

On **unique puzzles**, the oracle safety net never fires — every valid elimination IS correct. The solve is pure logic.

On **multi-solution puzzles**, the safety net steers the solve toward the chosen solution by rejecting eliminations valid for OTHER solutions.

### Research-Only Techniques

`larsdoku-research` includes two techniques not in the main solver:

- **FPC-Elim** — FPC in elimination mode: trial-place a candidate, propagate, if contradiction → eliminate. Uses oracle to define "contradiction" as disagreement with the trusted solution.
- **FinnedPointingChain** — Gold-filtered finned pointing chain placement.

These exist ONLY in `larsdoku-research`. They never touch the main solver.

### Examples

**Super-sus solve (auto-backtrack):**

```bash
larsdoku-research "980700600700000090006050000..." --super-sus --detail --board
```

**Solve to a specific solution:**

```bash
larsdoku-research "000003020300080009000900300..." --trust-solve-to "179653824365284719428971356..." --board
```

**Find solution #3 and solve to it:**

```bash
larsdoku-research "000003020300080009000900300..." --solution-num 3 --detail --board
```

**Test: can techniques solve a multi-solution puzzle?**

```bash
# Step 1: Find all solutions
larsdoku --solutions 10 "000003020300080009000900300..."

# Step 2: Try solving to each one
larsdoku-research "000003020300080009000900300..." --solution-num 1 --detail --board
larsdoku-research "000003020300080009000900300..." --solution-num 5 --detail --board
larsdoku-research "000003020300080009000900300..." --solution-num 10 --detail --board
```

This reveals which solutions are reachable by technique + oracle, and how many oracle saves each requires. More saves = more sus. Zero saves = pure logic.

---

## larsdoku-bench

### Usage

```bash
larsdoku-bench [options]
```

### Options

| Flag | Short | Description |
|---|---|---|
| `--collection NAME` | `-c` | Which collection: `top1465`, `expert`, `famous`, or `all` |
| `--limit N` | `-l` | Max puzzles per collection (0 = all) |

### Examples

```bash
# Run everything
larsdoku-bench

# Just the Top1465
larsdoku-bench --collection top1465

# Quick smoke test
larsdoku-bench --collection top1465 --limit 50

# Famous 10 only
larsdoku-bench --collection famous
```
