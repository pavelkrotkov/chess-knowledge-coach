"""Do not overlook checking replies or unsupported captures elsewhere."""

from .material_reply_guard import MAX_REPLIES


def reason(board, replies, target):
    if board.is_game_over(claim_draw=True) or board.is_repetition(2):
        return "terminal_or_claimable_history"
    if len(replies) > MAX_REPLIES:
        return "reply_limit"
    if any(board.gives_check(move) for move in replies):
        return "checking_reply_unresolved"
    if _other_capture(board, replies, target):
        return "other_capture_unresolved"
    return None


def _other_capture(board, replies, target):
    return any(board.is_capture(move) and move.to_square != target for move in replies)
