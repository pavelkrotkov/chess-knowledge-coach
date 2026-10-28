"""Fail safely if other tables reference mastery history."""

import sqlite3


def check_dependents(connection: sqlite3.Connection) -> None:
    tables = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    for (name,) in tables:
        quoted = name.replace('"', '""')
        for ref in connection.execute(f'PRAGMA foreign_key_list("{quoted}")'):
            if ref[2] == "mastery_states" and name != "mastery_events":
                raise RuntimeError("cannot migrate mastery with external state references")
            if ref[2] == "mastery_events":
                raise RuntimeError("cannot migrate mastery with external event references")


def trend_is_nullable(connection: sqlite3.Connection) -> bool:
    columns = connection.execute("PRAGMA table_info(mastery_states)")
    return any(row[1] == "trend_30d" and row[3] == 0 for row in columns)
