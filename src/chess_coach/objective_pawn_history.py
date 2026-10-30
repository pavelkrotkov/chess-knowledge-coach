"""Replay each proved pawn turn on the original full game history."""

import json

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_answer import answer
from .objective_pawn_replay import input_check, replay
from .pawn_scope import history_known


def before_answer(db, session, rows):
    data = json.loads(session["provenance_json"])
    board = decision_board(db, position_row(db, data["position_id"]))
    if board.fen() != session["prompt_fen"] or not history_known(board):
        raise ValueError("pawn history unavailable")
    prior_reply = None
    for event in rows[:-1]:
        prior_reply = replay(db, session, event, board, prior_reply)
    input_check(rows[-1], board, prior_reply)
    return board, answer(board, session, rows[-1])
