"""Find bounded legal fork threats without treating geometry as proof."""

from .fork_defense_candidates import legal_candidates
from .fork_defense_history import unsupported
from .fork_proof import fork_proof
from .fork_targets import unsupported_shape

MAX_MOVES = 128
MAX_CANDIDATES = 16


def scan(board, *, check=None, on_proof=None):
    tick = check or (lambda: None)
    if not board.is_valid() or unsupported(board):
        return None
    moves = list(board.legal_moves)
    if not moves or len(moves) > MAX_MOVES:
        return None
    candidates = legal_candidates(board, moves, tick)
    if len(candidates) > MAX_CANDIDATES:
        return None
    return _classify(board, candidates, check, on_proof)


def _classify(board, candidates, check, on_proof):
    proven, uncertain = {}, []
    for move in candidates:
        if check is not None:
            check()
        proof = None
        if not unsupported_shape(board, move):
            if on_proof is not None:
                on_proof()
            proof = fork_proof(board, move, check=check)
        if proof:
            proven[move.uci()] = proof
        else:
            uncertain.append(move.uci())
    return {"proven": proven, "uncertain": uncertain}
