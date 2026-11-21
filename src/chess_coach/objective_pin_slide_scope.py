"""Check a named relative pin and the supported quiet slide scope."""

from .material_exchange_rules import unclear
from .objective_pin_prevent_existing import _matches
from .objective_pin_slide_budget import take
from .objective_protection_other import reason
from .pawn_scope import history_known
from .related_pin_slide_proof import pin


def named_pin(board, named):
    take(64)
    candidate = pin(board, "relative_pin")
    return candidate if candidate is not None and _matches(candidate, named) else None


def _quiet(board, move):
    if move is None or move not in board.legal_moves:
        return False
    return not any(
        (
            not board.is_valid(),
            not history_known(board),
            unclear(board),
            board.is_game_over(claim_draw=True),
            board.ep_square is not None,
            board.is_capture(move),
            board.gives_check(move),
            move.promotion,
        )
    )


def replies_supported(board, replies, target):
    if board.ep_square is not None or any(move.promotion for move in replies):
        return False
    return reason(board, replies, target) is None
