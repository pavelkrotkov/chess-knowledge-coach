"""Do not overlook checking replies or unsupported captures elsewhere."""

from .material_reply_guard import MAX_REPLIES


def reason(board, replies, target, *, check=None):
    if board.is_game_over(claim_draw=True) or board.is_repetition(2):
        return "terminal_or_claimable_history"
    if len(replies) > MAX_REPLIES:
        return "reply_limit"
    for move in replies:
        if check is not None:
            check()
        if board.gives_check(move):
            return "checking_reply_unresolved"
    if _other_capture(board, replies, target, check=check):
        return "other_capture_unresolved"
    return None


def _other_capture(board, replies, target, *, check=None):
    for move in replies:
        if check is not None:
            check()
        if board.is_capture(move) and move.to_square != target:
            return True
    return False
