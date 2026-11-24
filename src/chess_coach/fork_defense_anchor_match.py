"""Bound the legal fork proofs considered for an anchor."""

import chess

from .fork_proof import fork_proof
from .fork_targets import targets


def find_fork(board, candidates, budget, *, check=None, on_proof=None):
    for text, squares in candidates.items():
        if check is not None:
            check()
        fork = chess.Move.from_uci(text)
        found = targets(board, fork)
        if found is None or list(found[1]) != squares:
            continue
        budget -= 1
        if budget < 0:
            return None, budget
        if on_proof is not None:
            on_proof()
        proof = fork_proof(board, fork, check=check)
        if proof:
            return proof, budget
    return None, budget
