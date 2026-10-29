"""Reject unsupported capture inputs before bounded proof."""


def reason(board, move, clock, start, seconds):
    if clock() - start > seconds:
        return "timeout"
    if board.is_game_over(claim_draw=True) or board.is_repetition(2):
        return "terminal_or_claimable_history"
    if not move or move not in board.legal_moves:
        return "illegal_move"
    if _special(board, move):
        return "checking_or_special_move"
    return None


def _special(board, move):
    return (
        board.is_check() or board.ep_square is not None or move.promotion or board.gives_check(move)
    )
