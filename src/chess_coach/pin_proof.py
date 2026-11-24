"""Bounded proof that every immediate pin defense leaves a material capture."""

import chess

from .material_exchange_rules import unclear
from .pin_geometry import pins
from .pin_proof_branch import witnesses
from .pin_proof_eligibility import eligible, previous_capture

MAX_REPLIES = 64


def proof(board, move, pin, *, check=None, on_proof=None):
    if check is not None:
        check()
    if on_proof is not None:
        on_proof()
    if not eligible(board, move) or previous_capture(board, pin):
        return None
    after = board.copy()
    after.push(move)
    replies = list(after.legal_moves)
    if unclear(after) or not 0 < len(replies) <= MAX_REPLIES:
        return None
    branches = witnesses(board, after, move, pin, replies, check=check)
    if branches is None:
        return None
    return {
        "move": move.uci(),
        "san": board.san(move),
        "type": pin["type"],
        "pinner": chess.square_name(move.to_square),
        "pinned": chess.square_name(pin["pinned"]),
        "rear": chess.square_name(pin["rear"]),
        "legal_replies": len(replies),
        "branches": branches,
        "minimum_gain": _material_floor(branches),
        "boundary": "every legal immediate reply, then a legal target capture and its immediate replies",
    }


def proven(board, move, *, check=None, on_proof=None):
    if check is not None:
        check()
    return [
        result
        for pin in pins(board, move)
        if (result := proof(board, move, pin, check=check, on_proof=on_proof))
    ]


def _material_floor(branches):
    return None if any(item["mate"] for item in branches) else 3
