"""Advance explicit compatible solution branches."""

from .puzzle_session_validate import legal_move


def advance(board, objective, lines, matched, index):
    index += 1
    if any(len(lines[i]) == index for i in matched):
        return _finished(board, objective, index, matched, None)
    reply = min(lines[i][index] for i in matched)
    matched = [i for i in matched if lines[i][index] == reply]
    board.push(legal_move(board, reply))
    index += 1
    if any(len(lines[i]) == index for i in matched):
        return _finished(board, objective, index, matched, reply)
    return move_state(board, "line_match", "active", index, matched, reply)


def _finished(board, objective, index, matched, reply):
    verified = objective in {
        "avoid_immediate_mate",
        "capture_named_target",
        "bounded_material_gain",
    } or (objective in {"checkmate", "mate_in_one", "mate_within_two"} and board.is_checkmate())
    status = "objective_verified" if verified else "line_completed"
    return move_state(board, status, status, index, matched, reply)


def move_state(board, feedback, status, index, candidates, reply=None):
    result = {
        "feedback": feedback,
        "fen": board.fen(),
        "status": status,
        "next_index": index,
        "candidates": candidates,
    }
    if reply is not None:
        result["opponent_move"] = reply
    return result
