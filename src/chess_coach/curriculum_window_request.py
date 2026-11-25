"""Distinguish signed window cursors from unchanged legacy plans."""

from .curriculum_window_cursor import decode


def _options_requested(goal, minutes, renew):
    return goal is not None or minutes is not None or renew


def requested(db, cursor, goal, minutes, renew):
    if cursor is None:
        if renew:
            raise ValueError("a practice window is required for renewal")
        return {} if _options_requested(goal, minutes, renew) else None
    try:
        return decode(db, cursor)
    except ValueError:
        if _options_requested(goal, minutes, renew):
            raise ValueError("practice window scope changed") from None
        return None
