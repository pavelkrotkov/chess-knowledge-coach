"""Compose a lazy capture recommendation without changing learning state."""

from .capture_plan_history import latest
from .capture_plan_sources import choose
from .learner_identity import normalize_identity


def report(db, subject, corpus, *, check=None):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("learner unavailable")
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    options = {"check": check} if check is not None else {}
    result = choose(db, learner, **options)
    result["history"] = (
        latest(db, subject, result["source"]["position_id"], corpus, **options)
        if result["source"]
        else None
    )
    if check is None and result["source"] and result["history"]:
        _optional(db, subject, corpus, result["source"]["position_id"], result["history"])
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("capture sources changed")
    return result


def _optional(db, subject, corpus, position, history):
    if history.get("status") == "correct" and history.get("assistance") == "unassisted":
        from .capture_difficulty import eligible

        try:
            eligible(db, subject, corpus, position, history["attempt_id"])
            history["harder"] = True
        except (ValueError, TypeError, KeyError, IndexError):
            pass
