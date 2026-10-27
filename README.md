# Chess Knowledge Graph / Adaptive Coach

Local-first foundations for turning chess games into reproducible skill evidence and adaptive training. This is deliberately not an engine-review UI: engines and detectors produce versioned facts; inference produces recomputable evidence; mastery and curriculum come later.

## Current vertical slice

- PGN ingestion, including Lichess `%clk` comments
- Lichess export synchronization with optional token authentication and idempotent GameId imports
- Deterministic atomic structure extraction with versioned episodes
- Immutable game and position records in SQLite
- Provenance tables for analysis runs and engine outputs
- Stockfish UCI fixed-node/depth analysis persistence
- Evidence records that preserve success, failure, and ambiguity
- Deterministic evidence reports suitable for human validation
- CLI and pytest coverage
- Optional Maia-3 and facts-only explanation adapters with separate provenance tables

## Install

The supported development environment is Python 3.11+ with SQLite. On Ubuntu:

Install `uv` first, then let it manage the project environment and lockfile:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates jq sqlite3 python3-dev build-essential zstd stockfish
uv sync --dev
```

`uv run` executes commands in the reproducible uv-managed environment; no manual
activation or `pip install` step is needed.

Ubuntu currently ships Stockfish 17. The pipeline records the engine identity and configuration. For the intended Stockfish 18 deployment, install the upstream compatible POPCNT/generic x64 binary and pass its path to the analysis adapter.

## Quick start

```bash
uv run chess-coach --db coach.sqlite init-db
uv run chess-coach --db coach.sqlite ingest-pgn games.pgn
uv run chess-coach --db coach.sqlite evidence-report
uv run pytest
```

```bash
uv run chess-coach --db coach.sqlite sync-lichess username --max-games 100
# Set LICHESS_API_TOKEN only when authenticating; it is never written to SQLite.
LICHESS_API_TOKEN=... uv run chess-coach --db coach.sqlite sync-lichess username --page-size 100
```

The adapter requests clocks and opening headers, uses bounded exponential-backoff
retries for rate limits and server errors, and pages backward by UTC timestamps.
Game IDs from Lichess are used as stable source IDs, so re-syncing is idempotent.

Maia is optional and can run in a separate environment behind a small JSON
subprocess adapter. Without a configured command, offline mode returns no Maia
prediction and the canonical game/position tables remain unchanged. Explanations
receive serialized facts and evidence only; they are stored separately and
cannot mutate canonical state.

For bulk analysis on newer hardware, copy the SQLite database or use a dedicated
analysis database, run bounded `analyze-game` jobs with explicit nodes/depth,
threads, hash, and MultiPV settings, then merge only the versioned analysis
outputs with `merge_analysis_outputs(target_db, source_db)`. That helper maps
games by `(source, source_id)`, positions by `(game_id, ply)`, remaps run and
position foreign keys, and commits atomically; missing stable games or plies
abort the entire import. Keep the 2010 Mac mini in ingestion/reporting mode
rather than running large engine or Maia batches locally.

The Python API can run a scan after ingestion:

```python
from chess_coach.analysis import analyze_game
from chess_coach.db import Database

 db = Database("coach.sqlite")
 db.initialize()
 run_id = analyze_game(db, game_id=1, nodes=20_000)
```

## Design & decisions

- [docs/adr/ADR.md](docs/adr/ADR.md) — architecture decision records: evidence-based
  mastery (never centipawn-loss mastery), deterministic-first with sandboxed LLM
  adapters, atomic imports/merges, reproducible engine configuration, provenance.
- [kg.md](kg.md) — the original concept: learner model, knowledge graph, learning loop.

## Roadmap / glue work

The GitHub issue tracker contains the implementation issues for the remaining build-order steps, including Lichess API sync, opening/structure datasets, detector validation, puzzle indexing, FSRS training, Maia enrichment, and explanation/publishing adapters.

## Code quality metrics

`uv run python -m scripts.quality --check` uses pinned Radon 6.0.1 to check all
production Python, including operational scripts and the checker. It reports
cyclomatic complexity (CC <= 8) for each callable and maintainability index
(MI > 50) for each module. Nested and async functions, methods, and lambdas are
included. Tests, the virtual environment, and Git internals are not production
code. Missing required source, unreadable files, and parse errors fail either mode.

MI uses Radon `mi_visit(source, multi=False)`: its normalized, clamped 0–100
formula is `100/171 * (171 - 5.2 ln(V) - 0.23 G - 16.2 ln(L) +
50 sin(sqrt(2.46 radians(C))))`, where V is Halstead volume, G is total
Radon complexity, L is logical lines, and C is comment tokens as a percentage
of source lines. When V or L is zero, Radon returns 100. Multiline strings do
not count as comments; ordinary comment tokens, including inline comments, do.
Do not add comments merely to improve the score.

Existing modules exceed the limits. CI and pre-commit use `--report-only` to
expose the baseline without claiming enforcement; it still fails for unreadable
or missing source and analysis errors. Global enforcement and remediation remain
tracked in [issue #29](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/29).
