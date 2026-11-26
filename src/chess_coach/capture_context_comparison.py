"""Describe one source-qualified capture context in independent games."""

import sqlite3

from .capture_context_presence import sample
from .capture_context_source import bind
from .capture_game_trend_report import report as capture_trend_report
from .curriculum_capture_inputs import observe
from .curriculum_capture_source_identity import require
from .curriculum_capture_witnesses import candidates


def profile(db, subject, corpus, as_of, report, check):
    # Unrelated unresolved turns widen bounds, not disqualify this context.
    # The boundary is the 41st independent game.
    if not report["comparable"] or not report["boundary"] or report["historical"]:
        return None
    options, _, identity, _ = candidates(db, subject, corpus, check, include_snapshot=True, limit=1)
    if not options:
        return None
    turns = report["newer"]["root_details"] + report["earlier"]["root_details"]
    source = bind(db, subject, corpus, as_of, options[0], turns, check)
    if source is None:
        return None
    newer = sample(report["newer"], source["wanted"], check)
    earlier = sample(report["earlier"], source["wanted"], check)
    if not newer["qualified"] or not earlier["qualified"]:
        return None
    require(db, subject, identity, check, limit=1)
    return {"source": source, "newer": newer, "earlier": earlier}


def read(db, subject, corpus, root, as_of, check):
    try:
        before = observe(db, subject, root, check)
        result = capture_trend_report(db, subject, root, check=check, as_of=as_of)
        if not result:
            return None
        value = profile(db, subject, corpus, as_of, result, check)
        if observe(db, subject, root, check) != before:
            return None
        result["context_profile"] = value
        return result
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
