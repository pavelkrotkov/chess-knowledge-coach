"""Validate a capture witness against its decision board."""

import chess


def capture_witness(board, fact):
    target = chess.parse_square(fact["target"])
    for role in ("best", "played"):
        line = fact.get(role) or {}
        moves = line.get("uci") or []
        if not moves:
            continue
        move = chess.Move.from_uci(moves[0])
        if move in board.legal_moves and board.is_capture(move) and move.to_square == target:
            return {"role": role, "uci": moves, "san": line.get("san", [])}
    return None
