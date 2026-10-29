"""Find bounded legal fork threats without treating geometry as proof."""

from .fork_proof import fork_proof
from .fork_targets import targets

MAX_MOVES = 128
MAX_CANDIDATES = 16


def scan(board):
    if not _valid(board):
        return None
    moves = list(board.legal_moves)
    if not moves or len(moves) > MAX_MOVES:
        return None
    candidates = [move for move in moves if targets(board, move) is not None]
    if len(candidates) > MAX_CANDIDATES:
        return None
    return _classify(board, candidates)


def _classify(board, candidates):
    proven, uncertain = {}, []
    for move in candidates:
        proof = fork_proof(board, move)
        if proof:
            proven[move.uci()] = proof
        else:
            uncertain.append(move.uci())
    return {"proven": proven, "uncertain": uncertain}


def _valid(board):
    return (
        board.is_valid()
        and not board.is_check()
        and board.ep_square is None
        and not board.is_game_over()
        and not board.is_repetition(2)
        and not board.is_fifty_moves()
    )
