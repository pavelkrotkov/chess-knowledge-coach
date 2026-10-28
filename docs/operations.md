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
without replacing it. After authorization, link the three reviewed units
without overwriting existing files, reload the manager, and enable the browser
and worker timer:

```sh
unitdir="$PWD/.runtime/units/<reviewed-full-sha>"
mkdir -p "$HOME/.config/systemd/user"
for unit in chess-coach-web.service chess-coach-worker.service chess-coach-worker.timer; do
  ln -s "$unitdir/$unit" "$HOME/.config/systemd/user/$unit"
done
systemctl --user daemon-reload
systemctl --user enable --now chess-coach-web.service chess-coach-worker.timer
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
chess-coach-worker.timer` and the browser status page to inspect recent
processing, failures, and any server-requested retry deadline. Worker runs are
bounded and serialized, and the timer does not immediately restart a failed
run. Logs remain private and project-local. Stop the timer, any already-running worker, and the browser; then verify
each is inactive before backup, upgrade, or rollback:

```sh
systemctl --user stop chess-coach-worker.timer chess-coach-worker.service chess-coach-web.service
for unit in chess-coach-worker.timer chess-coach-worker.service chess-coach-web.service; do
  if systemctl --user is-active --quiet "$unit"; then
    printf 'Still active: %s\n' "$unit"
    exit 1
  fi
done
```

Stopping the timer alone does not stop a running oneshot worker. Do not
remove data.

Before an upgrade, stop and verify all three units as above, run `backup-db` to a new path under
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
