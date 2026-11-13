"""Reuse the named-piece worker binding for created-exposure answers."""

from .objective_created_judge import judge
from .objective_protection_verify import verify as verify_protection


def verify(board, move, request, events, clock, start, seconds, base, data):
    return verify_protection(
        board, move, request, events, clock, start, seconds, base, data, verifier=judge
    )
