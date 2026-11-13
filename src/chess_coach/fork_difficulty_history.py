"""Validate the two ordered, current fork results for progression."""

from .capture_difficulty_history import _ordered
from .fork_followup_first import compatible
from .fork_followup_prior import _prior
from .fork_plan_history import _candidates
from .protection_progress_item import _answer, _time


def _pair(db, subject, corpus, evidence, attempt, check):
    matches, boundary = _candidates(db, subject, evidence, check)
    if len(matches) < 2:
        raise ValueError("harder fork unavailable")
    recent, earlier = matches[:2]
    _ordered(matches, boundary)
    if recent["attempt_id"] != attempt:
        raise ValueError("harder fork changed")
    current = [_prior(db, subject, corpus, row["attempt_id"], check) for row in (recent, earlier)]
    if current[0] != current[1] or current[0][0] != evidence:
        raise ValueError("harder fork context changed")
    compatible(recent, earlier)
    _answer(db, recent)
    if _time(_answer(db, earlier)) >= _time(recent["started_at"]):
        raise ValueError("harder fork ordering unavailable")
    expected = dict(current[0][1])
    expected["rating_band"] += 1
    if expected["rating_band"] >= 20:
        raise ValueError("harder fork band unavailable")
    check()
    return {
        "evidence": evidence,
        "earlier": earlier["attempt_id"],
        "attempt": attempt,
        "expected": expected,
        "side": recent["learner_color"],
    }
