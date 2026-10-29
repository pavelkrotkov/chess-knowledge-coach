"""Choose a safe resumable attempt or create a fresh one."""

import time

from .puzzle_snapshot_http import strong_etag
from .puzzle_snapshot_paths import new_attempt
from .puzzle_snapshot_state import SOURCE_URL, read_state, write_state


def select_attempt(path, version):
    check_provider_backoff(path.parent)
    attempts = sorted(path.glob("attempt-*"), key=lambda item: item.stat().st_mtime, reverse=True)
    for attempt in attempts:
        state = read_state(attempt)
        if not state:
            continue
        if state.get("archive_complete") and state.get("resumable"):
            return attempt, state
        if state.get("resumable") and strong_etag(state.get("etag")):
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
    for state_path in base.glob("*/attempt-*/state.json"):
        state = read_state(state_path.parent)
        if state and state.get("retry_at", 0) > time.time():
            raise ValueError("provider backoff is still active")
