"""Replay the exact fork successes recorded at harder admission."""

from .fork_followup_first import compatible
from .fork_followup_prior import _prior
from .harder_prior_rows import load
from .protection_progress_item import _answer, _time


def verify(db, subject, corpus, source, as_of, check):
    lineage = source["controls"].get("lineage")
    if not isinstance(lineage, dict):
        raise ValueError("fork harder lineage unavailable")
    earlier, recent = load(db, subject, lineage.get("earlier"), lineage.get("attempt"))
    harder = source["practice"]["row"]
    evidence = source["practice"]["binding"]["evidence_id"]
    current = [
        _prior(db, subject, corpus, row["attempt_id"], check, as_of=as_of)
        for row in (earlier, recent)
    ]
    if current[0] != current[1] or current[0][0] != evidence:
        raise ValueError("fork harder source changed")
    compatible(recent, earlier)
    expected = dict(current[0][1])
    expected["rating_band"] += 1
    actual = source["practice"]["binding"]["assessment"]["context"]
    if (lineage.get("evidence"), lineage.get("side"), lineage.get("expected"), actual) != (
        evidence,
        harder["learner_color"],
        expected,
        expected,
    ):
        raise ValueError("fork harder context changed")
    if _time(_answer(db, earlier)) >= _time(recent["started_at"]):
        raise ValueError("fork harder ordering unavailable")
    if _time(_answer(db, recent)) >= _time(harder["started_at"]):
        raise ValueError("fork harder ordering unavailable")
    check()
