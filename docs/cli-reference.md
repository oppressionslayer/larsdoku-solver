# CLI Reference

## Usage

```bash
larsdoku [PUZZLE] [OPTIONS]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `PUZZLE` | 81-character puzzle string (0 or . for empty cells) |

## Options

| Option | Description |
|--------|-------------|
| `--steps`, `-s` | Show step-by-step solution trace with elimination events |
| `--board`, `-b` | Show the solved board grid |
| `--level N`, `-l N` | Max technique level (1-7, default: all) |
| `--preset NAME` | Technique preset: `expert`, `larstech`, or `wsrf` |
| `--only TECHS`, `-o` | Only use specific techniques (comma-separated) |
| `--json` | Output results as JSON |
| `--serve [PORT]` | Start web API server (default port 8265) |

## Presets

| Preset | Includes | Top1465 Rate |
|--------|----------|-------------|
| `expert` | Standard Sudoku techniques only (L1-L6, no WSRF) | 99.5% |
| `larstech` | Standard + FPC, GF2, D2B, FPF, FPCE | 100% |
| `wsrf` | Full stack including Deep Resonance | 100% |

## Examples

```bash
# Basic solve
larsdoku "003000600900700010080005020..."

# Expert-approved techniques with step trace
larsdoku "003000600..." --preset expert --steps

# Show solved board
larsdoku "003000600..." --board

# JSON for scripting
larsdoku "003000600..." --json

# Only specific techniques
larsdoku "003000600..." --only "crossHatch,nakedSingle,als"

# Web API
larsdoku --serve 8080
```

## API Endpoint

When running `--serve`:

```
POST /api/solve
Content-Type: application/json

{
  "puzzle": "806090207040705090701000405...",
  "preset": "expert",
  "level": 99
}
```

Response:

```json
{
  "success": true,
  "n_steps": 49,
  "technique_counts": {"crossHatch": 28, "nakedSingle": 15, ...},
  "validated": true,
  "elapsed_ms": 118.3
}
```
