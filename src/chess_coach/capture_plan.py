"""Compose a lazy capture recommendation without changing learning state."""

from .capture_plan_history import latest
from .capture_plan_sources import choose
from .learner_identity import normalize_identity


def report(db, subject):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("learner unavailable")
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    result = choose(db, learner)
    result["history"] = (
        latest(db, subject, result["source"]["position_id"]) if result["source"] else None
    )
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("capture sources changed")
    return result
