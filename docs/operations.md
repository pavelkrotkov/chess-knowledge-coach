# Hermes operation

The browser and bounded worker are separate processes. Keep all application
data, configuration, logs, backups, and release artifacts inside the
selected project directory.

## Prepare the runtime

From the project root, create private directories and empty logs without
truncating existing logs:

```sh
umask 077
install -d -m 700 .runtime .runtime/data .runtime/logs .runtime/backups \
  .runtime/tmp .runtime/cache .runtime/releases .runtime/units
for name in web worker; do
  file=".runtime/logs/$name.log"
  test ! -L "$file" || exit 1
  test -e "$file" || : > "$file"
  chmod 600 "$file"
done
```

Create `.runtime/config.env` with mode 0600 and systemd-compatible
`KEY=value` entries for `CHESS_DB`, `CHESS_SUBJECT`,
`CHESS_REVIEW_ACTOR`, `CHESS_CORPUS`, `CHESS_TAILSCALE_LOGIN`,
`CHESS_WEB_ORIGIN`, `LICHESS_USERNAME`, and optionally
`LICHESS_API_TOKEN`. `CHESS_DB` is an absolute path to an existing database
under `.runtime/data`; both services use it. The subject and Lichess username
identify the same learner. Use the exact HTTPS origin including port 8448,
without a trailing slash, and the exact allowed Tailscale login. Keep actual
identities and credentials out of the repository, command history, output,
and logs. The reviewed units set the project root and socket path.

Back up an existing database before running code that can migrate it. Check
the installed Stockfish binary and its UCI options; the worker defaults to
`/usr/games/stockfish`. Initialize and import data only with the reviewed
release prepared below, never with a newer development checkout.

## Prepare a reviewed release

Choose an exact reviewed full commit SHA. This command archives that commit,
installs its frozen lock non-editably in `.runtime/releases/<sha>/venv`,
checks installed imports and browser assets with isolated Python, and renders
units in `.runtime/units/<sha>`. It seals the release against accidental
writes but does not activate anything. An incomplete release is retained for
inspection. Installation or verification failures write bounded, sanitized
diagnostics to its private `prepare-error.log`; existing paths are preserved.

```sh
export UV_PROJECT_ENVIRONMENT="$PWD/.venv/env"
export UV_CACHE_DIR="$PWD/.venv/cache/uv"
export XDG_CACHE_HOME="$PWD/.venv/cache"
export TMPDIR="$PWD/.venv/tmp"
uv run --no-sync python -m chess_coach.ops_release --project-root "$PWD" --commit <reviewed-full-sha>
```

The installer disables interpreter downloads and uses project-local caches
and temporary files. The units run the exact release's installed Python with
`-I`, with no mutable release pointer. Verify independently from outside
the source tree:

```sh
cd .runtime
./releases/<reviewed-full-sha>/venv/bin/python -I -B -c 'import chess_coach; print(chess_coach.__file__)'
cd ..
```

The import path must be inside that release's `venv`; its `COMMIT` file
must match the selected SHA.

For a new, absent database only, initialize and import the project-local
puzzle corpus with that same reviewed release:

```sh
release="$PWD/.runtime/releases/<reviewed-full-sha>/venv/bin/python"
"$release" -I -B -m chess_coach.cli --db "$PWD/.runtime/data/coach.sqlite" init-db
"$release" -I -B -m chess_coach.cli --db "$PWD/.runtime/data/coach.sqlite" import-puzzles <project-local-csv> --version <version>
```

Use the imported version for `CHESS_CORPUS`.

## Registration and private access

The next steps write outside the project: unit links under
`~/.config/systemd/user`, user-manager state, and Tailscale Serve state under
`/var/lib/tailscale`. Obtain explicit authorization for those writes before
running them. Linger is already enabled; do not change it.

Inspect existing user unit names and `tailscale serve status --json`. If any
unit name or HTTPS port 8448 route conflicts, stop and resolve the conflict
without replacing it. After authorization, link the five reviewed units
without overwriting existing files, reload the manager, and enable the browser
and both timers:

```sh
unitdir="$PWD/.runtime/units/<reviewed-full-sha>"
mkdir -p "$HOME/.config/systemd/user"
for unit in chess-coach-web.service chess-coach-worker.service chess-coach-worker.timer chess-coach-retry.service chess-coach-retry.timer; do
  ln -s "$unitdir/$unit" "$HOME/.config/systemd/user/$unit"
done
systemctl --user daemon-reload
systemctl --user enable --now chess-coach-web.service chess-coach-worker.timer chess-coach-retry.timer
```

After checking port 8448 is unused and receiving authorization, configure
only the private Serve endpoint from the project root:

```sh
tailscale serve --bg --https=8448 "unix:$PWD/.runtime/web.sock"
```

Do not use Funnel or expose a TCP backend. Confirm the resulting route and
tailnet ACLs, access for the allowed operator, denial for a different identity,
and absence of a direct backend TCP listener. Serve supplies `Host: localhost`
to the Unix backend and the browser requires that exact backend Host and the
exact configured Tailscale login. This is not validation of the original public
Host. For state-changing requests, the browser separately requires the exact
configured public HTTPS Origin and a valid session CSRF token. Missing, `null`,
or incorrect Origins are rejected.

The server returns `Referrer-Policy: same-origin`. The [Fetch Standard](https://fetch.spec.whatwg.org/#origin-header)
allows ordinary same-origin HTTPS form submissions to retain their actual
Origin under this policy; `no-referrer` can cause an `Origin: null` form POST.
The [Referrer Policy specification](https://w3c.github.io/webappsec-referrer-policy/#referrer-policy-same-origin)
withholds referrer information from other origins. Same-origin requests may
include the full page URL as referrer, so keep service logs private.

`X-Forwarded-Host` can be supplied by a caller in this setup; the browser does
not use it to establish identity or origin. Keep the socket directory mode 0700
and its socket mode 0600. Processes with access to that socket are trusted to
supply the identity header, so the service account and directory must remain
private.

If the browser returns 403, first check privately that the request uses the
intended private Serve route and that the allowed login matches the signed-in
Tailscale identity. Check the configured HTTPS origin, including its port,
against the browser address. For a failed state change, reload the page and
retry so the browser obtains a current session and CSRF token; sessions expire
when the server restarts. Browser privacy settings or extensions may also
suppress the Origin; check them privately or try another approved browser. Do
not allow `null` Origins or disable the Origin or CSRF checks. A 403 on a read
can indicate an identity or backend Host mismatch; a 403 on a state change can also indicate an Origin or CSRF
mismatch. Do not print, copy, or share identity headers, credentials, or private
configuration while troubleshooting. Never use a forwarded Host header to
bypass these checks.

## Health, backup, upgrade, and rollback

Use `systemctl --user status chess-coach-web.service
chess-coach-worker.timer chess-coach-retry.timer` and the browser status page to inspect recent
processing, failures, and any server-requested retry deadline. Worker runs are
bounded; the retry timer checks persisted deadlines every 10 seconds and synchronizes only when one is due. It also processes a small local batch of pending owned mate-in-one verifications without contacting Lichess. Synchronization is serialized across both services, and the timer does not immediately restart a failed
run. Logs remain private and project-local. Analysis temporarily spools engine output fields to a private file beside the database and closes it on completion or failure; allow disk space for this bounded-memory staging. Stop the timer, any already-running worker, and the browser; then verify
each is inactive before backup, upgrade, or rollback:

```sh
systemctl --user stop chess-coach-worker.timer chess-coach-worker.service chess-coach-retry.timer chess-coach-retry.service chess-coach-web.service
for unit in chess-coach-worker.timer chess-coach-worker.service chess-coach-retry.timer chess-coach-retry.service chess-coach-web.service; do
  if systemctl --user is-active --quiet "$unit"; then
    printf 'Still active: %s\n' "$unit"
    exit 1
  fi
done
```

Stopping the timer alone does not stop a running oneshot worker. Do not
remove data.

Before an upgrade, stop and verify all five units as above, run `backup-db` to a new path under
`.runtime/backups`, and `restore-db` that backup to a separate new path
under `.runtime/data`; both require `--project-root "$PWD"`. The commands
verify integrity and foreign keys and refuse existing destinations and SQLite
companions. Keep exclusive control of the destination directory. Compare
representative game, provenance, review, training, and schedule records in the
restored database. Copying only a WAL database's main file is insufficient.

Prepare and review new exact-SHA units before changing any links; require
authorization for external links and manager updates. Keep the old release,
units, database, and backup. If older code cannot safely read a newer schema,
restore the prior verified backup to a *new* database path and update private
`CHESS_DB` for both services. Never overwrite the original to force rollback.
After authorization, relink the previously reviewed units, reload and restart,
and verify browser status and logs.

Perform end-to-end acceptance on a backup-derived separate database with an
explicitly labelled release-smoke review actor. Do not review production
evidence or invent candidate evidence or mastery to make the test pass;
insufficient evidence is a valid result.

### Official puzzle snapshots

Install the `zstd` executable on the host. The following operator-only command
streams the official [Lichess puzzle export](https://database.lichess.org/#puzzles)
without credentials. Choose a unique version and set byte, disk reserve, and
time budgets from available capacity; the values below are examples, not a
claim about the current archive size:

```sh
chess-coach acquire-puzzles --project-root "$CHESS_PROJECT_ROOT" --version snapshot-2026-01 \
  --max-archive-bytes 10000000000 --max-csv-bytes 50000000000 \
  --reserve-bytes 10000000000 --seconds 7200 --connect-timeout 10 --read-timeout 30
chess-coach acquisition-status --project-root "$CHESS_PROJECT_ROOT"
```

Progress also appears on the authenticated browser status page; the browser
never starts a download. The command stops on provider backoff, honoring
`Retry-After` (at least one minute), and can be run again with the same version.
Snapshot paths reject existing symlink components to keep reads and writes
inside the selected project. Partial transfers resume only after matching a
strong ETag, exact range and length, and a locally checked partial hash. Without a strong ETag, or after a
mismatching response, the next attempt starts in a new directory. Failed and
partial files remain in the project; ready versions are never overwritten.
The transfer timeout is checked between reads, with each read bounded by the
configured read timeout. Decoding is bounded by the same overall time, decoded
size and disk reserve. It requires successful zstd EOF and valid UTF-8.

The ready `puzzle-snapshots/VERSION/manifest.json` identifies the immutable
CSV, archive and their byte counts and SHA-256 digests. Those hashes are
locally computed, not publisher-authenticated. Archive offsets are not CSV
record offsets; the staging command performs its own decoded-record
checkpoints.

### Stage a downloaded puzzle snapshot

Use a reviewed release and an isolated validation database before touching the
service database. Read `csv_path`, `version`, `csv_sha256`, `archive_sha256`,
and `source_url` from the ready manifest; pass them as `CSV`, `VERSION`,
`CSV_SHA256`, `ARCHIVE_SHA256`, and `SOURCE_URL` respectively. The archive
hash identifies the downloaded source, while the importer verifies the decoded
CSV hash; neither is an independently published checksum. Choose a database
and all output, backups, caches and temporary directories inside the selected
project. Do not overwrite a version or an existing backup.

```sh
chess-coach --db "$VALIDATION_DB" stage-puzzles "$CSV" --project-root "$CHESS_PROJECT_ROOT" \
  --version "$VERSION" --csv-sha256 "$CSV_SHA256" --archive-sha256 "$ARCHIVE_SHA256" \
  --source-url "$SOURCE_URL" --selection-manifest "$SELECTION_MANIFEST" \
  --max-rows 20000 --batch-size 50 \
  --min-free-bytes 16106127360 --enable-wal
chess-coach --db "$VALIDATION_DB" corpus-status
```

The row limit applies to each invocation. Inspect the reported state and
counts, including quarantined records and errors, before proceeding; a
`staging` version is intentionally unavailable for practice. Repeating the
same arguments resumes from a committed decoded-record checkpoint and hashes
the whole CSV again. Only after budgeting storage and runtime for the entire
source should the operator use `--max-rows 0` to process to EOF. Publication
occurs after the entire file is rechecked and reconciled. Do not call a
partially staged file a ready library. A derived subset needs a separate
version and a manifest recording its selection, count, its own hash, and both
parent hashes; its label must say that it is a subset. Pass the validated
selection JSON with `--selection-manifest` on every invocation, including
resumes. The selection is an operator declaration bound to the derived CSV
and archive identities; the importer does not independently reconstruct the
prefix from the parent CSV. The recorded selected count must match accepted
plus quarantined records before publication. Existing imports without selection
metadata remain unknown, not assumed to be full snapshots. For a full source
with no selection manifest, omit that option. For a prefix, the JSON fields are
`policy` (`source_order_prefix`), `fullsource_count`, `selected_count`,
`parent_csv_sha256`, `parent_archive_sha256`, `derived_csv_sha256`, and
`representative` (`false`). Hashes must be lowercase SHA-256; the selected
count cannot exceed the source count.

Test backup and restore to new project-local paths with `backup-db` and
`restore-db`, then verify old unfinished sessions and references on the
restored copy. Check query plans and measured resource use on the actual
snapshot. Before activating a production corpus, back up the service database,
finish and verify publication, and check the authenticated library and practice
flows on the reviewed release. Measure browser responsiveness during import
on the actual deployment; isolated database timings do not establish an HTTP
latency budget. Preserve old corpus versions and the rollback backup.

### Measured initial subset

The prepared October 2026 source snapshot contains 6,157,341 CSV records;
the archive is 307,234,795 bytes and the decoded CSV is 1,139,783,132 bytes.
The initial library is deliberately capped at the first 100,000 source-order
records. This prefix is not random or representative. Its derived CSV is
18,608,905 bytes, has a separate SHA-256 and manifest linking the parent CSV
and archive hashes, and remains separate from the unchanged full snapshot.
The isolated import accepted 100,000 and quarantined zero. It contains 73
themes, including 12,818 forks, 5,998 pins, 13,245 mate-in-two and 50,229
endgame tags. Rating counts were 22,628 below 1000, 32,830 at 1000–1499,
25,832 at 1500–1999, and 18,710 at 2000 or above. Tags describe content;
they do not establish skill evidence.

On Hermes, using 50-row transactions and a 15 GiB free-space reserve, this
isolated run took 355.57 seconds including a checkpoint backup, restore and
resume. The 2,000 batch operations measured 324.73 ms p95 and 5,509.01 ms
max. This duration may include waiting for SQLite locks and is not a direct measurement of lock
hold time; the smaller batch does not guarantee a shorter maximum delay.
The restored copy preserved an unfinished synthetic legacy session. Four
indexed theme/rating keyset probes measured 0.55–6.45 ms p95 over 100
queries each; the query plan used the covering theme index and puzzle key.
The ready database was 101,212,160 bytes after a passive checkpoint, with
5,228,312 WAL bytes before the checkpoint; the checkpoint reported no busy
readers and two frames checkpointed. These are isolated measurements, not
production HTTP or lock-latency guarantees.

The full snapshot is retained for later expansion. Before importing a larger
selection, record its deterministic selection and source hashes, measure its
storage and latency under the actual service workload, and use a new version.
Keep the 15 GiB reserve and old versions until recovery and historical
references have been verified.

### Observed production activation

The reviewed d711 release was activated with schema 20 and the ready
`lichess-20261002-first100000` source-order subset. The prior corpus and
35 existing tables were preserved. Verified backup and restore retained the
selection provenance. An authenticated plan and practice flow was checked,
and synthetic graded practice plus an unfinished legacy session were verified
on a restored copy; no production training writes were made for that test.

The live import took 503.85 seconds with 100,000 accepted records. During the
run, 757 authenticated library requests returned HTTP 200, with 307.87 ms p95
and 987.21 ms maximum observed latency. One connection was refused without a
timing measurement; its cause was not established. Twenty subsequent
readiness requests returned HTTP 200 and a missing identity was denied. An
external private HTTPS plan request also returned HTTP 200.

Measured transaction lock hold, from successful `BEGIN` acquisition through
commit, was 372.916 ms p95 and 3,129.248 ms maximum. An independent empty
writer measured acquisition waits of 229.656 ms p95 and 743.811 ms maximum.
Indexed production theme/rating queries measured 1.551–2.334 ms p95. A passive
checkpoint reported zero busy and 333 of 333 frames checkpointed; free space
remained above the 15 GiB reserve. These observations are not latency or
availability guarantees. The original source snapshot remained unchanged,
conflicting identities and corrupted snapshots were rejected, and staged rows
remained unavailable.

The retained full source can support later expansion. Related retrieval,
unified playable own-game and canonical sessions, and broader alternative
handling remain required in [#142](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/142),
[#140](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/140), and
[#144](https://github.com/pavelkrotkov/chess-knowledge-coach/issues/144).
Source tags describe material and do not establish mastery.

### Exact-runtime validation on GitHub

After the manual **Exact runtime validation** workflow exists on the default
branch, dispatch it with a full lowercase 40-character commit SHA. The commit
must contain `package-lock.json` and `scripts/js-quality.cjs`. The workflow
checks out that exact commit, verifies the pinned Python 3.12.13 executable and
Node 22.23.2, installs its locked dependencies, and runs the full suite with
a maximum of 200 collected cases and an informational coverage report. It
installs Stockfish from the runner's Ubuntu repository, reports its package
version and binary hash, and requires five native engine cases to run without
skips. This hosted run uses
public source and synthetic tests; its engine may differ from Hermes and it
does not replace private deployment or performance checks.
