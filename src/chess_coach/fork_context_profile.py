"""Describe one practiced fork context in independent game samples."""

from .capture_context_presence import sample
from .fork_context_presence import turn
from .fork_context_source import bind


def profile(db, subject, corpus, as_of, report, check):
    if report["historical"] or not report["comparable"] or not report["boundary"]:
        return None
    turns = report["newer"]["root_details"] + report["earlier"]["root_details"]
    try:
        source = bind(db, subject, corpus, as_of, turns, check)
        if source is None:
            return None
        newer = sample(report["newer"], source["wanted"], check, turn=turn)
        earlier = sample(report["earlier"], source["wanted"], check, turn=turn)
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    if not newer["qualified"] or not earlier["qualified"]:
        return None
    return {"source": source, "newer": newer, "earlier": earlier}
