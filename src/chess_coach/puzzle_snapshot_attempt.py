"""Choose a safe resumable attempt or create a fresh one."""

import time

from .puzzle_snapshot_boundary import checked_path
from .puzzle_snapshot_http import strong_etag
from .puzzle_snapshot_paths import existing_attempts, new_attempt
from .puzzle_snapshot_state import SOURCE_URL, read_state, write_state


def select_attempt(path, version):
    check_provider_backoff(path.parent)
    attempts = [checked_path(item, path.parents[1]) for item in path.glob("attempt-*")]
    attempts.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    for attempt in attempts:
        state = read_state(attempt)
        if not state:
            continue
        if state.get("archive_complete") and state.get("resumable"):
            checked_path(attempt / "archive.zst", path.parents[1])
            return attempt, state
        if state.get("resumable") and strong_etag(state.get("etag")):
            checked_path(attempt / "archive.zst", path.parents[1])
            return attempt, state
    attempt = new_attempt(path)
    state = {
        "version": version,
        "source_url": SOURCE_URL,
        "phase": "starting",
        "downloaded_bytes": 0,
        "resumable": True,
    }
    write_state(attempt, state)
    return attempt, state


def check_provider_backoff(base):
    for attempt in existing_attempts(base):
        state = read_state(attempt)
        if state and state.get("retry_at", 0) > time.time():
            raise ValueError("provider backoff is still active")
