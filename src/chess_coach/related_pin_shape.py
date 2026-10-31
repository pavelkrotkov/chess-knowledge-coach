"""Describe pinner, pinned piece and rear piece in the learner's coordinates."""

import chess

from .related_capture_position import _material, _phase


def features(board, move, pin):
    front = _square(pin["pinned"])
    rear = _square(pin["rear"])
    mover = board.piece_at(move.from_square)
    pinned = board.piece_at(front)
    back = board.piece_at(rear)
    if not mover or not pinned or not back:
        raise ValueError("pin roles unavailable")
    if mover.color != board.turn or pinned.color == board.turn or back.color == board.turn:
        raise ValueError("pin roles unavailable")
    return {
        "mover": mover.piece_type,
        "target": (pinned.piece_type, back.piece_type),
        "geometry": (
            pin["type"],
            _offset(board, move.from_square, front),
            _offset(board, move.to_square, front),
            _offset(board, rear, front),
        ),
        "material": _material(board),
        "phase": _phase(board),
    }


def _offset(board, square, anchor):
    direction = 1 if board.turn else -1
    return (
        chess.square_file(square) - chess.square_file(anchor),
        direction * (chess.square_rank(square) - chess.square_rank(anchor)),
    )


def _square(value):
    return chess.parse_square(value) if isinstance(value, str) else value
