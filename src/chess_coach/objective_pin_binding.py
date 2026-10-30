"""Validate the named pin identities against the reconstructed board."""

import chess


def binding(board, data):
    origin = chess.parse_square(data["pin_attacker"])
    pinned = chess.parse_square(data["pin_pinned"])
    rear = chess.parse_square(data["pin_rear"])
    kind = data["pin_type"]
    if kind not in {"absolute_pin", "relative_pin"}:
        raise ValueError
    if not all(board.piece_at(square) for square in (origin, pinned, rear)):
        raise ValueError
    return origin, pinned, rear, kind
