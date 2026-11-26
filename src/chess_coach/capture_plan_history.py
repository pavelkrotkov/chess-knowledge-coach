"""Read one bounded, source-bound certified capture outcome."""

import json

from .capture_plan_result import result
from .mastery_time import parse_utc
from .mate_assessment_events import replay
from .related_capture_objective import is_source
from .tactical_exposure_progress import apply as apply_exposure
from .unified_source_current import require_current

LIMIT = 100


def _rows(db, subject):
    return db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? ORDER BY started_at DESC,attempt_id LIMIT ?""",
        (subject, LIMIT + 1),
    ).fetchall()


def _matching(row, position, corpus):
    if row["source_version"] != corpus or not is_source(row):
        return False
    binding = json.loads(row["provenance_json"])["related_capture"]
    return binding["position_id"] == position


def _selected(rows, position, corpus, *, check=lambda: None):
    chosen = None
    for row in rows:
        check()
        if not _matching(row, position, corpus):
            continue
        when = parse_utc(row["started_at"])
        if when is None or when.isoformat() != row["started_at"]:
            raise ValueError("assessment time unavailable")
        if chosen is None:
            chosen = row
        elif row["started_at"] == chosen["started_at"]:
            raise ValueError("assessment order unavailable")
        else:
            break
    return chosen


def _latest_proven(rows, selected, check):
    # Supported unified session creation writes canonical UTC via session_state.now.
    # The complete 101-row observed window must obey that ordering contract.
    previous = None
    for row in rows:
        check()
        value = row["started_at"]
        when = parse_utc(value)
        if when is None or when.isoformat() != value or (previous and when > previous):
            return False
        previous = when
    return selected["started_at"] > rows[-1]["started_at"]


def _proof(rows, selected, limited, enabled, check):
    if limited and enabled:
        return {"latest_proven": _latest_proven(rows, selected, check)}
    return {}


def latest(db, subject, position, corpus, *, check=None, prove_latest=False):
    related_check = check
    check = check or (lambda: None)
    try:
        # Inspect only the newest bounded session window; an older result may exist.
        rows = _rows(db, subject)
        check()
        limited = len(rows) > LIMIT
        row = _selected(rows[:LIMIT], position, corpus, check=check)
        if row is None:
            return {"status": "none", "limited": limited}
        if row["status"] == "active":
            require_current(db, row, related_check=related_check)
        observed = replay(db, row)
        check()
        state = (
            {"status": "incomplete"}
            if row["status"] == "active"
            else result(db, row, observed, related_check=related_check)
        )
        # Latest observation is narrower than a claim about complete history.
        state = apply_exposure(db, row, state)
        proof = _proof(rows, row, limited, prove_latest, check)
        return {
            **state,
            "attempt_id": row["attempt_id"],
            "limited": limited,
            **proof,
            "hints": observed["hints"],
            "reveals": observed["reveals"],
        }
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {"status": "stale"}
