# HYPERSIRO

HYPERSIRO extends SIRO from 3 dimensions (row/col/box) to **10 dimensions** — adding band, stack, miniline, cross-band, cross-stack, and unconnected zone metrics. It also introduces **Zone Position Hidden Singles**, a new technique with zero overlap with any existing Sudoku technique.

## The 10 Dimensions

| # | Zone | Cells | Sum | What it measures |
|---|------|-------|-----|-----------------|
| 1 | Row | 9 | 45 | Standard row rivals |
| 2 | Col | 9 | 45 | Standard column rivals |
| 3 | Box | 9 | 45 | Standard box rivals |
| 4 | Band | 27 | 135 | Rivals across 3-row band |
| 5 | Stack | 27 | 135 | Rivals across 3-column stack |
| 6 | Row-ML | 3 | — | Miniline: cells in same box & same row |
| 7 | Col-ML | 3 | — | Miniline: cells in same box & same col |
| 8 | Cross-band | 2 boxes | — | Other boxes in same band |
| 9 | Cross-stack | 2 boxes | — | Other boxes in same stack |
| 10 | Unconnected | 4 boxes | — | Boxes sharing no row or col |

## HYPERSIRO Cascade

Standard SIRO predicts all cells equally. HYPERSIRO orders predictions by **channeling** — how many cross-zone boxes have the digit placed. The most channeled cells get predicted first, and propagation handles the rest.

```python
from wsrf_zone_oracle import ZoneAnalyzer

analyzer = ZoneAnalyzer()
result = analyzer.hypersiro_cascade("980700600...", solution="985732641...")
print(f"Accuracy: {result['accuracy']:.1%}")
```

### Results (50 Hardest Puzzles)

| Method | Accuracy |
|--------|----------|
| Standard SIRO cascade | 41.4% |
| HYPERSIRO (channeling order) | 46.1% |
| HYPERSIRO + Zone Hidden Singles | **57.6%** |

**+16.2 percentage points** over standard SIRO on the world's hardest puzzles.

## Zone Position Hidden Singles

**Discovered by Lars Rocha, March 2026.**

The 9 box positions (TL/TC/TR/ML/MC/MR/BL/BC/BR) form 9 groups of 9 cells each. If a digit appears as a candidate in only ONE cell of its position group — that's a Zone Hidden Single.

### Key Properties

- **Zero overlap** with standard hidden singles (row/col/box)
- **50.5% accuracy** when pinned (row or col rivals ≤ 1)
- **28.3% accuracy** unpinned
- **12.1 per puzzle** on average — lots of signal
- A completely new constraint dimension in Sudoku

### Why It Works

Standard hidden singles find digits unique in a row, column, or box. Zone hidden singles find digits unique across a **positional pattern** — all cells at the same relative position within their boxes. This captures structural relationships that cross row/col/box boundaries.

```python
analyzer = ZoneAnalyzer()
zhs = analyzer.zone_hidden_singles("980700600...", solution="985732641...")

for z in zhs:
    if z['pinned']:
        print(f"R{z['row']+1}C{z['col']+1} d={z['digit']} {z['box_pos']} "
              f"confidence={z['confidence']:.1%}")
```

## Cross-Zone Tension

Each candidate has a **tension** between its zone levels:

- `band_vs_row = band_ratio - row_ratio`
- `stack_vs_col = stack_ratio - col_ratio`

Negative tension means the digit is MORE constrained at the larger scale — the band/stack is channeling it. This correlates with oracle accuracy.

## Closeness to 135

Each band sums to 135, each stack to 135, each row to 45. The residual (target - placed sum) constrains which digits can go where. HYPERSIRO tracks these residuals and uses them as additional prediction signals.

## HTML Integration

The Larsdoku Research HTML (`larsdoku_deploy_hypersiro.html`) provides:

- **TGZ Button** — Toggle Zone highlighting: click a cell, press TGZ, see all cells in the same box-position that share the same Likely #1 prediction
- **HYPERSIRO Cascade Button** — Run the full cascade with channeling + ZHS boost
- **10-zone inspector** — Every candidate shows band/stack rivals, ML confinement, cross-zone coverage, tension vectors, residuals, and band/stack harmonic distances
- **Zone data attributes** — Every cell has `data-band`, `data-stack`, `data-box`, `data-boxpos` for CSS targeting

## The Channeling Signal

Candidates with `band_boxes_placed + stack_boxes_placed >= 2` are **2.2x more likely** to be the oracle (37.5% vs 16.7%). This signal doesn't improve per-cell prediction directly, but it dramatically improves **cascade ordering** — predict the most channeled cells first.

## ML Confinement

When a digit is confined to a single miniline within its box (`row_ml_confined` or `col_ml_confined`), that's a pointing pair signal. This correlates with oracle accuracy at 43.4% (above the 41% baseline).
