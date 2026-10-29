"""Replay short verified continuations and measure their concrete material change."""

from .material_line_rules import eligible_moves, valid_end, valid_start, valid_step
from .material_values import VALUES


def material(board, color):
    return sum(
        value * (len(board.pieces(piece, color)) - len(board.pieces(piece, not color)))
        for piece, value in VALUES.items()
    )


def continuation(board, line, expected=None):
    moves = eligible_moves(line, expected)
    if moves is None or not valid_start(board):
        return None
    replay = board.copy()
    initial = material(replay, replay.turn)
    color = replay.turn
    san = []
    for text in moves:
        try:
            move = replay.parse_uci(text)
        except ValueError:
            return None
        if not valid_step(replay, move):
            return None
        san.append(replay.san(move))
        replay.push(move)
        if not valid_end(replay):
            return None
    return {"uci": moves, "san": san, "material_delta": material(replay, color) - initial}


def unopposed_material_loss(best_line, played_line):
    best = best_line.get("score_value")
    played = played_line.get("score_value")
    return type(best) is int and type(played) is int and best - played >= 150
