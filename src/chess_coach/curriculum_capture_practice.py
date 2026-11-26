"""Compare exact-source verified capture practice without scoring missing evidence."""

from .capture_compare_scope import scope
from .capture_plan_history import _matching
from .fact_fingerprint import digest
from .mastery_time import parse_utc


def _complete(history):
    if not isinstance(history, dict) or not isinstance(history.get("attempt_id"), str):
        return False
    status = tuple(
        history.get(key) for key in ("status", "assistance", "hints", "reveals", "limited")
    )
    return status in {
        ("correct", "unassisted", 0, 0, False),
        ("incorrect", "unassisted", 0, 0, False),
    }


def _chronology(row, history, as_of):
    started, answered, cutoff = map(
        parse_utc, (row["started_at"], history.get("answered_at"), as_of)
    )
    return bool(started and answered and cutoff and started <= answered <= cutoff)


def evidence(db, subject, corpus, position, history, as_of, check):
    """Return a fact only when its complete source and practice scope is current."""
    if not _complete(history):
        return None
    check()
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE subject=? AND attempt_id=?",
        (subject, history["attempt_id"]),
    ).fetchone()
    if row is None or not _matching(row, position, corpus):
        return None
    matched = scope(row, corpus)
    check()
    if matched is None or row["learner_color"] not in {"white", "black"}:
        return None
    if not _chronology(row, history, as_of):
        return None
    return {
        "context": digest(matched["key"]),
        "side": row["learner_color"],
        "result": history["status"],
    }
