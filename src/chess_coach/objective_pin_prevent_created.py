"""Verify only supported newly created opponent pins after a defense."""

from .fork_defense_safety import quiet_after, safe_material
from .mate_proof_moves import immediate_mates
from .objective_pin_prevent_match import matches
from .pin_scan import MAX_MOVES, scan


def judge(board, move, named):
    after, reason = _prepare(board, move)
    if reason:
        return "unresolved", reason, None
    found = scan(after)
    if found is None:
        return "unresolved", "pin_scan_unavailable", None
    witness = next((item for item in found["proven"] if matches(item, move, named)), None)
    if witness:
        return "incorrect", "named_created_pin_proved", witness
    if not _safe(found, after):
        return "unresolved", "pin_or_compensation_unresolved", None
    return "correct", "supported_new_pin_prevented", None


def _prepare(board, move):
    after = quiet_after(board, move)
    if after is None or len(list(after.legal_moves)) > MAX_MOVES:
        return None, "defense_outside_supported_scope"
    if immediate_mates(after):
        return None, "other_immediate_mate_unresolved"
    return after, None


def _safe(found, after):
    return not found["proven"] and not found["uncertain"] and safe_material(after)
