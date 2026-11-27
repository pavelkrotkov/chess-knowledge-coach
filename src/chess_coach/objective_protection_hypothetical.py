"""Bound hypothetical reply scans after original-history checks."""

from .material_reply_guard import MAX_REPLIES
from .objective_protection_other import reason


def supported(board, target, *, check=None):
    hypothetical = board.copy(stack=False)
    hypothetical.turn = not hypothetical.turn
    replies = list(hypothetical.legal_moves)
    return (
        len(replies) <= MAX_REPLIES and reason(hypothetical, replies, target, check=check) is None
    )
