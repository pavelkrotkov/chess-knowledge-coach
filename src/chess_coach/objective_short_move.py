"""Apply one legal move at the final announced mating ply."""


def move_result(board, submitted):
    try:
        move = board.parse_uci(submitted)
        if not move or move not in board.legal_moves:
            raise ValueError
    except (TypeError, ValueError):
        return {"feedback": "illegal", "status": "needs_verification", "fen": board.fen()}
    board.push(move)
    if board.is_checkmate():
        return {
            "feedback": "objective_verified",
            "status": "objective_verified",
            "fen": board.fen(),
        }
    return {"feedback": "incorrect", "status": "line_completed", "fen": board.fen()}
