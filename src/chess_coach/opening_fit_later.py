"""Compare later opening opportunities using existing bounded source checks."""

import sqlite3
import time

from .opening_fit import _owned_scope
from .opening_fit_later_index import locate
from .opening_fit_later_owned import collect
from .opening_fit_later_public import samples
from .opening_fit_later_rank import rank
from .opening_fit_owned_summary import _control
from .opening_queue_budget import BrowserBudget
from .style_schedule_budget import BudgetExceeded
from .style_time_candidates import verified
from .style_time_query import load_game
from .tactical_course_budget import PreviewUnavailable

SECONDS = 12


def assess(db, root, learner, decision, choice, *, source="broadcast"):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    result = {"status": "unavailable"}
    try:
        if not 1 <= decision["ply"] <= 20:
            return result
        index = locate(root, learner, source)
        game = load_game(db.connection, decision["game_id"])
        if verified(game, learner) != decision["color"]:
            return result
        control = _control(game["time_control"])
        moves = [decision["played_uci"], choice["uci"]]
        with _owned_scope(db, budget):
            owned = collect(db, learner, decision, moves)
        public = samples(index, decision, moves, control, budget, source)
        budget.check()
        if locate(root, learner, source) != index:
            raise ValueError("public opening source changed")
        winner = rank(moves, owned.get("branches", {}), public, control)
        return {
            "status": "checked",
            "owned": owned,
            "public": public,
            "control": control,
            "recommended": winner,
            "reference": source,
            "source_metadata": index[3] if source == "recent" else None,
        }
    except (
        PreviewUnavailable,
        BudgetExceeded,
        TimeoutError,
        OSError,
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
    ):
        return result
