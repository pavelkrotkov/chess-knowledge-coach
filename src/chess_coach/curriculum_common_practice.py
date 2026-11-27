"""Read only the exact recorded first attempts and their harder lineage."""

import json

from .common_practice_ratings import read as ratings
from .curriculum_capture_practice_binding import _counter
from .fork_first_result import read as first_fork


def _attempt(db, subject, corpus, attempt, check):
    check()
    row = db.connection.execute(
        "SELECT * FROM unified_sessions WHERE subject=? AND attempt_id=?", (subject, attempt)
    ).fetchone()
    if row is None:
        return [attempt, None], []
    provenance = json.loads(row["provenance_json"])
    binding = provenance.get("related_capture") or provenance.get("related_fork") or {}
    position = binding.get("position_id")
    rating = ratings(db, corpus, row["source_key"], position, row["learner_color"])
    counts = [
        _counter(db, table, [attempt])
        for table in ("unified_session_events", "objective_requests", "objective_results")
    ]
    progression = binding.get("progression", {}).get("prior_attempts", [])
    controls = binding.get("assessment", {}).get("common_controls", {})
    lineage = controls.get("lineage", {})
    return [tuple(row), rating, counts], [
        *progression,
        lineage.get("earlier"),
        lineage.get("attempt"),
    ]


def observe(db, subject, corpus, attempts, check):
    values = []
    for attempt in dict.fromkeys(value for value in attempts if isinstance(value, str)):
        value, prior = _attempt(db, subject, corpus, attempt, check)
        values.append(value)
        for earlier in prior:
            if isinstance(earlier, str) and earlier != attempt:
                values.append(_attempt(db, subject, corpus, earlier, check)[0])
    return values


def selected(db, subject, corpus, options, fork, as_of, check):
    attempts = [report["history"].get("attempt_id") for _, report in options]
    if fork is not None:
        try:
            result = first_fork(db, subject, corpus, fork["source_evidence_id"], as_of, check)
            if result is not None:
                attempts.append(result["row"]["attempt_id"])
        except (ValueError, TypeError, KeyError, IndexError):
            check()
    return attempts
