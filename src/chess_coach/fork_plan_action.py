"""Offer an optional fork action from a bounded recurring coaching lesson."""

import sqlite3

from .coaching_quick_view import preview
from .fork_plan_history import report as history
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import PreviewUnavailable


def _source(preview_result, actions):
    for group, action in zip(preview_result["groups"], actions, strict=True):
        if group["miss_games"] >= 2 and action and action["kind"] == "fork":
            return {"source": action, "games": group["miss_games"]}
    return None


def recommendation(db, subject, corpus):
    try:
        version = db.connection.execute("PRAGMA data_version").fetchone()[0]
        result, actions = preview(db, subject, (("fork", "execute"),))
        source = _source(result, actions)
        if not source:
            return None
        budget = BrowserBudget(db)
        if budget.version != version:
            return None
        try:
            assessment = history(db, subject, corpus, source["source"]["evidence_id"], budget)
        except (
            sqlite3.Error,
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            AttributeError,
            PreviewUnavailable,
        ):
            assessment = {"status": "unknown"}
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            return None
        return {**source, "assessment": assessment}
    except (
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        PreviewUnavailable,
    ):
        return None


# Reuse the same finder and history while the caller owns the snapshot budget.
def checked(db, subject, corpus, check, *, as_of=None):
    from .coaching_quick_pair import build
    from .coaching_quick_practice import choose
    from .fork_plan_history import checked as checked_history
    from .preview_snapshot import preview_history

    with preview_history(db, subject) as history_scope:
        groups, limited, _ = build(
            db, subject, ("fork", "execute"), check, _history=history_scope, as_of=as_of
        )
        actions = [
            choose(db, subject, group, check, source_check=True, _history=history_scope)
            for group in groups
        ]
    selected = _source({"groups": groups}, actions)
    if selected is None:
        return None
    evidence = selected["source"]["evidence_id"]
    assessment = checked_history(db, subject, corpus, evidence, check, as_of=as_of)
    harder = _harder(db, subject, corpus, evidence, assessment, check, as_of)
    return {**selected, "assessment": assessment, "harder": harder, "limited": limited}


def _harder(db, subject, corpus, evidence, assessment, check, as_of):
    if assessment["status"] != "correct":
        return False
    from .fork_difficulty_history import _pair

    try:
        _pair(db, subject, corpus, evidence, assessment["attempt"], check, as_of=as_of)
        return True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return False
