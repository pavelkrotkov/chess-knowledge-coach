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

The adapter requests clocks, opening headers, and finished games, using bounded
requests and retries. New-game and new-position counts exclude identical
replays. A conflicting PGN for an existing Lichess game ID is rejected without
changing the stored game.

Sync keeps separate private SQLite progress for recent polling and historical
reconciliation. Recent polling overlaps by one day; a rotating historical sweep
revisits the configured range, so games that finish long after they start can be
found in a later sweep. The next kind of work is persisted so even a one-game
budget gives both queues a turn. The status distinguishes completed bootstrap,
the current recent and history windows, and a saturated window. A saturated one-second window
is left incomplete; increase the game limit and retry. A one-second window with
1,000 or more games cannot be completed automatically. A first --since sets the
earliest creation timestamp for that account in milliseconds, rounded down to
the nearest second; later calls must use the same value or omit it. A bounded
invocation may need to be run again to complete its windows.

Lichess orders exports by game creation time. See the
[export API](https://github.com/lichess-org/api/blob/master/doc/specs/tags/games/api-games-user-username.yaml)
and [API rate-limit guidance](https://lichess.org/page/api-tips). HTTP 429
retries wait at least one minute; retryable responses honor valid Retry-After
seconds or HTTP dates. Errors do not advance the current window.

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

## Engine decision provenance

Each stored position remains the board after its recorded move. Engine analysis
reconstructs the board before that move from the game PGN, verifies it against
the stored position, and records it as decision_fen. The played and best moves
refer to that same board. The score_cp value is from the mover indicated by
score_pov (white or black); mate scores use the stored run configuration
convention (mate_score 100000). An unavailable score or best move is NULL. Older
outputs whose decision and perspective were not recorded retain NULL provenance
and should not be treated as corrected analysis. A failed run commits no partial
outputs. Engine evaluations are not mastery evidence.

## Learner decision context

The Python API exposes per-move context without storing an account identifier
in the source tree:

    import os
    from chess_coach.learner_context import decision_contexts

    for context in decision_contexts(db, game_id=1, learner=os.environ.get("LICHESS_USERNAME")):
        if context["subject"] is not None:
            print({key: context[key] for key in ("game_id", "ply", "mover")})

Only a uniquely matched, case-insensitive learner side receives a subject on
its own moves. Opponent moves and unknown or inconsistent identities have no
subject. The context uses the PGN UTC game-start time when both UTC date and
time are available; otherwise observation time is unknown. Processing time is
separate. A recorded clock is after the move, while the prior clock for the same
side is supplied separately when available. This context does not itself create
or validate skill evidence.

## Versioned detector facts

The Python API provides record_fact_run for immutable detector facts scoped
to a producer and position. Provide deterministic JSON input data and facts as
objects with fact_type and payload. Exact replays return the same run and
fact IDs; a new successful run supersedes only its producer/position scope.
Legacy facts without run provenance retain unknown timestamps and ownership.
The record_fact_run_in_transaction function supports a caller-owned transaction
and never commits it.

Motif and ontology mapping now write producer-scoped runs with links to their
source facts. Repeating an identical run preserves evidence IDs; a new run
supersedes only its own scope and keeps prior reviews attached to prior evidence.
An empty run can replace a scope. Duplicate active fact, subject, skill, and
operation combinations are rejected. Historical records with unproven source
lineage remain visible as unknown. The two existing mappers use the unassigned
subject until learner attribution supplies one.

Mastery reports recompute eligible evidence at access time. Superseding a
mapping or its detector input invalidates affected cached states without
deleting their event history. Callers composing fact and mapping writes can use
the in-transaction mapping primitive in the same transaction as the detector
primitive; callers own commit and rollback.

## Scheduler provenance

Training attempts record the installed FSRS version and actual scheduler
parameters, including learning steps, retention, interval limit, and fuzzing.
Review durations are accepted in integer seconds and converted to milliseconds
for FSRS. Review times must be timezone-aware and cannot precede the previous
review; they are stored in UTC. Existing records without saved scheduler
configuration retain an unknown value.

## Structure and opening history

Structure extraction and opening classification retain immutable generations.
The current results are available in `current_structure_episodes` and
`current_game_openings`; the underlying tables retain prior and legacy rows.
Runs record production time and the detector or classifier version. Opening
runs also identify the imported dataset and fingerprint its contents. A
no-match opening is stored as a current classification with a NULL opening
node and zero confidence. Old rows whose production time and run identity were
never recorded retain NULLs and are not guessed into the current views.

## Database upgrades

Startup applies ordered schema upgrades atomically and records their version in
SQLite `user_version`. Existing observation timestamps are retained. When a
legacy evidence record has no observation timestamp, the value is NULL rather
than a guessed date, and that record is excluded from temporal trend comparisons.
An unsupported newer database version is rejected without modification.

## Database backup and restore

Before a schema upgrade, create a verified online backup without initializing
or migrating the source database. From the project root, choose new paths whose
parent directories already exist:

```bash
uv run chess-coach backup-db coach.sqlite coach-backup.sqlite --project-root "$PWD"
uv run chess-coach restore-db coach-backup.sqlite coach-restored.sqlite --project-root "$PWD"
```

Both paths must be inside the explicitly selected project root. The source is
opened read-only, and SQLite's online backup API captures a consistent copy
including committed WAL data. The copy is checked with `integrity_check` and
`foreign_key_check` before publication; the new file has owner-only permissions.
An existing destination or its SQLite journal, WAL, or shared-memory companion
is never overwritten. Keep exclusive control of the destination directory while
the operation runs so another process cannot create a companion afterward.
Temporary files are created in
the destination directory and cleaned up after completion or a handled failure.
Restoring does not replace the original database or run schema migrations. It
requires a standalone rollback-journal backup, such as one produced by
`backup-db`; use `backup-db` first for a WAL-mode source.

For a WAL database, keep the database and its SQLite-managed sidecars available
to the live SQLite connection; copying the main file alone can omit committed
data. See [SQLite's online backup documentation](https://www.sqlite.org/backup.html).

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

CI and pre-commit enforce these thresholds with `--check`. The optional
`--report-only` mode remains available for diagnosis and still fails on missing,
unreadable, or invalid source. This is an early enforcement checkpoint; final
verification after the remaining release work is tracked in
[issue #29](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/29).

## Daily practice plan

For scheduled copies of the same canonical prompt, planning uses the schedule with
the latest valid actual review; known review times outrank unknown ones, and the
lowest item ID breaks ties. The bounded cross-schedule scan may require a
continuation before a due item can be offered. Missing or malformed scheduled
sources prevent that check and produce an actionable repair diagnostic.

`daily-plan` produces a bounded, read-only plan for a runtime learner and
selected puzzle corpus. It selects supported due items first, then scans puzzles
in rating and ID order. Every offered puzzle is checked for an immediate legal
mate by the expected first learner move; themes alone are not proof. Repeated
prompt positions are included only once in a plan.

```bash
uv run chess-coach --db coach.sqlite daily-plan corpus-v1 --subject learner --limit 10
```

The plan reports cold start, insufficient evidence, supported weakness, or no
supported weakness, along with the eligible supporting evidence IDs once for
all selections. If evidence exceeds the scan limit, it reports an incomplete
evidence scan and infers no weakness; the limit can be raised to at most 1,000.
A mastery score below 0.6 is a transparent planning heuristic, not a calibrated
diagnosis. Unknown or empty corpora, invalid negative ratings, scan limits, and missing
new candidates are explicit. A truncated due scan prevents new items from being
selected until due priority can be resolved. When `next_cursor` is present,
repeat `daily-plan` with the same subject, corpus, limits and `--cursor` value
to continue the same bounded plan; combine the incremental items from each page
until no cursor remains. The cursor retains the original as-of time.
The cursor is local to this database and must be restarted after source data
changes. If a scheduled puzzle's prompt cannot be reconstructed, new selection
stops and identifies the scheduled item to repair or the corpus to restore.
Selecting a plan changes no schedule or evidence; create an item and complete it
using the verified practice flow below. Existing ontology edges describe
containment, not prerequisites.

## Verified puzzle practice

Import a Lichess puzzle CSV with `import-puzzles`, then select a puzzle ID from
`query-puzzles`. Use the same database and corpus version for the session:

```bash
uv run chess-coach --db coach.sqlite import-puzzles puzzles.csv --version corpus-v1
uv run chess-coach --db coach.sqlite query-puzzles --version corpus-v1 --limit 10
uv run chess-coach --db coach.sqlite start-puzzle corpus-v1 puzzle-id attempt-1
uv run chess-coach --db coach.sqlite show-puzzle attempt-1
uv run chess-coach --db coach.sqlite hint-puzzle attempt-1 --event-id hint-1
uv run chess-coach --db coach.sqlite play-puzzle attempt-1 e7e5 --event-id move-1
```

Replace the example puzzle ID and move with one from the selected corpus and
the move you choose. The displayed FEN is after the opponent's setup move.
Moves use UCI notation, including a promotion suffix such as `a7a8q`. A correct
move may be followed by the recorded opponent reply; a legal incorrect move ends
the attempt, while an illegal move leaves it active. A hint reveals the origin
square of the next move and is recorded as assistance. The prompt does not
include the remaining solution.

Choose a new attempt ID for each attempt and a new event ID for each move or
hint. To safely retry a request, reuse its event ID with the same input. The
attempt can be resumed by ID after restarting; its puzzle version, checksum,
and line are snapshotted so reimporting a corpus cannot change an in-progress
attempt.

To connect a terminal move to training, create a puzzle item and provide its ID
and the learner subject when playing:

```bash
uv run chess-coach --db coach.sqlite create-puzzle-training corpus-v1 puzzle-id mate_in_one execute
uv run chess-coach --db coach.sqlite show-puzzle attempt-1 --training-item-id 1
uv run chess-coach --db coach.sqlite play-puzzle attempt-1 c5c8 --event-id move-1 --training-item-id 1 --subject learner
```

Use the ID returned by the create command and a subject supplied at runtime.
The terminal move, completion, and FSRS review commit together. The scheduling
policy uses `good` for an unhinted solve, `hard` for a hinted solve, and `again`
for a failure. Active duration is unknown, rather than inferred from elapsed
wall time. When the training item explicitly requests mate in one and the prompt contains
an immediate mate, the training-aware view says Find mate in one without
revealing moves. An unhinted first-decision checkmate creates unreviewed
`mate_in_one/execute` success evidence. An unhinted legal nonmating move that
ends the explicitly requested task as incorrect creates unreviewed failure
evidence. Hinted and unsupported decisions record a reason instead of guessing
skill evidence.
Evidence remains subject to the ordinary human-review policy. Retrying the same
terminal event returns the stored result; conflicting retries are rejected.
Use `play-puzzle` without training options for a standalone practice attempt.

## Tactical opportunities

The mate-in-one preview checks legal moves on the learner's reconstructed
pre-move position. A played mating move is a success; a move that immediately
stalemates when mate was available is a narrowly defined failure. Other legal
moves remain ambiguous, as does a decision with contradictory engine output.
These are chess observations, not claims about calculation, recognition, or
mastery. Descriptive fork and hanging-piece labels alone do not establish an
opportunity or outcome.

To create an explicit ontology version and inspect a game using a learner
identity supplied at runtime:

```python
import os
from chess_coach.db import Database
from chess_coach.tactical_ontology import seed_tactical_ontology
from chess_coach.tactical_opportunities import record_game_opportunities

db = Database("coach.sqlite")
db.initialize()
seed_tactical_ontology(db, version="tactical-mate-v1")
candidates = record_game_opportunities(
    db,
    game_id=1,
    learner=os.environ.get("LICHESS_USERNAME"),
    ontology_version="tactical-mate-v1",
)
```

The returned candidates include the decision, mating moves, detector and mapper
versions, source-fact IDs, and a reason for the outcome. Detector facts and
scoped evidence mappings are persisted atomically with lineage. New evidence is
unreviewed; an exact replay keeps the same IDs and any existing review. Confidence
1.0 describes the deterministic terminal-board observation, not player ability;
ambiguous observations have confidence 0.0. Unmatched learner identities produce
no learner candidates. Evidence must be reviewed before it can contribute to
mastery, and this rule makes no claim about calculation or recognition.

A synthetic fixture report covering both colors, alternative mates, stalemate,
ambiguous moves, a pinned pseudo-capture, and no opportunity can be inspected
without using private game data:

```bash
uv run python examples/tactical_fixture_report.py
```

## Reviewing evidence

List evidence by stable ID, inspect the decision context and linked facts, then
record a decision with an explicit operator identity:

```bash
uv run chess-coach --db coach.sqlite list-evidence --limit 50
uv run chess-coach --db coach.sqlite inspect-evidence 1
uv run chess-coach --db coach.sqlite review-evidence 1 --decision accept --actor local-operator
uv run chess-coach --db coach.sqlite review-evidence 1 --decision reject --actor local-operator --rationale 'Needs another look'
uv run chess-coach --db coach.sqlite review-evidence 1 --decision revoke --actor local-operator
```

Use your chosen operator label instead of the example. Each action appends a
timestamped event; corrections do not erase earlier decisions. Review state
(unreviewed, accepted, rejected, revoked, legacy accepted, or legacy unknown)
is separate
from mapping lifecycle (active, superseded, or unscoped). A legacy validation
flag has an unknown reviewer and review time; no event is fabricated for it.
That legacy flag remains visible separately after a later review decision.
Rejected and revoked items are excluded from the aggregate evidence report and
cannot contribute to mastery. Review changes invalidate existing mastery state.
The compatibility command `validate-evidence` also requires `--actor`.

## Mastery estimates

`mastery-report --subject learner` recomputes an uncalibrated outcome heuristic
at access time. Current, explicitly accepted, provenance-linked success and
failure evidence must identify an attributed learner decision in a game or a
verified, unhinted practice completion, with a known UTC observation time. Unassigned, ambiguous, unreviewed, rejected, revoked,
superseded, legacy-unproven, future, and expired evidence is excluded. The
report includes exclusion counts and supporting evidence IDs.

A game contributes at most one context, even across moves, producers, and
import routes. Game identity uses the verified starting position, legal moves,
normalized players, and UTC game time, so indistinguishable games are treated
conservatively as one. Practice prompts use the verified position after the
setup move, excluding move counters; repeated prompts use the latest eligible
completion across attempts and corpus versions. A practice prompt matching an
eligible game decision counts only through the game, without claiming an
origin for the practice. At least three independent contexts are required for
a score. Confidence weights
decay with a 90-day half-life over whole UTC days; the horizon is 365 days.
Uncertainty is `1 / (1 + effective weight)`. The 30-day trend is unknown when
there are not both recent and older contexts. A result with insufficient
contexts has no score and marks any prior cached score stale while retaining
its event history. This is a descriptive heuristic, not a calibrated ability
or centipawn-loss measure. Training evidence must be explicitly accepted,
directly linked to a verified completion, and supported by its immutable
session and terminal event; a self-rating alone is not mastery evidence.

## Bounded processing pipeline

`process-pipeline` resumes Lichess synchronization and advances pending games
through complete engine analysis, structure extraction, optional opening
classification, tactical candidate generation, and a fresh mastery report.
The worker never accepts evidence on a person’s behalf. Set `LICHESS_USERNAME`
in the private runtime environment, and set `LICHESS_API_TOKEN` there if the
export requires a token. An explicit username argument is also supported.

```bash
uv run chess-coach --db .venv/coach.sqlite process-pipeline \
  --max-games 10 --max-scan 500 --max-positions 200 \
  --nodes 10000 --seconds-per-position 1 --threads 1 --hash-mb 64 \
  --network-requests 25 --network-retries 1 --network-timeout 20 \
  --network-seconds 120 --network-bytes 8388608 --network-sleep 60
uv run chess-coach --db .venv/coach.sqlite pipeline-status
```

Game and scan limits bound the work selected per invocation. Processing-setting
changes and opening dataset additions restart the bounded game scan, so
completion requires scanning every game under the current inputs; changing only scheduling or network budgets preserves
the scan cursor. Engine nodes and
seconds apply to each position; thread and hash limits apply to each engine.
The request count, aggregate response bytes, elapsed time, individual request
timeout and retry-sleep budget bound the network portion. When the server’s
required retry delay exceeds the remaining budget, synchronization records a
UTC retry deadline and stops rather than retrying early. Later scheduled runs
make no Lichess requests until that deadline; they can still advance local
work. `pipeline-status` exposes the deadline and waiting status. Unrelated
network budget failures do not create a cooldown. Large games receive a
`position_budget_exceeded` status and do not prevent later games from advancing.

To classify openings, supply both `--opening-version` and `--opening-source`
for an imported dataset. Missing or unconfigured opening data is shown as a
skipped stage and does not fabricate a classification. Run status includes
sanitized sync diagnostics, the scan count, and per-game stage codes; use
`pipeline-status` to read persisted timestamps and the last sync/run outcome
without starting work. A `running` status left by an interrupted process is
resolved by the next invocation. The lock is local to the database host.
Run the synchronous worker as a dedicated process on its main thread; its
network deadline uses the process timer and will refuse to replace an active
timer or run inside a request thread.

Completed stage inputs and configuration versions are checkpointed. A retry
reuses a pending generation, while a changed configuration or an externally
superseded output creates a new current generation. Engine outputs and their
completion checkpoint commit together. Untimed or unassigned decisions do not
produce learner tactical candidates. Candidate evidence still requires an
explicit review before it can contribute to mastery.


## Private browser tutor

The browser process reuses the existing evidence review, curriculum, puzzle,
and scheduler services. It requires a pre-existing database and does not run
the background worker. Configure these environment variables in a private
runtime environment (not in the repository):

- `CHESS_PROJECT_ROOT`: selected project folder.
- `CHESS_DB`: existing SQLite database inside that folder.
- `CHESS_WEB_SOCKET`: new Unix socket path inside a user-owned directory with
  mode 0700; the socket is created with mode 0600.
- `CHESS_SUBJECT`, `CHESS_REVIEW_ACTOR`, `CHESS_CORPUS`: the configured
  learner, explicit review actor, and imported puzzle corpus version.
- `CHESS_TAILSCALE_LOGIN`: the single allowed exact Tailscale login.
- `CHESS_WEB_ORIGIN`: the exact externally served HTTPS origin, including
  the port if present, without a trailing slash.

Run `uv run python -m chess_coach.web_server` with those values configured.
Proxy the Unix socket with Tailscale Serve, not a TCP listener or Funnel. Serve
strips incoming spoofed identity headers before supplying its own identity;
the socket directory and its account must remain private because local processes
with socket access are trusted. Requests with missing or mismatched identity
or host are rejected, and state changes require the exact origin and a session
CSRF token. The signing key is process-local, so sessions expire on restart. A private
lifetime lock prevents overlapping browser instances; on Linux a stale owned
socket is reclaimed only if no process has it bound. Unexpected paths are left
untouched.
This command does not configure Tailscale Serve or install a service.
