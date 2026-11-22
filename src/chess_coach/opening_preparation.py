"""Produce a versioned, snapshot-bound inventory of one opening experiment."""

import sqlite3
import time

from . import opening_decision_budget, opening_preparation_history
from .fact_fingerprint import canonical, digest
from .opening_decision_source import source
from .opening_experiment_current import current
from .opening_preparation_graph import graph
from .opening_preparation_history import coverage
from .opening_queue_budget import BrowserBudget
from .recurrence_snapshot import read_snapshot
from .style_schedule_budget import BudgetExceeded, history_budget
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable

VERSION = "opening-preparation-inventory-v1"


def _history(db, learner, color, branches, budget):
    try:
        with budget.scope(snapshot=False):
            deadline = min(budget.expires, time.monotonic() + SLICE_SECONDS)
            with history_budget(deadline=deadline):
                return coverage(db, learner, color, branches)
    except (BudgetExceeded, PreviewUnavailable, sqlite3.OperationalError):
        return {
            "status": "incomplete",
            "time_projection": opening_preparation_history.TIME_VERSION,
            "limits": {
                "games": opening_preparation_history.MAX_GAMES,
                "positions_per_game": opening_preparation_history.MAX_POSITIONS,
                "pgn_bytes": opening_preparation_history.MAX_GAME_BYTES,
                "history_steps": opening_preparation_history.HISTORY_LIMIT,
            },
        }


def report(db, root, learner, game_id, position_id, move, *, deadline=None):
    budget = BrowserBudget(db)
    if deadline is not None:
        budget.expires = min(budget.expires, deadline)
    with read_snapshot(db):
        decision, choice, experiment, measurement = current(
            db, root, learner, game_id, position_id, move, with_identity=True, budget=budget
        )
        with budget.scope(snapshot=False):
            opening, _, board = source(db, game_id, position_id, learner)
            branches = graph(board, experiment)
        history = _history(db, learner, decision["color"], branches, budget)
        binding = digest(
            canonical(
                {
                    "version": VERSION,
                    "measurement": measurement,
                    "color": decision["color"],
                    "source": [
                        opening["version"],
                        opening["source_url"],
                        opening["classifier_version"],
                        opening["content_revision"],
                    ],
                    "parent": board.fen(),
                    "history_root": board.root().fen(),
                    "history": [item.uci() for item in board.move_stack],
                    "graph": opening_decision_budget.GRAPH_SHA256,
                    "history_filter": [history["time_projection"], history["limits"]],
                    "played": experiment["played"]["uci"],
                    "alternative": experiment["alternative"]["uci"],
                }
            )
        )
    budget.check()
    return (
        decision,
        choice,
        experiment,
        {"version": VERSION, "binding": binding, "branches": branches, "history": history},
    )
