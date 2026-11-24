"""Verify each immediate defense and a resulting legal capture."""

import chess

from .material_exchange_rules import unclear
from .material_lines import material
from .pin_capture import capture


def branch(board, reply, attacker, pin, color, initial, *, check=None):
    if board.gives_check(reply) or reply.promotion or board.is_en_passant(reply):
        return None
    after = board.copy()
    after.push(reply)
    if unclear(after) or not after.piece_at(attacker):
        return None
    for square in (pin["pinned"], pin["rear"]):
        witness = capture(after, attacker, square, color, initial, check=check)
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


def witnesses(board, after, move, pin, replies, *, check=None):
    initial = material(board, board.turn)
    branches = []
    for reply in replies:
        if check is not None:
            check()
        witness = branch(after, reply, move.to_square, pin, board.turn, initial, check=check)
        if witness is None:
            return None
        branches.append(witness)
    return branches
