# Chess Knowledge Graph / Adaptive Coach

Local-first foundations for turning chess games into reproducible skill evidence and adaptive training. This is deliberately not an engine-review UI: engines and detectors produce versioned facts; inference produces recomputable evidence; mastery and curriculum come later.

## Current vertical slice

- PGN ingestion, including Lichess `%clk` comments
- Lichess export synchronization with optional token authentication and idempotent GameId imports
- Immutable game and position records in SQLite
- Provenance tables for analysis runs and engine outputs
- Stockfish UCI fixed-node/depth analysis persistence
- Evidence records that preserve success, failure, and ambiguity
- Deterministic evidence reports suitable for human validation
- CLI and pytest coverage

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

The Python API can run a scan after ingestion:

```python
from chess_coach.analysis import analyze_game
from chess_coach.db import Database

 db = Database("coach.sqlite")
 db.initialize()
 run_id = analyze_game(db, game_id=1, nodes=20_000)
```

## Design boundaries

- Raw games and positions are immutable inputs; analysis and mapping are versioned.
- Stockfish owns move/evaluation facts. It does not own mastery.
- A centipawn loss is not automatically a skill failure.
- Evidence is opportunity-based and can be ambiguous.
- LLM features, Maia-3, named structures, style, and recommendations are intentionally deferred until evidence reports make chess sense.

## Roadmap / glue work

The GitHub issue tracker contains the implementation issues for the remaining build-order steps, including Lichess API sync, opening/structure datasets, detector validation, puzzle indexing, FSRS training, Maia enrichment, and explanation/publishing adapters.
