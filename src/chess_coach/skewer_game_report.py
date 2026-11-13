"""Private, source-bound royal-skewer inspection for one decision."""

import time

from .protection_game_source import binding
from .short_mate_game_source import prepare, recheck
from .skewer_game_proof import inspect

SECONDS = 3.0


def report(db, learner, position_id, *, clock=time.monotonic):
    row = _decision(db, position_id)
    deadline = clock() + SECONDS
    before = binding(db, row["game_id"])
    source = prepare(db, learner, row["game_id"])
    pair = next(
        (
            (context, board)
            for context, board in source["pairs"]
            if context["position_id"] == position_id and context["subject"]
        ),
        None,
    )
    if pair is None:
        raise ValueError("owned decision unavailable")
    context, board = pair
    proof, reason = inspect(board, context["played_move"], deadline, clock)
    recheck(db, learner, source)
    if binding(db, row["game_id"]) != before:
        raise ValueError("analysis changed during inspection")
    if clock() >= deadline:
        proof, reason = None, "time limit"
    return {"position_id": position_id, "fen": board.fen(), "proof": proof, "reason": reason}


def _decision(db, position_id):
    if type(position_id) is not int or not 0 < position_id < 2**63 or db.connection.in_transaction:
        raise ValueError("decision unavailable")
    row = db.connection.execute(
        "SELECT game_id FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if row is None:
        raise ValueError("decision unavailable")
    return row
