"""Verify a complete supplied line and its bounded anchored defense."""

from .puzzle_session_validate import legal_move
from .related_fork_prevention_anchor import anchor
from .related_fork_prevention_budget import take
from .related_fork_prevention_line import root, safe
from .related_fork_prevention_roles import compatible, describe


def features(prompt, line, source, budget):
    if not take(budget, "lines"):
        return None
    try:
        board = root(prompt, line)
        if board is None:
            return None
        defense = legal_move(board, line[0])
        witness = anchor(board, source, budget)
        if witness is None or not safe(board, defense, budget):
            return None
        anchored, proof = witness
        result = describe(board, defense, anchored, proof)
        return result if compatible(source, result) else None
    except (ValueError, TypeError, IndexError, KeyError):
        return None
