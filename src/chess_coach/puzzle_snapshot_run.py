"""Acquire a private, immutable official puzzle snapshot."""

import os
import time

import httpx

from .puzzle_snapshot_attempt import select_attempt
from .puzzle_snapshot_boundary import checked_path
from .puzzle_snapshot_budget import check_budget
from .puzzle_snapshot_client import make_client
from .puzzle_snapshot_decode import decode
from .puzzle_snapshot_digest import digest_file
from .puzzle_snapshot_download import transfer
from .puzzle_snapshot_publish import make_manifest, publish
from .puzzle_snapshot_state import write_state


def acquire_locked(path, version, limits, client):
    attempt, state = select_attempt(path, version)
    state.pop("error", None)
    deadline = time.monotonic() + limits.seconds
    own_client = client is None
    client = client or make_client(limits)
    try:
        archive = checked_path(attempt / "archive.zst", path.parents[1])
        if not state.get("archive_complete"):
            archive = transfer(attempt, state, limits, deadline, client)
        check_budget(attempt, limits, deadline, archive.stat().st_size, limits.max_archive_bytes)
        archive_hash = digest_file(archive, limits, deadline)
        if archive_hash != state.get("partial_sha256"):
            raise ValueError("archive hash differs from checkpoint")
        os.chmod(archive, 0o444)
        csv, csv_hash = decode(archive, attempt, state, limits, deadline)
        manifest = make_manifest(version, archive, csv, archive_hash, csv_hash)
        publish(path, attempt, state, manifest)
        return manifest
    except (OSError, ValueError, TimeoutError, httpx.HTTPError) as exc:
        state.update(phase="failed", error=str(exc)[:300])
        if isinstance(exc, ValueError):
            state["resumable"] = False
        write_state(attempt, state)
        raise
    finally:
        if own_client:
            client.close()
