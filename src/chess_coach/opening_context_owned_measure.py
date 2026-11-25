"""Read exact same-history owned queue results separately from public evidence."""

import chess

from .opening_storage import position_key
from .opening_unfamiliar_measure_source import find
from .opening_unfamiliar_measure_state import checked
from .style_schedule_budget import BudgetExceeded, history_budget
from .tactical_course_budget import PreviewUnavailable

MAX_GAMES = 20


def enrich(db, root, learner, games, color, parent, path, items, budget):
    board = chess.Board()
    for move in path:
        board.push_uci(move)
    if position_key(board) != parent:
        raise ValueError("owned context parent changed")
    try:
        with history_budget(deadline=budget.expires):
            for item in items:
                found = find(
                    db, learner, games[:MAX_GAMES], color, board.fen(), item, budget, path=path
                )
                item["owned_comparison"] = (
                    checked(db, root, learner, *found, budget)
                    if found
                    else {"status": "no_verified_anchor_in_checked_sample"}
                )
    except (BudgetExceeded, PreviewUnavailable):
        budget.check()
        for item in items:
            item.setdefault("owned_comparison", {"status": "incomplete"})
