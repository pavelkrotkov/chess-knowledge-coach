"""Inspect optional private measurements without changing the source report."""

import time

import chess

from .opening_explore_recent import recent
from .opening_queue_budget import BrowserBudget
from .opening_unfamiliar_measure_source import find
from .opening_unfamiliar_measure_state import checked

SECONDS = 10


def measurements(db, root, learner, report):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    with budget.scope(snapshot=False):
        games, _ = recent(db, learner)
    result = {}
    board = chess.Board()
    for color in ("white", "black"):
        suggestion = report[color]
        if color == "black" and report["parent"]:
            board.push_san(report["parent"])
        if not suggestion:
            continue
        found = find(db, learner, games, color, board.fen(), suggestion, budget)
        result[color] = (
            checked(db, root, learner, *found, budget) if found else {"status": "missing"}
        )
    budget.check()
    return result
