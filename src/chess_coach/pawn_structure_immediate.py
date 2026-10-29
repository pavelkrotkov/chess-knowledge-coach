"""Inspect only immediate legal captures after a recorded root move."""

import chess

from .material_exchange import exchange
from .material_exchange_rules import unclear


def _target_after(move, target):
    square = chess.parse_square(target["square"])
    if move.to_square == square:
        return None
    return move.to_square if move.from_square == square else square


def _capture_status(board, square):
    if unclear(board) or board.ep_square is not None:
        return {"status": "unknown", "captures": []}
    captures = [m for m in board.legal_moves if m.to_square == square]
    gains = [exchange(board, move) for move in captures]
    if None in gains:
        return {"status": "unknown", "captures": []}
    return {
        "status": "checked",
        "captures": [
            {"san": board.san(move), "gain": gain}
            for move, gain in zip(captures, gains, strict=True)
        ],
    }


def immediate(board, root, targets):
    move = chess.Move.from_uci(root)
    after = board.copy()
    after.push(move)
    result = []
    for target in targets:
        square = _target_after(move, target)
        owner = target["color"] == "white"
        if square is None or after.turn == owner:
            continue
        result.append(
            {
                "target": target["square"],
                "after_square": chess.square_name(square),
                **_capture_status(after, square),
            }
        )
    return result
