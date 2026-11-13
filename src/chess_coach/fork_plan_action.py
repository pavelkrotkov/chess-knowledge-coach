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
