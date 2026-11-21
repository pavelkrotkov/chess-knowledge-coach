"""Compare indexed tactical exposure times with an assessment answer."""

from .mastery_time import parse_utc


def _times(db, identity, key):
    kinds = ("served", "download", "study_verified", "study_pending", "historical_unknown")
    times = {}
    for kind in kinds:
        row = db.connection.execute(
            """SELECT occurred_at FROM tactical_exposures
            INDEXED BY idx_tactical_exposure_prompt
            WHERE subject=? AND prompt_key=? AND kind=? ORDER BY occurred_at LIMIT 1""",
            (identity, key, kind),
        ).fetchone()
        if row is not None:
            times[kind] = parse_utc(row[0])
    return times


def _provided(times, cutoff):
    for kind, moment in times.items():
        if moment is None:
            return "coverage_unavailable"
        if kind in {"served", "download", "study_verified"} and moment <= cutoff:
            return "provided"
    return None


def ledger_check(db, identity, key, cutoff, start, intent):
    times = _times(db, identity, key)
    outcome = _provided(times, cutoff)
    if outcome is not None:
        return outcome
    if intent != "not_recorded":
        return intent
    if "historical_unknown" in times:
        return "publication_time_unknown"
    # A pending send does not establish when the learner received it.
    pending = times.get("study_pending")
    if pending is not None and pending <= cutoff:
        return "publication_time_unknown"
    if cutoff < start:
        return "legacy_coverage_unknown"
    return "not_recorded"
