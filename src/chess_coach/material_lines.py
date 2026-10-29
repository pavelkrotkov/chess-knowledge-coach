"""Replay short verified continuations and measure their concrete material change."""

from .material_line_positions import valid_start
from .material_line_replay import replay_line
from .material_line_rules import eligible_moves
from .material_values import VALUES


def material(board, color):
    return sum(
        value * (len(board.pieces(piece, color)) - len(board.pieces(piece, not color)))
        for piece, value in VALUES.items()
    )


def continuation(board, line, expected=None, *, allow_checks=False):
    moves = eligible_moves(line, expected, allow_checks=allow_checks)
    if moves is None or not valid_start(board):
        return None
    initial = material(board, board.turn)
    result = replay_line(board, moves, allow_checks=allow_checks)
    if result is None:
        return None
    replay, used, san = result
    return {"uci": used, "san": san, "material_delta": material(replay, board.turn) - initial}


def unopposed_material_loss(best_line, played_line):
    best = best_line.get("score_value")
    played = played_line.get("score_value")
    return type(best) is int and type(played) is int and best - played >= 150
