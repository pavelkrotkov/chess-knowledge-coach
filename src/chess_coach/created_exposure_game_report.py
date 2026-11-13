"""Summarize independent, profile-bound exposure observations."""

import sqlite3
import time

from .capture_game_trend_bounds import bounds
from .created_exposure_game_answer import first_answer, follows
from .created_exposure_game_context import matched
from .created_exposure_game_counts import bounded, sample
from .created_exposure_game_current import current
from .learner_identity import normalize_identity
from .mate_game_comparability import reason as comparability_reason

SECONDS = 2.0


def _reason(state, newer, earlier):
    if not state["selection_complete"]:
        return "selection_pending"
    if newer["withheld_games"] or earlier["withheld_games"]:
        return "source_unavailable"
    reason = comparability_reason(
        (newer, earlier),
        [game["date"] for game in state["games"]],
        state["coverage"],
        state["unavailable"],
    )
    return reason or state.get("time_control_reason")


# Timing and comparability answer different questions: a sparse window can
# still have a valid date relationship to the verified practice answer. Only
# complete selections and full windows establish their eventual oldest date.
def _report(db, learner, state, deadline):
    games = state["games"]
    newer, earlier = sample(games[:20]), sample(games[20:40])
    reason = _reason(state, newer, earlier)
    contexts_match = reason is None and matched(db, learner, games)
    bound = bounds(contexts_match, bounded(earlier), bounded(newer))
    answer = first_answer(db, learner, state["profile"], deadline)
    relation = {
        name: (
            follows(window["oldest"], answer["answered_at"])
            if answer and state["selection_complete"] and window["games"] == 20
            else None
        )
        for name, window in (("earlier", earlier), ("newer", newer))
    }
    return {
        "profile": state["profile"],
        "newer": newer,
        "earlier": earlier,
        "comparable_reason": reason,
        "contexts_match": contexts_match,
        "bounds": bound,
        "answer": answer,
        "relation": relation,
        "coverage": state["coverage"],
        "duplicates": state["duplicates"],
        "unavailable": state["unavailable"],
    }


def report(db, learner, root):
    learner = normalize_identity(learner)
    if not learner:
        return None
    try:
        before = db.connection.execute("PRAGMA data_version").fetchone()[0]
        state = current(db, learner, root)
        if state is None:
            return None
        deadline = time.monotonic() + SECONDS
        db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        try:
            result = _report(db, learner, state, deadline)
        finally:
            db.connection.set_progress_handler(None, 0)
        if time.monotonic() >= deadline:
            return None
        return (
            result if db.connection.execute("PRAGMA data_version").fetchone()[0] == before else None
        )
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
