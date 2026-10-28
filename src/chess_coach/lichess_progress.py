"""Durable, account-scoped history and recent-window progress."""

from __future__ import annotations

import json

from .db import Database
from .lichess_state import account_key, read_state, save_state

OVERLAP_SECONDS = 86400


def prepare_progress(db: Database, username: str, since: int | None, now: int) -> dict:
    if db.connection.in_transaction:
        raise RuntimeError("cannot synchronize during an existing transaction")
    key = account_key(username)
    start = since // 1000 if since is not None else 0
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        db.connection.execute(
            """INSERT OR IGNORE INTO sync_progress
            (account_key, history_start, history_windows, recent_windows, recent_end, recent_target)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                key,
                start,
                json.dumps([[start, now]]),
                json.dumps([[max(start, now - OVERLAP_SECONDS), now]]),
                max(start, now - OVERLAP_SECONDS),
                now,
            ),
        )
        state = read_state(db.connection, key)
        if since is not None and state["history_start"] != start:
            raise ValueError("cannot change the history start of an existing sync")
        if now <= state["history_start"]:
            raise ValueError("clock is earlier than the configured history start")
        reset_windows(state, now)
        save_state(db.connection, state)
        db.connection.commit()
        return state
    except BaseException:
        db.connection.rollback()
        raise


def reset_windows(state: dict, now: int) -> None:
    if not state["history_windows"]:
        state["history_windows"] = [[state["history_start"], now]]
    if not state["recent_windows"]:
        start = min(now - 1, max(state["history_start"], state["recent_end"] - OVERLAP_SECONDS))
        state["recent_windows"] = [[start, now]]
        state["recent_target"] = now
