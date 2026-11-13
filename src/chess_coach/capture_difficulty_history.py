"""Find the two latest ordered capture assessments for one source."""

from itertools import pairwise

from .capture_plan_history import LIMIT, _matching, _rows
from .protection_progress_item import _time


def _candidates(rows, position, corpus, check):
    matches = []
    for row in rows:
        check()
        if _matching(row, position, corpus):
            matches.append(row)
    return matches


def pair(db, subject, corpus, position, attempt, check):
    rows = _rows(db, subject)
    boundary = rows[LIMIT]["started_at"] if len(rows) > LIMIT else None
    selected = _candidates(rows[:LIMIT], position, corpus, check)
    if len(selected) < 2:
        raise ValueError("harder capture unavailable")
    recent, earlier = selected[:2]
    _ordered(selected, boundary)
    if recent["attempt_id"] != attempt:
        raise ValueError("harder capture changed")
    return recent, earlier


def _ordered(selected, boundary):
    times = [_time(row["started_at"]) for row in selected[:3]]
    if any(a <= b for a, b in pairwise(times)):
        raise ValueError("harder capture ordering unavailable")
    if boundary is not None and times[-1] <= _time(boundary):
        raise ValueError("harder capture ordering unavailable")
