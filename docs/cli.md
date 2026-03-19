# CLI Reference

Larsdoku installs two commands: `larsdoku` (solver) and `larsdoku-bench` (benchmarks).

## larsdoku

### Basic Usage

```bash
larsdoku <puzzle> [options]
```

### Options

| Flag | Short | Description |
|---|---|---|
| `--board` | `-b` | Print solved board grid |
| `--steps` | `-s` | Show step-by-step solution trace |
| `--detail` | `-d` | Rich round-by-round output with candidates and explanations |
| `--no-oracle` | `-n` | Pure logic only — stop when stalled, no guessing |
| `--level N` | `-l N` | Max technique level (1-7) |
| `--only TECHS` | `-o` | Only use specific techniques (comma-separated) |
| `--exclude TECHS` | `-x` | Exclude specific techniques |
| `--preset NAME` | | Use preset: `expert` or `wsrf` |
| `--cell CELL` | `-c` | Query solution for a specific cell (e.g., R3C5) |
| `--path` | `-p` | Show technique path to `--cell` |
| `--bench N` | | Benchmark N shuffled variants |
| `--json` | `-j` | Output as JSON |
| `--gf2x` | | Enable GF(2) Extended mode |
| `--autotrust` | | Trust backtrack solution for verification (enables DeepResonance) |
| `--serve` | | Launch the web UI (default port 8765) |
| `--port N` | | Port for `--serve` (default: 8765) |
| `--verbose` | `-v` | Verbose output during solve |

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
| `template` | Template |
| `bowman` | BowmanBingo |

### Mask Tools

| Flag | Description |
|---|---|
| `--to-mask PUZZLE` | Convert a puzzle string to its mask (`0` → `0`, nonzero → `X`) |
| `--forge-solve MASK` | Forge guaranteed-unique puzzles from a mask, then solve each one |
| `--forge-count N` | Number of forged puzzles to solve (default 5) |
| `--test-mask MASK` | Test a mask: generate 25 puzzles + 25 shuffled variants, report solve rates |
| `--test-mask-count N` | Puzzles per round in `--test-mask` (default 25) |

### Examples

**Solve Inkala's "World's Hardest" with board output:**

```bash
larsdoku "800000000003600000070090200050007000000045700000100030001000068008500010090000400" --board --no-oracle
```

**Watch the engine solve AI Escargot step by step:**

```bash
larsdoku "100007090030020008009600500005300900010080002600004000300000010040000007007000300" --steps
```

**Detailed trace of Easter Monster with round-by-round candidates:**

```bash
larsdoku "100000002090400050006000700050903000000070000000850040700000600030009080002000001" --detail --board
```

**How does the engine solve cell R5C5?**

```bash
larsdoku "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........" --cell R5C5 --path
```

**Benchmark 250 shuffled variants of Golden Nugget:**

```bash
larsdoku "000000039000010005003005800008009006070020000100400000009008050020000600400700000" --bench 250
```

**See how far L1+L2+GF(2) alone can go:**

```bash
larsdoku "800000000003600000070090200050007000000045700000100030001000068008500010090000400" --level 2 --no-oracle --board
```

**Expert-approved techniques only (no WSRF inventions):**

```bash
larsdoku "4...3.......6..8..........1....5..9..8....6...7.2........1.27..5.3....4.9........" --preset expert --no-oracle --board
```

**JSON output piped to pretty-printer:**

```bash
larsdoku "000000039000010005003005800008009006070020000100400000009008050020000600400700000" --json --no-oracle | python -m json.tool
```

**Extract a mask from any puzzle:**

```bash
larsdoku --to-mask "000004006000201090001070800060000020350000008000000370009080500040302000700100000"
# Output: Mask (23 clues): 00000X00X000X0X0X000X0X0X000X00000X0XX000000X000000XX000X0X0X000X0X0X000X00X00000
```

**Forge 10 guaranteed-unique puzzles from a mask and solve them all:**

```bash
larsdoku --forge-solve "XX0X00X000X00X00X000XX000X00X0X0000X00X0X000X00000X0X00X000X00X000X00X000X00X0XX" --forge-count 10
```

**Test a mask — how many random boards produce unique puzzles?**

```bash
larsdoku --test-mask "XX0X00X000X00X00X000XX000X00X0X0000X00X0X000X00000X0X00X000X00X000X00X000X00X0XX"
```

**Launch the web UI:**

```bash
larsdoku --serve
# Open http://localhost:8765

# Custom port
larsdoku --serve --port 9000
```

The web UI exposes the full Python engine through an interactive board with step-by-step playback, candidate notes, technique breakdown, cell query, and all CLI options (level, preset, no-oracle, autotrust, GF(2)) via a collapsible options panel. Check "Python Engine" to activate it — the JS solver works standalone as a fallback.

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
