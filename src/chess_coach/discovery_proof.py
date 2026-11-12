"""Conservative legal proof of a discovered attack and its consequence."""

from .discovery_branch import unclear as _unclear
from .discovery_geometry import discoveries
from .discovery_material_proof import candidates as material_candidates
from .discovery_witness import mate_candidates as _mate_candidates

MAX_REPLIES = 64


def prove(board, move, *, check=None):
    tick = check or (lambda: None)
    tick()
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
    return material_candidates(board, after, move, candidates, replies, check)
