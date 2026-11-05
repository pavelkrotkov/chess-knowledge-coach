"""Recognize fully played, unassisted prepared short-mate rehearsals."""

from .coaching_short_rehearsal_verify import completed
from .objective_events import MAX_EVENTS
from .objective_short_source import VERSION
from .unified_source_current import require_current


def rehearsed_sources(db, subject, keys, boards=frozenset()):
    if not keys and not boards:
        return {}
    rows = db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? ORDER BY started_at DESC,attempt_id LIMIT 100""",
        (subject,),
    ).fetchall()
    completed = {}
    for row in rows:
        key = row["source_key"]
        board = " ".join(row["prompt_fen"].split()[:4])
        if (key in keys or board in boards) and key not in completed and _completed(db, row):
            completed[key] = board
    return completed


def _completed(db, row):
    if (row["source_type"], row["source_version"], row["objective"], row["status"]) != (
        "own-game",
        VERSION,
        "mate_within_two",
        "objective_verified",
    ) or row["hints_used"] != 0:
        return False
    try:
        require_current(db, row)
        events = db.connection.execute(
            """SELECT kind,submitted_move,response_json FROM unified_session_events
            WHERE attempt_id=? ORDER BY rowid LIMIT ?""",
            (row["attempt_id"], MAX_EVENTS + 1),
        ).fetchall()
        return len(events) <= MAX_EVENTS and completed(row, events)
    except (ValueError, TypeError, KeyError, IndexError):
        return False
