"""Find a distinct public rehearsal with its own original replayed history."""

import sqlite3

from .opening_context_replay import replay
from .opening_course_public_candidate import candidate
from .opening_distance_branch import records
from .opening_profile_lookup import MAX_GAMES, guard


def qualify(context):
    item, budget = context["item"], context["budget"]
    first = item["source"]["line"]
    selection = item["selection"]
    parent, move = selection["parent"], item["uci"]
    connection = sqlite3.connect(
        context["guard"][1].as_uri() + "?mode=ro&immutable=1", uri=True, timeout=1
    )
    try:
        guard(connection, budget.expires)
        rows = records(connection, parent, move)
        checked = 0
        for record, ply in rows[:MAX_GAMES]:
            budget.check()
            checked += 1
            if record == first["record"]:
                continue
            try:
                line = candidate(connection, record, ply, parent, move, None)
                if line is None or line["moves"] == first["moves"]:
                    continue
                history = replay(connection, record, ply, parent, line, budget)
            except (ValueError, TypeError, KeyError, IndexError):
                continue
            return {
                "second": {"line": line, "history": history},
                "checked": checked,
                "limit": MAX_GAMES,
                "more": len(rows) > MAX_GAMES,
            }
        return {
            "second": None,
            "checked": checked,
            "limit": MAX_GAMES,
            "more": len(rows) > MAX_GAMES,
        }
    finally:
        connection.close()
