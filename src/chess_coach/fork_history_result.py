"""Read a source-bound fork assessment result without performing a new proof."""

import json

from .fork_history_proof import valid
from .objective_current import current
from .objective_history_dispatch import replay


def result(db, row, *, check, cache=None):
    return details(db, row, check=check, cache=cache)[0]


def details(db, row, *, check, cache=None):
    requests = db.connection.execute(
        "SELECT * FROM objective_requests WHERE attempt_id=? ORDER BY rowid LIMIT 2",
        (row["attempt_id"],),
    ).fetchall()
    if len(requests) != 1:
        return "stale", None
    request = requests[0]
    session, events = current(db, request, related_check=check, related_cache=cache)
    board, move = replay(db, session, events, request)
    record = db.connection.execute(
        "SELECT result_json FROM objective_results WHERE attempt_id=? AND event_id=?",
        (row["attempt_id"], request["event_id"]),
    ).fetchone()
    if record is None:
        return "pending", None
    stored = json.loads(record["result_json"])
    if not valid(stored, request, events, board, move, session):
        return "stale", None
    return stored["status"], events[-1]["created_at"]
