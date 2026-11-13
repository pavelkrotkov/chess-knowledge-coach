"""Prove a supported immediate reply to a named absolute-pin capture."""

import chess

from .capture_game_replies import reply_status
from .mate_proof_moves import immediate_mates
from .material_check_rules import eligible
from .material_lines import material
from .material_reply_guard import MAX_REPLIES


def refutation(after, move, attacker):
    capture = chess.Move(attacker, move.to_square)
    if not eligible(after, capture) or immediate_mates(after):
        return None
    color, initial = after.turn, material(after, after.turn)
    after = after.copy(stack=True)
    after.push(capture)
    replies = sorted(after.legal_moves, key=lambda candidate: candidate.uci())
    if not replies or len(replies) > MAX_REPLIES:
        return None
    witness = next(
        (move for move in replies if reply_status(after, move, color, initial) == "disproved"), None
    )
    if witness is None:
        return None
    return {"capture": capture.uci(), "reply": witness.uci()}
