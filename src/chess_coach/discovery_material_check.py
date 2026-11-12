"""Verify the named discovered attack cannot reach the same target."""

import chess

from .discovery_geometry import discoveries


def origin(played, proof):
    target = chess.parse_square(proof["target"])
    return played.from_square if played.to_square == target else target


def prevents(board, played, move, proof):
    origin_square = origin(played, proof)
    piece = board.piece_at(origin_square)
    if piece is None or piece.color != board.turn:
        return False
    after = board.copy()
    after.push(move)
    destination = move.to_square if move.from_square == origin_square else origin_square
    if after.piece_at(destination) != piece:
        return False
    try:
        attack = after.parse_uci(proof["move"])
    except ValueError:
        return True
    slider = chess.parse_square(proof["slider"])
    return not any(
        item["slider"] == slider and item["target"] == destination
        for item in discoveries(after, attack)
    )
