"""Compare later opening opportunities using existing bounded source checks."""

import sqlite3
import time

from .opening_fit import _owned_scope
from .opening_fit_later_index import locate
from .opening_fit_later_owned import collect
from .opening_fit_later_rank import rank
from .opening_fit_owned_summary import _control
from .opening_fit_reference import sample
from .opening_queue_budget import BrowserBudget
from .style_schedule_budget import BudgetExceeded
from .style_time_candidates import verified
from .style_time_query import load_game
from .tactical_course_budget import PreviewUnavailable

SECONDS = 12


def assess(db, root, learner, decision, choice):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    result = {"status": "unavailable"}
    try:
        if not 1 <= decision["ply"] <= 20:
            return result
        index = locate(root, learner)
        game = load_game(db.connection, decision["game_id"])
        if verified(game, learner) != decision["color"]:
            return result
        control = _control(game["time_control"])
        moves = [decision["played_uci"], choice["uci"]]
        with _owned_scope(db, budget):
            owned = collect(db, learner, decision, moves)
        public = {}
        for move in moves:
            budget.check()
            public[move] = sample(
                index[0],
                decision["catalog"]["parent"],
                move,
                decision["color"],
                control,
                budget.expires,
                decision_ply=decision["ply"],
                transform=index[2],
            )
        budget.check()
        if locate(root, learner) != index:
            raise ValueError("public opening source changed")
        winner = rank(moves, owned.get("branches", {}), public, control)
        return {
            "status": "checked",
            "owned": owned,
            "public": public,
            "control": control,
            "recommended": winner,
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
