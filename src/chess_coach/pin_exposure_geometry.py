"""Find existing pins and verify captures after the pinned piece moves."""

import chess

from .material_lines import material
from .pin_capture import capture
from .pin_geometry_ray import ray


def exposed(board, move, candidates):
    after = board.copy()
    after.push(move)
    for attacker, pin in candidates:
        if move.from_square != pin["pinned"]:
            continue
        target = _target(after, attacker, move, pin)
        if target is None:
            continue
        witness = capture(after, attacker, target, after.turn, material(after, after.turn))
        if witness:
            target_move = chess.Move.from_uci(witness)
            completed = after.copy()
            completed.push(target_move)
            mate = completed.is_checkmate()
            return {
                "mode": "exposure" if pin["type"] == "relative_pin" else "pinned_capture",
                "type": pin["type"],
                "move": witness,
                "san": after.san(target_move),
                "pinner": chess.square_name(attacker),
                "pinned": chess.square_name(pin["pinned"]),
                "rear": chess.square_name(pin["rear"]),
                "mate": mate,
                "minimum_gain": None if mate else 3,
                "boundary": "legal capture of exposed rear target and all immediate replies",
            }
    return None


def _target(after, attacker, move, pin):
    if pin["type"] == "relative_pin":
        return pin["rear"]
    current = ray(after, attacker, move.to_square)
    if current and current["type"] == "absolute_pin" and current["rear"] == pin["rear"]:
        return move.to_square
    return None
