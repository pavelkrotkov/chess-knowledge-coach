"""Recheck an existing public continuation from its original starting position."""

import sqlite3

from .opening_context_replay import replay
from .opening_course_public_candidate import candidate
from .opening_profile_lookup import guard
from .opening_profile_play import PARENT_PLIES
from .opening_unfamiliar_public import public


def checked(root, subject, parent, item, budget, index):
    value = public(root, subject, parent, item["uci"], budget)
    if value is None:
        return None
    line, profile = value
    connection = sqlite3.connect(index.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(connection, budget.expires)
        rows = connection.execute(
            "SELECT ply FROM moves WHERE game_id=? AND parent=? AND uci=? AND ply<=? ORDER BY ply LIMIT ?",
            (line["record"], parent, item["uci"], PARENT_PLIES, PARENT_PLIES),
        ).fetchall()
        for (first,) in rows:
            budget.check()
            current = candidate(connection, line["record"], first, parent, item["uci"], None)
            if current and current["reference"] == line["reference"]:
                source = replay(connection, line["record"], first, parent, line, budget)
                return {"line": line, "profile": profile, "source_history": source}
        return None
    finally:
        connection.close()


def recorded(index, parent, items, budget):
    if not items:
        return set()
    connection = sqlite3.connect(index.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1)
    try:
        guard(connection, budget.expires)
        placeholders = ",".join("?" for _ in items)
        rows = connection.execute(
            f"SELECT DISTINCT uci FROM moves WHERE parent=? AND ply<=? AND uci IN ({placeholders})",
            (parent, PARENT_PLIES, *(item["uci"] for item in items)),
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        connection.close()
