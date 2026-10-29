"""Check one defense of a fork against concrete legal target captures."""

import chess

from .fork_capture import capture
from .material_exchange_rules import unclear


def defense_witness(board, reply, attacker, targets, color, initial):
    if _unsupported(board, reply):
        return None
    after = board.copy()
    after.push(reply)
    if unclear(after) or not after.piece_at(attacker):
        return None
    for square in targets:
        witness = capture(after, attacker, square, color, initial)
        if witness:
            return {
                "reply": reply.uci(),
                "reply_san": board.san(reply),
                "capture": witness,
                "capture_san": after.san(chess.Move.from_uci(witness)),
            }
    return None


def _unsupported(board, reply):
    return board.is_capture(reply) or board.gives_check(reply) or reply.promotion is not None
