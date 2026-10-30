"""Describe a mating attacker and its king escape structure."""

import chess

from .related_capture_position import _material, _phase


def features(root, mate, final, mover, attacker, timing):
    king = mate.king(mate.turn)
    direction = 1 if root.turn else -1
    geometry = (
        attacker,
        chess.square_file(final.to_square) - chess.square_file(king),
        direction * (chess.square_rank(final.to_square) - chess.square_rank(king)),
        _escape_structure(mate, king, root.turn),
    )
    return {
        "mover": mover,
        "target": attacker,
        "timing": timing,
        "geometry": geometry,
        "material": _material(root),
        "phase": _phase(root),
    }


def _escape_structure(board, king, attacker):
    neighbors = list(chess.SquareSet(chess.BB_KING_ATTACKS[king]))
    occupied = sum(
        bool(board.piece_at(square) and board.color_at(square) != attacker) for square in neighbors
    )
    guarded = sum(board.is_attacked_by(attacker, square) for square in neighbors)
    return len(neighbors), occupied, guarded
