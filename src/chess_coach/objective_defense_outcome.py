"""Classify a completed legal reply scan and preserve its witness."""


def classify(board, scan, count, base):
    replies = sorted(move.uci() for move in board.legal_moves)
    if len(replies) != count:
        return {**base, "status": "unresolved", "reason": "incomplete_replies"}
    base = {**base, "legal_replies": replies}
    mates = [item["move"] for item in scan["back_rank"]] + scan["other_mates"]
    if mates:
        return {
            **base,
            "status": "incorrect",
            "reason": "opponent_immediate_checkmate",
            "mate_reply": mates[0],
            "replies_scanned": count,
        }
    if board.can_claim_draw():
        return {
            **base,
            "status": "unresolved",
            "reason": "draw_claim_available",
            "replies_scanned": count,
        }
    return {
        **base,
        "status": "correct",
        "reason": "no_immediate_checkmate_reply",
        "replies_scanned": count,
    }
