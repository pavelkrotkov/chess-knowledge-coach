"""Replay a short legal opening branch for a worked experiment."""

MAX_PLIES = 4
MIN_PLIES = 3


def branch(board, line):
    moves = (line.get("pv") or "").split()[:MAX_PLIES]
    if len(moves) < MIN_PLIES:
        return None
    replay = board.copy()
    san = []
    try:
        for text in moves:
            move = replay.parse_uci(text)
            san.append(replay.san(move))
            replay.push(move)
    except ValueError:
        return None
    return {"uci": " ".join(moves), "san": san, "score": line["score_value"]}
