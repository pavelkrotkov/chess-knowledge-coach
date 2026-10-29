"""Check the specified piece against bounded legal immediate captures."""

from .material_defense_safety import new_other_threat
from .material_threats import threats
from .objective_protection_other import reason as other_reason
from .objective_protection_result import result


def assess(board, target, before, clock, start, seconds, base):
    if clock() - start > seconds:
        return unknown(base, "timeout")
    replies = list(board.legal_moves)
    reason = other_reason(board, replies, target)
    if reason:
        return unknown(base, reason)
    following = threats(board, hypothetical=False)
    if following is None or following["uncertain"]:
        return unknown(base, "unresolved_attack")
    if new_other_threat(before, following, target):
        return unknown(base, "other_material_threat")
    return result(board, target, following, replies, clock, start, seconds, base)


def unknown(base, reason):
    return {**base, "status": "unresolved", "reason": reason}
