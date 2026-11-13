"""Check bounded original-history protection threats before the played move."""

from .material_threats import threats
from .objective_protection_before import probe
from .objective_protection_judge import judge
from .pawn_scope import history_known


def before(board, deadline, clock):
    if clock() >= deadline:
        return None, "deadline"
    if not board.is_valid() or not history_known(board):
        return None, "unsupported_history"
    before = threats(board, hypothetical=True)
    if clock() >= deadline:
        return None, "deadline"
    if before is None or before["uncertain"]:
        return None, "threat_unresolved"
    if not before["targets"]:
        return None, None
    return _supported(board, deadline, clock)


def _supported(board, deadline, clock):
    before = probe(board)
    if clock() >= deadline:
        return None, "deadline"
    return (before, None) if before else (None, "threat_unresolved")


def status(board, move, target, deadline, clock):
    start = clock()
    if start >= deadline:
        return "unresolved"
    result = judge(board, move, target, clock, start, deadline - start, {})
    return result["status"]
