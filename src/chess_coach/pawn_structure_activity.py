"""Inspect immediate exchanges of pieces supported by an observed pawn."""

import chess

from .pawn_structure_activity_compare import comparison
from .pawn_structure_activity_recapture import recaptures
from .pawn_structure_activity_roots import after_root
from .pawn_structure_geometry import supported_pieces
from .pawn_structure_immediate import _capture_status


def activity(board, targets, lines):
    result = []
    for target in targets:
        for square in supported_pieces(board, target):
            piece = board.piece_at(square)
            assert piece is not None
            roots = {
                role: after_root(board, line["uci"][0], target, square) if line else None
                for role, line in lines.items()
            }
            current = _capture_status(board, square) if board.turn != piece.color else None
            if current is not None:
                current["pawn_recaptures"] = recaptures(
                    board, chess.parse_square(target["square"]), square, current
                )
            result.append(
                {
                    "pawn": target["square"],
                    "color": target["color"],
                    "piece": chess.piece_name(piece.piece_type),
                    "square": chess.square_name(square),
                    "current": current,
                    "roots": roots,
                    "comparison": comparison(roots),
                }
            )
    return result
