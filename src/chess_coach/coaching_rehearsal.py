"""Recognize bounded, exact-source mate rehearsals without changing learning state."""

from .coaching_rehearsal_verify import checkmate
from .objective_contract import VERSION
from .unified_source_current import require_current


def rehearsed_sources(db, subject, keys):
    if not keys:
        return {}
    rows = db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? ORDER BY started_at DESC,attempt_id LIMIT 100""",
        (subject,),
    ).fetchall()
    completed = {}
    for row in rows:
        key = row["source_key"]
        if key in keys and key not in completed and _completed(db, row):
            completed[key] = " ".join(row["prompt_fen"].split()[:4])
    return completed


def _completed(db, row):
    if (row["source_type"], row["source_version"], row["objective"], row["status"]) != (
        "own-game",
        VERSION,
        "mate_in_one",
        "objective_verified",
    ):
        return False
    try:
        events = db.connection.execute(
            """SELECT kind,submitted_move,response_json FROM unified_session_events
            WHERE attempt_id=? LIMIT 2""",
            (row["attempt_id"],),
        ).fetchall()
        if len(events) != 1 or events[0]["kind"] != "move":
            return False
        if not checkmate(row["prompt_fen"], events[0]):
            return False
        require_current(db, row)
        return True
    except (ValueError, TypeError, KeyError, IndexError):
        return False
