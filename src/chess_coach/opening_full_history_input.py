"""Read the complete bounded UCI history and independent source identity."""

import json

from .opening_reference_play import MAX_GAME_PLIES
from .opening_storage import position_key


def load(db, game_id, total):
    value = db.execute(
        "SELECT identity,moves FROM histories WHERE game_id=?", (game_id,)
    ).fetchone()
    if value is None or not isinstance(value[0], str) or len(value[0]) != 64:
        raise ValueError("public history unavailable")
    moves = json.loads(value[1])
    if not isinstance(moves, list) or len(moves) != total or not 1 <= total <= MAX_GAME_PLIES:
        raise ValueError("public history length differs")
    return value[0], moves


def verified_move(board, uci, ply, decision, branch):
    if board.outcome(claim_draw=False) is not None:
        raise ValueError("public history continues after terminal")
    move = board.parse_uci(uci)
    if ply == decision["ply"] and (
        position_key(board) != decision["catalog"]["parent"] or uci != branch
    ):
        raise ValueError("public branch differs")
    return move
