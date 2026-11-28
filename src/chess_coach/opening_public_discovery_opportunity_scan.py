"""Inspect every legal root at the first supported public position."""

from functools import partial

import chess

from .discovery_geometry import discoveries
from .discovery_proof import prove
from .opening_public_discovery_material_example import certificates
from .opening_public_mate_policy import check


def _root(board, move, recorded, tick):
    tick()
    if not discoveries(board, move):
        return None, False
    proofs = [proof for proof in prove(board, move, check=tick) if not proof["mate"]]
    if not proofs:
        return None, True
    return {
        "move": move.uci(),
        "san": board.san(move),
        "recorded": move == recorded,
        "moving_piece": chess.piece_name(board.piece_type_at(move.from_square)),
        "certificates": certificates(board, proofs),
    }, False


def position(board, recorded, deadline):
    roots = [
        recorded,
        *sorted((m for m in board.legal_moves if m != recorded), key=lambda m: m.uci()),
    ]
    found = []
    unresolved = 0
    tick = partial(check, deadline)
    for number, move in enumerate(roots):
        try:
            value, unknown = _root(board, move, recorded, tick)
        except TimeoutError:
            return found, number, unresolved, len(roots) - number
        unresolved += int(unknown)
        if value:
            found.append(value)
    return found, len(roots), unresolved, 0
