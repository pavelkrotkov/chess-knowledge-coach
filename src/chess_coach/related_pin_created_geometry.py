"""Bound cheap pin geometries and describe one checked counterfactual."""

import chess

from .pin_defense_success import MAX_ROOT_MOVES
from .pin_geometry import pins
from .related_pin_contract import PIN_GEOMETRY_LIMIT
from .related_pin_prevent_shape import features


def geometry(after):
    moves = list(after.legal_moves)
    if len(moves) > MAX_ROOT_MOVES:
        return None
    result = []
    for move in moves:
        result.extend((move, pin) for pin in pins(after, move))
        if len(result) > PIN_GEOMETRY_LIMIT:
            return None
    return result


def shape(board, good, bound):
    pin = {
        "type": bound["kind"],
        "pinned": chess.parse_square(bound["pinned"]),
        "rear": chess.parse_square(bound["rear"]),
    }
    return {
        **features(board, good, chess.parse_square(bound["attacker"]), pin),
        "origin": "counterfactual",
    }
