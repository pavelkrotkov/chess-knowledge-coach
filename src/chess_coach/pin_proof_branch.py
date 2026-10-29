"""Verify each immediate defense and a resulting legal capture."""

import chess

from .material_exchange_rules import unclear
from .pin_capture import capture


def branch(board, reply, attacker, pin, color, initial):
    if board.gives_check(reply) or reply.promotion or board.is_en_passant(reply):
        return None
    after = board.copy()
    after.push(reply)
    if unclear(after) or not after.piece_at(attacker):
        return None
    for square in (pin["pinned"], pin["rear"]):
        witness = capture(after, attacker, square, color, initial)
        if witness:
            completed = after.copy()
            completed.push(chess.Move.from_uci(witness))
            return {
                "mate": completed.is_checkmate(),
                "reply": reply.uci(),
                "reply_san": board.san(reply),
                "capture": witness,
                "capture_san": after.san(chess.Move.from_uci(witness)),
            }
    return None
