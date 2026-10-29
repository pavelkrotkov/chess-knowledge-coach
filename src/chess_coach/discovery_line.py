"""Validate and replay comparable legal analysis lines."""

from .discovery_line_replay import replay


def lines(board, best, actual, best_line, played_line):
    best_view = _line(board, best, best_line)
    played_view = _line(board, actual, played_line)
    if best_view is None or played_view is None:
        return None
    return {"best": best_view, "played": played_view}


def _line(board, move, line):
    if not isinstance(line, dict) or line.get("status") != "limited":
        return None
    if line.get("root_move") != move.uci() or line.get("score_bound") != "exact":
        return None
    pv = line.get("pv")
    if not isinstance(pv, str):
        return None
    moves = pv.split()
    if not moves or moves[0] != move.uci():
        return None
    return replay(board, moves)
