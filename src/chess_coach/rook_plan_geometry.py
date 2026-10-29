"""Find legal rook entries on open or half-open files."""

import chess

from .pawn_structure_immediate import _capture_status


def file_kind(features, color, square):
    file = chess.FILE_NAMES[chess.square_file(square)]
    if file in features["open_files"]:
        return "open"
    if file in features["half_open_files"][color]:
        return "half-open"
    return None


def entries(board, source, features):
    color = "white" if board.turn else "black"
    result = []
    for move in board.legal_moves:
        rank = chess.square_rank(move.to_square)
        if move.from_square != source or (rank < 4 if board.turn else rank > 3):
            continue
        kind = file_kind(features, color, move.to_square)
        if kind:
            after = board.copy()
            after.push(move)
            result.append(
                {
                    "san": board.san(move),
                    "square": chess.square_name(move.to_square),
                    "file": kind,
                    "captures": _capture_status(after, move.to_square),
                }
            )
    return result
