"""Distinguish signed window cursors from unchanged legacy plans."""

from .curriculum_window_cursor import decode


def _options_requested(goal, minutes, renew):
    return goal is not None or minutes is not None or renew


def requested(db, cursor, goal, minutes, renew, due_recheck=False):
    if cursor is None:
        if renew:
            raise ValueError("a practice window is required for renewal")
        return {} if _options_requested(goal, minutes, renew) else None
    try:
        value = decode(db, cursor)
    except ValueError:
        if _options_requested(goal, minutes, renew):
            raise ValueError("practice window scope changed") from None
        return None
    return _purpose(value, due_recheck, renew)


def _purpose(value, due_recheck, renew):
    if value["selection_only"] and (not due_recheck or renew):
        raise ValueError("practice window cursor is for due recheck only")
    return value
