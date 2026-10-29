"""Bound the legal fork proofs considered for an anchor."""

import chess

from .fork_proof import fork_proof
from .fork_targets import targets


def find_fork(board, candidates, budget):
    for text, squares in candidates.items():
        fork = chess.Move.from_uci(text)
        found = targets(board, fork)
        if found is None or list(found[1]) != squares:
            continue
        budget -= 1
        if budget < 0:
            return None, budget
        proof = fork_proof(board, fork)
        if proof:
            return proof, budget
    return None, budget
