"""Reconstruct the owned pre-answer board and retain its legal move stack."""

from .decision_history import decision_board
from .mate_inspection_source import position_row
from .objective_answer import answer
from .objective_history_replay import replay as _replay
from .pawn_scope import history_known


def before_answer(db, session, rows):
    import json

    provenance = json.loads(session["provenance_json"])
    board = decision_board(db, position_row(db, provenance["position_id"]))
    if board.fen() != session["prompt_fen"] or not history_known(board):
        raise ValueError("history unavailable")
    for event in rows[:-1]:
        _replay(board, event)
    return board, answer(board, session, rows[-1])
