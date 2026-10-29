"""Enumerate immediate legal checks and their king replies in original history."""

import chess

from .mate_proof_moves import move_view

MAX_MOVES = 100


def terminal(board):
    return board.outcome(claim_draw=True) is not None or board.is_repetition(2)


def _check(board, move):
    view = move_view(board, move)
    board.push(move)
    if board.is_checkmate():
        result = {**view, "mate": True, "king_replies": []}
    elif terminal(board):
        result = {**view, "mate": False, "king_replies": [], "terminal": True}
    else:
        replies = [
            board.san(m)
            for m in board.legal_moves
            if board.piece_type_at(m.from_square) == chess.KING
        ]
        result = {**view, "mate": False, "king_replies": sorted(replies)}
    board.pop()
    return result


def _captures(board, moves):
    return (
        [board.san(m) for m in moves if board.is_capture(m)],
        [board.san(m) for m in moves if m.promotion],
    )


def scan(board, move):
    view = {
        **move_view(board, move),
        "check": board.gives_check(move),
        "capture": board.is_capture(move),
        "promotion": bool(move.promotion),
    }
    board.push(move)
    if terminal(board):
        board.pop()
        return {"move": view, "status": "terminal"}
    moves = sorted(board.legal_moves, key=lambda m: m.uci())
    if len(moves) > MAX_MOVES:
        board.pop()
        return {"move": view, "status": "unknown"}
    checks = [_check(board, m) for m in moves if board.gives_check(m)]
    captures, promotions = _captures(board, moves)
    board.pop()
    return {
        "move": view,
        "status": "complete",
        "checks": checks,
        "captures": captures,
        "promotions": promotions,
    }
