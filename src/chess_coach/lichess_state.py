"""Read and compare-and-swap private synchronization progress."""

from __future__ import annotations

import hashlib
import json
import sqlite3


def account_key(username: str) -> str:
    return hashlib.sha256(username.casefold().encode()).hexdigest()


def read_state(connection: sqlite3.Connection, key: str) -> dict:
    row = connection.execute("SELECT * FROM sync_progress WHERE account_key = ?", (key,)).fetchone()
    if row is None:
        raise RuntimeError("missing synchronization progress")
    state = dict(row)
    for field in ("history_windows", "recent_windows"):
        state[field] = json.loads(state[field])
    return state


def save_state(connection: sqlite3.Connection, state: dict) -> None:
    cursor = connection.execute(
        """UPDATE sync_progress SET history_windows = ?, recent_windows = ?, history_cycles = ?,
        recent_end = ?, recent_target = ?, revision = revision + 1
        WHERE account_key = ? AND revision = ?""",
        (
            json.dumps(state["history_windows"]),
            json.dumps(state["recent_windows"]),
            state["history_cycles"],
            state["recent_end"],
            state["recent_target"],
            state["account_key"],
            state["revision"],
        ),
    )
    if cursor.rowcount != 1:
        raise RuntimeError("synchronization progress changed concurrently")
    state["revision"] += 1
