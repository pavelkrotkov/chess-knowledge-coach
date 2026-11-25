"""Bind selected context to the exact goal and wall-clock window."""

from .curriculum_window_cursor import decode
from .fact_fingerprint import canonical, digest


def _scope(window):
    return digest(canonical([window["goal"], window["issued_at"], window["expires_at"]]))


def result(plan):
    window = plan.get("window")
    return digest(canonical(None)) if window is None else _scope(window)


def cursor(db, value, owner):
    try:
        window = decode(db, value)
    except ValueError:
        from .curriculum_cursor_codec import decode_cursor

        decode_cursor(db, value)
        return digest(canonical(None))
    if window["selection_only"] or window["state"]["subject_hash"] != owner:
        raise ValueError("practice window scope changed")
    return _scope(window)
