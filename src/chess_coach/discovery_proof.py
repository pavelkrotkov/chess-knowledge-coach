"""Conservative legal proof of a discovered attack and its consequence."""

import chess

from .discovery_branch import unclear as _unclear
from .discovery_branch import witness as _witness
from .discovery_geometry import discoveries
from .discovery_witness import mate_candidates as _mate_candidates
from .discovery_witness import proof as _proof
from .material_lines import material

MAX_REPLIES = 64


def prove(board, move):
    if not board.is_valid() or _unclear(board):
        return []
    candidates = discoveries(board, move)
    if not candidates:
        return []
    after = board.copy()
    after.push(move)
    if after.is_checkmate():
        return _mate_candidates(board, after, move, candidates)
    if _unclear(after):
        return []
    replies = list(after.legal_moves)
    if not 0 < len(replies) <= MAX_REPLIES:
        return []
    return _material_candidates(board, after, move, candidates, replies)


def _material_candidates(board, after, move, candidates, replies):
    return [
        proof
        for item in candidates
        if (proof := _material_proof(board, after, move, item, replies))
    ]


def _material_proof(board, after, move, item, replies):
    if after.piece_type_at(item["target"]) == chess.KING:
        return None
    initial = material(board, board.turn)
    witnesses = [_witness(after, reply, item, board.turn, initial) for reply in replies]
    if any(witness is None for witness in witnesses):
        return None
    return _proof(board, move, item, witnesses, mate=False)
