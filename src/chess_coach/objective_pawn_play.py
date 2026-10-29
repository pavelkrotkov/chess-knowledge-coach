"""Replay a legal answer and its bound training reply."""

from .objective_short_history import history_hash


def play(board, event, detail, result):
    move = board.parse_uci(event["submitted_move"])
    if not move or move not in board.legal_moves or result.get("move") != move.uci():
        raise ValueError("pawn move unavailable")
    board.push(move)
    if detail.get("fen") != board.fen():
        raise ValueError("pawn history changed")
    return _reply(board, result)


def _reply(board, result):
    data = result["continuation"]
    reply = board.parse_uci(data["reply"])
    if not reply or reply not in board.legal_moves:
        raise ValueError("pawn reply unavailable")
    board.push(reply)
    if board.fen() != data["fen"] or history_hash(board) != data["history_hash"]:
        raise ValueError("pawn reply changed")
    return reply.uci()
