"""Describe the proved line and its legal witness branches."""

import chess


def proof(board, move, item, witnesses, *, mate):
    return {
        "move": move.uci(),
        "san": board.san(move),
        "slider": chess.square_name(item["slider"]),
        "moved_from": chess.square_name(move.from_square),
        "moved_to": chess.square_name(move.to_square),
        "target": chess.square_name(item["target"]),
        "double_check": _double_check(board, move),
        "mate": mate,
        "legal_replies": len(witnesses),
        "branches": witnesses,
        "minimum_gain": None if mate else 3,
        "boundary": "immediate mate or every legal reply, then a legal target capture and immediate replies",
    }


def _double_check(board, move):
    after = board.copy()
    after.push(move)
    return len(after.checkers()) >= 2


def mate_candidates(board, after, move, candidates):
    return [
        proof(board, move, item, [], mate=True)
        for item in candidates
        if item["slider"] in after.checkers()
    ]
