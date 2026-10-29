"""Verify every legal defense against a back-rank mating root."""

from .back_rank_scan import MAX_MOVES, mate_scan


def defenses(board, candidate, budget):
    replies = sorted(board.legal_moves, key=lambda move: move.uci())
    if len(replies) > MAX_MOVES:
        return {"move": candidate["move"], "status": "unknown", "reason": "reply_limit"}
    witnesses = []
    for reply in replies:
        result = _reply(board, reply, budget)
        if result["status"] != "proved":
            return {"move": candidate["move"], **result}
        witnesses.append(result["witness"])
    return {
        "move": candidate["move"],
        "status": "proved",
        "distance_plies": 3,
        "defenses": witnesses,
    }


def _reply(board, reply, budget):
    if not budget.visit():
        return {"status": "unknown", "reason": "node_limit"}
    view = {"uci": reply.uci(), "san": board.san(reply)}
    board.push(reply)
    try:
        if board.outcome(claim_draw=False):
            return {"status": "disproved"}
        scan = mate_scan(board, budget)
        if scan["status"] != "complete":
            return scan
        if not scan["back_rank"]:
            return {"status": "disproved"}
        return {"status": "proved", "witness": {"defense": view, "mate": scan["back_rank"][0]}}
    finally:
        board.pop()
