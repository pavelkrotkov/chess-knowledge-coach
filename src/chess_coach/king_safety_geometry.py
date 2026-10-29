"""Describe shelter geometrically, without treating attacks as legal moves."""

import chess


def _zone(king, color):
    direction = 1 if color else -1
    files = range(max(0, chess.square_file(king) - 1), min(8, chess.square_file(king) + 2))
    ranks = [chess.square_rank(king) + direction * n for n in (1, 2)]
    return [chess.square(f, r) for f in files for r in ranks if 0 <= r < 8]


def shelter(board, color):
    king = board.king(color)
    if king is None:
        return None
    zone = _zone(king, color)
    pawns = [
        chess.square_name(s) for s in zone if board.piece_at(s) == chess.Piece(chess.PAWN, color)
    ]
    attacked = [chess.square_name(s) for s in zone if board.is_attacked_by(not color, s)]
    return {
        "king": chess.square_name(king),
        "zone": [chess.square_name(s) for s in zone],
        "pawns": pawns,
        "attacked": attacked,
    }


def change(board, move):
    before = shelter(board, board.turn)
    after_board = board.copy()
    after_board.push(move)
    after = shelter(after_board, board.turn)
    if before is None or after is None or before == after:
        return None
    return before, after
