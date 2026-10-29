"""Show legal king moves conditional on one legal opposing reply."""

import chess

from .king_safety_scan import terminal
from .mate_proof_moves import move_view


def witness(board, root):
    replay = board.copy()
    replay.push(chess.Move.from_uci(root["move"]["uci"]))
    moves = sorted(replay.legal_moves, key=lambda m: (not replay.is_capture(m), m.uci()))
    if not moves:
        return None
    move = moves[0]
    reply = move_view(replay, move)
    replay.push(move)
    if terminal(replay):
        return {"reply": reply, "status": "terminal"}
    king_moves = [
        replay.san(m)
        for m in replay.legal_moves
        if replay.piece_type_at(m.from_square) == chess.KING
    ]
    return {"reply": reply, "status": "complete", "king_moves": sorted(king_moves)}
