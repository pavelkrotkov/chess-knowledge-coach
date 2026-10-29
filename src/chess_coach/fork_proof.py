"""Bounded universal immediate-defense proof for a material fork."""

import chess

from .fork_branch import defense_witness
from .fork_targets import targets
from .material_lines import material

MAX_REPLIES = 64


def fork_proof(board, move):
    candidate = targets(board, move)
    if candidate is None:
        return None
    after, squares = candidate
    replies = _replies(after)
    if replies is None:
        return None
    initial = material(board, board.turn)
    witnesses = [
        defense_witness(after, reply, move.to_square, squares, board.turn, initial)
        for reply in replies
    ]
    if any(witness is None for witness in witnesses):
        return None
    return {
        "move": move.uci(),
        "san": board.san(move),
        "attacker": chess.square_name(move.to_square),
        "targets": [chess.square_name(square) for square in squares],
        "legal_replies": len(replies),
        "branches": witnesses,
        "minimum_gain": 3,
        "boundary": "all legal immediate defenses, then one legal target capture and its immediate replies only",
    }


def _replies(board):
    if board.is_game_over() or board.is_repetition(2) or board.is_fifty_moves():
        return None
    replies = list(board.legal_moves)
    return replies if 0 < len(replies) <= MAX_REPLIES else None
