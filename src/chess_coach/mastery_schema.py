"""Allow unknown trends without discarding mastery state or event history."""

from __future__ import annotations

import re
import sqlite3

from .mastery_schema_guard import check_dependents, trend_is_nullable


def allow_unknown_trend(connection: sqlite3.Connection) -> None:
    if trend_is_nullable(connection):
        return
    check_dependents(connection)
    state_sql = _table_sql(connection, "mastery_states")
    event_sql = _table_sql(connection, "mastery_events")
    indexes = connection.execute(
        """SELECT sql FROM sqlite_master WHERE tbl_name IN ('mastery_states', 'mastery_events')
        AND type IN ('index', 'trigger') AND sql IS NOT NULL ORDER BY type, name"""
    ).fetchall()
    new_state = _replace_once(
        state_sql, r"(?i)^CREATE TABLE\s+mastery_states\b", "CREATE TABLE mastery_states_new"
    )
    new_state = _replace_once(new_state, r"(?i)\btrend_30d\s+REAL\s+NOT\s+NULL\b", "trend_30d REAL")
    new_event = _replace_once(
        event_sql, r"(?i)^CREATE TABLE\s+mastery_events\b", "CREATE TABLE mastery_events_new"
    )
    new_event = _replace_once(
        new_event, r"(?i)\bREFERENCES\s+mastery_states\s*\(", "REFERENCES mastery_states_new("
    )
    connection.execute(new_state)
    connection.execute(new_event)
    connection.execute("INSERT INTO mastery_states_new SELECT * FROM mastery_states")
    connection.execute("INSERT INTO mastery_events_new SELECT * FROM mastery_events")
    connection.execute("DROP TABLE mastery_events")
    connection.execute("DROP TABLE mastery_states")
    connection.execute("ALTER TABLE mastery_states_new RENAME TO mastery_states")
    connection.execute("ALTER TABLE mastery_events_new RENAME TO mastery_events")
    for (sql,) in indexes:
        connection.execute(sql)
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise RuntimeError("mastery migration would leave invalid foreign keys")


def _table_sql(connection: sqlite3.Connection, name: str) -> str:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        raise RuntimeError("mastery migration requires existing tables")
    return row[0]


def _replace_once(text: str, pattern: str, replacement: str) -> str:
    result, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise RuntimeError("unsupported mastery table schema")
    return result
