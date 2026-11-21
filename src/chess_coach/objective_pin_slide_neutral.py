"""Validate an actual neutral recapture and its immediate continuation."""

from .material_exchange_rules import unclear
from .material_lines import material
from .objective_pin_slide_budget import take
from .objective_pin_slide_scope import replies_supported


def neutral(board, reply, target, color, initial):
    if any(
        (
            reply.to_square != target,
            not board.is_capture(reply),
            board.gives_check(reply),
            reply.promotion,
            board.is_en_passant(reply),
        )
    ):
        return False
    after = board.copy(stack=True)
    after.push(reply)
    if unclear(after) or after.is_game_over(claim_draw=True):
        return False
    if material(after, color) - initial > 0:
        return False
    continuations = list(after.legal_moves)
    take(len(continuations) + 1)
    if not replies_supported(after, continuations, target):
        return False
    return not any(move.to_square == target and after.is_capture(move) for move in continuations)
