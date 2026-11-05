"""Check bounded, current and unassisted owned short-mate attempts."""

from .coaching_short_async import completed as async_completed
from .coaching_short_rehearsal_verify import completed as prepared_completed
from .objective_events import MAX_EVENTS
from .objective_short_source import VERSION
from .unified_source_current import require_current


def completed(db, row):
    if (
        (row["source_type"], row["source_version"], row["objective"])
        != (
            "own-game",
            VERSION,
            "mate_within_two",
        )
        or row["status"] not in {"objective_verified", "needs_verification"}
        or row["hints_used"] != 0
    ):
        return False
    try:
        events = db.connection.execute(
            """SELECT event_id,kind,submitted_move,response_json FROM unified_session_events
            WHERE attempt_id=? ORDER BY rowid LIMIT ?""",
            (row["attempt_id"], MAX_EVENTS + 1),
        ).fetchall()
        if len(events) > MAX_EVENTS:
            return False
        if row["status"] == "objective_verified" and _prepared(db, row, events):
            return True
        return async_completed(db, row, events)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False


def _prepared(db, row, events):
    try:
        if not prepared_completed(row, events):
            return False
        require_current(db, row)
        return True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False
