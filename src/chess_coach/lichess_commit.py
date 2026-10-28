"""Commit imported windows and their cursors in a single transaction."""

from __future__ import annotations

from .db import Database
from .lichess_import import import_records
from .lichess_state import read_state, save_state


def apply_window(db: Database, state: dict, field: str, records: list[str]) -> dict[str, int]:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        current = read_state(db.connection, state["account_key"])
        if current["revision"] != state["revision"]:
            raise RuntimeError("synchronization progress changed concurrently")
        totals = import_records(db, records)
        state[field].pop(0)
        if not state[field] and field == "history_windows":
            state["history_cycles"] += 1
        if not state[field] and field == "recent_windows":
            state["recent_end"] = state["recent_target"]
        save_state(db.connection, state)
        db.connection.commit()
        return totals
    except BaseException:
        db.connection.rollback()
        raise


def split_progress(db: Database, state: dict, field: str, children: list[list[int]]) -> None:
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        state[field][:1] = children
        save_state(db.connection, state)
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise
