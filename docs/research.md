# Research Tool

`larsdoku-research` is a **separate program** for exploring what techniques can do when guided by an oracle. It never touches the main solver's code.

## The Question It Answers

*"If I already know the solution, which legitimate Sudoku techniques could have gotten me there?"*

Every individual move in a super-sus solve is logically valid. The oracle just decides which valid moves to keep and which to skip. It's like having the answer key open while doing homework — the work is real, the selection is guided.

## Super-Sus Mode

```bash
larsdoku-research <puzzle> --super-sus --detail --board
```

### How It Works

1. **Backtrack first** — gets the solution upfront
2. **Run ALL techniques** — each makes eliminations and placements
3. **Oracle safety net** — checks each elimination: "does this remove the correct answer?" If yes → undo and try the next technique
4. **Report** — shows which techniques solved it, how many oracle saves occurred

### Oracle Saves

An oracle save means a technique tried to make a valid elimination that would have steered the solve toward a DIFFERENT solution. On unique puzzles, oracle saves = 0 (there's only one solution). On multi-solution puzzles, oracle saves reveal the "sus" — the places where the answer key guided the selection.

## Multi-Solution Puzzles

This is where `larsdoku-research` shines. Main `larsdoku` can't fully solve multi-solution puzzles because pure logic can't determine which solution is "correct" — they're ALL correct.

```bash
# Find all solutions
larsdoku --solutions 10 "000003020300080009000900300..."

# Solve to a specific one
larsdoku-research "000003020300080009000900300..." --trust-solve-to "179653824365284719..." --detail --board

# Or auto-pick solution #3
larsdoku-research "000003020300080009000900300..." --solution-num 3 --detail --board
```

### Testing Technique Legitimacy

The research tool reveals which techniques work differently on multi-solution puzzles:

- **0 oracle saves** → the technique naturally converges. It's legitimate regardless of which solution you target.
- **N oracle saves** → the technique needed the oracle N times. Those N moments are where the answer key steered the solve.

This lets you test: "Is my technique really finding the right answer, or is it accidentally assuming uniqueness?"

## Research-Only Techniques

Two techniques exist ONLY in `larsdoku-research`:

### FPC-Elim

FPC in elimination mode. Trial-places each candidate, propagates L1+L2. If the propagation produces a digit that disagrees with the oracle → eliminate that candidate.

On unique puzzles, "disagrees with oracle" = "Sudoku contradiction." On multi-solution puzzles, it means "leads to a different solution."

### FinnedPointingChain

Finned Pointing Chain with gold-filtered placement. Finds digit patterns where a pointing pair + fin cell force a placement.

## Rich Terminal Output

```bash
larsdoku-research <puzzle> --super-sus --detail --board
```

Uses `rich` for colored panels:

- **Cyan** — L1 techniques (crossHatch, nakedSingle)
- **Green** — FPC, FinnedPointingChain, ForcingChain
- **Red** — DeepResonance, D2B
- **Yellow** — ALS-XZ, ALS-XYWing
- **Magenta** — JuniorExocet, Template, BowmanBingo

Each step shows:
- Technique name with colored highlight
- Cell and placed digit
- Notes before → placed (with strikethrough on eliminated candidates)
- Technique-specific reason
- Oracle save warnings
