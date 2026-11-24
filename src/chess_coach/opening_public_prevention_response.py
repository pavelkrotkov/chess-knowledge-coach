"""Assess one quiet response using the existing owned-work reservation."""

from .fork_defense_safety import quiet_after
from .objective_fork_defense_assess import assess
from .objective_fork_defense_budget import scope


def assessment(board, move, clock, start, deadline, check, charge):
    with scope():
        result = assess(
            board,
            move,
            clock,
            start,
            deadline - start,
            {"verifier": "public-knight-fork-prevention-v1", "objective_version": "public"},
            check=check,
            on_proof=charge,
        )
    return result if result["status"] == "correct" else None


def alternative(board, recorded, clock, start, deadline, check, charge, maximum):
    choices = [move for move in board.legal_moves if move != recorded and quiet_after(board, move)]
    for move in choices[:maximum]:
        check()
        response = assessment(board, move, clock, start, deadline, check, charge)
        if response:
            return (move, response), None
    return None, "incomplete" if len(choices) > maximum else "unsupported"
