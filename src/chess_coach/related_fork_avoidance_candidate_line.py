"""Verify one supplied good line before looking for a bad counterfactual."""

from .puzzle_session_validate import legal_move
from .related_fork_avoidance_line import non_losing
from .related_fork_avoidance_witness import witness
from .related_fork_prevention_budget import take
from .related_fork_prevention_line import root, safe


def candidate_line(prompt, line, source, budget):
    if not take(budget, "lines"):
        return None
    try:
        board = root(prompt, line)
        if board is None:
            budget["unknown"] += 1
            return None
        good = legal_move(board, line[0])
        if not non_losing(board, line) or not safe(board, good, budget):
            budget["unknown"] += 1
            return None
        return witness(board, good, source, budget)
    except (ValueError, TypeError, IndexError, KeyError):
        budget["unknown"] += 1
        return None
