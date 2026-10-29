# Chess Knowledge Graph / Adaptive Coach

Local-first chess coaching foundations: engines and detectors produce versioned facts, evidence is reviewed, and an uncalibrated mastery heuristic and narrow mate-in-one curriculum are available. The broader adaptive coach remains in development.

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
prediction and the canonical game/position tables remain unchanged. The optional
explanation adapter receives serialized facts and evidence and stores text separately. It is not a security sandbox: configure only trusted callables.

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
  mastery (never centipawn-loss mastery), deterministic-first with trusted optional
  explanation adapters, atomic imports/merges, reproducible engine configuration, provenance.
- [kg.md](kg.md) — the original concept: learner model, knowledge graph, learning loop.

## Roadmap / glue work

The next release and its mandatory delivery issues are tracked by [#119](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/119). See the [release contract](docs/adaptive-release-contract.md) for the original-vision audit, coverage, and acceptance scenarios. Run `uv run chess-coach capabilities` or open the private browser’s Capabilities page to see the versioned current coverage.

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

Each new run also stores separately bounded best-line and forced-played-root
searches from the same pre-move board with reconstructed game history. Native
centipawn or mate scores, bounds, optional engine WDL, legal PV and actual work
are recorded without converting score loss into mastery. Limits apply per
search, so analysis can take approximately twice the earlier scan budget.
`uv run chess-coach --db coach.sqlite inspect-decision POSITION_ID` or the
private evidence page shows SAN continuations and run provenance. Legacy runs
show comparison data as unavailable. Automatic deep searches are bounded engine
estimates, not proof of a skill or chess claim.


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

The private Structures page and `structure-history --learner NAME` derive
named observations from positions covered by current atomic episodes. Matcher
version 1.2.0 adds narrow Maróczy-like, Hedgehog-like and Sicilian
Scheveningen-like and Boleslavsky-like skeletons to version 1.1.0 French-like,
Caro-Kann-like and modern Benoni-like skeletons and version 1.0.0 isolated d-file pawn and
Carlsbad matches, for both colors. These geometry labels do not classify the
opening, and can overlap. Use `--matcher-version 1.0.0` or
`--matcher-version 1.1.0`, or the browser version links, to recompute prior
rules over current atomic episodes. Each interval
retains atomic run, detector version, source episode IDs and a source position;
repeated extraction is safe.
Counts describe games and contiguous matching intervals, not playing skill.
Unmatched positions may contain other structures. Typical plans are educational
ideas, not evaluated recommendations. The view examines at most 100 attributable
games, scanning at most 1,000 candidates, and 1,000 covered positions per game; it reports truncation. The
definitions and reference links are displayed in the report; changing matcher
rules requires a new matcher version.

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
`foreign_key_check`, then its logical schema, metadata, rowids, storage types and
values are compared with that same pinned source snapshot before publication. The
new file has owner-only permissions.
An existing destination or its SQLite journal, WAL, or shared-memory companion
is never overwritten. Keep exclusive control of the destination directory while
the operation runs so another process cannot create a companion afterward.
Temporary files are created in
the destination directory and cleaned up after completion or a handled failure.
Restoring does not replace the original database or run schema migrations. It
requires a standalone rollback-journal backup, such as one produced by
`backup-db`; use `backup-db` first for a WAL-mode source.

The comparison supports ordinary rowid and WITHOUT ROWID tables and fails closed
on virtual tables, inaccessible hidden rowids, unsupported schemas, oversized
records, or a comparison error. A metadata-only preflight bounds each aggregate
row, including conservative per-field overhead, before fetching payloads. It
streams rows with a 16 MiB aggregate-row and SQLite value limit,
a 4,096-object schema limit, a 512-column table limit and a 16 MiB total schema
definition limit. The pinned snapshot has a five-minute cooperative deadline;
an operating-system I/O call may exceed it. WAL readers do not normally block
writers but can delay checkpointing and WAL truncation; rollback-journal readers
can block writer commits during the snapshot.

The restore comparison proves equality to the supplied backup, not that the backup
matched some earlier source. It cannot detect common-mode faults or changes after
verification. Independently preserved backups remain important.

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

For JavaScript, install the locked development tools with `npm ci --ignore-scripts`
and run `node scripts/js-quality.cjs`. CI and pre-commit check every JavaScript
file in `src` and `scripts`, including the checker: ESLint enforces CC <= 8
for every function, and TyphonJS/escomplex enforces normalized module MI > 50.
TyphonJS uses per-function mean Halstead effort and logical source lines in its
MI calculation, normalized from 0–171 to 0–100. This JavaScript variant is
different from Radon’s Python formula below. npm audit checks the locked tools;
Dependabot tracks their updates.

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

A separate private decision inspection checks immediate mates and bounded
three-ply forced-mate proofs from current owned analysis. Unknown or exhausted
searches do not establish failure, and this inspection does not update mastery.
A separate bounded worker publishes provisional mate observations and prepared own-game lines; short searches are selective, and the new family remains ineligible for mastery. See [automatic mate observations](docs/mate-automatic-observations.md) and [mate proof inspection](docs/mate-proof-inspection.md) for the boundaries.

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
work. The deployed retry timer checks every 10 seconds, synchronizes only when the deadline is due, and separately processes a small local batch of pending mate-in-one checks, even during analysis; it resumes after restart and serializes synchronization with the regular worker. `pipeline-status` exposes the deadline and waiting status. Unrelated
network budget failures do not create a cooldown. Large games receive a
`position_budget_exceeded` status and do not prevent later games from advancing.

To classify openings, supply both `--opening-version` and `--opening-source`
for an imported dataset. Missing or unconfigured opening data is shown as a
skipped stage and does not fabricate a classification. Run status includes
sanitized sync diagnostics, the scan count, and per-game stage codes; use
`pipeline-status` to read persisted timestamps, all per-game stage details and
the last sync/run outcome without starting work. The private dashboard shows
aggregate stage counts without loading the full detail list. A `running` status
left by an interrupted process is resolved by the next invocation. The lock is local to the database host.
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
strips incoming spoofed identity headers before supplying its own identity.
The Unix server checks that identity against the exact configured login and
requires the backend `Host: localhost` supplied by Serve. It does not validate
the original public Host. State changes require the exact configured public
HTTPS Origin and a session CSRF token; missing, `null`, and incorrect Origins
are rejected. The response uses `Referrer-Policy: same-origin` so ordinary
same-origin HTTPS forms retain their Origin while cross-origin requests carry no
referrer information. Same-origin requests may include the page URL as a
referrer. `X-Forwarded-Host` is caller-spoofable in this setup and is not an
authority for identity or origin. The socket
directory must remain mode 0700 and the socket mode 0600: local processes with
socket access are trusted. The signing key is process-local, so sessions expire
on restart. A private lifetime lock prevents overlapping browser instances; on
Linux a stale owned socket is reclaimed only if no process has it bound.
Unexpected paths are left untouched.
This command does not configure Tailscale Serve or install a service.

For private service installation, backup, upgrade, and recovery, see the
[Hermes operations guide](docs/operations.md).

## Competency coverage

`chess-coach competencies` reports the current versioned learning graph, typed
prerequisites and support relationships, and capability-backed coverage. The
private browser exposes the same report at **Competencies**. Observation-only
geometry or opening classification is not a skill outcome; unsupported names
and puzzle themes are not mastery evidence. Supported mate-in-one execution
links to its implementation and positive, negative and ambiguous tests.

`chess-coach --db coach.sqlite seed-competencies` stores this graph in the
existing ontology tables without changing older versions. Seeding is idempotent
and rejects a conflicting copy of the same version. Relations are directed from
a prerequisite or supporting skill to the skill it helps; `contains` expresses
taxonomy rather than a prerequisite.


## Manual selection for later deep analysis

After the bounded pipeline has completed a game’s current cheap analysis, set
`LICHESS_USERNAME` in the environment and run:

```bash
uv run chess-coach --db coach.sqlite select-deep --game-id 1 --per-game 4 --total 12
uv run chess-coach --db coach.sqlite show-deep-selection 1
uv run chess-coach --db coach.sqlite list-deep-selections
```

Repeat `--game-id` to select multiple games, up to 20 per invocation. The
per-game and total limits cap selected positions; a deterministic control
sample is reserved before nominated score changes, uncertain scores and possible
motifs. A limit of one can therefore select only a control. Coverage shows
eligible, missing, overlapping, capped-out and omitted critical candidates,
plus category targets and allocations. Static motifs are observations, and
engine scores do not create mastery evidence. The private browser’s Deep
selection page shows pending candidates and their immutable selection history.
Selection and deeper execution also run automatically within independent worker
budgets, and manual commands remain available. Currentness is
relative to the completed cheap checkpoint and its recorded engine/configuration
provenance. Selection does not rehash the executable or infer unrun configuration
changes. If source data or its cheap checkpoint changes, a selection becomes
stale. Analysis handoff rejects
source databases containing selection, deep or material history until a provenance-aware
merge is implemented; it never silently drops that history.

## Automatic selective deep analysis

The regular worker rotates through games with current cheap analysis, selects up
to four learner decisions per game, and processes at most four deep decisions in
one invocation. The automatic scan examines at most 100 games and selects at
most four games each time. Unfinished selections remain available on later scans;
changing deep limits creates new job configurations without re-running cheap
analysis. The automatic and manual deep defaults use one thread, 50,000 nodes and two
seconds per search, with up to three best alternatives. The earlier cheap pass defaults to
10,000 nodes and one second per search, with one best line; these settings do
not imply a known difference in accuracy. Best MultiPV shares one work count;
the played move is a separate bounded search. Source or cheap-analysis changes
supersede stale selections. The private status page and `pipeline-status` show
current selected, pending, capped-out, insufficient and unstable counts, scoped
to the configured learner and bounded to 25 current selections (with a truncation indicator).

Use `process-pipeline --help` for limits or `--no-deep` to disable automatic
deep work for an invocation. Independent sync retry retains its own deadline
and lock while deep search runs. See [synthetic proxy benchmark](docs/deep-analysis-proxy-benchmark.md)
for achieved work, timing, disagreements and the limits of this small experiment.
An unavailable external NNUE file hash makes score comparisons incomparable;
file contents are not independently reconciled by this automatic scheduler.

## Bounded deep execution

With `LICHESS_USERNAME` set and a current selection already recorded:

```bash
uv run chess-coach --db coach.sqlite run-deep SELECTION_ID --max-jobs 4
```

Each selected position uses one bounded MultiPV best search and a separate
forced-played search from the original game history. Limits apply to each search;
MultiPV work is shared across alternatives and is not summed. Results and
attempts are stored separately from the cheap pipeline; the decision page shows
both. A separate worker lock permits synchronization to progress while the engine
is thinking. Interrupted jobs resume; insufficient searches can be retried with
`--retry-insufficient`. Current defaults are provisional and do not constitute a
benchmark or a chess proof. Scores and alternatives do not create skill evidence.
Stability comparisons require matching recorded engine, history and score
semantics. If external neural-network identity is not provably identical,
the comparison is marked incomparable rather than guessing.


For licensed direct-prompt PGN and FEN material, see the [public training guide](docs/public-training.md).

## Staged puzzle corpus

The existing `import-puzzles` command preserves legacy behavior and labels those
corpora **legacy_ready**; that label does not claim complete line validation.
For a decoded UTF-8 CSV already inside the project, compute its SHA-256 and run:

```sh
uv run chess-coach --db PROJECT_DB stage-puzzles PROJECT_CSV --project-root PROJECT_ROOT \
  --version SNAPSHOT --csv-sha256 DECODED_SHA256 --max-rows 1000
uv run chess-coach --db PROJECT_DB corpus-status
```

Repeat the same command to resume. `--max-rows 0` processes through EOF in
transactions of at most 100 records by default; `--batch-size` may be 1–500.
The default 10 GiB free-space reserve pauses import before another batch; the
operator may set `--min-free-bytes`. `--enable-wal` explicitly enables SQLite
WAL for a supported local filesystem; it changes the database journal mode.
The importer verifies the decoded digest again before publication. Optional
`--archive-sha256` and `--source-url` record source metadata separately;
this importer does not verify an archive or perform a download. The later
acquisition and activation work remains required.

Only **ready** and **legacy_ready** corpora are available for practice.
A ready version is immutable; a conflicting source identity is rejected.
Malformed CSV stops the import; illegal chess records are quarantined and
reported, and cannot be practiced. Theme names and `unknown` objectives are
content metadata, not skill evidence. The private **Library** page and
`corpus-status` show state, counts, checkpoint and bounded error examples.
For published versions, `query-puzzles --theme THEME` uses a normalized index;
after 1,000 offsets use `--after-rating R --after-id ID` from the last row.

A 20,000-row synthetic Hermes fixture using local WAL and 100-row batches
measured 22.16 seconds import, 0.37 ms p95 database reads, 28.34 ms p95
concurrent training writes, 141.5 ms p95 batch transactions (826.63 ms max),
and 4.46 ms p95 indexed theme queries. This is a fixture measurement, not a
full-corpus or browser-response guarantee; the real corpus and disk budget
must be measured during #138.

### Opening repertoire

The bundled opening names are the five ECO TSV files from the
[Lichess chess-openings dataset](https://github.com/lichess-org/chess-openings/tree/e76b8b4ec5c8aeeba41dac6caf4a60b938f652db),
released under CC0. The snapshot is pinned to commit
`e76b8b4ec5c8aeeba41dac6caf4a60b938f652db`; import verifies the SHA-256 of
each source file before atomically adding its positions and edges:

```bash
uv run chess-coach --db PATH import-lichess-openings
```

The bounded `process-pipeline` command defaults to this dataset and reports it
missing until imported. It reclassifies affected games when dataset contents
change. Explicit `--opening-version` and `--opening-source` select another
imported dataset. The private browser's Repertoire page and `repertoire
--learner NAME` report up to 100 attributable games in 1,000 candidates.
They expose unclassified, unknown, stale and truncated coverage; positions
merge transpositions while played lines remain separate. Outcomes and named
structures describe observations, not mastery or opening quality. Accepted
active failure evidence appearing in at least two games is linked without an
opportunity denominator; the fuller recurrence analysis remains future work.

### Descriptive choice profile

`chess-coach --db PATH style-choices --learner NAME` and the private Choice
profile page report selected learner decisions using current completed deep
MultiPV results. Only the actual played root present in that same search and
similarly evaluated alternatives contribute. This is a selected and biased
sample, not a personality, mastery, or playing-strength assessment. Results
include selection/alternative coverage, reasons for exclusion, source run and
attempt identity, game outcomes separately, and strata for color, ratings,
clock/time control, material phase, opening, structure and familiarity.
Indistinguishable game records are conservatively collapsed before counting games;
identical games with missing dates can therefore be undercounted. Familiarity is
unknown because game-start timestamps do not establish when a position occurred.
The count of earlier-started games eventually containing the same position is
a noncausal sample proxy: games can overlap and the position may have been
reached later. It is unknown when timestamps or sample history are incomplete.
The two-period comparison groups games by start time; overlapping games mean it
does not establish decision-time order.

Method `style-choices-v2` compares exact centipawn scores within 50 cp at
minimum depth four and replays four legal PV plies per choice. It uses conventional
1/3/3/5/9 material units and requires a one-pawn material difference opposed by
three distinct enemy-half squares attacked by non-pawn, non-king pieces; the
attack map includes pinned pieces and is not legal mobility or initiative.
Simplification requires a two-piece difference in total non-pawn, non-king
material. Multiple alternatives with conflicting directions are ambiguous.
These are provisional geometric proxies and projections, not calibrated chess
judgments; a sample direction requires five opportunities across three games.
Game outcomes and same-search score gaps are shown separately and cannot prove
that a choice caused the result. Missing or incomplete comparisons never become
preference evidence. Other style dimensions remain planned.

## Provisional material observations

The automatic worker separately scans up to 40 recorded positions and verifies
at most four new learner decisions per invocation. It reuses only the current
cheap checkpoint or individually verified lines from a current owned deep
attempt and checks those inputs again before committing. An incomplete deep
attempt can support only its independently valid played line; it is never
combined with a cheap best line. Identical active observations replay without replacing
reviews; changed source or analysis generations create new lineage. Use
`process-pipeline --help` to set those bounds or `--no-material` to disable the
pass for one invocation. Engine search is not repeated by this detector.

The current family describes limited non-pawn captures and immediate material
protection, using legal recaptures on one square and short recorded engine lines.
It cannot prove an opportunity is safe against every forcing move or later
compensation. Checking captures are used only when every legal immediate evasion passes a
bounded material check; capture version 1.1.0 can replay a checking reply in
the played line when it legally resolves within eight plies; ordinary played
lines retain their four-ply comparison. Checking played alternatives and
unresolved checks, en passant, promotion, direct
pawn-capture claims, pins, unclear exchanges and conflicting lines remain ambiguous
or outside coverage. A pawn can protect a piece by capturing an unrecapturable
attacker. A score difference only vetoes a potentially misleading failure; it
never creates an observation on its own. The private evidence page displays
SAN lines, source context and the boundary. Outcomes do not imply recognition
or intent, and mappings start unreviewed. Independently validated protection
version 1.0.0 and capture version 1.1.0 can qualify for mastery only after review
and all existing context and currentness checks. Current exercise candidates
show their actual review state. Other versions remain ineligible; see the
[material validation](docs/material-observation-validation.md) limits.

### Direct-source practice sessions

The private Library can start sessions from ready corpus and licensed public
collections. Corpus records retain their original setup convention; licensed
tasks begin at their direct prompt. Sessions snapshot their source and explicit
lines, preserve the learner orientation, and resume with idempotent move and
hint events. A legal move outside the supplied lines is marked as needing
verification, not incorrect. A completed line is not automatically a verified
objective; explicitly validated checkmate is the currently verified case.
Own-game material practice requires a current witness and independent validation of the
detector family. Protection version 1.0.0 and capture version 1.1.0 have scoped
validation. Unreviewed observations are provisional, and rejected
or revoked observations cannot be used.
The library's bounded material preview reuses reconstructed history only within
one read-only snapshot, retaining at most four games and the requested decisions
from the bounded candidate scan. Currentness is checked against that snapshot;
a concurrent commit can become visible to the next request. When called inside
an existing transaction, the preview uses that transaction's snapshot and does
not end it. The cache is discarded after each preview, and session admission
and subsequent actions independently recheck source, ownership, version and
review. Detector and mapping fingerprints and publication are unchanged.
Its bounded first-move line does not establish a complete forced objective. Sessions are
rechecked against their source and review when resumed or played. These sessions do not
write mastery evidence or FSRS reviews. General objective-aware grading remains separate work.

In browser practice, choose squares with a mouse or keyboard, or enter a move in
chess notation or coordinates. A text-only form works without JavaScript. The
history controls show positions already played without changing the attempt.
Hint and reveal are explicit actions and are recorded as hints; a revealed line
is one supplied continuation, not proof that other legal moves fail.

## Provisional pin observations

The pin workers inspect current learner decisions using reconstructed game history
and independent rotating cursors. Detector and mapper version 1.0.1 reject repeated,
fifty-move-rule or terminal roots before the tested move. Version 1.0.0 facts and
reviews remain historical and cannot support a current claim. A pin is descriptive
geometry until a bounded consequence is verified. The execute path considers newly created slider pins to
a king or more valuable piece; it does not score a position where the same pin
already existed or the pinned or rear piece could already be legally captured.
Every legal immediate reply must admit a verified target capture followed by all
immediate replies, or an immediate checkmate. Unresolved checks, recaptures,
promotions, en passant, repetitions, and compensation outside the proof remain
unresolved rather than inferred from a single engine line. Scans cap legal moves
at 64, pin candidates at 16 and immediate replies at 64.

Prevention includes moving an already relatively pinned piece off the line, or
sliding an absolutely pinned piece along its pin. A verified capture of the exposed
or pinned piece and an independently verified legal capture of the pinner supply
the compared consequences. Either of multiple qualifying captures can be observed. The result addresses those tested lines, not overall safety or
the best move. The separate created-pin defense scan uses bounded alternatives;
checks, unresolved exchanges, alternative compensation and unexamined branches
remain ambiguous. Review displays the linked current source and proof; observations
are provisional and all pin mastery remains closed pending independent held-out
qualification. No general pin practice grading is implied.

The recurrence report can filter each pin kind by execute or prevent, subject to
its normal sampling limits. It checks the current source marker without replaying
the proof for each count. A grounded lesson separately rechecks the current source,
then displays legally replayed proof or unresolved-geometry lines, with practical
questions that distinguish the recorded move from tested alternatives. It does not
establish overall safety, compensation, intent or mastery.

## Owned immediate-mate defense verification

Current owned back-rank prevention observations can offer a one-move objective to prevent every legal immediate opposing checkmate. A source-proven example is checked against this exact goal, and other legal answers are processed by the existing bounded local worker with original game history. Any legal mating reply refutes the objective, including mates unrelated to the back rank; an exhaustive absence of mating replies verifies the defense. Draw or history uncertainty, terminal positions without checkmate, timeouts and incomplete scans stay ungraded. This provisional result does not establish overall safety, a win, mastery or scheduling progress.

## Owned mate-within-two alternative verification

Current owned short-mate observations can offer an explicitly announced mate-within-two objective. One supplied root is shown through its legal defensive branches; an unlisted legal root is queued for the existing local verification worker. The worker uses original game history and a bounded three-ply search, checking every legal defense and retaining a mating witness for each. A proved alternative remains playable against a stored legal defense; only a played checkmate completes the objective. A definitive refutation is incorrect for this horizon, while exhausted node or time limits and unavailable history remain ungraded. Current ownership, source version and review are rechecked before results and continuation. Hints and reveals remain distinct, and this provisional practice does not update mastery or scheduling.

## Provisional discovered-attack execution

A bounded rotating worker inspects current owned decisions and records one scoped
observation per decision. It checks the vacating piece and the newly exposed
bishop, rook or queen line, and identifies double checks from the legal resulting
position. A supported witness is either immediate mate with the revealed slider checking, or a material gain of at
least three pawns: every legal immediate defense must leave the exposed slider a
legal target capture, with bounded immediate replies. Captures by the vacating
piece can be included. Draw claims, repetition, terminal positions, unsupported
counterplay and insufficient source lines are excluded or ambiguous. A missed
immediate mate can be a failure; other alternatives are unresolved. The worker
reports scan limits, ambiguous observations and unavailable decisions.

Evidence and source-linked recurrence lessons preserve the tested best and
played roots and a legal witness; multiple proved lines share one decision
observation. Current owned examples can be verified and practiced as prepared
lines; unlisted legal moves need verification. These observations do not establish
intent, ability or mastery. Independent held-out validation and an explicit policy
are required before mastery eligibility. Prevention is a separate required slice.
## Owned mate-in-one alternative verification

The private library can offer a separate, explicitly labeled mate-in-one task
from a current owned mate source. It retains one prepared example; a different
legal move is recorded without changing the original event response and is
queued for bounded verification. The worker reconstructs the original owned
game (at most 1,000 decisions and 1,000,000 PGN bytes) and accepted session
history, checks source and review currentness before
and after verification, and appends a result. The existing retry service runs bounded subject-owned checks even when no sync
retry is due; it does not contact Lichess for this verification. A legal checkmate is correct;
a legal non-mate is incorrect only for this announced one-move objective.
Insufficient history, stale sources, timeouts and cancellation remain unresolved.
Hints and reveals remain distinct, and no verification updates mastery or FSRS.
Existing generic checkmate tasks are unchanged; standalone compositions and
other objectives do not use this verification policy.

## Provisional fork observations

The automatic worker scans a separate rotating bounded set of decisions, using
the material scan and decision limits. It uses reconstructed boards and the
current owned deep result when available, otherwise the current cheap source.
The candidate is the played move or current engine best root, not an exhaustive
search of all legal moves; a missing best source remains ambiguous. A supported
noncapturing fork attacks at least two valuable targets, then tests
every legal immediate defense and a legal unrecapturable target capture, bounded
by 64 replies and the material verifier. Subsequent tactics and compensation are
not exhaustively proven. A missed fork additionally requires legal source lines,
a concrete material comparison and a score veto; a score gap alone never
creates an outcome. Capturing fork moves, mate-only consequences, promotions,
recaptures, unresolved checks, sacrifices and counterplay are outside scope or
ambiguous. Evidence starts unreviewed. Independently qualified version 1.0.1
pawn and knight noncapturing execute successes and failures may contribute to
mastery only after explicit review and current source checks. Other game-derived
fork evidence remains readable as history but is not mastery-eligible. Fork
exercise access remains closed. The browser shows source
currentness and a representative legal line; stale evidence is historical.

The initial development smoke checks used synthetic mirrored positions with
current owned-deep Stockfish sources. Both executed knight-fork cases and both
pawn-move missed-fork cases produced bounded observations. Two king-move
alternatives remained ambiguous because their forced played continuations contained
only the root move. These examples are not independent validation or an accuracy
estimate; other checks, defended targets, counterplay and insufficient lines can
remain ambiguous. The worker reports its scan, decision caps and unavailable inputs.


## Provisional fork-defense observations

A separate bounded worker scans reconstructed learner decisions with its own
cursor and the material scan and decision limits. It may inspect a stackless
opponent-to-move position only as a positional candidate filter; it does not
insert a null move or make a historical claim from that position. An existing
threat is reported only when a legal alternative learner move retains it and the
fork has a bounded proof using the original game history. A newly exposed fork
may be reported only from a recorded engine continuation rooted at the legal
played move, with its concrete material consequence and a verified alternative.
The engine continuation is hypothetical; it does not claim the opponent actually
played the fork or intended it. Equivalent quiet defenses can
be successes. All legal in-scope immediate opponent fork candidates are checked
within caps of 128 legal moves and 16 fork candidates per scan. The legal anchor
search considers at most 64 learner moves and 32 fork proofs; exhausted anchor
budgets are labeled. Direct material threats, unresolved candidates, checks,
capturing defenses, promotions, counterplay, missing lines, draw or repetition
boundaries and exhausted budgets are ambiguous or excluded. A quiet alternative's
recorded continuation may include a check only when its legal reply resolves it. Score gaps only veto
an otherwise supported failure. The private evidence page identifies the actual
source and distinguishes a legal counterfactual from the played line. Version
1.0.0 success and failure observations for noncapturing knight fork threats may
contribute to mastery after explicit review and current source checks. Other
fork-defense evidence remains visible but ineligible; fork exercise access
remains closed. Existing fork execution and material policies are separate.

## Related capture practice

From a decision with a current learner-owned material-capture failure, the private
browser offers **Practice this capture pattern**. The matching operation is an
immediate, bounded capture of non-pawn material in the supplied legal line;
other material, fork, mate and endgame operations remain outside this slice.
Unreviewed source observations are provisional, and rejection, revocation or
source changes invalidate previews and cued sessions. A transfer attempt keeps
its originating evidence, source fingerprint, review event, matching version
and pattern-cued status in immutable session provenance; it does not itself
create learning evidence.

The selected ready corpus is searched using its theme/rating index: up to 100
entries from each of five content-rating buckets, plus up to 100 tasks from
each of the first 100 public collections and 500 public tasks total. Only the
post-setup Lichess learner position and the replayed legal supplied line are
compared. Matching roles and capture geometry, material, phase, available
opening labels and content rating/deviation rank the results. This bounded pool
is not an exhaustive search; a declared source-order prefix is not
representative. Known own-game positions, known source games, and previous
practice prompts are excluded conservatively. Legacy puzzle attempts have no
subject, so all are treated as familiar. If the bounded familiarity scan is
exceeded, transfer is unavailable rather than claiming unfamiliarity.

A source-game rating, if recorded, is a rough content-filter reference and is
not a calibrated puzzle skill estimate. With no rating, the explicit 600–2200
content range and its 1400 sorting midpoint are a cold-start convention.
Matched supplied lines do not establish that every other legal move loses.

The same preview and guarded start are available through the CLI (replace the
uppercase placeholders with locally available values):

```bash
uv run chess-coach --db PROJECT_DB related-captures --subject LEARNER --position POSITION_ID --corpus CORPUS_VERSION
uv run chess-coach --db PROJECT_DB start-related-capture --subject LEARNER --position POSITION_ID --corpus CORPUS_VERSION --attempt ATTEMPT_ID --reference OPAQUE_REFERENCE
```

The preview returns an opaque reference per example and an optional cursor;
pass `--cursor CURSOR` to continue. References and cursors must be regenerated
when the source, review, corpus, public collections, familiarity or baseline
changes. `show-unified`, `move-unified`, and `hint-unified` use the existing
legal session and reveal paths. Other operation-specific transfer adapters
remain required release work.


### Recurring-pattern candidates

`chess-coach --db PATH recurrence --learner NAME` and the private **Recurring
patterns** page compare the previous and current 30-day game-start windows.
Supply timezone-aware `--compare-start`, `--start`, and `--end` values to choose
other adjacent, half-open windows. The browser fields accept the same ISO 8601
values. To page older records, select both `--skill` and `--operation`, then pass
the returned `--cursor` with the same learner, database and explicit windows.
The browser offers next, previous and reset links. Pages use live data and are
partial; changes between requests can affect them, and independent games should
not be summed across pages. Page history is capped at 100 continuations.
Game-start dates do not establish the order of decisions in overlapping
games. Unknown game dates cannot be placed in a period.

The report reads at most 300 newest mapping records for each listed skill and
operation, then reconstructs at most 20 evidence-bearing games in fixed skill
order, newest evidence first. Raw active mapping counts are a separate,
non-deduplicated and unverified cohort; they are not a denominator for the
inspected examples. The game analysis-stage counts sample the 100 most recent
attributable games among 1,000 game records and are not the candidate cohort.
Limits and exclusions are displayed. Candidate counts represent detector-selected
positions, not every opportunity in a game; an unprocessed or inconclusive
position is never assumed to be a non-opportunity. Import aliases are collapsed
when their independently replayed game identity and decision match. Game-start
metadata may be unavailable, as may exact clock, rating and opening familiarity.
Familiarity remains unavailable rather than using later games as prior knowledge.

Material source markers are compared against the same consumed game and analysis
rows as `material_source_marker`, sharing the game portion within each report;
fork-family markers are checked when present. Matching markers establish input
identity, not a fresh detector proof. Other family currentness is unverified;
a source can have changed since its recorded observation. All counts are
provisional descriptive candidates, not claims of confirmed weakness or mastery.
Rejected, revoked and known-stale evidence is excluded. The linked individual
evidence page performs its existing deeper source checks. No review, training,
or mastery state is created by this report. Practice/game progress remains
separate release work; bounded source-linked lessons are described below.

## Provisional pawn-structure lessons

The private decision page and `inspect-decision` show attributable isolated and
backward pawn geometry, plans and counterplans when a current decision source is
available. Typical plans are ideas, not automatic recommendations. The worker
uses its own rotating cursor and the material scan and decision limits. It checks
current source fingerprints and immutable fact/mapping lineage before treating a
position as a replay; current and opponent positions consume scan budget but not
decision attempts. New, stale or unavailable decisions consume the decision
budget. A truncated scan reports coverage as unknown and partial; a known pending
decision is not skipped when the attempt budget is exhausted. It writes versioned descriptive facts and unreviewed,
always ambiguous mappings, preserving prior reviews on supersession.

When a pawn geometrically attacks the square of a friendly non-pawn piece,
the lesson checks immediate legal captures of that piece after each available
legal recorded root, verifies any legal pawn recapture, and can compare their
bounded exchanges. A pinned pawn may have no legal recapture. This is a concrete local consequence, not proof
of overall compensation or of why the player chose a move.

A legally replayed best or played continuation may show a pawn capture and a
bounded target-square exchange. The immediate comparison examines legal
captures of the same pawn after a recorded root move, at most the existing
exchange checker's 64 nodes and six plies. Checks, en passant, repetition,
terminal positions, exhausted exchange bounds and unsupported captures remain
unknown. A continuation is one possibility, not a forced loss or proof of a
positional cause; activity, compensation, other plans and later tactics are not
resolved. A legal alternative and a favorable immediate exchange do not prove
it is the best plan. No outcome or mastery is inferred from a structure label,
engine score or this bounded observation. This family remains ineligible for
mastery even if a human accepts the descriptive mapping. See
[qualification status](docs/pawn-structure-validation.md). Objective-aware
practice and related training remain part of issues #141, #142 and #144.
## Source-linked coaching lessons

The private recurring-pattern report builds provisional coaching from rechecked,
learner-owned sources in its bounded sample. It selects up to three independent
games from at most ten candidate game identities per group; sources that no
longer pass their own currentness and mapping checks are skipped. Each displayed
continuation is replayed from the reconstructed decision board and must use
canonical legal SAN. Missing or stale sources leave a diagnostic cue rather than
an invented example. A candidate's review status is shown; unreviewed evidence
remains unreviewed. Counts are partial samples, not rates or diagnoses.

Pawn-structure observations can also be grouped as descriptive, always-ambiguous
contexts. Repeated structures are not repeated mistakes or evidence of mastery;
plans and counterplans are ideas, not conclusions about overall advantage.

A lesson separates observed source facts, a possible mechanism to investigate,
a diagnostic question, a habit and practice links. The source proofs are bounded:
later counterplay, compensation and overall safety may remain unknown. The
browser's explicit save action appends a lesson version; history remains a
snapshot even if its source later changes. Saving does not create reviews,
training attempts or mastery evidence.

The Python `lesson_generator.generate` API can optionally call a trusted
injected generator. The generator receives the deterministic lesson and may
return only a JSON permutation of its example indices. Any other output or
provider exception falls back to deterministic order. A validated response is
recorded by the existing `enrichment.explain_position` adapter with model,
prompt version and input provenance. Only configure a callable you trust; it is not a sandbox, and
no external generator is enabled by default. Call it outside a transaction;
otherwise it falls back to avoid committing unrelated caller work.


## Provisional rook-file plans

The worker uses a separate rotating cursor and the existing material position and
decision budgets to inspect learner-owned decisions. It requires distinct legal
recorded best and played continuations, and at least one rook move onto a file
that is open or half-open in the source position. It lists that rook's legal
entry moves into the enemy half, and checks immediate opponent captures after
each entry and each recorded root. The two roots also report their rooks’
geometric enemy-half attack squares, including occupied squares and pinned rooks;
these are not legal moves or recaptures. Each target-square exchange uses at most 64
nodes and six plies; checks, terminal or repetition boundaries, en passant and
unsupported or exhausted exchanges remain unresolved. A pinned attacker is
only counted when its capture is legal. One recorded continuation or a local
exchange is not a forced result or proof of overall safety, compensation,
advantage, intent or preference. Positions without the required source lines
are not graded; the worker reports no-match-or-unsupported, unavailable and capped coverage.

Facts and mappings retain their source, producer version and immutable history.
Currentness checks source and output fingerprints without repeating the chess
inference. The private decision and recurrence lessons show the source, conditional plans,
counterplans, legal alternatives, capture checks and review status. The plan
names the recorded move and, where verified, the opponent capture and its bounded
exchange; an inconclusive capture check is explicitly unsupported. Recurring
observations are descriptive, not repeated mistakes. Version 1.1.0 mappings are
always ambiguous and never mastery-eligible, even when accepted. An independent held-out review of version 1.0.0 covered two positive, two
negative and two ambiguous cases and reported zero false factual claims; it
identified missing position-specific plans and did not qualify mastery. Version
1.1.0 has not yet received independent held-out review. Before opening mastery,
a separate held-out review and documented decision are required. See the
[version 1.0.0 review](https://github.com/pavelkrotkov/chess-knowledge-coach/pull/218#pullrequestreview-5700914014).

## King-safety observations

The bounded material worker also inspects current attributable decisions where the mover’s king zone, shelter pawns or geometric attacks change. The zone consists of the king’s adjacent files, one and two ranks ahead. Attacks are geometric, including attacks by pinned pieces; they are not legal threats. The worker checks the played move and at most eight legal alternatives, recording coverage and unresolved cases, immediate legal checks, mates, captures and promotions, and king moves after a specific legal opponent reply. The displayed alternative minimizes immediate mate and check counts among the completed sampled moves; it is not a best-move recommendation. Source continuations are legal possibilities, not forced lines. Captures and checks can provide counterplay, but overall compensation and later safety are not established. A shelter change does not prove a mistake.

Draw-claim, repeated-root and terminal histories and unsupported bounds are reported as unavailable rather than classified. Observations remain ambiguous and ineligible for mastery even if accepted for review. Before changing that gate, independently qualify a held-out positive, negative and ambiguous fixture set, report its counts and false claims, and document the validation decision. The current implementation has not passed that qualification. Recurrence and decision lessons retain source links and review state; a bounded scan may require another worker run.

## Lesson diagnostic probes

Saved fork, mate and pawn-ending lessons can offer short, source-linked probes
when their cited proof supports the question. Fork and mate tasks ask about a
checked threat; pawn-ending tasks ask for a result-preserving choice. The
lesson has already shown the position or pattern, so each task is marked cued
and familiar. A single response cannot establish the cause of a game move,
attention, calculation, or mastery.

A task stores its accepted answers and proof provenance privately. The prompt
does not expose those answers; a reveal is recorded as assistance. Answers not
covered by the bounded proof stay ungraded. Answer, elapsed wall time since
start, hints, reveals and outcome are retained independently from move practice.
Reusing an event ID with the same input returns the original result; conflicting
retries are rejected. The learner and cited lesson source are rechecked before
starting or recording an event, and rejected, revoked, or changed sources
cannot be resumed. Probe results do not change reviews, FSRS, or mastery.

## Related fork execution practice

A current subject-owned pawn or knight fork execution observation can lead from
its evidence or grounded lesson to unfamiliar related practice. The exact
selected evidence must retain its active producer, mapper version and scope,
source fact and latest accepted or unreviewed review status. A successful fork
and a missed fork are labeled separately; neither is treated as mastery. The
existing capture-transfer path and its historical session bindings remain
unchanged. Related material-protection practice is not yet supported.

Candidates come from a bounded indexed `fork` theme pool and licensed public
collections. The theme is only a search hint. After the corpus setup move, the
complete supplied line is replayed; the learner must create a legal pawn or
knight fork immediately and the same piece must capture an original fork target
on the next learner move. Target piece roles, relative geometry, material,
phase, opening context and content difficulty determine ranking. Candidate
forks later in the line, unresolved en-passant states and other fork operations
are outside this slice. A supplied example line does not prove the move wins
against every defense. Familiar positions and games are excluded under the
same rules and limits as capture transfer, and source/version/review changes
invalidate the opaque reference and the resulting cued session.

```bash
uv run chess-coach --db PROJECT_DB related-forks --subject LEARNER --evidence EVIDENCE_ID --corpus CORPUS_VERSION
uv run chess-coach --db PROJECT_DB start-related-fork --subject LEARNER --evidence EVIDENCE_ID --corpus CORPUS_VERSION --attempt ATTEMPT_ID --reference OPAQUE_REFERENCE
```

Use `--cursor CURSOR` to continue a preview. The source observation, rank
version and operation are saved in immutable unified-session provenance as
pattern-cued practice. For a public task with multiple supplied lines, the
session retains only lines that match the fork; other legal choices need
verification. The source line digest, selected indices and filter version are
rechecked on resume. Existing session moves and reveal accounting apply;
completion does not create skill evidence or verify unlisted alternatives.
