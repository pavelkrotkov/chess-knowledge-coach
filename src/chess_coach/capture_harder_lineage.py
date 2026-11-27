"""Replay the exact capture successes recorded at harder admission."""

from operator import itemgetter

from .capture_compare_scope import scope
from .capture_compare_signature import signature
from .capture_difficulty_context import context
from .harder_prior_rows import load
from .protection_progress_item import _answer, _time
from .unified_session_state import session_row


def _recorded(db, subject, source):
    practice = source["common_practice"]
    progression = practice["binding"].get("progression")
    if not isinstance(progression, dict) or progression.get("policy") != "capture-harder-v1":
        raise ValueError("capture harder lineage unavailable")
    attempts = progression.get("prior_attempts")
    if not isinstance(attempts, list) or len(attempts) != 2:
        raise ValueError("capture harder lineage unavailable")
    earlier, recent = load(db, subject, *attempts)
    harder = session_row(db, practice["attempt"], subject)
    return earlier, recent, harder


def verify(db, subject, corpus, source, check):
    practice = source["common_practice"]
    earlier, recent, harder = _recorded(db, subject, source)
    matches = [scope(row, corpus) for row in (earlier, recent)]
    identity = itemgetter("position_id", "evidence_id", "source_fingerprint", "review_event_id")
    expected_source = identity(practice["binding"])
    if any(value is None or identity(value["binding"]) != expected_source for value in matches):
        raise ValueError("capture harder source changed")
    expected, _, side = context(db, corpus, recent, earlier, check)
    if (signature(practice["context"], corpus), harder["learner_color"]) != (expected, side):
        raise ValueError("capture harder context changed")
    if _time(_answer(db, recent)) >= _time(harder["started_at"]):
        raise ValueError("capture harder ordering unavailable")
    check()
