"""Display a position from the side to move, without interpreting it."""

import chess


def board_rows(fen: str | None) -> list[list[dict]]:
    if not fen:
        return []
    try:
        board = chess.Board(fen)
        if not board.is_valid():
            return []
    except (TypeError, ValueError):
        return []
    ranks = range(7, -1, -1) if board.turn == chess.WHITE else range(8)
    files = range(8) if board.turn == chess.WHITE else range(7, -1, -1)
    return [[_square(board, file, rank) for file in files] for rank in ranks]


def _square(board: chess.Board, file: int, rank: int) -> dict:
    square = chess.square(file, rank)
    piece = board.piece_at(square)
    return {
        "name": chess.square_name(square),
        "piece": piece.unicode_symbol() if piece else "",
        "description": ("white " if piece.color else "black ") + chess.piece_name(piece.piece_type)
        if piece
        else "empty",
        "color": "light" if (file + rank) % 2 else "dark",
    }
