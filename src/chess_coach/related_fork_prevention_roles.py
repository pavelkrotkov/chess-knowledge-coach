"""Describe the anchored knight and defended target roles without solution disclosure."""

import chess

from .related_fork_geometry import features


def describe(board, defense, anchored, proof):
    fork = anchored.parse_uci(proof["move"])
    piece = anchored.piece_at(fork.from_square)
    if piece is None or piece.piece_type != chess.KNIGHT or fork not in anchored.legal_moves:
        raise ValueError("unsupported knight threat")
    targets = [chess.parse_square(square) for square in proof["targets"]]
    result = features(anchored, fork, piece, targets)
    defender = board.piece_at(defense.from_square)
    if defender is None or defender.color != board.turn:
        raise ValueError("defender unavailable")
    result["defender"] = defender.piece_type
    result["defense_role"] = "move_target" if defense.from_square in targets else "other_quiet"
    return result


def compatible(source, candidate):
    return bool(
        candidate
        and all(
            source[key] == candidate[key] for key in ("mover", "target", "defender", "defense_role")
        )
    )
