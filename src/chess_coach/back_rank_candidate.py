"""Cheap geometry nominates work without establishing a chess claim."""

import chess


def candidate(board, color):
    king = board.king(color)
    rank = 0 if color == chess.WHITE else 7
    return (
        king is not None
        and chess.square_rank(king) == rank
        and bool(board.pieces(chess.ROOK, not color) | board.pieces(chess.QUEEN, not color))
    )


def unknown(mate_proof, roots):
    return any(root["status"] == "unknown" for root in roots) or any(
        root.get("status") == "unknown" for root in mate_proof.get("alternatives", [])
    )
