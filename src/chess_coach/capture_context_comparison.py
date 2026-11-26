"""Describe one source-qualified capture context in independent games."""

import sqlite3

from .capture_context_presence import sample
from .capture_context_source import bind
from .capture_game_trend_report import report as capture_trend_report
from .curriculum_capture_inputs import observe
from .curriculum_capture_source_identity import require
from .curriculum_capture_witnesses import descriptive


def _profile(db, subject, corpus, as_of, report, option, check):
    turns = report["newer"]["root_details"] + report["earlier"]["root_details"]
    try:
        source = bind(db, subject, corpus, as_of, option, turns, check)
        if source is None:
            return None
        newer = sample(report["newer"], source["wanted"], check)
        earlier = sample(report["earlier"], source["wanted"], check)
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    if not newer["qualified"] or not earlier["qualified"]:
        return None
    return {"source": source, "newer": newer, "earlier": earlier}


def _comparison(first, second):
    left, right = first["source"], second["source"]
    common_left = (left["practice"], left["turn"]["side"], left["turn"]["time_control"])
    common_right = (right["practice"], right["turn"]["side"], right["turn"]["time_control"])
    comparable = (
        common_left == common_right
        and left["practice"]["controls"]["baseline_band"] is not None
        and left["wanted"] != right["wanted"]
    )
    winner = None
    if comparable:
        # Both profiles use the same qualified 20-game sample.
        a, b = first["newer"], second["newer"]
        if a["lower"] > b["upper"]:
            winner = 0
        elif b["lower"] > a["upper"]:
            winner = 1
    return {"other": second, "comparable": comparable, "winner": winner}


def profile(db, subject, corpus, as_of, report, check):
    # Unrelated unresolved turns widen bounds, not disqualify this context.
    # The boundary is the 41st independent game.
    if not report["comparable"] or not report["boundary"] or report["historical"]:
        return None
    options, identity = descriptive(db, subject, corpus, check)
    profiles = []
    for option in options:
        current = _profile(db, subject, corpus, as_of, report, option, check)
        if current is not None:
            profiles.append(current)
    require(db, subject, identity, check, limit=2)
    if not profiles:
        return None
    first = profiles[0]
    if len(profiles) == 2:
        first["comparison"] = _comparison(first, profiles[1])
    return first


def read(db, subject, corpus, root, as_of, check):
    try:
        before = observe(db, subject, root, check)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return capture_trend_report(db, subject, root, check=check, as_of=as_of)
    try:
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
