"""Locate the next occupied square beyond a slider target."""

import chess


def next_piece(board, attacker, square):
    step = _step(attacker, square)
    if step is None:
        return None
    x, y = chess.square_file(square), chess.square_rank(square)
    while True:
        x, y = x + step[0], y + step[1]
        if not (0 <= x < 8 and 0 <= y < 8):
            return None
        rear = chess.square(x, y)
        if board.piece_at(rear):
            return rear


def _step(a, b):
    dx, dy = (
        chess.square_file(b) - chess.square_file(a),
        chess.square_rank(b) - chess.square_rank(a),
    )
    if not (dx == 0 or dy == 0 or abs(dx) == abs(dy)):
        return None
    return (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
