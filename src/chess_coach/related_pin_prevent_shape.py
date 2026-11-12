"""Describe an existing pin capture for contextual ranking."""

from .related_capture_position import _material, _phase
from .related_pin_shape import _offset


def features(board, move, attacker, pin):
    mover = board.piece_at(move.from_square)
    pinned = board.piece_at(pin["pinned"])
    rear = board.piece_at(pin["rear"])
    if not mover or not pinned or not rear:
        raise ValueError("pin roles unavailable")
    if mover.color != board.turn or pinned.color != board.turn or rear.color != board.turn:
        raise ValueError("pin roles unavailable")
    return {
        "operation": "prevent",
        "pin_kind": pin["type"],
        "mover": mover.piece_type,
        "target": (pinned.piece_type, rear.piece_type),
        "geometry": (
            pin["type"],
            _offset(board, move.from_square, attacker),
            _offset(board, pin["pinned"], attacker),
            _offset(board, pin["rear"], attacker),
        ),
        "material": _material(board),
        "phase": _phase(board),
    }
