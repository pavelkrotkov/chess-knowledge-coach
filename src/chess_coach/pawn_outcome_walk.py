"""Explore legal choices and combine outcome bounds for the moving player."""


def moves(board, tablebase, budget, depth, evaluate):
    low = high = 0 if board.can_claim_draw() else -1
    reason = "draw_claim" if low == 0 else "search"
    moves = sorted(board.legal_moves, key=lambda m: (not board.is_zeroing(m), m.uci()))
    for move in moves:
        board.push(move)
        child_low, child_high, child_reason = evaluate(board, tablebase, budget, depth - 1)
        board.pop()
        low, high = max(low, -child_high), max(high, -child_low)
        if child_low != child_high:
            reason = child_reason
        if low == 1:
            return (1, 1, "forced_win")
    return (low, high, reason)
