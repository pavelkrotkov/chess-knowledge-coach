"""Cheap legal geometry filter; an accepted shape still needs the full fork proof."""

import chess

from .fork_defense_scan import MAX_MOVES
from .fork_targets import targets
from .related_fork_avoidance_roles import describe_choice, same_roles


def possible(board, good, bad, after, before, source):
    moves = list(after.legal_moves)
    if len(moves) > MAX_MOVES:
        return None
    return any(_matches(board, good, bad, after, move, before, source) for move in moves)


def _matches(board, good, bad, after, move, before, source):
    piece = after.piece_at(move.from_square)
    if piece is None or piece.piece_type != chess.KNIGHT:
        return False
    shape = targets(after, move)
    if shape is None or before.get(move.uci()) == list(shape[1]):
        return False
    proof = {"move": move.uci(), "targets": [chess.square_name(square) for square in shape[1]]}
    try:
        return same_roles(source, describe_choice(board, good, bad, after, proof))
    except (ValueError, TypeError, KeyError, IndexError):
        return False
