"""Count selected check contexts separately from scored contrasts."""


def record(counts, board, context, status):
    if board is None or board.fen() != context["pre_move_fen"]:
        counts["check_context_unknown"] += 1
        return
    if not board.is_check():
        counts["outside_check"] += 1
        return
    counts["selected_in_check"] += 1
    if board.legal_moves.count() == 1:
        counts["forced_check"] += 1
    if status == "comparable":
        counts["comparable_in_check"] += 1
